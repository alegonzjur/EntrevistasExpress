"""
ETL de carga de candidatos desde el Excel semanal de admisiones.

Antes, toda esta lógica (leer el Excel, limpiarlo, detectar sede, parsear
franjas, filtrar, deduplicar e insertar) vivía mezclada dentro de la
función de la ruta `cargar_excel_candidatos` en routes/candidatos.py, en
un único bloque de ~200 líneas. Se separa aquí en tres fases testeables
por separado, al estilo Extract/Transform/Load:

- `extraer(filepath)`: lee el Excel crudo. Las primeras 23 filas son el
  cuadro-resumen del informe (título, criterios de filtro, nº de
  solicitantes) y no se usan — `header=23` las salta porque la fila 24
  (índice 23 para pandas) es la cabecera real de la tabla de candidatos.
- `transformar(...)`: limpia, detecta sede, parsea franjas, aplica los
  filtros (umbral de nota y/o selección manual de nº de solicitud) y
  elimina los candidatos que ya estuvieran cargados de una semana
  anterior (el Excel semanal repite a los candidatos de semanas
  pasadas, así que esto es lo que evita duplicados).
- `cargar(df)`: inserta el DataFrame ya transformado en la base de datos.

La ruta HTTP solo orquesta estas tres funciones y traduce el resultado
(o un `ErrorCargaExcel`) a una respuesta JSON.
"""

import json

import pandas as pd

from app.extensions import db
from app.models import Candidato
from app.services.candidatos import detectar_sede_desde_primera_opcion
from app.services.franjas import parsear_franjas_disponibilidad

# Columnas del Excel que deben existir sí o sí para poder cargar algo.
COLUMNAS_NECESARIAS = [
    "Clave académica",
    "Solicitud",
    "Apellidos",
    "Nombre",
    "Correo electrónico",
    "Media estudios realizados",
    "Primera opción",
]

# Columnas que se usan si están, pero cuya ausencia no es un error.
COLUMNAS_OPCIONALES = [
    "Entrevistas",
    "Tel. Movil",
    "Forma de acceso",
    "Tipo Bachillerato",
    "Tipo FPII/CGS",
    "Convocatoria",
]

MAPEO_COLUMNAS = {
    "Clave académica": "clave_academica",
    "Solicitud": "solicitud",
    "Apellidos": "apellidos",
    "Nombre": "nombre",
    "Correo electrónico": "email",
    "Tel. Movil": "telefono",
    "Media estudios realizados": "media_estudios",
    "Primera opción": "primera_opcion",
    "Entrevistas": "franjas_disponibilidad",
    "Forma de acceso": "forma_acceso",
    "Tipo Bachillerato": "tipo_bachillerato",
    "Tipo FPII/CGS": "tipo_fpii_cgs",
    "Convocatoria": "convocatoria",
}

# Columnas opcionales a las que, si vienen vacías en el Excel (o si la
# columna no existe en absoluto para esa semana), se les pone este texto
# en vez de dejarlas en NULL — a petición expresa de negocio, distinto
# del resto de columnas opcionales (p. ej. telefono o forma_acceso, que
# si faltan se quedan simplemente en None).
VALOR_POR_DEFECTO_SI_VACIO = {
    "tipo_bachillerato": "No disponible",
    "tipo_fpii_cgs": "No disponible",
}


class ErrorCargaExcel(Exception):
    """
    Error esperado durante el ETL (columnas faltantes, formato de rango
    de solicitudes inválido, cero candidatos tras filtrar...). La ruta
    HTTP lo atrapa y lo traduce a un 400 con `mensaje` y cualquier dato
    extra adjunto, en vez de dejar que se propague como un 500 genérico.
    """

    def __init__(self, mensaje, **extra):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.extra = extra


