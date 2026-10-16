"""
Pruebas de las tres modificaciones pedidas en "Todas las Reservas"
(vista de administración):

1. Campo "Curso" (académico, 1 sep - 31 ago), calculado a partir de la
   fecha de la reserva, usado como columna y como filtro.
2. Orden: de lunes a viernes, y dentro de un mismo día por la franja
   horaria más temprana primero.
3. Se muestra el nombre completo del profesor en vez de su username.
"""

from datetime import date, time

from app.extensions import db
from app.models import Espacio, Reserva, Usuario
from app.utils.cursos import (
    obtener_curso_academico,
    obtener_cursos_disponibles,
    rango_fechas_curso,
)
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# app/utils/cursos.py
# ---------------------------------------------------------------------------

def test_obtener_curso_academico_en_septiembre_empieza_curso_nuevo():
    assert obtener_curso_academico(date(2026, 9, 1)) == "2026/2027"


def test_obtener_curso_academico_en_agosto_sigue_en_el_curso_anterior():
    assert obtener_curso_academico(date(2027, 8, 31)) == "2026/2027"


def test_obtener_curso_academico_dia_antes_de_septiembre():
    assert obtener_curso_academico(date(2026, 8, 31)) == "2025/2026"


def test_rango_fechas_curso():
    inicio, fin = rango_fechas_curso("2026/2027")
    assert inicio == date(2026, 9, 1)
    assert fin == date(2027, 8, 31)


def test_obtener_cursos_disponibles_mas_reciente_primero():
    fechas = [date(2025, 10, 1), date(2026, 10, 1), date(2024, 1, 1)]
    assert obtener_cursos_disponibles(fechas) == [
        "2026/2027",
        "2025/2026",
        "2023/2024",
    ]


# ---------------------------------------------------------------------------
# Reserva.curso
# ---------------------------------------------------------------------------

def test_reserva_curso_se_calcula_desde_la_fecha(app):
    with app.app_context():
        r = Reserva(
            usuario_id=1, espacio_id=1, fecha=date(2026, 10, 15),
            hora_inicio=time(10, 0), hora_fin=time(10, 30),
        )
        assert r.curso == "2026/2027"


# ---------------------------------------------------------------------------
# Integración: /admin/todas-reservas
# ---------------------------------------------------------------------------

def _crear_profesor(nombre_completo, username):
    profe = Usuario(
        username=username, nombre_completo=nombre_completo,
        email=f"{username}@example.com",
        password=generate_password_hash("x"), rol="profesor", activo=True,
    )
    db.session.add(profe)
    db.session.commit()
    return profe


def _crear_espacios():
    nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
    espacios = []
    for nombre in nombres:
        e = Espacio(nombre=nombre, descripcion="d", color="#000")
        db.session.add(e)
        espacios.append(e)
    db.session.commit()
    return espacios


def test_todas_reservas_ordena_lunes_a_viernes_y_por_hora(app, admin_client, admin_user):
    with app.app_context():
        profe = _crear_profesor("Ana Pérez García", "aperez")
        lunes, martes, miercoles, jueves, viernes = _crear_espacios()

        # Las creamos deliberadamente en un orden distinto al esperado.
        db.session.add_all(
            [
                Reserva(
                    usuario_id=profe.id, espacio_id=viernes.id,
                    fecha=date(2026, 10, 16), hora_inicio=time(11, 0),
                    hora_fin=time(11, 30),
                ),
                Reserva(
                    usuario_id=profe.id, espacio_id=lunes.id,
                    fecha=date(2026, 10, 12), hora_inicio=time(17, 0),
                    hora_fin=time(17, 30),
                ),
                Reserva(
                    usuario_id=profe.id, espacio_id=lunes.id,
                    fecha=date(2026, 10, 12), hora_inicio=time(10, 0),
                    hora_fin=time(10, 30),
                ),
                Reserva(
                    usuario_id=profe.id, espacio_id=martes.id,
                    fecha=date(2026, 10, 13), hora_inicio=time(9, 0),
                    hora_fin=time(9, 30),
                ),
            ]
        )
        db.session.commit()

    resp = admin_client.get("/admin/todas-reservas")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")

    # El orden esperado en el HTML: Lunes 10:00, Lunes 17:00, Martes 9:00,
    # Viernes 11:00 — lunes a viernes, y dentro del lunes, la hora más
    # temprana primero.
    pos_lunes_10 = body.index("10:00 - 10:30")
    pos_lunes_17 = body.index("17:00 - 17:30")
    pos_martes_9 = body.index("09:00 - 09:30")
    pos_viernes_11 = body.index("11:00 - 11:30")

    assert pos_lunes_10 < pos_lunes_17 < pos_martes_9 < pos_viernes_11


def test_todas_reservas_muestra_nombre_completo_no_username(app, admin_client, admin_user):
    with app.app_context():
        profe = _crear_profesor("Ana Pérez García", "aperez")
        lunes = _crear_espacios()[0]

        db.session.add(
            Reserva(
                usuario_id=profe.id, espacio_id=lunes.id,
                fecha=date(2026, 10, 12), hora_inicio=time(10, 0),
                hora_fin=time(10, 30),
            )
        )
        db.session.commit()

    resp = admin_client.get("/admin/todas-reservas")
    body = resp.data.decode("utf-8")
    assert "Ana Pérez García" in body
    # El username no debe aparecer como etiqueta visible del profesor en
    # la tabla ni en el selector de filtro.
    assert ">aperez<" not in body


def test_todas_reservas_muestra_columna_y_filtro_de_curso(app, admin_client, admin_user):
    with app.app_context():
        profe = _crear_profesor("Ana Pérez García", "aperez")
        lunes = _crear_espacios()[0]

        db.session.add(
            Reserva(
                usuario_id=profe.id, espacio_id=lunes.id,
                fecha=date(2026, 10, 12), hora_inicio=time(10, 0),
                hora_fin=time(10, 30),
            )
        )
        db.session.commit()

    resp = admin_client.get("/admin/todas-reservas")
    body = resp.data.decode("utf-8")
    assert "2026/2027" in body  # columna Curso + opción del selector
    assert 'name="curso"' in body


def test_todas_reservas_filtra_por_curso(app, admin_client, admin_user):
    with app.app_context():
        profe = _crear_profesor("Ana Pérez García", "aperez")
        lunes = _crear_espacios()[0]

        db.session.add_all(
            [
                Reserva(  # curso 2025/2026
                    usuario_id=profe.id, espacio_id=lunes.id,
                    fecha=date(2026, 3, 1), hora_inicio=time(10, 0),
                    hora_fin=time(10, 30),
                ),
                Reserva(  # curso 2026/2027
                    usuario_id=profe.id, espacio_id=lunes.id,
                    fecha=date(2026, 10, 12), hora_inicio=time(11, 0),
                    hora_fin=time(11, 30),
                ),
            ]
        )
        db.session.commit()

    resp = admin_client.get("/admin/todas-reservas?curso=2025/2026")
    body = resp.data.decode("utf-8")
    assert "10:00 - 10:30" in body
    assert "11:00 - 11:30" not in body