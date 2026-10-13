"""
Datos iniciales (seed) de la aplicación.

Extrae a una sola función la lógica que, en el proyecto original, estaba
duplicada literalmente en dos sitios: el bloque `if __name__ == "__main__":`
de app.py (líneas ~5518-5594) y la función `inicializar_datos()` de
serve.py. En ambos sitios se creaba exactamente el mismo usuario admin y
los mismos 5 Espacios (días de la semana con sus colores) si no existían
ya — la única diferencia entre las dos copias era que la de serve.py
envolvía el bloque en un try/except con sys.exit(1) y mensajes de
diagnóstico.

Esa parte de manejo de errores (específica de "qué hacer si falla al
arrancar un servidor") se queda en run.py, que es quien decide cómo
reaccionar; aquí solo vive la lógica de datos en sí, para que sea
reutilizable (p. ej. desde tests) sin arrastrar sys.exit().
"""

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Espacio, Usuario

DIAS_SEMANA = [
    {"nombre": "Lunes", "descripcion": "Primer día de la semana", "color": "#667eea"},
    {"nombre": "Martes", "descripcion": "Segundo día de la semana", "color": "#764ba2"},
    {"nombre": "Miércoles", "descripcion": "Tercer día de la semana", "color": "#f093fb"},
    {"nombre": "Jueves", "descripcion": "Cuarto día de la semana", "color": "#4facfe"},
    {"nombre": "Viernes", "descripcion": "Quinto día de la semana", "color": "#43e97b"},
]


def inicializar_datos(app):
    """
    Crea las tablas si no existen, y siembra el usuario admin y los 5
    Espacios (días de la semana) si la base de datos está vacía.

    Debe llamarse dentro de un contexto de aplicación activo, o se le pasa
    la app y lo abre ella misma (igual que hacían los dos originales, que
    llamaban a esto dentro de `with app.app_context():`).

    Nota de fidelidad: ni app.py ni serve.py ponían `nombre_completo` ni
    `activo` al crear el admin (aunque el modelo Usuario sí tiene esos
    campos, con default `activo=True`), así que aquí tampoco se ponen —
    se preserva el comportamiento original, no el que "debería" tener.
    """
    with app.app_context():
        db.create_all()
        print("✅ Tablas de base de datos verificadas")

        admin = Usuario.query.filter_by(username="admin").first()
        if not admin:
            admin = Usuario(
                username="admin",
                email="admin@ejemplo.com",
                password=generate_password_hash("admin123"),
                rol="admin",
            )
            db.session.add(admin)
            print("✅ Usuario administrador creado: admin / admin123")
            print("   ⚠️  IMPORTANTE: cambia esta contraseña después del primer login")
        else:
            print("ℹ️  Usuario administrador ya existe")

        if Espacio.query.count() == 0:
            for dia in DIAS_SEMANA:
                db.session.add(Espacio(**dia))
            print("✅ Días de la semana creados correctamente")
        else:
            print("ℹ️  Espacios (días) ya existen")

        db.session.commit()