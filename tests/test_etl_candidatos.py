"""
Pruebas del ETL de carga de candidatos (app/services/etl_candidatos.py):
el parser de rangos de solicitud (sintaxis "páginas a imprimir") y la
fase de transformación, incluyendo el nuevo comportamiento del umbral
(0 = sin límite, antes el umbral era obligatorio y siempre filtraba) y
su combinación con la selección manual de solicitudes.
"""

import io

import openpyxl
import pandas as pd
import pytest

from app.extensions import db
from app.models import Candidato
from app.services.etl_candidatos import (
    ErrorCargaExcel,
    extraer,
    parsear_rango_solicitudes,
    transformar,
)


# ---------------------------------------------------------------------------
# parsear_rango_solicitudes
# ---------------------------------------------------------------------------

def test_parsear_rango_mixto():
    assert parsear_rango_solicitudes("1-4,6,8,9") == {1, 2, 3, 4, 6, 8, 9}


def test_parsear_rango_con_espacios():
    assert parsear_rango_solicitudes(" 1 - 4 , 6 , 8 , 9 ") == {1, 2, 3, 4, 6, 8, 9}


def test_parsear_rango_numero_suelto():
    assert parsear_rango_solicitudes("5") == {5}


@pytest.mark.parametrize("texto", [None, "", "   "])
def test_parsear_rango_vacio_es_sin_restriccion(texto):
    assert parsear_rango_solicitudes(texto) is None


def test_parsear_rango_invertido_lanza_error():
    with pytest.raises(ErrorCargaExcel):
        parsear_rango_solicitudes("9-1")


def test_parsear_rango_no_numerico_lanza_error():
    with pytest.raises(ErrorCargaExcel):
        parsear_rango_solicitudes("1-4,seis,9")


def test_parsear_rango_mal_formado_lanza_error():
    with pytest.raises(ErrorCargaExcel):
        parsear_rango_solicitudes("1-4-9")


# ---------------------------------------------------------------------------
# transformar: fixture de un DataFrame "crudo" tal como lo deja `extraer`
# ---------------------------------------------------------------------------

def _df_crudo(filas):
    """
    Construye un DataFrame con las columnas tal como las nombra el Excel
    (antes del renombrado), para un número de filas arbitrario. `filas`
    es una lista de dicts con, como mínimo, 'solicitud' y 'media'.
    """
    registros = []
    for f in filas:
        registros.append(
            {
                "Clave académica": f["clave"],
                "Solicitud": f["solicitud"],
                "Apellidos": "Pérez",
                "Nombre": "Ana",
                "Correo electrónico": "ana@example.com",
                "Media estudios realizados": f["media"],
                "Primera opción": "Grado en Enfermería. CCS de Bormujos.",
            }
        )
    return pd.DataFrame(registros)


def test_transformar_umbral_cero_no_filtra_por_nota(app):
    with app.app_context():
        df = _df_crudo(
            [
                {"clave": "C001", "solicitud": 1, "media": 9.5},
                {"clave": "C002", "solicitud": 2, "media": 3.0},
            ]
        )
        df_filtrado, stats = transformar(
            df, umbral=0, solicitudes_seleccionadas=None,
            semana="2026-W42", archivo_origen="test.xlsx",
        )
        # Con umbral=0 (el nuevo valor por defecto) no se filtra por nota:
        # antes de este cambio, 0 habría excluido a todo el mundo
        # (media < 0 nunca es cierto).
        assert stats["candidatos_finales"] == 2
        assert set(df_filtrado["clave_academica"]) == {"C001", "C002"}


def test_transformar_umbral_positivo_filtra_por_nota(app):
    with app.app_context():
        df = _df_crudo(
            [
                {"clave": "C001", "solicitud": 1, "media": 9.5},
                {"clave": "C002", "solicitud": 2, "media": 3.0},
            ]
        )
        df_filtrado, stats = transformar(
            df, umbral=7.0, solicitudes_seleccionadas=None,
            semana="2026-W42", archivo_origen="test.xlsx",
        )
        assert stats["candidatos_finales"] == 1
        assert list(df_filtrado["clave_academica"]) == ["C002"]


def test_transformar_combina_umbral_y_solicitudes_con_y_logico(app):
    with app.app_context():
        df = _df_crudo(
            [
                {"clave": "C001", "solicitud": 1, "media": 3.0},  # pasa nota, no pasa rango
                {"clave": "C002", "solicitud": 2, "media": 3.0},  # pasa ambos
                {"clave": "C003", "solicitud": 2, "media": 9.0},  # pasa rango, no pasa nota
            ]
        )
        df_filtrado, stats = transformar(
            df, umbral=7.0, solicitudes_seleccionadas={2},
            semana="2026-W42", archivo_origen="test.xlsx",
        )
        assert stats["candidatos_finales"] == 1
        assert list(df_filtrado["clave_academica"]) == ["C002"]


