# ====================================================================
# RUTAS DE ADMINISTRACIÓN DE CANDIDATOS
# Añadir estas rutas a app.py
# ====================================================================

import pandas as pd
from werkzeug.utils import secure_filename
import hashlib
import subprocess
from datetime import date

# Configuración de uploads
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"xlsx", "xls"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Crear carpeta si no existe
import os

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    """Verifica si el archivo tiene extensión permitida"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def calcular_semana_iso(fecha):
    """Calcula la semana ISO de una fecha"""
    return fecha.strftime("%Y-W%W")


def parsear_semana_iso(semana_iso):
    """Convierte semana ISO a rango de fechas (lunes-viernes)"""
    año, semana = semana_iso.split("-W")
    primer_dia = datetime.strptime(f"{año}-W{semana}-1", "%Y-W%W-%w").date()
    viernes = primer_dia + timedelta(days=4)
    return primer_dia, viernes


def obtener_semanas_disponibles():
    """Obtiene lista de semanas para el selector"""
    hoy = date.today()
    semanas = []

    # 2 semanas atrás hasta 8 semanas adelante
    for i in range(-2, 9):
        fecha = hoy + timedelta(weeks=i)
        # Calcular lunes de esa semana
        dias_hasta_lunes = fecha.weekday()
        lunes = fecha - timedelta(days=dias_hasta_lunes)
        viernes = lunes + timedelta(days=4)

        semana_iso = calcular_semana_iso(lunes)

        semanas.append(
            {
                "iso": semana_iso,
                "lunes": lunes.strftime("%d/%m/%Y"),
                "viernes": viernes.strftime("%d/%m/%Y"),
                "label": f"Semana {semana_iso.split('-W')[1]} ({lunes.strftime('%d/%m')} - {viernes.strftime('%d/%m')})",
                "es_actual": i == 0,
            }
        )

    return semanas


@app.route("/admin/candidatos")
@admin_required
def admin_candidatos():
    """Vista principal de gestión de candidatos"""
    # Obtener estadísticas generales
    total_candidatos = Candidato.query.count()
    candidatos_pendientes = Candidato.query.filter_by(estado="pendiente").count()
    candidatos_asignados = Candidato.query.filter_by(estado="asignado").count()
    candidatos_entrevistados = Candidato.query.filter_by(estado="entrevistado").count()

    # Obtener semanas con candidatos
    from sqlalchemy import func

    semanas_con_candidatos = (
        db.session.query(
            Candidato.semana_carga,
            func.count(Candidato.id).label("total"),
            func.sum(db.case((Candidato.estado == "pendiente", 1), else_=0)).label(
                "pendientes"
            ),
            func.sum(db.case((Candidato.estado == "asignado", 1), else_=0)).label(
                "asignados"
            ),
        )
        .group_by(Candidato.semana_carga)
        .order_by(Candidato.semana_carga.desc())
        .all()
    )

    # Últimas cargas de Excel
    ultimas_cargas = (
        CargaExcel.query.order_by(CargaExcel.fecha_carga.desc()).limit(5).all()
    )

    # Últimos logs de asignación
    ultimos_logs = (
        LogAsignacion.query.order_by(LogAsignacion.fecha_ejecucion.desc())
        .limit(5)
        .all()
    )

    # Lista de semanas disponibles para selector
    semanas_disponibles = obtener_semanas_disponibles()

    return render_template(
        "admin_candidatos.html",
        total_candidatos=total_candidatos,
        candidatos_pendientes=candidatos_pendientes,
        candidatos_asignados=candidatos_asignados,
        candidatos_entrevistados=candidatos_entrevistados,
        semanas_con_candidatos=semanas_con_candidatos,
        ultimas_cargas=ultimas_cargas,
        ultimos_logs=ultimos_logs,
        semanas_disponibles=semanas_disponibles,
        username=session["username"],
    )


@app.route("/admin/candidatos/cargar-excel", methods=["POST"])
@admin_required
def cargar_excel_candidatos():
    """Procesa y carga un archivo Excel de candidatos"""

    # Verificar que se subió un archivo
    if "archivo" not in request.files:
        return jsonify({"error": "No se ha seleccionado ningún archivo"}), 400

    file = request.files["archivo"]

    if file.filename == "":
        return jsonify({"error": "No se ha seleccionado ningún archivo"}), 400

    if not allowed_file(file.filename):
        return (
            jsonify(
                {"error": "Tipo de archivo no permitido. Solo se aceptan .xlsx y .xls"}
            ),
            400,
        )

    try:
        # Obtener parámetros
        semana = request.form.get("semana")
        umbral = float(request.form.get("umbral", 7.0))

        if not semana:
            return jsonify({"error": "Debe especificar una semana"}), 400

        # Guardar archivo temporalmente
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_final = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename_final)
        file.save(filepath)

        # Calcular hash del archivo
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        archivo_hash = hash_md5.hexdigest()

        # Verificar si ya se cargó este archivo
        carga_existente = CargaExcel.query.filter_by(archivo_hash=archivo_hash).first()
        if carga_existente:
            os.remove(filepath)  # Eliminar archivo duplicado
            return (
                jsonify(
                    {
                        "error": f'Este archivo ya fue cargado el {carga_existente.fecha_carga.strftime("%d/%m/%Y %H:%M")}',
                        "duplicado": True,
                    }
                ),
                400,
            )

        # Procesar Excel
        df = pd.read_excel(filepath, header=23)  # Fila 24 = índice 23

        # Verificar columnas necesarias
        columnas_necesarias = [
            "Solicitud",
            "Apellidos",
            "Nombre",
            "Media estudios realizados",
            "Primera opción",
        ]
        columnas_faltantes = [
            col for col in columnas_necesarias if col not in df.columns
        ]

        if columnas_faltantes:
            os.remove(filepath)
            return (
                jsonify(
                    {"error": f'Columnas faltantes: {", ".join(columnas_faltantes)}'}
                ),
                400,
            )

        # Procesar datos
        df_procesado = df[columnas_necesarias].copy()
        df_procesado.rename(
            columns={
                "Solicitud": "solicitud",
                "Apellidos": "apellidos",
                "Nombre": "nombre",
                "Media estudios realizados": "media_estudios",
                "Primera opción": "primera_opcion",
            },
            inplace=True,
        )

        # Limpiar datos
        df_procesado = df_procesado.dropna(
            subset=["solicitud", "apellidos", "nombre", "media_estudios"]
        )
        df_procesado["solicitud"] = pd.to_numeric(
            df_procesado["solicitud"], errors="coerce"
        )
        df_procesado["media_estudios"] = pd.to_numeric(
            df_procesado["media_estudios"], errors="coerce"
        )
        df_procesado = df_procesado.dropna(subset=["solicitud", "media_estudios"])

        total_leidos = len(df)
        total_validos = len(df_procesado)

        # Filtrar por umbral
        df_filtrado = df_procesado[df_procesado["media_estudios"] < umbral].copy()

        # Añadir campos de gestión
        df_filtrado["email"] = None
        df_filtrado["estado"] = "pendiente"
        df_filtrado["fecha_carga"] = datetime.now()
        df_filtrado["semana_carga"] = semana
        df_filtrado["archivo_origen"] = filename

        candidatos_finales = len(df_filtrado)

        if candidatos_finales == 0:
            os.remove(filepath)
            return (
                jsonify(
                    {
                        "error": f"No hay candidatos con nota inferior a {umbral}",
                        "total_leidos": total_leidos,
                        "total_validos": total_validos,
                    }
                ),
                400,
            )

        # Guardar en base de datos
        for col in ["apellidos", "nombre", "primera_opcion", "archivo_origen"]:
            if col in df_filtrado.columns:
                df_filtrado[col] = df_filtrado[col].apply(
                    lambda x: (
                        str(x).encode("utf-8", "ignore").decode("utf-8")
                        if x is not None and str(x) != "nan"
                        else x
                    )
                )

        df_filtrado.to_sql(
            "candidatos",
            db.engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=100,
        )

        # Registrar carga
        carga = CargaExcel(
            archivo_nombre=filename,
            archivo_hash=archivo_hash,
            candidatos_totales=total_leidos,
            candidatos_importados=candidatos_finales,
            candidatos_duplicados=0,
            cargado_por_usuario_id=session["user_id"],
            semana_destino=semana,
            estado="completado",
            mensaje=f"Importación exitosa. {candidatos_finales} candidatos con nota < {umbral}",
        )
        db.session.add(carga)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "mensaje": f"{candidatos_finales} candidatos importados correctamente",
                "total_leidos": total_leidos,
                "total_validos": total_validos,
                "candidatos_finales": candidatos_finales,
                "umbral": umbral,
                "semana": semana,
            }
        )

    except Exception as e:
        if "filepath" in locals() and os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({"error": f"Error al procesar el archivo: {str(e)}"}), 500


@app.route("/admin/candidatos/ejecutar-asignacion", methods=["POST"])
@admin_required
def ejecutar_asignacion():
    """Ejecuta el algoritmo de asignación automática"""

    try:
        data = request.json
        semana_carga = data.get("semana_carga")
        max_por_profesor = data.get("max_por_profesor")

        if not semana_carga:
            return jsonify({"error": "Debe especificar una semana de carga"}), 400

        # Calcular semana de entrevistas (siguiente)
        año, semana_num = semana_carga.split("-W")
        primer_dia = datetime.strptime(f"{año}-W{semana_num}-1", "%Y-W%W-%w").date()
        siguiente_lunes = primer_dia + timedelta(days=7)
        semana_entrevistas = siguiente_lunes.strftime("%Y-W%W")

        # Verificar candidatos pendientes
        candidatos_pendientes = Candidato.query.filter_by(
            semana_carga=semana_carga, estado="pendiente"
        ).count()

        if candidatos_pendientes == 0:
            return (
                jsonify(
                    {
                        "error": f"No hay candidatos pendientes para la semana {semana_carga}",
                        "candidatos_pendientes": 0,
                    }
                ),
                400,
            )

        # Verificar reservas disponibles
        lunes_entrevistas, viernes_entrevistas = parsear_semana_iso(semana_entrevistas)

        reservas = (
            Reserva.query.filter(Reserva.fecha >= lunes_entrevistas)
            .filter(Reserva.fecha <= viernes_entrevistas)
            .count()
        )

        if reservas == 0:
            return (
                jsonify(
                    {
                        "error": f'No hay reservas para la semana de entrevistas {semana_entrevistas} ({lunes_entrevistas.strftime("%d/%m")} - {viernes_entrevistas.strftime("%d/%m")})',
                        "reservas_disponibles": 0,
                    }
                ),
                400,
            )

        # Importar y ejecutar asignador (inline para evitar subprocess)
        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=db.engine)
        session_asignacion = Session()

        inicio = datetime.now()

        # Obtener candidatos ordenados por nota
        candidatos = (
            session_asignacion.query(Candidato)
            .filter_by(semana_carga=semana_carga, estado="pendiente")
            .order_by(Candidato.media_estudios.asc())
            .all()
        )

        # Obtener reservas con espacios
        reservas_obj = (
            session_asignacion.query(Reserva)
            .filter(Reserva.fecha >= lunes_entrevistas)
            .filter(Reserva.fecha <= viernes_entrevistas)
            .order_by(Reserva.fecha, Reserva.hora_inicio)
            .all()
        )

        franjas_disponibles = []
        for reserva in reservas_obj:
            asignaciones_existentes = (
                session_asignacion.query(Asignacion)
                .filter_by(reserva_id=reserva.id)
                .count()
            )

            espacios_libres = 2 - asignaciones_existentes
            if espacios_libres > 0:
                franjas_disponibles.append(
                    {
                        "reserva": reserva,
                        "espacios_libres": espacios_libres,
                        "asignaciones_actuales": asignaciones_existentes,
                    }
                )

        # Asignar
        asignaciones_creadas = []
        idx_candidato = 0
        idx_franja = 0

        asignaciones_por_profesor = {}

        while idx_candidato < len(candidatos) and idx_franja < len(franjas_disponibles):
            candidato = candidatos[idx_candidato]
            franja = franjas_disponibles[idx_franja]
            reserva = franja["reserva"]
            entrevistador_id = reserva.usuario_id

            # Verificar límite por profesor
            if max_por_profesor:
                actual = asignaciones_por_profesor.get(entrevistador_id, 0)
                if actual >= max_por_profesor:
                    idx_franja += 1
                    continue

            # Determinar posición
            if franja["asignaciones_actuales"] == 0:
                posicion = 1
                minuto_inicio = 0
            else:
                posicion = 2
                minuto_inicio = 15

            # Crear asignación
            asignacion = Asignacion(
                candidato_id=candidato.id,
                reserva_id=reserva.id,
                entrevistador_id=entrevistador_id,
                posicion=posicion,
                minuto_inicio=minuto_inicio,
                estado="confirmado",
                fecha_asignacion=datetime.now(),
                asignado_por_admin_id=session["user_id"],
            )

            session_asignacion.add(asignacion)
            asignaciones_creadas.append(asignacion)

            # Actualizar contadores
            asignaciones_por_profesor[entrevistador_id] = (
                asignaciones_por_profesor.get(entrevistador_id, 0) + 1
            )
            franja["espacios_libres"] -= 1
            franja["asignaciones_actuales"] += 1

            idx_candidato += 1

            if franja["espacios_libres"] == 0:
                idx_franja += 1

        # Guardar
        session_asignacion.commit()

        # Crear log
        tiempo_total = (datetime.now() - inicio).total_seconds()

        log = LogAsignacion(
            fecha_ejecucion=datetime.now(),
            semana_objetivo=semana_carga,
            candidatos_procesados=len(candidatos),
            candidatos_filtrados=0,
            candidatos_asignados=len(asignaciones_creadas),
            candidatos_sin_asignar=len(candidatos) - len(asignaciones_creadas),
            franjas_utilizadas=len(set([a.reserva_id for a in asignaciones_creadas])),
            algoritmo_usado="balanceado",
            tiempo_ejecucion_segundos=round(tiempo_total, 2),
            estado=(
                "exito" if len(asignaciones_creadas) == len(candidatos) else "parcial"
            ),
            mensaje=f'Asignación desde interfaz web. Candidatos W{semana_carga.split("-W")[1]} → Entrevistas W{semana_entrevistas.split("-W")[1]}',
            ejecutado_por_usuario_id=session["user_id"],
        )

        session_asignacion.add(log)
        session_asignacion.commit()
        session_asignacion.close()

        return jsonify(
            {
                "success": True,
                "mensaje": f"{len(asignaciones_creadas)} candidatos asignados correctamente",
                "candidatos_asignados": len(asignaciones_creadas),
                "candidatos_sin_asignar": len(candidatos) - len(asignaciones_creadas),
                "franjas_utilizadas": len(
                    set([a.reserva_id for a in asignaciones_creadas])
                ),
                "semana_carga": semana_carga,
                "semana_entrevistas": semana_entrevistas,
                "tiempo_segundos": round(tiempo_total, 2),
            }
        )

    except Exception as e:
        return jsonify({"error": f"Error al ejecutar asignación: {str(e)}"}), 500


@app.route("/admin/candidatos/semana/<semana>")
@admin_required
def ver_candidatos_semana(semana):
    """Ver candidatos de una semana específica"""

    candidatos = (
        Candidato.query.filter_by(semana_carga=semana)
        .order_by(Candidato.media_estudios.asc())
        .all()
    )

    # Obtener estadísticas
    stats = obtener_estadisticas_semana_candidatos(semana)

    return render_template(
        "candidatos_semana.html",
        candidatos=candidatos,
        semana=semana,
        stats=stats,
        username=session["username"],
    )


@app.route("/admin/candidatos/asignaciones/<semana>")
@admin_required
def ver_asignaciones_semana(semana):
    """Ver asignaciones de una semana específica"""

    asignaciones = (
        db.session.query(Asignacion)
        .join(Candidato)
        .join(Reserva)
        .join(Usuario, Asignacion.entrevistador_id == Usuario.id)
        .filter(Candidato.semana_carga == semana)
        .order_by(Reserva.fecha, Reserva.hora_inicio, Asignacion.posicion)
        .all()
    )

    return render_template(
        "asignaciones_semana.html",
        asignaciones=asignaciones,
        semana=semana,
        username=session["username"],
    )