def parsear_rango_solicitudes(texto):
    """
    Convierte un texto de selección de solicitudes, con la misma sintaxis
    que el selector de páginas a imprimir de un documento (p. ej.
    "1-4,6,8,9"), en un set de enteros: {1, 2, 3, 4, 6, 8, 9}.

    Reglas:
    - Trozos separados por comas; cada trozo es un número suelto o un
      rango "inicio-fin" (ambos extremos incluidos).
    - Los espacios alrededor de números, guiones y comas se ignoran.
    - Texto None o vacío (tras strip) -> None, que significa "sin
      restricción por número de solicitud" (se cargan todas las que
      pasen el resto de filtros, igual que si el campo no existiera).

    Lanza ErrorCargaExcel con un mensaje claro ante un trozo mal
    formado, en vez de dejar que pandas o un IndexError silencioso
    produzcan un resultado inesperado.
    """
    if texto is None:
        return None

    texto = texto.strip()
    if texto == "":
        return None

    solicitudes = set()
    for trozo in texto.split(","):
        trozo = trozo.strip()
        if not trozo:
            continue

        if "-" in trozo:
            partes = trozo.split("-")
            if len(partes) != 2:
                raise ErrorCargaExcel(
                    f"Rango de solicitudes inválido: '{trozo}'. Usa el formato "
                    "'inicio-fin', por ejemplo '1-4'."
                )
            inicio_str, fin_str = partes[0].strip(), partes[1].strip()
            if not inicio_str.isdigit() or not fin_str.isdigit():
                raise ErrorCargaExcel(
                    f"Rango de solicitudes inválido: '{trozo}'. Ambos extremos "
                    "deben ser números enteros."
                )
            inicio, fin = int(inicio_str), int(fin_str)
            if inicio > fin:
                raise ErrorCargaExcel(
                    f"Rango de solicitudes inválido: '{trozo}'. El primer número "
                    "debe ser menor o igual que el segundo."
                )
            solicitudes.update(range(inicio, fin + 1))
        else:
            if not trozo.isdigit():
                raise ErrorCargaExcel(
                    f"Valor de solicitud inválido: '{trozo}'. Debe ser un número "
                    "entero o un rango 'inicio-fin'."
                )
            solicitudes.add(int(trozo))

    if not solicitudes:
        return None

    return solicitudes


def extraer(filepath):
    """Lee el Excel crudo, saltando el cuadro-resumen (filas 1-23)."""
    return pd.read_excel(filepath, header=23)  # Fila 24 = índice 23