def test_transformar_solo_solicitudes_sin_umbral(app):
    with app.app_context():
        df = _df_crudo(
            [
                {"clave": "C001", "solicitud": 1, "media": 9.9},
                {"clave": "C002", "solicitud": 2, "media": 9.9},
                {"clave": "C003", "solicitud": 3, "media": 9.9},
            ]
        )
        df_filtrado, stats = transformar(
            df, umbral=0, solicitudes_seleccionadas={1, 3},
            semana="2026-W42", archivo_origen="test.xlsx",
        )
        assert stats["candidatos_finales"] == 2
        assert set(df_filtrado["clave_academica"]) == {"C001", "C003"}


def test_transformar_excluye_candidatos_ya_cargados(app):
    with app.app_context():
        existente = Candidato(
            clave_academica="C001", solicitud=1, apellidos="Ya", nombre="Cargado",
            email="x@example.com", media_estudios=5.0, semana_carga="2026-W41",
        )
        db.session.add(existente)
        db.session.commit()

        df = _df_crudo(
            [
                {"clave": "C001", "solicitud": 1, "media": 5.0},  # ya existe
                {"clave": "C002", "solicitud": 2, "media": 5.0},  # nuevo
            ]
        )
        df_filtrado, stats = transformar(
            df, umbral=0, solicitudes_seleccionadas=None,
            semana="2026-W42", archivo_origen="test.xlsx",
        )
        assert stats["candidatos_duplicados"] == 1
        assert list(df_filtrado["clave_academica"]) == ["C002"]


def test_transformar_sin_candidatos_tras_filtrar_lanza_error(app):
    with app.app_context():
        df = _df_crudo([{"clave": "C001", "solicitud": 1, "media": 9.9}])
        with pytest.raises(ErrorCargaExcel):
            transformar(
                df, umbral=7.0, solicitudes_seleccionadas=None,
                semana="2026-W42", archivo_origen="test.xlsx",
            )


def test_transformar_columnas_faltantes_lanza_error(app):
    with app.app_context():
        df = pd.DataFrame([{"Apellidos": "Pérez"}])  # faltan casi todas las columnas
        with pytest.raises(ErrorCargaExcel):
            transformar(
                df, umbral=0, solicitudes_seleccionadas=None,
                semana="2026-W42", archivo_origen="test.xlsx",
            )


# ---------------------------------------------------------------------------
# extraer: Excel real con el cuadro-resumen de 23 filas delante
# ---------------------------------------------------------------------------

def _construir_excel_con_resumen(filas_candidatos):
    """
    Construye, en memoria, un .xlsx con la misma forma que el Excel real:
    23 filas de resumen (irrelevantes), cabecera en la fila 24 y los
    candidatos a partir de la 25.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Calificaciones"

    ws.cell(row=2, column=12, value="Gestión de admisiones de grado.")
    ws.cell(row=20, column=2, value="Solicitantes:")
    ws.cell(row=20, column=6, value=len(filas_candidatos))

    headers = [
        "Clave académica", "Solicitud", "Apellidos", "Nombre",
        "Correo electrónico", "Media estudios realizados", "Primera opción",
    ]
    for col, h in enumerate(headers, start=1):
        ws.cell(row=24, column=col, value=h)

    for i, f in enumerate(filas_candidatos):
        fila = 25 + i
        ws.cell(row=fila, column=1, value=f["clave"])
        ws.cell(row=fila, column=2, value=f["solicitud"])
        ws.cell(row=fila, column=3, value="Pérez")
        ws.cell(row=fila, column=4, value="Ana")
        ws.cell(row=fila, column=5, value="ana@example.com")
        ws.cell(row=fila, column=6, value=f["media"])
        ws.cell(row=fila, column=7, value="Grado en Enfermería. CCS de Bormujos.")

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_extraer_salta_el_cuadro_resumen(tmp_path):
    buf = _construir_excel_con_resumen(
        [{"clave": "C001", "solicitud": 1, "media": 7.0}]
    )
    filepath = tmp_path / "candidatos.xlsx"
    filepath.write_bytes(buf.read())

    df = extraer(str(filepath))

    assert "Clave académica" in df.columns
    assert len(df) == 1
    assert df.iloc[0]["Clave académica"] == "C001"