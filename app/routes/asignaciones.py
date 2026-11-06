"""
Gestión manual de asignaciones ya existentes: ver las asignaciones de una
semana, la vista de gestión manual (candidatos + reservas con ocupación),
asignar/desasignar/reasignar un candidato a mano, consultar el detalle de
una reserva, y los borrados de asignaciones (por semana completa o de un
log de asignación individual). La ejecución del algoritmo automático y el
CRUD de candidatos viven en routes/candidatos.py.
"""

from datetime import date, datetime, timedelta

from flask import jsonify, render_template, request, session

from app.extensions import db
from app.models import (
    Asignacion,
    Candidato,
    DiaBloqueado,
    LogAsignacion,
    Reserva,
    Sede,
    Usuario,
)
from app.services.candidatos import obtener_estadisticas_semana_candidatos
from app.services.logs import registrar_log
from app.utils.decorators import admin_required


def _sedes_para_bloqueo():
    """Campus que se pueden bloquear: activos, o con `activa` sin rellenar
    (una sede creada a mano en SQL puede tener NULL en vez de True)."""
    return (
        Sede.query.filter(db.or_(Sede.activa.is_(True), Sede.activa.is_(None)))
        .order_by(Sede.nombre)
        .all()
    )


def register(app):
    @app.route("/admin/dias-bloqueados")
    @admin_required
    def admin_dias_bloqueados():
        """Días en los que no se asignan entrevistas a candidatos de un campus."""
        bloqueos = DiaBloqueado.query.order_by(DiaBloqueado.fecha, DiaBloqueado.sede).all()
        sedes = _sedes_para_bloqueo()
        return render_template(
            "dias_bloqueados.html",
            bloqueos=bloqueos,
            sedes=sedes,
            hoy=date.today(),
            username=session["username"],
        )

    @app.route("/admin/dias-bloqueados/crear", methods=["POST"])
    @admin_required
    def crear_dia_bloqueado():
        datos = request.get_json(silent=True) or {}
        try:
            fecha = datetime.strptime(str(datos.get("fecha", "")), "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Fecha no válida"}), 400

        sedes_validas = {s.nombre for s in _sedes_para_bloqueo()}
        sedes = datos.get("sedes")
        if not isinstance(sedes, list) or not sedes:
            return jsonify({"error": "Selecciona al menos un campus"}), 400
        if any(s not in sedes_validas for s in sedes):
            return jsonify({"error": "Campus no válido"}), 400

        motivo = (datos.get("motivo") or "").strip()[:255] or None
        creadas, existentes = [], []
        for sede in dict.fromkeys(sedes):
            if DiaBloqueado.query.filter_by(fecha=fecha, sede=sede).first():
                existentes.append(sede)
                continue
            db.session.add(
                DiaBloqueado(
                    fecha=fecha, sede=sede, motivo=motivo,
                    creado_por_usuario_id=session.get("user_id"),
                )
            )
            creadas.append(sede)

        if not creadas:
            return jsonify({"error": "Ese día ya está bloqueado para los campus elegidos"}), 400
        db.session.commit()

        registrar_log(
            accion="bloquear_dia",
            entidad="dia_bloqueado",
            entidad_id=None,
            descripcion=f"Día {fecha.isoformat()} bloqueado para: {', '.join(creadas)}",
            datos_nuevos={"fecha": fecha.isoformat(), "sedes": creadas, "motivo": motivo},
            nivel="info",
        )
        return jsonify({"success": True, "creadas": creadas, "ya_existian": existentes})

    @app.route("/admin/dias-bloqueados/eliminar/<int:bloqueo_id>", methods=["POST"])
    @admin_required
    def eliminar_dia_bloqueado(bloqueo_id):
        bloqueo = db.get_or_404(DiaBloqueado, bloqueo_id)
        info = {"fecha": bloqueo.fecha.isoformat(), "sede": bloqueo.sede, "motivo": bloqueo.motivo}
        db.session.delete(bloqueo)
        db.session.commit()
        registrar_log(
            accion="desbloquear_dia",
            entidad="dia_bloqueado",
            entidad_id=bloqueo_id,
            descripcion=f"Día {info['fecha']} desbloqueado para {info['sede']}",
            datos_anteriores=info,
            nivel="info",
        )
        return jsonify({"success": True})

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

    @app.route("/admin/candidatos/gestion-manual/<semana>")
    @admin_required
    def gestion_manual_candidatos(semana):
        """Vista de gestión manual de candidatos y asignaciones"""

        # Clave del candidato a resaltar/preseleccionar al entrar (viene
        # del botón "Reasignar" de /admin/candidatos/semana/<semana>), para
        # que el admin llegue aquí viendo ya marcados tanto el candidato
        # como la franja en la que estaba reservado, sin tener que buscarlo
        # a mano entre toda la lista.
        candidato_resaltado = request.args.get("candidato")

        # Obtener candidatos de la semana. Sin nota (media_estudios None)
        # se ordena como si fuera un 5, igual que en el resto de la app.
        candidatos = (
            Candidato.query.filter_by(semana_carga=semana)
            .order_by(db.func.coalesce(Candidato.media_estudios, 5).asc())
            .all()
        )

        # Calcular semana de entrevistas (siguiente semana)
        año, semana_num = semana.split("-W")
        primer_dia = datetime.strptime(f"{año}-W{semana_num}-1", "%Y-W%W-%w").date()
        siguiente_lunes = primer_dia + timedelta(days=7)
        viernes = siguiente_lunes + timedelta(days=4)
        semana_entrevistas = siguiente_lunes.strftime("%Y-W%W")

        # Obtener reservas de la semana de entrevistas
        reservas = (
            Reserva.query.filter(Reserva.fecha >= siguiente_lunes)
            .filter(Reserva.fecha <= viernes)
            .order_by(Reserva.fecha, Reserva.hora_inicio)
            .all()
        )

        # Preparar datos de reservas con ocupación
        reservas_info = []
        for reserva in reservas:
            asignaciones = Asignacion.query.filter_by(reserva_id=reserva.id).all()
            num_asignaciones = len(asignaciones)

            reservas_info.append(
                {
                    "reserva": reserva,
                    "num_asignaciones": num_asignaciones,
                    "espacios_libres": 2 - num_asignaciones,
                    "asignaciones": asignaciones,
                    "color_estado": (
                        "success"
                        if num_asignaciones == 0
                        else "warning" if num_asignaciones == 1 else "danger"
                    ),
                }
            )

        # Estadísticas
        stats = obtener_estadisticas_semana_candidatos(semana)

        # Obtener lista de entrevistadores
        entrevistadores = (
            Usuario.query.filter_by(activo=True).order_by(Usuario.username).all()
        )

        # Centros que realmente aparecen entre los candidatos de la semana,
        # para el desplegable de filtro por centro.
        sedes_filtro = sorted({c.sede for c in candidatos if c.sede})

        return render_template(
            "gestion_manual.html",
            candidatos=candidatos,
            sedes_filtro=sedes_filtro,
            # Centros para el filtro del panel de reservas (el centro de una
            # reserva es el de su profesor, no el de un candidato).
            sedes_reservas=[
                s.nombre for s in Sede.query.filter_by(activa=True).order_by(Sede.nombre)
            ],
            reservas_info=reservas_info,
            semana=semana,
            semana_entrevistas=semana_entrevistas,
            stats=stats,
            entrevistadores=entrevistadores,
            lunes=siguiente_lunes,
            viernes=viernes,
            username=session["username"],
            candidato_resaltado=candidato_resaltado,
        )

    @app.route("/admin/candidatos/asignar-manual", methods=["POST"])
    @admin_required
    def asignar_candidato_manual():
        """Asigna un candidato a una reserva manualmente"""

        try:
            data = request.json

            # DEBUG: Imprimir datos recibidos
            print("=" * 50)
            print("📥 DATOS RECIBIDOS EN ASIGNAR MANUAL:")
            print(f"Data completo: {data}")
            print(f"candidato_clave: {data.get('candidato_clave')}")
            print(f"reserva_id: {data.get('reserva_id')}")
            print(f"posicion: {data.get('posicion')}")
            print("=" * 50)

            # Obtener datos
            candidato_clave = data.get("candidato_clave")
            reserva_id = data.get("reserva_id")
            posicion = data.get("posicion")

            # Validación detallada
            errores = []

            if not candidato_clave:
                errores.append("candidato_clave es requerido")

            if not reserva_id:
                errores.append("reserva_id es requerido")

            if not posicion:
                errores.append("posicion es requerido")

            if errores:
                error_msg = f"Faltan datos requeridos: {', '.join(errores)}"
                print(f"❌ ERROR: {error_msg}")
                return jsonify({"error": error_msg}), 400

            # Validar candidato
            candidato_clave = candidato_clave.strip() if candidato_clave else None
            candidato = Candidato.query.filter_by(
                clave_academica=candidato_clave
            ).first()
            if not candidato:
                print(f"❌ ERROR: Candidato con clave '{candidato_clave}' no encontrado")
                return (
                    jsonify(
                        {
                            "error": f"Candidato con clave {candidato_clave} no encontrado"
                        }
                    ),
                    404,
                )

            print(f"✅ Candidato encontrado: {candidato.nombre} {candidato.apellidos}")

            # Validar reserva
            reserva = Reserva.query.get(reserva_id)
            if not reserva:
                print(f"❌ ERROR: Reserva {reserva_id} no encontrada")
                return jsonify({"error": "Reserva no encontrada"}), 404

            print(f"✅ Reserva encontrada: {reserva.fecha} {reserva.hora_inicio}")

            # Verificar que el candidato no tenga ya una asignación
            asignacion_existente = Asignacion.query.filter_by(
                candidato_clave=candidato_clave
            ).first()
            if asignacion_existente:
                error_msg = f"El candidato ya tiene una asignación"
                print(f"❌ ERROR: {error_msg}")
                return jsonify({"error": error_msg}), 400

            # Verificar espacios disponibles
            asignaciones_actuales = Asignacion.query.filter_by(
                reserva_id=reserva_id
            ).count()
            if asignaciones_actuales >= 2:
                print(f"❌ ERROR: Reserva completa ({asignaciones_actuales}/2)")
                return jsonify({"error": "Esta reserva ya tiene 2 asignaciones"}), 400

            # Verificar que la posición no esté ocupada
            posicion_ocupada = Asignacion.query.filter_by(
                reserva_id=reserva_id, posicion=posicion
            ).first()
            if posicion_ocupada:
                print(f"❌ ERROR: Posición {posicion} ocupada")
                return (
                    jsonify({"error": f"La posición {posicion} ya está ocupada"}),
                    400,
                )

            # Calcular minuto de inicio
            minuto_inicio = 0 if posicion == 1 else 15

            print(
                f"✅ Creando asignación: posición={posicion}, minuto_inicio={minuto_inicio}"
            )

            # Crear asignación
            asignacion = Asignacion(
                candidato_clave=candidato_clave,
                reserva_id=reserva_id,
                entrevistador_id=reserva.usuario_id,
                posicion=posicion,
                minuto_inicio=minuto_inicio,
                estado="confirmado",
                fecha_asignacion=datetime.now(),
                asignado_por_admin_id=session["user_id"],
            )

            db.session.add(asignacion)

            # Actualizar estado del candidato
            candidato.estado = "asignado"

            db.session.commit()

            print(f"✅ Asignación creada exitosamente: ID={asignacion.id}")

            # Registrar en logs
            registrar_log(
                accion="asignar",
                entidad="asignacion",
                entidad_id=asignacion.id,
                descripcion=f"Asignación manual: {candidato.nombre} {candidato.apellidos}",
                datos_nuevos={
                    "candidato_clave": candidato_clave,
                    "reserva_id": reserva_id,
                    "posicion": posicion,
                },
                nivel="info",
            )

            return jsonify(
                {
                    "success": True,
                    "mensaje": f"Candidato {candidato.nombre} {candidato.apellidos} asignado correctamente",
                    "asignacion_id": asignacion.id,
                }
            )

        except Exception as e:
            db.session.rollback()

            print("=" * 50)
            print(f"💥 EXCEPCIÓN EN ASIGNAR MANUAL:")
            print(f"Error: {str(e)}")
            import traceback

            traceback.print_exc()
            print("=" * 50)

            registrar_log(
                accion="asignar",
                entidad="asignacion",
                entidad_id=None,
                descripcion=f"Error al asignar candidato: {str(e)}",
                nivel="error",
            )

            return jsonify({"error": f"Error al asignar candidato: {str(e)}"}), 500

    @app.route("/admin/candidatos/desasignar-manual", methods=["POST"])
    @admin_required
    def desasignar_candidato_manual():
        """Desasigna un candidato de una entrevista"""

        try:
            data = request.json
            asignacion_id = data.get("asignacion_id")

            if not asignacion_id:
                return jsonify({"error": "ID de asignación no proporcionado"}), 400

            # Buscar asignación
            asignacion = Asignacion.query.get(asignacion_id)
            if not asignacion:
                return jsonify({"error": "Asignación no encontrada"}), 404

            # Guardar datos del candidato antes de eliminar
            candidato = asignacion.candidato
            candidato_nombre = f"{candidato.nombre} {candidato.apellidos}"

            # Actualizar estado del candidato
            candidato.estado = "pendiente"

            # Eliminar asignación
            db.session.delete(asignacion)
            db.session.commit()

            return jsonify(
                {
                    "success": True,
                    "mensaje": f"Asignación de {candidato_nombre} eliminada correctamente",
                    "candidato_id": candidato.clave_academica,
                }
            )

        except Exception as e:
            db.session.rollback()
            import traceback

            traceback.print_exc()
            return jsonify({"error": f"Error al desasignar candidato: {str(e)}"}), 500

    @app.route("/admin/candidatos/reasignar-manual", methods=["POST"])
    @admin_required
    def reasignar_candidato_manual():
        """Reasigna un candidato a otra reserva"""

        try:
            data = request.json
            asignacion_id = data.get("asignacion_id")
            nueva_reserva_id = data.get("nueva_reserva_id")
            nueva_posicion = data.get("nueva_posicion")

            if not all([asignacion_id, nueva_reserva_id, nueva_posicion]):
                return jsonify({"error": "Faltan datos requeridos"}), 400

            # Buscar asignación actual
            asignacion = Asignacion.query.get(asignacion_id)
            if not asignacion:
                return jsonify({"error": "Asignación no encontrada"}), 404

            # Validar nueva reserva
            nueva_reserva = Reserva.query.get(nueva_reserva_id)
            if not nueva_reserva:
                return jsonify({"error": "Nueva reserva no encontrada"}), 404

            # Verificar espacios disponibles en nueva reserva
            asignaciones_nuevas = Asignacion.query.filter_by(
                reserva_id=nueva_reserva_id
            ).count()
            if asignaciones_nuevas >= 2:
                return (
                    jsonify({"error": "La nueva reserva ya tiene 2 asignaciones"}),
                    400,
                )

            # Verificar que la posición no esté ocupada
            posicion_ocupada = Asignacion.query.filter_by(
                reserva_id=nueva_reserva_id, posicion=nueva_posicion
            ).first()
            if posicion_ocupada:
                return (
                    jsonify(
                        {"error": f"La posición {nueva_posicion} ya está ocupada"}
                    ),
                    400,
                )

            # Actualizar asignación
            asignacion.reserva_id = nueva_reserva_id
            asignacion.entrevistador_id = nueva_reserva.usuario_id
            asignacion.posicion = nueva_posicion
            asignacion.minuto_inicio = 0 if nueva_posicion == 1 else 15
            asignacion.fecha_asignacion = datetime.now()
            asignacion.asignado_por_admin_id = session["user_id"]

            db.session.commit()

            return jsonify(
                {
                    "success": True,
                    "mensaje": f"Candidato reasignado correctamente",
                    "nueva_hora": (
                        asignacion.hora_exacta.strftime("%H:%M")
                        if asignacion.hora_exacta
                        else None
                    ),
                }
            )

        except Exception as e:
            db.session.rollback()
            import traceback

            traceback.print_exc()
            return jsonify({"error": f"Error al reasignar candidato: {str(e)}"}), 500

    @app.route("/admin/candidato/<clave_academica>/asignacion")
    @admin_required
    def ver_asignacion_candidato(clave_academica):
        """
        Detalle de la asignación (entrevista) de un candidato concreto:
        día, hora, profesor y sede/espacio. Usado por el botón "Ver
        asignación" de /admin/candidatos/semana/<semana>, que solo se
        ofrece para candidatos en estado 'asignado'.
        """
        candidato = Candidato.query.filter_by(
            clave_academica=clave_academica.strip()
        ).first()

        if not candidato or not candidato.asignacion:
            return jsonify({"error": "Este candidato no tiene ninguna asignación."}), 404

        asignacion = candidato.asignacion
        reserva = asignacion.reserva

        return jsonify(
            {
                "candidato": f"{candidato.nombre} {candidato.apellidos}",
                "fecha": reserva.fecha.strftime("%d/%m/%Y") if reserva else None,
                "dia_semana": reserva.fecha.strftime("%A") if reserva else None,
                "hora": (
                    asignacion.hora_exacta.strftime("%H:%M")
                    if asignacion.hora_exacta
                    else None
                ),
                "profesor": (
                    (reserva.usuario.nombre_completo or reserva.usuario.username)
                    if reserva and reserva.usuario
                    else None
                ),
                "sede": reserva.espacio.nombre if reserva and reserva.espacio else None,
                "posicion": asignacion.posicion,
                "reserva_id": reserva.id if reserva else None,
            }
        )

    @app.route("/admin/candidatos/info-reserva/<int:reserva_id>")
    @admin_required
    def info_reserva(reserva_id):
        """
        Obtiene información detallada de una reserva.

        BUG corregido: el bucle de más abajo leía `asig.candidato_id`, pero
        `Asignacion` no tiene ningún campo con ese nombre — su FK hacia
        Candidato se llama `candidato_clave` (verificado contra el
        modelo). Esto hacía que la ruta lanzara `AttributeError` en cuanto
        la reserva consultada tenía alguna asignación (el caso normal por
        el que tendría sentido pedir esta información) — solo "funcionaba"
        cuando `asignaciones` estaba vacío. Sigue siendo una ruta
        inalcanzable desde la UI (ningún `url_for` ni fetch() fijo la
        llama, confirmado por grep), pero ya no falla si en el futuro se
        enlaza desde algún sitio. La clave del JSON de salida se mantiene
        como "candidato_id" (no se renombra) para no romper a un futuro
        consumidor que ya esperase ese nombre de clave.
        """

        reserva = Reserva.query.get_or_404(reserva_id)
        asignaciones = Asignacion.query.filter_by(reserva_id=reserva_id).all()

        asignaciones_data = []
        for asig in asignaciones:
            asignaciones_data.append(
                {
                    "id": asig.id,
                    "candidato_id": asig.candidato_clave,
                    "candidato_nombre": f"{asig.candidato.nombre} {asig.candidato.apellidos}",
                    "candidato_nota": (
                        float(asig.candidato.media_estudios)
                        if asig.candidato.media_estudios
                        else None
                    ),
                    "posicion": asig.posicion,
                    "hora_exacta": (
                        asig.hora_exacta.strftime("%H:%M") if asig.hora_exacta else None
                    ),
                    "estado": asig.estado,
                }
            )

        return jsonify(
            {
                "reserva_id": reserva.id,
                "fecha": reserva.fecha.strftime("%d/%m/%Y"),
                "dia_semana": reserva.fecha.strftime("%A"),
                "hora_inicio": reserva.hora_inicio.strftime("%H:%M"),
                "hora_fin": reserva.hora_fin.strftime("%H:%M"),
                "entrevistador": reserva.usuario.username,
                "espacio": reserva.espacio.nombre if reserva.espacio else "N/A",
                "num_asignaciones": len(asignaciones),
                "espacios_libres": 2 - len(asignaciones),
                "asignaciones": asignaciones_data,
            }
        )

    @app.route("/admin/asignaciones/semana/<semana>/eliminar-todas", methods=["POST"])
    @admin_required
    def eliminar_asignaciones_semana(semana):
        """Elimina todas las asignaciones de una semana y resetea candidatos a pendiente"""

        try:
            # Obtener candidatos de la semana
            candidatos = Candidato.query.filter_by(semana_carga=semana).all()
            candidatos_claves = [c.clave_academica for c in candidatos]

            # Obtener asignaciones
            asignaciones = Asignacion.query.filter(
                Asignacion.candidato_clave.in_(candidatos_claves)
            ).all()
            num_asignaciones = len(asignaciones)

            if num_asignaciones == 0:
                return jsonify({"error": "No hay asignaciones en esta semana"}), 404

            # Eliminar asignaciones
            for asignacion in asignaciones:
                db.session.delete(asignacion)

            # Resetear estado de candidatos a pendiente
            for candidato in candidatos:
                if candidato.estado == "asignado":
                    candidato.estado = "pendiente"

            db.session.commit()

            # Registrar en logs
            registrar_log(
                accion="eliminar",
                entidad="asignaciones_semana",
                entidad_id=None,
                descripcion=f"Asignaciones eliminadas de semana {semana}: {num_asignaciones} asignaciones",
                datos_anteriores={"semana": semana, "asignaciones": num_asignaciones},
                nivel="warning",
            )

            return jsonify(
                {
                    "success": True,
                    "mensaje": f"Todas las asignaciones eliminadas correctamente",
                    "asignaciones_eliminadas": num_asignaciones,
                }
            )

        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Error al eliminar asignaciones: {str(e)}"}), 500

    @app.route("/admin/log-asignacion/<int:log_id>/eliminar", methods=["POST"])
    @admin_required
    def eliminar_log_asignacion(log_id):
        """Elimina un registro de log de asignación"""

        # BUG corregido: `get_or_404()` iba dentro del `try` de más abajo,
        # cuyo único `except` es un `Exception` genérico. Cuando log_id no
        # existe, get_or_404 lanza werkzeug.exceptions.NotFound (pensado
        # para que Flask lo convierta automáticamente en un 404 limpio),
        # pero el except genérico lo capturaba primero y lo envolvía en un
        # 500 con un mensaje confuso ("Error al eliminar log: 404 Not
        # Found: ..."). Sacando la búsqueda fuera del try, NotFound vuelve
        # a propagarse a Flask sin que nadie la intercepte, y se obtiene el
        # 404 limpio que la función ya pretendía dar.
        log = LogAsignacion.query.get_or_404(log_id)

        try:
            semana = log.semana_objetivo

            db.session.delete(log)
            db.session.commit()

            # Registrar en logs de auditoría
            registrar_log(
                accion="eliminar",
                entidad="log_asignacion",
                entidad_id=log_id,
                descripcion=f"Log de asignación eliminado: semana {semana}",
                nivel="info",
            )

            return jsonify({"success": True, "mensaje": "Log eliminado correctamente"})

        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Error al eliminar log: {str(e)}"}), 500