"""
Calendario de reservas: la vista semanal, la consulta de franjas libres,
crear/cancelar una reserva, "mis reservas" del profesor, y la vista de
administración con todas las reservas de todo el mundo.
"""

from datetime import datetime, timedelta

from flask import jsonify, render_template, request, session

from app.constants import MAX_RESERVAS_POR_FRANJA
from app.extensions import db
from app.models import Espacio, Reserva, Usuario
from app.services.logs import registrar_log
from app.utils.decorators import admin_required, login_required


def register(app):
    @app.route("/reservas")
    @login_required
    def reservas():
        fecha_str = request.args.get("fecha", datetime.now().strftime("%Y-%m-%d"))
        fecha_base = datetime.strptime(fecha_str, "%Y-%m-%d")

        dias_hasta_lunes = fecha_base.weekday()
        lunes = fecha_base - timedelta(days=dias_hasta_lunes)

        espacios_db = Espacio.query.order_by(Espacio.id).limit(5).all()

        dias_semana = []
        nombres_dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

        for i, espacio in enumerate(espacios_db):
            dia = lunes + timedelta(days=i)
            dias_semana.append(
                {
                    "id": espacio.id,
                    "nombre": nombres_dias[i] if i < len(nombres_dias) else espacio.nombre,
                    "fecha": dia.strftime("%Y-%m-%d"),
                    "fecha_completa": dia.strftime("%d/%m/%Y"),
                    "color": espacio.color if espacio.color else "#667eea",
                }
            )

        semana_anterior = (lunes - timedelta(days=7)).strftime("%Y-%m-%d")
        semana_siguiente = (lunes + timedelta(days=7)).strftime("%Y-%m-%d")

        usuarios_lista = []
        if session.get("rol") == "admin":
            usuarios_lista = (
                Usuario.query.filter_by(activo=True).order_by(Usuario.username).all()
            )
            usuarios_lista = [
                {"id": u.id, "username": u.username, "email": u.email}
                for u in usuarios_lista
            ]

        return render_template(
            "reservas.html",
            espacios=dias_semana,
            fecha_seleccionada=fecha_str,
            semana_anterior=semana_anterior,
            semana_siguiente=semana_siguiente,
            fecha_inicio_semana=lunes.strftime("%d/%m/%Y"),
            fecha_fin_semana=(lunes + timedelta(days=4)).strftime("%d/%m/%Y"),
            username=session["username"],
            es_admin=session.get("rol") == "admin",
            usuarios_lista=usuarios_lista,
            max_reservas=MAX_RESERVAS_POR_FRANJA,
        )

    @app.route("/api/franjas/<int:dia_id>")
    @login_required
    def obtener_franjas(dia_id):
        fecha_str = request.args.get("fecha")
        if not fecha_str:
            return jsonify({"error": "Fecha no proporcionada"}), 400

        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()

        franjas = []

        # Franjas de mañana: 10:00 - 13:00
        franjas_manana = [
            ("10:00", "10:30"),
            ("10:30", "11:00"),
            ("11:00", "11:30"),
            ("11:30", "12:00"),
            ("12:00", "12:30"),
            ("12:30", "13:00"),
        ]

        # Franjas de tarde: 15:00 - 19:00
        franjas_tarde = [
            ("15:00", "15:30"),
            ("15:30", "16:00"),
            ("16:00", "16:30"),
            ("16:30", "17:00"),
            ("17:00", "17:30"),
            ("17:30", "18:00"),
            ("18:00", "18:30"),
            ("18:30", "19:00"),
        ]

        todas_franjas = franjas_manana + franjas_tarde

        for franja_inicio, franja_fin in todas_franjas:
            reservas_franja = Reserva.query.filter_by(
                espacio_id=dia_id,
                fecha=fecha,
                hora_inicio=datetime.strptime(franja_inicio, "%H:%M").time(),
            ).all()

            num_reservas = len(reservas_franja)

            tiene_secundaria = any(r.prioridad == "secundaria" for r in reservas_franja)
            solo_secundarias = (
                all(r.prioridad == "secundaria" for r in reservas_franja)
                if num_reservas > 0
                else False
            )

            mis_reservas_franja = [
                r for r in reservas_franja if r.usuario_id == session.get("user_id")
            ]
            tiene_mi_reserva = len(mis_reservas_franja) > 0

            reservas_info = []
            for r in reservas_franja:
                reservas_info.append(
                    {
                        "id": r.id,
                        "usuario": r.usuario.username,
                        "notas": r.notas,
                        "es_mia": r.usuario_id == session.get("user_id"),
                        "prioridad": r.prioridad,
                    }
                )

            franjas.append(
                {
                    "hora_inicio": franja_inicio,
                    "hora_fin": franja_fin,
                    "num_reservas": num_reservas,
                    "max_reservas": MAX_RESERVAS_POR_FRANJA,
                    "disponible": num_reservas == 0,
                    "parcial": 0 < num_reservas < MAX_RESERVAS_POR_FRANJA,
                    "completa": num_reservas >= MAX_RESERVAS_POR_FRANJA,
                    "tiene_mi_reserva": tiene_mi_reserva,
                    "tiene_secundaria": tiene_secundaria,
                    "solo_secundarias": solo_secundarias,
                    "reservas": reservas_info,
                    "puede_reservar": num_reservas < MAX_RESERVAS_POR_FRANJA,
                }
            )

        return jsonify(franjas)

    @app.route("/api/reservar", methods=["POST"])
    @login_required
    def hacer_reserva():
        data = request.json
        espacio_id = data["espacio_id"]
        fecha_str = data["fecha"]
        hora_inicio_str = data["hora_inicio"]
        hora_fin_str = data["hora_fin"]
        notas = data.get("notas", "")
        prioridad = data.get("prioridad", "normal")

        usuario_id_destino = data.get("usuario_id", session["user_id"])

        if usuario_id_destino != session["user_id"] and session.get("rol") != "admin":
            return (
                jsonify(
                    {"error": "No tienes permiso para reservar en nombre de otros usuarios"}
                ),
                403,
            )

        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        hora_inicio = datetime.strptime(hora_inicio_str, "%H:%M").time()
        hora_fin = datetime.strptime(hora_fin_str, "%H:%M").time()

        # Verificar que no existan más de MAX_RESERVAS_POR_FRANJA reservas
        reservas_existentes = Reserva.query.filter_by(
            espacio_id=espacio_id, fecha=fecha, hora_inicio=hora_inicio
        ).all()

        if len(reservas_existentes) >= MAX_RESERVAS_POR_FRANJA:
            return (
                jsonify(
                    {
                        "error": f"Esta franja ya tiene el máximo de {MAX_RESERVAS_POR_FRANJA} reservas"
                    }
                ),
                400,
            )

        # Verificar que el usuario no tenga ya una reserva en esta franja
        reserva_usuario = Reserva.query.filter_by(
            usuario_id=usuario_id_destino,
            espacio_id=espacio_id,
            fecha=fecha,
            hora_inicio=hora_inicio,
        ).first()

        if reserva_usuario:
            return jsonify({"error": "Ya tienes una reserva en esta franja"}), 400

        nueva_reserva = Reserva(
            usuario_id=usuario_id_destino,
            espacio_id=espacio_id,
            fecha=fecha,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            notas=notas,
            prioridad=prioridad,
            creado_por_admin=(
                session["user_id"] if usuario_id_destino != session["user_id"] else None
            ),
        )

        db.session.add(nueva_reserva)
        db.session.commit()

        # Registrar creación de reserva
        usuario_destino = Usuario.query.get(usuario_id_destino)
        espacio = Espacio.query.get(espacio_id)

        registrar_log(
            accion="crear",
            entidad="reserva",
            entidad_id=nueva_reserva.id,
            descripcion=f'Reserva creada: {usuario_destino.username} - {espacio.nombre if espacio else "N/A"} - {fecha_str} {hora_inicio_str}',
            datos_nuevos={
                "usuario": usuario_destino.username,
                "fecha": fecha_str,
                "hora_inicio": hora_inicio_str,
                "hora_fin": hora_fin_str,
                "prioridad": prioridad,
                "notas": notas,
            },
            nivel="info",
        )

        if usuario_id_destino != session["user_id"]:
            usuario_destino = Usuario.query.get(usuario_id_destino)
            mensaje = f"Reserva creada correctamente para {usuario_destino.username}"
        else:
            prioridad_texto = "secundaria" if prioridad == "secundaria" else "normal"
            mensaje = f"Reserva {prioridad_texto} realizada correctamente"

        return jsonify({"success": True, "mensaje": mensaje})

    @app.route("/api/cancelar", methods=["POST"])
    @login_required
    def cancelar_reserva():
        data = request.json
        reserva_id = data.get("reserva_id")

        if reserva_id:
            reserva = Reserva.query.get(reserva_id)
        else:
            espacio_id = data["espacio_id"]
            fecha_str = data["fecha"]
            hora_inicio_str = data["hora_inicio"]

            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            hora_inicio = datetime.strptime(hora_inicio_str, "%H:%M").time()

            reserva = Reserva.query.filter_by(
                espacio_id=espacio_id, fecha=fecha, hora_inicio=hora_inicio
            ).first()

        if not reserva:
            return jsonify({"error": "Reserva no encontrada"}), 404

        if reserva.usuario_id != session["user_id"] and session.get("rol") != "admin":
            return jsonify({"error": "No tienes permiso para cancelar esta reserva"}), 403
        datos_reserva = {
            "id": reserva.id,
            "usuario": reserva.usuario.username,
            "fecha": reserva.fecha.strftime("%d/%m/%Y"),
            "hora_inicio": reserva.hora_inicio.strftime("%H:%M"),
            "prioridad": reserva.prioridad,
            "espacio": reserva.espacio.nombre if reserva.espacio else "N/A",
        }

        registrar_log(
            accion="eliminar",
            entidad="reserva",
            entidad_id=reserva.id,
            descripcion=f'Reserva cancelada: {datos_reserva["usuario"]} - {datos_reserva["espacio"]} - {datos_reserva["fecha"]} {datos_reserva["hora_inicio"]}',
            datos_anteriores=datos_reserva,
            nivel="info",
        )

        db.session.delete(reserva)
        db.session.commit()

        return jsonify({"success": True, "mensaje": "Reserva cancelada correctamente"})

    @app.route("/mis-reservas")
    @login_required
    def mis_reservas():
        hoy = datetime.now().date()
        reservas_futuras = (
            Reserva.query.filter(
                Reserva.usuario_id == session["user_id"], Reserva.fecha >= hoy
            )
            .order_by(Reserva.fecha, Reserva.hora_inicio)
            .all()
        )

        reservas_pasadas = (
            Reserva.query.filter(
                Reserva.usuario_id == session["user_id"], Reserva.fecha < hoy
            )
            .order_by(Reserva.fecha.desc(), Reserva.hora_inicio.desc())
            .limit(10)
            .all()
        )

        return render_template(
            "mis_reservas.html",
            reservas_futuras=reservas_futuras,
            reservas_pasadas=reservas_pasadas,
            username=session["username"],
            es_admin=session.get("rol") == "admin",
        )

    @app.route("/admin/todas-reservas")
    @admin_required
    def todas_reservas():
        usuario_filtro = request.args.get("usuario", "")
        dia_filtro = request.args.get("dia", "")
        fecha_desde = request.args.get("fecha_desde", "")
        fecha_hasta = request.args.get("fecha_hasta", "")

        query = Reserva.query

        if usuario_filtro:
            query = query.filter(Reserva.usuario_id == int(usuario_filtro))

        if dia_filtro:
            query = query.filter(Reserva.espacio_id == int(dia_filtro))

        if fecha_desde:
            fecha_desde_obj = datetime.strptime(fecha_desde, "%Y-%m-%d").date()
            query = query.filter(Reserva.fecha >= fecha_desde_obj)

        if fecha_hasta:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
            query = query.filter(Reserva.fecha <= fecha_hasta_obj)

        reservas_filtradas = query.order_by(
            Reserva.fecha.desc(), Reserva.hora_inicio.desc()
        ).all()

        usuarios = Usuario.query.filter_by(activo=True).order_by(Usuario.username).all()
        espacios = Espacio.query.order_by(Espacio.id).all()

        total_reservas = len(reservas_filtradas)
        usuarios_unicos = len(set(r.usuario_id for r in reservas_filtradas))
        dias_con_reservas = len(set(r.espacio_id for r in reservas_filtradas))

        return render_template(
            "todas_reservas.html",
            reservas=reservas_filtradas,
            usuarios=usuarios,
            espacios=espacios,
            total_reservas=total_reservas,
            usuarios_unicos=usuarios_unicos,
            dias_con_reservas=dias_con_reservas,
            usuario_filtro=usuario_filtro,
            dia_filtro=dia_filtro,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            username=session["username"],
        )