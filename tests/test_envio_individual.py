"""
Pruebas del envío individual de emails (GET + POST
/admin/candidatos/envio-individual/<semana>), pensado para no tener que
reenviar a toda la semana cada vez que se gestiona manualmente una sola
entrevista:

- Candidatos ofrecidos: cargados Y asignados (tienen Asignacion) con el
  email todavía SIN enviar.
- Profesores ofrecidos: todos los que tengan alguna asignación esta
  semana, se les haya enviado ya su resumen o no.
- El envío en sí solo toca a quien se seleccionó, no a toda la semana.
"""

from datetime import date, time

from app.extensions import db
from app.models import Asignacion, Candidato, Espacio, Reserva, Usuario
from werkzeug.security import generate_password_hash


def _crear_candidato(clave, email="candidato@example.com", semana="2026-W43"):
    c = Candidato(
        clave_academica=clave, solicitud=1, nombre="Ana", apellidos=f"Pérez {clave}",
        email=email, semana_carga=semana, primera_opcion="Bormujos",
        media_estudios=8.5,
    )
    db.session.add(c)
    db.session.commit()
    return c


def _crear_profesor(username, email):
    profe = Usuario(
        username=username, nombre_completo=f"Profesor {username}", email=email,
        password=generate_password_hash("x"), rol="profesor", activo=True,
    )
    db.session.add(profe)
    db.session.commit()
    return profe


def _crear_reserva(usuario_id, espacio=None):
    if espacio is None:
        espacio = Espacio(nombre="Lunes", descripcion="d", color="#000")
        db.session.add(espacio)
        db.session.commit()
    reserva = Reserva(
        usuario_id=usuario_id, espacio_id=espacio.id, fecha=date(2026, 10, 19),
        hora_inicio=time(9, 0), hora_fin=time(10, 0),
    )
    db.session.add(reserva)
    db.session.commit()
    return reserva, espacio


def _crear_asignacion(candidato, entrevistador_id, reserva, posicion=1):
    asign = Asignacion(
        candidato_clave=candidato.clave_academica, reserva_id=reserva.id,
        entrevistador_id=entrevistador_id, posicion=posicion, minuto_inicio=0,
    )
    db.session.add(asign)
    db.session.commit()
    return asign


# ---------------------------------------------------------------------------
# GET — quién se puede elegir
# ---------------------------------------------------------------------------

def test_get_solo_ofrece_candidatos_con_email_pendiente(app, admin_client, admin_user):
    with app.app_context():
        c1 = _crear_candidato("C001")
        c2 = _crear_candidato("C002")
        profe = _crear_profesor("profe1", "profe1@example.com")
        reserva, _ = _crear_reserva(admin_user)

        a1 = _crear_asignacion(c1, profe.id, reserva, posicion=1)
        a2 = _crear_asignacion(c2, profe.id, reserva, posicion=2)
        # C002 ya tiene el email enviado -> no debe ofrecerse.
        a2.enviado_email = True
        db.session.commit()
        a1_id = a1.id

    resp = admin_client.get("/admin/candidatos/envio-individual/2026-W43")
    assert resp.status_code == 200
    data = resp.get_json()

    claves = [c["clave_academica"] for c in data["candidatos"]]
    assert "C001" in claves
    assert "C002" not in claves
    assert data["candidatos"][0]["asignacion_id"] == a1_id


def test_get_candidato_no_asignado_no_se_ofrece(app, admin_client, admin_user):
    """Un candidato cargado pero sin Asignacion (todavía no asignado a
    ninguna entrevista) no tiene a quién mandarle el email de
    confirmación, así que no debe aparecer en la lista."""
    with app.app_context():
        _crear_candidato("C003")  # cargado, pero sin Asignacion

    resp = admin_client.get("/admin/candidatos/envio-individual/2026-W43")
    data = resp.get_json()
    assert data["candidatos"] == []


