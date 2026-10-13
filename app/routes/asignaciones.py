"""
Gestión manual de asignaciones ya existentes: ver las asignaciones de una
semana, la vista de gestión manual (candidatos + reservas con ocupación),
asignar/desasignar/reasignar un candidato a mano, consultar el detalle de
una reserva, y los borrados de asignaciones (por semana completa o de un
log de asignación individual). La ejecución del algoritmo automático y el
CRUD de candidatos viven en routes/candidatos.py.
"""

from datetime import datetime, timedelta

from flask import jsonify, render_template, request, session

from app.extensions import db
from app.models import Asignacion, Candidato, LogAsignacion, Reserva, Usuario
from app.services.candidatos import obtener_estadisticas_semana_candidatos
from app.services.logs import registrar_log
from app.utils.decorators import admin_required


def register(app):
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

        # Obtener candidatos de la semana
        candidatos = (
            Candidato.query.filter_by(semana_carga=semana)
            .order_by(Candidato.media_estudios.asc())
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

        return render_template(
            "gestion_manual.html",
            candidatos=candidatos,
            reservas_info=reservas_info,
            semana=semana,
            semana_entrevistas=semana_entrevistas,
            stats=stats,
            entrevistadores=entrevistadores,
            lunes=siguiente_lunes,
            viernes=viernes,
            username=session["username"],
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

    @app.route("/admin/candidatos/info-reserva/<int:reserva_id>")
    @admin_required
    def info_reserva(reserva_id):
        """
        Obtiene información detallada de una reserva.

        BUG HEREDADO (no introducido en esta extracción): el bucle de más
        abajo lee `asig.candidato_id`, pero `Asignacion` no tiene ningún
        campo con ese nombre — su FK hacia Candidato se llama
        `candidato_clave` (verificado contra el modelo). Esto significa que
        esta ruta lanza `AttributeError` en cuanto la reserva consultada
        tiene alguna asignación (el caso normal por el que tendría sentido
        pedir esta información) — solo "funciona" cuando `asignaciones`
        está vacío. Comprobé también que ningún sitio de las plantillas
        llama a esta ruta (ni por `url_for`, ni como fetch() a una URL
        fija) — es inalcanzable desde la UI. Se preserva tal cual, sin
        arreglar.
        """

        reserva = Reserva.query.get_or_404(reserva_id)
        asignaciones = Asignacion.query.filter_by(reserva_id=reserva_id).all()

        asignaciones_data = []
        for asig in asignaciones:
            asignaciones_data.append(
                {
                    "id": asig.id,
                    "candidato_id": asig.candidato_id,
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

        try:
            log = LogAsignacion.query.get_or_404(log_id)

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