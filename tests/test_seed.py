"""
app/seed.py — la siembra inicial (admin + 5 Espacios) extraída del
bloque __main__ de app.py y de serve.py, que estaban duplicados.
"""

from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import Espacio, Usuario
from app.seed import inicializar_datos


def test_inicializar_datos_crea_admin_y_espacios(app):
    with app.app_context():
        inicializar_datos(app)

        admin = Usuario.query.filter_by(username="admin").first()
        assert admin is not None
        assert admin.rol == "admin"
        assert admin.email == "admin@ejemplo.com"
        # Fidelidad con el original: no se pone nombre_completo al crear
        # el admin (se queda en su default, None).
        assert admin.nombre_completo is None
        assert check_password_hash(admin.password, "admin123")

        espacios = Espacio.query.order_by(Espacio.id).all()
        assert [e.nombre for e in espacios] == [
            "Lunes", "Martes", "Miércoles", "Jueves", "Viernes",
        ]
        assert espacios[0].color == "#667eea"
        assert espacios[-1].color == "#43e97b"


def test_inicializar_datos_es_idempotente(app):
    """Una segunda llamada (p. ej. tras reiniciar el servidor) no debe
    duplicar ni el admin ni los Espacios."""
    with app.app_context():
        inicializar_datos(app)
        inicializar_datos(app)

        assert Usuario.query.filter_by(username="admin").count() == 1
        assert Espacio.query.count() == 5