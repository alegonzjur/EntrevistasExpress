"""
Páginas generales que no pertenecen a ningún área concreta: la raíz del
sitio (que solo redirige) y la guía de uso para profesores.

No se usa `flask.Blueprint` aquí a propósito: un Blueprint antepone
siempre su nombre al endpoint (p. ej. "main.login"), y las plantillas
Jinja (base.html y el resto) llaman a `url_for('login')`,
`url_for('reservas')`, etc. con el nombre PLANO, igual que
`utils/decorators.py`. Cambiar eso implica tocar todas las plantillas a
la vez, que es un paso posterior y separado. Por ahora, cada módulo de
`routes/` expone `register(app)` y registra sus vistas con `@app.route`
directamente sobre la app, conservando los mismos nombres de endpoint
que tenía el monolito.
"""

from flask import redirect, render_template, session, url_for

from app.utils.decorators import login_required


def register(app):
    @app.route("/")
    def index():
        if "user_id" in session:
            return redirect(url_for("reservas"))
        return redirect(url_for("login"))

    @app.route("/guia-uso")
    @login_required
    def guia_uso():
        """Página con guía de uso del sistema para profesores"""
        return render_template(
            "guia_uso.html", username=session["username"], rol=session["rol"]
        )