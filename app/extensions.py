"""
Instancias compartidas de las extensiones de Flask.

Se crean SIN vincularlas a una app concreta (sin pasar `app` al constructor).
Se vinculan más adelante, dentro de `create_app()` (en app/__init__.py), con
`db.init_app(app)` / `mail.init_app(app)`.

Por qué: así cualquier módulo (modelos, rutas, servicios) puede hacer
`from app.extensions import db` sin depender de que la app ya exista, y
evitamos los imports circulares típicos de tener `app = Flask(__name__)` y
`db = SQLAlchemy(app)` en el mismo módulo que luego todo el mundo importa.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail

db = SQLAlchemy()
mail = Mail()