"""
Gestión de candidatos: vista principal de administración, ejecución del
algoritmo de asignación, carga de Excel, y operaciones de borrado sobre
candidatos/semanas. (El resto de la administración de asignaciones ya
calculadas —gestión manual, reasignar, etc.— vive en routes/asignaciones.py;
la exportación de informes vive en routes/exportaciones.py.)
"""

import hashlib
import os
from datetime import datetime

from sqlalchemy import func

from flask import jsonify, render_template, request, session
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Asignacion, Candidato, CargaExcel, LogAsignacion
from app.services.asignacion import ejecutar_asignacion_automatica
from app.services.candidatos import obtener_estadisticas_semana_candidatos
from app.services.etl_candidatos import (
    ErrorCargaExcel,
    cargar,
    extraer,
    parsear_rango_solicitudes,
    transformar,
)
from app.services.logs import registrar_log
from app.utils.archivos import allowed_file
from app.utils.decorators import admin_required
from app.utils.semanas import obtener_semanas_disponibles


def register(app):
    @app.route("/admin/candidatos")
    @admin_required
    def admin_candidatos():
        """Vista principal de gestión de candidatos"""
        # Obtener estadísticas generales
        total_candidatos = Candidato.query.count()
        candidatos_pendientes = Candidato.query.filter_by(estado="pendiente").count()
        candidatos_asignados = Candidato.query.filter_by(estado="asignado").count()
        candidatos_entrevistados = Candidato.query.filter_by(
            estado="entrevistado"
        ).count()

        # Obtener semanas con candidatos
        semanas_con_candidatos = (
            db.session.query(
                Candidato.semana_carga,
                func.count(Candidato.clave_academica).label("total"),
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

    @app.route("/admin/candidatos/ejecutar-asignacion", methods=["POST"])
    @admin_required
    def ejecutar_asignacion():
        """
        Ruta fina: parsea la petición y traduce el resultado del algoritmo
        (en services/asignacion.py) a una respuesta HTTP. El algoritmo en
        sí —las 5 fases de clasificación, emparejamiento y guardado— vive
        en `ejecutar_asignacion_automatica`, para poder probarlo sin pasar
        por Flask.
        """
        try:
            data = request.json
            semana_carga = data.get("semana_carga")
            max_por_profesor = data.get("max_por_profesor")

            if not semana_carga:
                return jsonify({"error": "Debe especificar una semana de carga"}), 400

            payload, status = ejecutar_asignacion_automatica(
                semana_carga, session["user_id"], max_por_profesor
            )
            return jsonify(payload), status

        except Exception as e:
            db.session.rollback()
            import traceback

            traceback.print_exc()
            return jsonify({"error": f"Error al ejecutar asignación: {str(e)}"}), 500

    @app.route("/admin/candidatos/cargar-excel", methods=["POST"])
    @admin_required
    def cargar_excel_candidatos():
        """Procesa y carga un archivo Excel de candidatos"""

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
            umbral = float(request.form.get("umbral", 0))
            solicitudes_texto = request.form.get("solicitudes", "")

            if not semana:
                return jsonify({"error": "Debe especificar una semana"}), 400

            try:
                solicitudes_seleccionadas = parsear_rango_solicitudes(solicitudes_texto)
            except ErrorCargaExcel as e:
                return jsonify({"error": e.mensaje}), 400

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
            carga_existente = CargaExcel.query.filter_by(
                archivo_hash=archivo_hash
            ).first()
            if carga_existente:
                os.remove(filepath)
                return (
                    jsonify(
                        {
                            "error": f'Este archivo ya fue cargado el {carga_existente.fecha_carga.strftime("%d/%m/%Y %H:%M")}',
                            "duplicado": True,
                        }
                    ),
                    400,
                )

            # --- ETL: Extract ---
            df = extraer(filepath)

            # --- ETL: Transform ---
            try:
                df_filtrado, stats = transformar(
                    df,
                    umbral=umbral,
                    solicitudes_seleccionadas=solicitudes_seleccionadas,
                    semana=semana,
                    archivo_origen=filename,
                )
            except ErrorCargaExcel as e:
                os.remove(filepath)
                return jsonify({"error": e.mensaje, **e.extra}), 400

            total_leidos = stats["total_leidos"]
            total_validos = stats["total_validos"]
            candidatos_finales = stats["candidatos_finales"]
            candidatos_duplicados = stats["candidatos_duplicados"]
            candidatos_por_sede = stats["candidatos_por_sede"]
            candidatos_sin_sede = stats["candidatos_sin_sede"]
            candidatos_con_preferencias = stats["candidatos_con_preferencias"]
            candidatos_sin_preferencias = stats["candidatos_sin_preferencias"]

            # --- ETL: Load ---
            cargar(df_filtrado)

            # Registrar carga
            filtro_nota_texto = f"con nota < {umbral}" if umbral > 0 else "sin filtro de nota"
            filtro_solicitudes_texto = (
                f", solicitudes {solicitudes_texto.strip()}" if solicitudes_seleccionadas else ""
            )
            carga = CargaExcel(
                archivo_nombre=filename,
                archivo_hash=archivo_hash,
                candidatos_totales=total_leidos,
                candidatos_importados=candidatos_finales,
                candidatos_duplicados=candidatos_duplicados,
                cargado_por_usuario_id=session["user_id"],
                semana_destino=semana,
                estado="completado",
                mensaje=f"Importación exitosa. {candidatos_finales} candidatos {filtro_nota_texto}{filtro_solicitudes_texto}"
                + (
                    f" ({candidatos_duplicados} duplicados omitidos)"
                    if candidatos_duplicados > 0
                    else ""
                ),
            )
            db.session.add(carga)
            db.session.commit()

            # Registrar en logs
            registrar_log(
                accion="cargar_excel",
                entidad="candidatos",
                entidad_id=None,
                descripcion=f"Carga de Excel: {candidatos_finales} candidatos importados para semana {semana}",
                datos_nuevos={
                    "archivo": filename,
                    "semana": semana,
                    "candidatos_importados": candidatos_finales,
                    "candidatos_duplicados": candidatos_duplicados,
                    "umbral": umbral,
                    "candidatos_por_sede": candidatos_por_sede,
                    "con_preferencias": candidatos_con_preferencias,
                    "sin_preferencias": candidatos_sin_preferencias,
                },
                nivel="info",
            )

            # Mensajes informativos
            mensaje_sedes = ""
            if candidatos_por_sede:
                mensaje_sedes = "<br><strong>📍 Por sede:</strong><br>"
                for sede, cantidad in candidatos_por_sede.items():
                    mensaje_sedes += f"• {sede}: {cantidad}<br>"
            if candidatos_sin_sede > 0:
                mensaje_sedes += f"• ⚠️ Sin sede detectada: {candidatos_sin_sede}<br>"

            mensaje_preferencias = ""
            if candidatos_con_preferencias > 0:
                mensaje_preferencias = (
                    f"<br><strong>🕐 Preferencias de horario:</strong><br>"
                )
                mensaje_preferencias += (
                    f"• Con preferencias: {candidatos_con_preferencias}<br>"
                )
                mensaje_preferencias += (
                    f"• Sin preferencias: {candidatos_sin_preferencias}<br>"
                )

            mensaje_duplicados = ""
            if candidatos_duplicados > 0:
                mensaje_duplicados = f"<br><strong>⚠️ Duplicados omitidos:</strong> {candidatos_duplicados} candidatos ya existían<br>"

            # Eliminar archivo temporal
            os.remove(filepath)

            return jsonify(
                {
                    "success": True,
                    "mensaje": f"{candidatos_finales} candidatos importados correctamente",
                    "total_leidos": int(total_leidos),
                    "total_validos": int(total_validos),
                    "candidatos_finales": int(candidatos_finales),
                    "candidatos_duplicados": int(candidatos_duplicados),
                    "umbral": float(umbral),
                    "solicitudes": sorted(solicitudes_seleccionadas) if solicitudes_seleccionadas else None,
                    "semana": str(semana),
                    "candidatos_por_sede": candidatos_por_sede,
                    "candidatos_sin_sede": int(candidatos_sin_sede),
                    "candidatos_con_preferencias": int(candidatos_con_preferencias),
                    "candidatos_sin_preferencias": int(candidatos_sin_preferencias),
                    "mensaje_sedes": mensaje_sedes,
                    "mensaje_preferencias": mensaje_preferencias,
                    "mensaje_duplicados": mensaje_duplicados,
                }
            )

        except Exception as e:
            if "filepath" in locals() and os.path.exists(filepath):
                os.remove(filepath)
            import traceback

            traceback.print_exc()
            return jsonify({"error": f"Error al procesar el archivo: {str(e)}"}), 500

    @app.route("/admin/candidatos/semana/<semana>")
    @admin_required
    def ver_candidatos_semana(semana):
        """Ver candidatos de una semana específica"""

        candidatos_lista = (
            Candidato.query.filter_by(semana_carga=semana)
            .order_by(Candidato.media_estudios.asc())
            .all()
        )

        # Obtener estadísticas
        stats = obtener_estadisticas_semana_candidatos(semana)

        return render_template(
            "candidatos_semana.html",
            candidatos=candidatos_lista,
            semana=semana,
            stats=stats,
            username=session["username"],
        )

    @app.route("/admin/candidatos/eliminar/<clave_academica>", methods=["POST"])
    @admin_required
    def eliminar_candidato_por_clave(clave_academica):
        """Elimina un candidato de la base de datos"""

        try:
            # Limpiar la clave
            clave_academica = clave_academica.strip()

            # Buscar candidato
            candidato = Candidato.query.filter_by(
                clave_academica=clave_academica
            ).first()

            if not candidato:
                return jsonify({"error": "Candidato no encontrado"}), 404

            # Verificar si tiene asignaciones
            asignaciones = Asignacion.query.filter_by(
                candidato_clave=clave_academica
            ).count()
            if asignaciones > 0:
                return (
                    jsonify(
                        {
                            "error": f"No se puede eliminar. El candidato tiene {asignaciones} asignación(es). Debes eliminarlas primero."
                        }
                    ),
                    400,
                )

            # Guardar datos para log
            nombre_candidato = f"{candidato.nombre} {candidato.apellidos}"
            semana = candidato.semana_carga

            # Eliminar
            db.session.delete(candidato)
            db.session.commit()

            # Registrar en logs
            registrar_log(
                accion="eliminar",
                entidad="candidato",
                entidad_id=None,
                descripcion=f"Candidato eliminado: {nombre_candidato} ({clave_academica}) - Semana {semana}",
                datos_nuevos={
                    "clave_academica": clave_academica,
                    "nombre": nombre_candidato,
                    "semana": semana,
                },
                nivel="warning",
            )

            return jsonify(
                {
                    "success": True,
                    "mensaje": f"Candidato {nombre_candidato} eliminado correctamente",
                }
            )

        except Exception as e:
            db.session.rollback()
            print(f"❌ ERROR al eliminar candidato: {str(e)}")
            return jsonify({"error": f"Error al eliminar: {str(e)}"}), 500

    @app.route("/admin/candidatos/semana/<semana>/eliminar-todos", methods=["POST"])
    @admin_required
    def eliminar_candidatos_semana(semana):
        """Elimina todos los candidatos de una semana específica"""

        try:
            # Obtener candidatos
            candidatos_lista = Candidato.query.filter_by(semana_carga=semana).all()
            num_candidatos = len(candidatos_lista)

            if num_candidatos == 0:
                return jsonify({"error": "No hay candidatos en esta semana"}), 404

            # Obtener asignaciones
            candidatos_claves = [c.clave_academica for c in candidatos_lista]
            asignaciones = Asignacion.query.filter(
                Asignacion.candidato_clave.in_(candidatos_claves)
            ).all()
            num_asignaciones = len(asignaciones)

            # Eliminar asignaciones primero
            for asignacion in asignaciones:
                db.session.delete(asignacion)

            # Eliminar candidatos
            for candidato in candidatos_lista:
                db.session.delete(candidato)

            db.session.commit()

            # Registrar en logs
            registrar_log(
                accion="eliminar",
                entidad="candidatos_semana",
                entidad_id=None,
                descripcion=f"Candidatos eliminados de semana {semana}: {num_candidatos} candidatos, {num_asignaciones} asignaciones",
                datos_anteriores={
                    "semana": semana,
                    "candidatos": num_candidatos,
                    "asignaciones": num_asignaciones,
                },
                nivel="warning",
            )

            return jsonify(
                {
                    "success": True,
                    "mensaje": f"Todos los candidatos eliminados correctamente",
                    "candidatos_eliminados": num_candidatos,
                    "asignaciones_eliminadas": num_asignaciones,
                }
            )

        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Error al eliminar candidatos: {str(e)}"}), 500

    @app.route("/admin/candidato/<candidato_id>/eliminar", methods=["POST"])
    @admin_required
    def eliminar_candidato(candidato_id):
        """
        Elimina un candidato individual y su asignación si existe.

        BUGS corregidos (dos, en esta misma ruta):

        1. La clave primaria de Candidato es `clave_academica` (string,
           p. ej. "C001"), no un entero. La ruta declaraba
           `<int:candidato_id>`, así que en la práctica nunca podía
           encontrar un candidato real (su PK jamás es un entero puro).
           Se cambia el convertidor de la ruta a texto plano (sin
           `<int:...>`), igual que ya hace `eliminar_candidato_por_clave`
           más arriba en este mismo fichero.

        2. `get_or_404()` iba dentro del `try`/`except Exception`
           genérico de más abajo: un candidato_id inexistente lanzaba
           `werkzeug.exceptions.NotFound`, que ese except atrapaba como un
           error cualquiera, dando un 500 con mensaje de doble envoltura
           en vez de un 404 limpio (mismo patrón ya corregido en
           eliminar_log_asignacion y eliminar_carga). Se saca la búsqueda
           fuera del try.

        Esta ruta sigue sin tener ningún `url_for('eliminar_candidato')`
        en ninguna plantilla (confirmado por grep) — el borrado individual
        real desde la UI lo hace `eliminar_candidato_por_clave`, más
        arriba. Queda corregida por si en el futuro se enlaza desde algún
        sitio, no porque esté en uso ahora.
        """

        candidato = Candidato.query.get_or_404(candidato_id)

        try:
            # Eliminar asignación si existe
            asignacion = Asignacion.query.filter_by(
                candidato_clave=candidato_id
            ).first()
            if asignacion:
                db.session.delete(asignacion)

            nombre_completo = candidato.nombre_completo

            # Eliminar candidato
            db.session.delete(candidato)
            db.session.commit()

            # Registrar en logs
            registrar_log(
                accion="eliminar",
                entidad="candidato",
                entidad_id=candidato_id,
                descripcion=f"Candidato eliminado: {nombre_completo}",
                datos_anteriores={
                    "nombre": nombre_completo,
                    "solicitud": candidato.solicitud,
                    "estado": candidato.estado,
                },
                nivel="warning",
            )

            return jsonify(
                {"success": True, "mensaje": f"Candidato eliminado correctamente"}
            )

        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Error al eliminar candidato: {str(e)}"}), 500