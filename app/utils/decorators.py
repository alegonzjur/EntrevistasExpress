"""
Decoradores de control de acceso para las rutas.

Van en "utils" (no en "services") porque no son lógica de negocio: son
infraestructura de la capa web (leen la sesión de Flask y redirigen),
reutilizada por prácticamente todas las rutas protegidas.
"""

from functools import wraps

from flask import flash, redirect, session, url_for

from app.models import Usuario


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión para acceder a esta página", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión para acceder a esta página", "error")
            return redirect(url_for("login"))

        usuario = Usuario.query.get(session["user_id"])
        if not usuario or usuario.rol != "admin":
            flash("No tienes permisos para acceder a esta página", "error")
            return redirect(url_for("reservas"))
        return f(*args, **kwargs)

    return decorated_function