def transformar(df, umbral, solicitudes_seleccionadas, semana, archivo_origen):
    """
    Limpia el DataFrame crudo, aplica los filtros y elimina duplicados
    frente a lo que ya hay en base de datos.

    Args:
        df: DataFrame tal como lo devuelve `extraer`.
        umbral: nota de corte. Si es None o <= 0, no se filtra por nota
            (esto es lo nuevo: antes el umbral era siempre obligatorio y
            siempre filtraba; con 0 como valor por defecto, un umbral de
            0 significa "sin límite", no "ningún candidato pasa").
        solicitudes_seleccionadas: set de enteros ya parseado con
            `parsear_rango_solicitudes`, o None para no restringir por
            número de solicitud. Se combina con el umbral mediante Y
            lógico: si se indican ambos, un candidato debe cumplir los
            dos para cargarse.
        semana: semana de carga (se guarda tal cual en cada fila).
        archivo_origen: nombre del fichero Excel (idem).

    Returns:
        Tupla (df_filtrado, estadisticas) donde estadisticas es un dict
        con las mismas claves que antes devolvía la ruta directamente
        (total_leidos, total_validos, candidatos_finales,
        candidatos_duplicados, candidatos_por_sede, candidatos_sin_sede,
        candidatos_con_preferencias, candidatos_sin_preferencias).

    Lanza ErrorCargaExcel si faltan columnas obligatorias, o si no queda
    ningún candidato tras aplicar los filtros y/o la deduplicación.
    """
    columnas_faltantes = [col for col in COLUMNAS_NECESARIAS if col not in df.columns]
    if columnas_faltantes:
        raise ErrorCargaExcel(f'Columnas faltantes: {", ".join(columnas_faltantes)}')

    columnas_a_usar = COLUMNAS_NECESARIAS.copy()
    for col in COLUMNAS_OPCIONALES:
        if col in df.columns:
            columnas_a_usar.append(col)

    df_procesado = df[columnas_a_usar].copy()
    df_procesado.rename(columns=MAPEO_COLUMNAS, inplace=True)

    # Limpiar datos. Desde el cambio de 2026-10-15, media_estudios ya NO
    # es obligatoria: un alumno se carga igual aunque el Excel traiga esa
    # celda vacía (antes, dropna la descartaba aquí mismo). Se convierte
    # con pd.to_numeric + dtype=object para que una celda vacía quede en
    # None de Python (no NaN de numpy), igual que se hizo con
    # `convocatoria` — necesario para que to_sql la inserte como NULL.
    df_procesado = df_procesado.dropna(subset=["clave_academica", "apellidos", "nombre"])
    df_procesado["solicitud"] = pd.to_numeric(df_procesado["solicitud"], errors="coerce")
    media_estudios_numerica = pd.to_numeric(
        df_procesado["media_estudios"], errors="coerce"
    )
    df_procesado["media_estudios"] = pd.Series(
        [float(x) if pd.notna(x) else None for x in media_estudios_numerica],
        index=df_procesado.index,
        dtype=object,
    )
    df_procesado = df_procesado.dropna(subset=["solicitud"])

    df_procesado["clave_academica"] = (
        df_procesado["clave_academica"].astype(str).str.strip()
    )

    df_procesado["sede"] = df_procesado["primera_opcion"].apply(
        detectar_sede_desde_primera_opcion
    )
    # A petición de negocio: "Primera opción" deja de guardar el texto
    # libre completo del Excel ("Grado en Enfermería. CCS de Bormujos...")
    # y pasa a guardar solo el centro detectado (mismo valor que `sede`;
    # ver el comentario en el modelo sobre por qué se mantienen las dos
    # columnas).
    df_procesado["primera_opcion"] = df_procesado["sede"]

    # Columnas opcionales con valor por defecto si vienen vacías (o si la
    # columna no existe en absoluto en el Excel de esta semana).
    for columna, valor_defecto in VALOR_POR_DEFECTO_SI_VACIO.items():
        if columna in df_procesado.columns:
            df_procesado[columna] = df_procesado[columna].apply(
                lambda x: (
                    valor_defecto
                    if pd.isna(x) or str(x).strip() == ""
                    else str(x).strip()
                )
            )
        else:
            df_procesado[columna] = valor_defecto

    # Convocatoria es un entero (p. ej. "06" -> 6). Si falta o no es
    # numérica, se deja en None (a diferencia de tipo_bachillerato /
    # tipo_fpii_cgs, aquí no se pidió un valor por defecto).
    if "convocatoria" in df_procesado.columns:
        convocatoria_numerica = pd.to_numeric(
            df_procesado["convocatoria"], errors="coerce"
        )
        # dtype=object a propósito: si se deja que pandas infiera el
        # tipo (vía .apply normal), una columna sin ningún hueco vacío
        # se reconvierte a int64 y cada valor queda como numpy.int64 en
        # vez de int de Python — con psycopg2/to_sql eso puede fallar o
        # insertarse como un tipo inesperado. Construirla así garantiza
        # int (o None) nativos de Python en cada fila.
        df_procesado["convocatoria"] = pd.Series(
            [int(x) if pd.notna(x) else None for x in convocatoria_numerica],
            index=df_procesado.index,
            dtype=object,
        )
    else:
        df_procesado["convocatoria"] = None

    total_leidos = len(df)
    total_validos = len(df_procesado)

    # Filtro por nota: umbral <= 0 (incluido el valor por defecto, 0)
    # significa "sin límite", no "ningún candidato pasa". Un candidato
    # sin nota (media_estudios None) siempre pasa este filtro, pase lo
    # que pase con el umbral — no hay nota contra la que compararlo, y
    # la nota que falta no es un motivo para no cargarlo.
    df_filtrado = df_procesado
    if umbral is not None and umbral > 0:
        df_filtrado = df_filtrado[
            df_filtrado["media_estudios"].isna()
            | (df_filtrado["media_estudios"] < umbral)
        ].copy()
    else:
        df_filtrado = df_filtrado.copy()

    # Filtro por número de solicitud (selección manual, opcional).
    if solicitudes_seleccionadas is not None:
        df_filtrado = df_filtrado[
            df_filtrado["solicitud"].isin(solicitudes_seleccionadas)
        ].copy()

    # Parsear franjas de disponibilidad
    if "franjas_disponibilidad" in df_filtrado.columns:
        df_filtrado["tiene_preferencias"] = df_filtrado[
            "franjas_disponibilidad"
        ].notna() & (df_filtrado["franjas_disponibilidad"].astype(str).str.strip() != "")

        df_filtrado["franjas_parseadas"] = df_filtrado["franjas_disponibilidad"].apply(
            lambda x: (
                json.dumps(parsear_franjas_disponibilidad(x), ensure_ascii=False)
                if pd.notna(x) and str(x).strip() != ""
                else None
            )
        )
    else:
        df_filtrado["tiene_preferencias"] = False
        df_filtrado["franjas_parseadas"] = None
        df_filtrado["franjas_disponibilidad"] = None

    # Campos de gestión
    df_filtrado["estado"] = "pendiente"
    df_filtrado["fecha_carga"] = pd.Timestamp.now()
    df_filtrado["semana_carga"] = semana
    df_filtrado["archivo_origen"] = archivo_origen

    candidatos_finales = len(df_filtrado)
    if candidatos_finales == 0:
        raise ErrorCargaExcel(
            "Ningún candidato cumple los filtros indicados (nota y/o solicitudes)",
            total_leidos=int(total_leidos),
            total_validos=int(total_validos),
        )

    candidatos_por_sede = _contar_por_sede(df_filtrado)
    candidatos_sin_sede = int(df_filtrado["sede"].isna().sum())
    candidatos_con_preferencias = int(df_filtrado["tiene_preferencias"].sum())
    candidatos_sin_preferencias = candidatos_finales - candidatos_con_preferencias

    # Deduplicar frente a lo que ya hay en base de datos (claves ya
    # cargadas en una semana anterior).
    claves_en_df = df_filtrado["clave_academica"].tolist()
    candidatos_existentes = Candidato.query.filter(
        Candidato.clave_academica.in_(claves_en_df)
    ).all()
    candidatos_duplicados = len(candidatos_existentes)

    if candidatos_duplicados > 0:
        claves_duplicadas = [c.clave_academica for c in candidatos_existentes]
        df_filtrado = df_filtrado[
            ~df_filtrado["clave_academica"].isin(claves_duplicadas)
        ].copy()
        candidatos_finales = len(df_filtrado)

        if candidatos_finales == 0:
            raise ErrorCargaExcel(
                f"Todos los candidatos ({candidatos_duplicados}) ya están cargados",
                duplicados=candidatos_duplicados,
                total_leidos=int(total_leidos),
            )

        candidatos_por_sede = _contar_por_sede(df_filtrado)
        candidatos_sin_sede = int(df_filtrado["sede"].isna().sum())
        candidatos_con_preferencias = int(df_filtrado["tiene_preferencias"].sum())
        candidatos_sin_preferencias = candidatos_finales - candidatos_con_preferencias

    # Codificar campos de texto
    for col in [
        "apellidos",
        "nombre",
        "primera_opcion",
        "archivo_origen",
        "email",
        "telefono",
        "sede",
        "franjas_disponibilidad",
        "franjas_parseadas",
        "forma_acceso",
        "tipo_bachillerato",
        "tipo_fpii_cgs",
    ]:
        if col in df_filtrado.columns:
            df_filtrado[col] = df_filtrado[col].apply(
                lambda x: (
                    str(x).encode("utf-8", "ignore").decode("utf-8")
                    if x is not None and str(x) not in ["nan", "None"]
                    else None
                )
            )

    estadisticas = {
        "total_leidos": int(total_leidos),
        "total_validos": int(total_validos),
        "candidatos_finales": int(candidatos_finales),
        "candidatos_duplicados": int(candidatos_duplicados),
        "candidatos_por_sede": candidatos_por_sede,
        "candidatos_sin_sede": candidatos_sin_sede,
        "candidatos_con_preferencias": candidatos_con_preferencias,
        "candidatos_sin_preferencias": candidatos_sin_preferencias,
    }

    return df_filtrado, estadisticas


def _contar_por_sede(df):
    candidatos_por_sede_raw = df["sede"].value_counts().to_dict()
    return {
        str(k) if k is not None else "Sin detectar": int(v)
        for k, v in candidatos_por_sede_raw.items()
    }


def cargar(df_filtrado):
    """Inserta el DataFrame ya transformado en la tabla `candidatos`."""
    df_filtrado.to_sql(
        "candidatos",
        db.engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=100,
    )