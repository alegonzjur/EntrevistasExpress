"""
Smoke tests de la fábrica de la app: que create_app() ensambla las 9
rutas sin colisiones de endpoint ni imports circulares, con endpoints
planos (sin Blueprints).
"""

import os


def test_endpoints_son_planos_sin_puntos(app):
    """Ningún endpoint debería tener un punto salvo 'static' (eso
    indicaría que, por error, se ha usado flask.Blueprint en algún sitio,
    algo que se decidió activamente no hacer — ver app/__init__.py)."""
    endpoints = list(app.view_functions.keys())
    dotted = [e for e in endpoints if "." in e and e != "static"]
    assert dotted == []


def test_endpoints_clave_presentes(app):
    esperados = [
        "login", "logout", "index", "reservas", "registro",
        "admin_usuarios", "admin_candidatos", "admin_estadisticas",
        "ejecutar_asignacion", "ver_logs", "exportar_candidatos",
    ]
    endpoints = set(app.view_functions.keys())
    faltan = [e for e in esperados if e not in endpoints]
    assert faltan == []


def test_upload_folder_se_crea(app):
    assert os.path.isdir(app.config["UPLOAD_FOLDER"])


def test_plantillas_se_resuelven_desde_app_templates(app):
    """Flask(__name__) dentro del paquete `app` debe resolver
    app/templates y app/static por convención, sin pasar template_folder
    a mano (ver app/__init__.py)."""
    plantillas = set(app.jinja_loader.list_templates())
    assert "login.html" in plantillas
    assert "base.html" in plantillas
    assert "admin_estadisticas.html" in plantillas