def test_get_ofrece_profesores_aunque_ya_se_les_enviara(app, admin_client, admin_user):
    with app.app_context():
        c1 = _crear_candidato("C001")
        profe = _crear_profesor("profe1", "profe1@example.com")
        reserva, _ = _crear_reserva(admin_user)
        # El email del propio candidato sí se envió, pero el profesor
        # debe seguir ofreciéndose igualmente.
        a1 = _crear_asignacion(c1, profe.id, reserva, posicion=1)
        a1.enviado_email = True
        db.session.commit()

    resp = admin_client.get("/admin/candidatos/envio-individual/2026-W43")
    data = resp.get_json()
    nombres_profesores = [p["nombre"] for p in data["profesores"]]
    assert "Profesor profe1" in nombres_profesores
    assert data["profesores"][0]["num_asignaciones"] == 1


# ---------------------------------------------------------------------------
# POST — el envío en sí
# ---------------------------------------------------------------------------

def test_post_envia_solo_al_candidato_seleccionado(app, admin_client, admin_user):
    """Con dos candidatos pendientes, seleccionar solo uno no debe tocar
    el enviado_email del otro."""
    with app.app_context():
        c1 = _crear_candidato("C001")
        c2 = _crear_candidato("C002")
        profe = _crear_profesor("profe1", "profe1@example.com")
        reserva, _ = _crear_reserva(admin_user)
        a1 = _crear_asignacion(c1, profe.id, reserva, posicion=1)
        a2 = _crear_asignacion(c2, profe.id, reserva, posicion=2)
        a1_id, a2_id = a1.id, a2.id

    resp = admin_client.post(
        "/admin/candidatos/envio-individual/2026-W43",
        json={"asignaciones": [a1_id], "profesores": []},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["candidatos_enviados"] == 1

    with app.app_context():
        a1 = db.session.get(Asignacion, a1_id)
        a2 = db.session.get(Asignacion, a2_id)
        assert a1.enviado_email is True
        assert a1.fecha_email is not None
        assert a2.enviado_email is not True  # no tocado


def test_post_envia_resumen_a_profesor_seleccionado(app, admin_client, admin_user):
    with app.app_context():
        c1 = _crear_candidato("C001")
        profe = _crear_profesor("profe1", "profe1@example.com")
        reserva, _ = _crear_reserva(admin_user)
        _crear_asignacion(c1, profe.id, reserva, posicion=1)
        profe_id = profe.id

    resp = admin_client.post(
        "/admin/candidatos/envio-individual/2026-W43",
        json={"asignaciones": [], "profesores": [profe_id]},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["entrevistadores_enviados"] == 1
    assert data["entrevistadores_error"] == 0


def test_post_sin_seleccion_devuelve_error(app, admin_client, admin_user):
    resp = admin_client.post(
        "/admin/candidatos/envio-individual/2026-W43",
        json={"asignaciones": [], "profesores": []},
    )
    assert resp.status_code == 400


def test_post_candidato_de_otra_semana_no_se_envia(app, admin_client, admin_user):
    """Una Asignacion de otra semana_carga no debe poder colarse por id
    aunque se pida para la semana equivocada."""
    with app.app_context():
        c1 = _crear_candidato("C001", semana="2026-W40")  # otra semana
        profe = _crear_profesor("profe1", "profe1@example.com")
        reserva, _ = _crear_reserva(admin_user)
        a1 = _crear_asignacion(c1, profe.id, reserva, posicion=1)
        a1_id = a1.id

    resp = admin_client.post(
        "/admin/candidatos/envio-individual/2026-W43",
        json={"asignaciones": [a1_id], "profesores": []},
    )
    data = resp.get_json()
    assert data["candidatos_enviados"] == 0
    assert data["candidatos_error"] == 1

    with app.app_context():
        a1 = db.session.get(Asignacion, a1_id)
        assert a1.enviado_email is not True