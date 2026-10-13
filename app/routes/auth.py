"""
Autenticación: entrar y salir de la sesión. La creación de cuentas
(/registro) no está aquí porque es una operación de administración de
usuarios, no de autenticación — vive en routes/usuarios.py.
"""

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from app.models import Usuario
from app.services.logs import registrar_log


def register(app):
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if "user_id" in session:
            return redirect(url_for("reservas"))

        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]

            usuario = Usuario.query.filter_by(username=username).first()

            if (
                usuario
                and usuario.activo
                and check_password_hash(usuario.password, password)
            ):
                session["user_id"] = usuario.id
                session["username"] = usuario.username
                session["rol"] = usuario.rol
                registrar_log(
                    accion="login",
                    entidad="usuario",
                    entidad_id=usuario.id,
                    descripcion=f"Usuario {usuario.username} inició sesión",
                    nivel="info",
                )

                flash(f"¡Bienvenido, {usuario.username}!", "success")
                return redirect(url_for("reservas"))
            else:
                registrar_log(
                    accion="login_fallido",
                    entidad="usuario",
                    entidad_id=None,
                    descripcion=f"Intento de login fallido para usuario: {username}",
                    nivel="warning",
                )
                if usuario and not usuario.activo:
                    error = "Tu cuenta ha sido desactivada. Contacta con el administrador."
                else:
                    error = "Usuario o contraseña incorrectos"
                return render_template("login.html", error=error)

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        """Cerrar sesión del usuario"""

        # Registrar en logs antes de limpiar la sesión
        if "user_id" in session:
            registrar_log(
                accion="logout",
                entidad="usuario",
                entidad_id=session.get("user_id"),
                descripcion=f'Usuario cerró sesión: {session.get("username")}',
                nivel="info",
            )

        # Limpiar sesión
        session.clear()

        flash("Sesión cerrada correctamente", "success")
        return redirect(url_for("login"))