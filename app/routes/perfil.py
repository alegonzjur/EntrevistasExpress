"""
Área de perfil del usuario logueado: su enlace personal de videollamada,
la página de perfil con sus estadísticas, y el cambio de contraseña.
"""

from datetime import date

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import Asignacion, Reserva, Usuario
from app.services.logs import registrar_log
from app.utils.decorators import login_required


def register(app):
    @app.route("/api/actualizar-enlace-personal", methods=["POST"])
    @login_required
    def actualizar_enlace_personal():
        """Actualiza el enlace personal de videollamada del usuario"""

        try:
            data = request.json
            enlace = data.get("enlace", "").strip()

            # Obtener usuario actual
            usuario = Usuario.query.get(session["user_id"])
            if not usuario:
                return jsonify({"error": "Usuario no encontrado"}), 404

            # Validar formato de URL
            if enlace and not (
                enlace.startswith("http://") or enlace.startswith("https://")
            ):
                enlace = "https://" + enlace

            # Actualizar enlace
            usuario.enlace_videollamada_personal = enlace if enlace else None
            db.session.commit()

            return jsonify(
                {
                    "success": True,
                    "mensaje": "Enlace personal actualizado correctamente",
                    "enlace": usuario.enlace_videollamada_personal,
                }
            )

        except Exception as e:
            db.session.rollback()
            import traceback

            traceback.print_exc()
            return jsonify({"error": f"Error al actualizar enlace: {str(e)}"}), 500

    @app.route("/perfil")
    @login_required
    def mi_perfil():
        """Vista del perfil del usuario"""

        usuario = Usuario.query.get(session["user_id"])

        if not usuario:
            flash("Usuario no encontrado", "error")
            return redirect(url_for("login"))

        # Total de reservas del usuario
        total_reservas = Reserva.query.filter_by(usuario_id=usuario.id).count()

        # Reservas futuras (fecha >= hoy)
        hoy = date.today()
        reservas_futuras = Reserva.query.filter(
            Reserva.usuario_id == usuario.id, Reserva.fecha >= hoy
        ).count()

        # Entrevistas realizadas (asignaciones donde el usuario es entrevistador)
        entrevistas_realizadas = Asignacion.query.filter_by(
            entrevistador_id=usuario.id
        ).count()

        stats = {
            "total_reservas": total_reservas,
            "reservas_futuras": reservas_futuras,
            "entrevistas_realizadas": entrevistas_realizadas,
        }

        return render_template(
            "perfil.html",
            usuario=usuario,
            username=usuario.username,
            email=usuario.email,
            rol=usuario.rol,
            fecha_creacion=usuario.fecha_creacion,
            enlace_videollamada=usuario.enlace_videollamada_personal,
            sede=usuario.sede,
            stats=stats,
        )

    @app.route("/api/cambiar-contrasena", methods=["POST"])
    @login_required
    def cambiar_contrasena():
        """Permite al usuario cambiar su contraseña"""

        try:
            data = request.json
            contrasena_actual = data.get("contrasena_actual", "")
            contrasena_nueva = data.get("contrasena_nueva", "")
            contrasena_confirmacion = data.get("contrasena_confirmacion", "")

            # Validaciones
            if not all([contrasena_actual, contrasena_nueva, contrasena_confirmacion]):
                return jsonify({"error": "Todos los campos son obligatorios"}), 400

            if contrasena_nueva != contrasena_confirmacion:
                return jsonify({"error": "Las contraseñas nuevas no coinciden"}), 400

            if len(contrasena_nueva) < 6:
                return (
                    jsonify({"error": "La contraseña debe tener al menos 6 caracteres"}),
                    400,
                )

            # Obtener usuario actual
            usuario = Usuario.query.get(session["user_id"])

            if not usuario:
                return jsonify({"error": "Usuario no encontrado"}), 404

            # Verificar contraseña actual
            if not check_password_hash(usuario.password, contrasena_actual):
                registrar_log(
                    accion="cambiar_contrasena",
                    entidad="usuario",
                    entidad_id=usuario.id,
                    descripcion="Intento fallido de cambio de contraseña: contraseña actual incorrecta",
                    nivel="warning",
                )
                return jsonify({"error": "La contraseña actual es incorrecta"}), 403

            # Cambiar contraseña
            usuario.password = generate_password_hash(contrasena_nueva)
            db.session.commit()

            registrar_log(
                accion="cambiar_contrasena",
                entidad="usuario",
                entidad_id=usuario.id,
                descripcion=f"Contraseña cambiada exitosamente para {usuario.username}",
                nivel="info",
            )

            return jsonify(
                {"success": True, "mensaje": "Contraseña cambiada correctamente"}
            )

        except Exception as e:
            db.session.rollback()

            registrar_log(
                accion="cambiar_contrasena",
                entidad="usuario",
                entidad_id=session.get("user_id"),
                descripcion=f"Error al cambiar contraseña: {str(e)}",
                nivel="error",
            )

            return jsonify({"error": f"Error al cambiar la contraseña: {str(e)}"}), 500