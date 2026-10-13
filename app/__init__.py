"""
Fábrica de la aplicación Flask.

Reemplaza al bloque `app = Flask(__name__); db = SQLAlchemy(app); ...` que
vivía suelto en la cabecera del app.py original. `create_app()` crea la
app, le aplica la configuración, vincula las extensiones compartidas
(db, mail — definidas en extensions.py sin la app, para evitar imports
circulares), se asegura de que exista la carpeta de subida de Excels, y
registra las 9 rutas (cada una con su propio `register(app)`, sin usar
`flask.Blueprint` — ver el docstring de app/routes/__init__.py o el
historial de la conversación para el porqué de esa decisión).
"""

import os

from flask import Flask

from app.config import Config
from app.extensions import db, mail


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Vincular extensiones a esta app concreta
    db.init_app(app)
    mail.init_app(app)

    # Crear la carpeta de subida de Excels si no existe (igual que hacía
    # el app.py original a nivel de módulo, al arrancar)
    if not os.path.exists(app.config["UPLOAD_FOLDER"]):
        os.makedirs(app.config["UPLOAD_FOLDER"])

    # Importar los modelos para que SQLAlchemy registre sus mappers antes
    # de que se use la app (ver el docstring de app/models/__init__.py)
    from app import models  # noqa: F401

    # Registrar las rutas. Cada módulo expone register(app), que llama a
    # @app.route(...) directamente sobre esta instancia — no son
    # Blueprints, así que los endpoints quedan planos (p. ej. "login",
    # no "auth.login"), igual que en el app.py original, sin tener que
    # tocar las plantillas todavía.
    from app.routes import (
        asignaciones,
        auth,
        candidatos,
        exportaciones,
        logs,
        main,
        perfil,
        reservas,
        usuarios,
    )

    main.register(app)
    auth.register(app)
    reservas.register(app)
    perfil.register(app)
    usuarios.register(app)
    candidatos.register(app)
    asignaciones.register(app)
    exportaciones.register(app)
    logs.register(app)

    return app