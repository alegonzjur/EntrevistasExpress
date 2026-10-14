"""
Pruebas del límite de reservas por franja (profesores que pueden
reservar el mismo día/hora). Antes era un máximo de 2, ahora es
MAX_RESERVAS_POR_FRANJA = 6 (app/constants.py). Estas pruebas no tocan
el límite, distinto, de candidatos por reserva (app/services/
asignacion.py), que sigue en 2 y no forma parte de este cambio.
"""

from datetime import date

from app.constants import MAX_RESERVAS_POR_FRANJA
from app.extensions import db
from app.models import Espacio, Usuario
from werkzeug.security import generate_password_hash


def _crear_espacio(app):
    with app.app_context():
        espacio = Espacio(nombre="Lunes", descripcion="d", color="#000")
        db.session.add(espacio)
        db.session.commit()
        return espacio.id


def _crear_usuario(app, username):
    with app.app_context():
        u = Usuario(
            username=username,
            email=f"{username}@example.com",
            password=generate_password_hash("x"),
            rol="profesor",
            activo=True,
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def test_max_reservas_por_franja_es_6():
    """Documenta el valor actual de la constante, para que un cambio
    futuro accidental de este número se note en los tests."""
    assert MAX_RESERVAS_POR_FRANJA == 6


def test_franja_permite_hasta_6_profesores_y_bloquea_el_septimo(app, admin_client):
    espacio_id = _crear_espacio(app)
    fecha = date.today().isoformat()
    hora_inicio = "10:00"
    hora_fin = "10:30"

    usuario_ids = [_crear_usuario(app, f"profe{i}") for i in range(7)]

    # Reservar para los primeros 6 usuarios distintos debe funcionar.
    for i in range(6):
        resp = admin_client.post(
            "/api/reservar",
            json={
                "espacio_id": espacio_id,
                "fecha": fecha,
                "hora_inicio": hora_inicio,
                "hora_fin": hora_fin,
                "usuario_id": usuario_ids[i],
            },
        )
        assert resp.status_code == 200, resp.get_json()

        franjas = admin_client.get(
            f"/api/franjas/{espacio_id}?fecha={fecha}"
        ).get_json()
        franja = next(f for f in franjas if f["hora_inicio"] == hora_inicio)
        assert franja["num_reservas"] == i + 1
        assert franja["max_reservas"] == 6

        if i + 1 < 6:
            assert franja["parcial"] is True
            assert franja["completa"] is False
            assert franja["puede_reservar"] is True
        else:
            assert franja["parcial"] is False
            assert franja["completa"] is True
            assert franja["puede_reservar"] is False

    # El 7º profesor distinto no puede reservar: la franja ya está completa.
    resp = admin_client.post(
        "/api/reservar",
        json={
            "espacio_id": espacio_id,
            "fecha": fecha,
            "hora_inicio": hora_inicio,
            "hora_fin": hora_fin,
            "usuario_id": usuario_ids[6],
        },
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "6" in data["error"]