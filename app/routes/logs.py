"""
Auditoría (logs_actividad): la vista paginada con filtros, el detalle de
un log individual, su exportación a Excel, y el borrado de una carga de
Excel (con sus candidatos y asignaciones asociadas en cascada).
"""

from datetime import datetime
from io import BytesIO

from flask import jsonify, render_template, request, send_file, session
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from app.extensions import db
from app.models import Asignacion, Candidato, CargaExcel, LogActividad
from app.services.logs import registrar_log
from app.services.repetidos import borrar_repetidos
from app.utils.decorators import admin_required


def register(app):
    @app.route("/admin/logs")
    @admin_required
    def ver_logs():
        """Vista de logs de auditoría"""

        # Parámetros de filtro
        pagina = request.args.get("pagina", 1, type=int)
        por_pagina = request.args.get("por_pagina", 50, type=int)

        filtro_usuario = request.args.get("usuario", "")
        filtro_accion = request.args.get("accion", "")
        filtro_entidad = request.args.get("entidad", "")
        filtro_nivel = request.args.get("nivel", "")
        fecha_desde = request.args.get("fecha_desde", "")
        fecha_hasta = request.args.get("fecha_hasta", "")
        buscar = request.args.get("buscar", "")

        # Query base
        query = LogActividad.query

        # Aplicar filtros
        if filtro_usuario:
            query = query.filter(
                LogActividad.usuario_username.ilike(f"%{filtro_usuario}%")
            )

        if filtro_accion:
            query = query.filter(LogActividad.accion == filtro_accion)

        if filtro_entidad:
            query = query.filter(LogActividad.entidad == filtro_entidad)

        if filtro_nivel:
            query = query.filter(LogActividad.nivel == filtro_nivel)

        if fecha_desde:
            fecha_desde_obj = datetime.strptime(fecha_desde, "%Y-%m-%d")
            query = query.filter(LogActividad.fecha_hora >= fecha_desde_obj)

        if fecha_hasta:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, "%Y-%m-%d")
            fecha_hasta_obj = fecha_hasta_obj.replace(hour=23, minute=59, second=59)
            query = query.filter(LogActividad.fecha_hora <= fecha_hasta_obj)

        if buscar:
            query = query.filter(LogActividad.descripcion.ilike(f"%{buscar}%"))

        # Ordenar por fecha descendente
        query = query.order_by(LogActividad.fecha_hora.desc())

        # Paginación
        paginacion = query.paginate(page=pagina, per_page=por_pagina, error_out=False)
        logs = paginacion.items

        # Obtener valores únicos para filtros
        acciones_disponibles = (
            db.session.query(LogActividad.accion)
            .distinct()
            .order_by(LogActividad.accion)
            .all()
        )
        acciones_disponibles = [a[0] for a in acciones_disponibles]

        entidades_disponibles = (
            db.session.query(LogActividad.entidad)
            .distinct()
            .order_by(LogActividad.entidad)
            .all()
        )
        entidades_disponibles = [e[0] for e in entidades_disponibles]

        usuarios_disponibles = (
            db.session.query(LogActividad.usuario_username)
            .distinct()
            .filter(LogActividad.usuario_username.isnot(None))
            .order_by(LogActividad.usuario_username)
            .all()
        )
        usuarios_disponibles = [u[0] for u in usuarios_disponibles]

        # Estadísticas rápidas
        total_logs = LogActividad.query.count()
        logs_hoy = LogActividad.query.filter(
            LogActividad.fecha_hora >= datetime.now().replace(hour=0, minute=0, second=0)
        ).count()
        logs_error = LogActividad.query.filter(
            LogActividad.nivel.in_(["error", "critical"])
        ).count()

        return render_template(
            "admin_logs.html",
            logs=logs,
            paginacion=paginacion,
            acciones_disponibles=acciones_disponibles,
            entidades_disponibles=entidades_disponibles,
            usuarios_disponibles=usuarios_disponibles,
            total_logs=total_logs,
            logs_hoy=logs_hoy,
            logs_error=logs_error,
            filtro_usuario=filtro_usuario,
            filtro_accion=filtro_accion,
            filtro_entidad=filtro_entidad,
            filtro_nivel=filtro_nivel,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            buscar=buscar,
            por_pagina=por_pagina,
            username=session["username"],
        )

    @app.route("/admin/logs/<int:log_id>/detalle")
    @admin_required
    def detalle_log(log_id):
        """Obtiene el detalle completo de un log"""

        log = LogActividad.query.get_or_404(log_id)

        return jsonify(
            {
                "id": log.id,
                "fecha_hora": log.fecha_hora.strftime("%d/%m/%Y %H:%M:%S"),
                "usuario": log.usuario_username,
                "accion": log.accion,
                "entidad": log.entidad,
                "entidad_id": log.entidad_id,
                "descripcion": log.descripcion,
                "datos_anteriores": log.datos_anteriores,
                "datos_nuevos": log.datos_nuevos,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "nivel": log.nivel,
                "metadata": log.metadata_extra,
            }
        )

    @app.route("/admin/logs/exportar")
    @admin_required
    def exportar_logs():
        """Exporta logs filtrados a Excel"""

        # Aplicar los mismos filtros que en la vista
        filtro_usuario = request.args.get("usuario", "")
        filtro_accion = request.args.get("accion", "")
        filtro_entidad = request.args.get("entidad", "")
        filtro_nivel = request.args.get("nivel", "")
        fecha_desde = request.args.get("fecha_desde", "")
        fecha_hasta = request.args.get("fecha_hasta", "")
        buscar = request.args.get("buscar", "")

        query = LogActividad.query

        if filtro_usuario:
            query = query.filter(
                LogActividad.usuario_username.ilike(f"%{filtro_usuario}%")
            )

        if filtro_accion:
            query = query.filter(LogActividad.accion == filtro_accion)

        if filtro_entidad:
            query = query.filter(LogActividad.entidad == filtro_entidad)

        if filtro_nivel:
            query = query.filter(LogActividad.nivel == filtro_nivel)

        if fecha_desde:
            fecha_desde_obj = datetime.strptime(fecha_desde, "%Y-%m-%d")
            query = query.filter(LogActividad.fecha_hora >= fecha_desde_obj)

        if fecha_hasta:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, "%Y-%m-%d")
            fecha_hasta_obj = fecha_hasta_obj.replace(hour=23, minute=59, second=59)
            query = query.filter(LogActividad.fecha_hora <= fecha_hasta_obj)

        if buscar:
            query = query.filter(LogActividad.descripcion.ilike(f"%{buscar}%"))

        logs = (
            query.order_by(LogActividad.fecha_hora.desc()).limit(1000).all()
        )  # Límite de 1000

        # Crear Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Logs de Auditoría"

        # Estilos
        header_font = Font(bold=True, color="FFFFFF", size=12)
        header_fill = PatternFill(
            start_color="0066B3", end_color="0066B3", fill_type="solid"
        )
        border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        # Encabezados
        headers = [
            "ID",
            "Fecha/Hora",
            "Usuario",
            "Acción",
            "Entidad",
            "ID Entidad",
            "Descripción",
            "Nivel",
            "IP",
        ]
        ws.append(headers)

        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border

        # Datos
        for log in logs:
            row = [
                log.id,
                log.fecha_hora.strftime("%d/%m/%Y %H:%M:%S"),
                log.usuario_username or "Sistema",
                log.accion,
                log.entidad,
                log.entidad_id or "",
                log.descripcion,
                log.nivel.upper(),
                log.ip_address or "",
            ]
            ws.append(row)

            # Aplicar bordes
            for cell in ws[ws.max_row]:
                cell.border = border
                cell.alignment = Alignment(vertical="center")

        # Ajustar anchos
        ws.column_dimensions["A"].width = 8
        ws.column_dimensions["B"].width = 18
        ws.column_dimensions["C"].width = 15
        ws.column_dimensions["D"].width = 15
        ws.column_dimensions["E"].width = 12
        ws.column_dimensions["F"].width = 10
        ws.column_dimensions["G"].width = 60
        ws.column_dimensions["H"].width = 10
        ws.column_dimensions["I"].width = 15

        # Filtros automáticos
        ws.auto_filter.ref = ws.dimensions

        # Guardar
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        # Registrar la exportación
        registrar_log(
            accion="exportar",
            entidad="logs",
            entidad_id=None,
            descripcion=f"Exportación de {len(logs)} logs de auditoría",
            nivel="info",
            metadata={"cantidad": len(logs), "filtros_aplicados": True},
        )

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f'logs_auditoria_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
        )

    @app.route("/admin/cargas/eliminar/<int:carga_id>", methods=["POST"])
    @admin_required
    def eliminar_carga(carga_id):
        """Elimina una carga de Excel y todos sus candidatos asociados"""

        # BUG corregido: mismo patrón que en eliminar_log_asignacion()
        # (app/routes/asignaciones.py) y eliminar_candidato()
        # (app/routes/candidatos.py) — get_or_404() iba dentro del try de
        # más abajo, con un único except Exception genérico, así que un
        # carga_id inexistente producía un 500 con mensaje confuso en vez
        # de un 404 limpio. Se saca la búsqueda fuera del try para que
        # NotFound se propague a Flask sin que el except la intercepte.
        carga = CargaExcel.query.get_or_404(carga_id)

        try:
            # Obtener candidatos de esta carga
            candidatos = Candidato.query.filter_by(
                archivo_origen=carga.archivo_nombre, semana_carga=carga.semana_destino
            ).all()

            num_candidatos = len(candidatos)

            # Verificar si hay asignaciones
            candidatos_claves = [c.clave_academica for c in candidatos]
            asignaciones = Asignacion.query.filter(
                Asignacion.candidato_clave.in_(candidatos_claves)
            ).all()
            num_asignaciones = len(asignaciones)

            # Eliminar asignaciones primero (por FK)
            if num_asignaciones > 0:
                for asignacion in asignaciones:
                    db.session.delete(asignacion)

            # Eliminar candidatos
            for candidato in candidatos:
                db.session.delete(candidato)

            # Eliminar registro de carga
            db.session.delete(carga)
            db.session.commit()
            borrar_repetidos(carga_id)

            # Registrar en logs
            registrar_log(
                accion="eliminar",
                entidad="carga_excel",
                entidad_id=carga_id,
                descripcion=f"Carga eliminada: {carga.archivo_nombre} ({num_candidatos} candidatos, {num_asignaciones} asignaciones)",
                datos_anteriores={
                    "archivo": carga.archivo_nombre,
                    "semana": carga.semana_destino,
                    "candidatos": num_candidatos,
                    "asignaciones": num_asignaciones,
                },
                nivel="warning",
            )

            return jsonify(
                {
                    "success": True,
                    "mensaje": f"Carga eliminada correctamente",
                    "candidatos_eliminados": num_candidatos,
                    "asignaciones_eliminadas": num_asignaciones,
                }
            )

        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Error al eliminar carga: {str(e)}"}), 500