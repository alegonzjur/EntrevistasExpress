"""
Pruebas de los dos últimos cambios pedidos:

1. /admin/estadisticas deja de ser un "Top 10" de competición: lista a
   todos los profesores con reservas (de mayor a menor), y se puede
   acotar a una sede concreta.
2. /admin/todas-reservas gana un filtro más, por sede.

Ambos filtros de sede reutilizan Usuario.puede_atender_sede(), la misma
lógica que ya usa el algoritmo de asignación — no hay columna "sede" en
Reserva, así que se filtra por la sede que puede atender el profesor
que hizo la reserva.
"""

from datetime import date, time

from app.extensions import db
from app.models import Espacio, Reserva, Sede, Usuario
from werkzeug.security import generate_password_hash


def _crear_profesor(username, nombre_completo, sede=None, sedes=None):
    profe = Usuario(
        username=username, nombre_completo=nombre_completo,
        email=f"{username}@example.com",
        password=generate_password_hash("x"), rol="profesor", activo=True,
        sede=sede,
    )
    if sedes:
        profe.sedes = sedes
    db.session.add(profe)
    db.session.commit()
    return profe


def _crear_espacio(nombre="Lunes"):
    e = Espacio(nombre=nombre, descripcion="d", color="#000")
    db.session.add(e)
    db.session.commit()
    return e


# ---------------------------------------------------------------------------
# /admin/estadisticas
# ---------------------------------------------------------------------------

def test_estadisticas_lista_mas_de_10_profesores_de_mayor_a_menor(
    app, admin_client, admin_user
):
    """Ya no hay límite de Top 10: con 12 profesores con reservas, deben
    aparecer los 12, ordenados de más a menos reservas."""
    with app.app_context():
        espacio = _crear_espacio()
        totales_esperados = []
        for i in range(12):
            profe = _crear_profesor(f"profe{i}", f"Profesor {i}", sede="Bormujos")
            num_reservas = 12 - i  # cada profesor siguiente tiene menos
            for j in range(num_reservas):
                db.session.add(Reserva(
                    usuario_id=profe.id, espacio_id=espacio.id,
                    fecha=date(2026, 10, 12 + j), hora_inicio=time(10, 0),
                    hora_fin=time(10, 30),
                ))
            totales_esperados.append(f"Profesor {i}")
        db.session.commit()

    resp = admin_client.get("/admin/estadisticas")
    body = resp.data.decode("utf-8")
    assert resp.status_code == 200
    # Los 12 profesores deben aparecer (antes el Top 10 recortaba a 10).
    for nombre in totales_esperados:
        assert nombre in body
    # Y en orden: "Profesor 0" (12 reservas) debe aparecer antes que
    # "Profesor 11" (1 reserva).
    assert body.index("Profesor 0") < body.index("Profesor 11")


def test_estadisticas_filtra_por_sede(app, admin_client, admin_user):
    with app.app_context():
        espacio = _crear_espacio()
        sede_bormujos = Sede(nombre="Bormujos", activa=True)
        sede_ciempozuelos = Sede(nombre="Ciempozuelos", activa=True)
        db.session.add_all([sede_bormujos, sede_ciempozuelos])
        db.session.commit()

        profe_bormujos = _crear_profesor(
            "profeb", "Profesor de Bormujos", sede="Bormujos"
        )
        profe_ciempozuelos = _crear_profesor(
            "profec", "Profesor de Ciempozuelos", sede="Ciempozuelos"
        )
        for profe in (profe_bormujos, profe_ciempozuelos):
            db.session.add(Reserva(
                usuario_id=profe.id, espacio_id=espacio.id,
                fecha=date(2026, 10, 12), hora_inicio=time(10, 0),
                hora_fin=time(10, 30),
            ))
        db.session.commit()

    resp = admin_client.get("/admin/estadisticas?sede=Bormujos")
    body = resp.data.decode("utf-8")
    assert "Profesor de Bormujos" in body
    assert "Profesor de Ciempozuelos" not in body


# ---------------------------------------------------------------------------
# /admin/todas-reservas — filtro de sede
# ---------------------------------------------------------------------------

def test_todas_reservas_filtra_por_sede(app, admin_client, admin_user):
    with app.app_context():
        espacio = _crear_espacio()
        db.session.add_all(
            [Sede(nombre="Bormujos", activa=True), Sede(nombre="Ciempozuelos", activa=True)]
        )
        db.session.commit()

        profe_bormujos = _crear_profesor(
            "profeb", "Profesor de Bormujos", sede="Bormujos"
        )
        profe_ciempozuelos = _crear_profesor(
            "profec", "Profesor de Ciempozuelos", sede="Ciempozuelos"
        )
        db.session.add_all(
            [
                Reserva(
                    usuario_id=profe_bormujos.id, espacio_id=espacio.id,
                    fecha=date(2026, 10, 12), hora_inicio=time(10, 0),
                    hora_fin=time(10, 30),
                ),
                Reserva(
                    usuario_id=profe_ciempozuelos.id, espacio_id=espacio.id,
                    fecha=date(2026, 10, 12), hora_inicio=time(11, 0),
                    hora_fin=time(11, 30),
                ),
            ]
        )
        db.session.commit()

    resp = admin_client.get("/admin/todas-reservas?sede=Bormujos")
    body = resp.data.decode("utf-8")
    assert "10:00 - 10:30" in body
    assert "11:00 - 11:30" not in body


def test_todas_reservas_muestra_selector_de_sede(app, admin_client, admin_user):
    with app.app_context():
        db.session.add(Sede(nombre="Bormujos", activa=True))
        db.session.commit()

    resp = admin_client.get("/admin/todas-reservas")
    body = resp.data.decode("utf-8")
    assert 'name="sede"' in body
    assert "Bormujos" in body