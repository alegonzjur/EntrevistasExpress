"""
Pruebas de regresión para los bugs heredados del app.py original que se
han corregido durante la reconstrucción. Cada test documenta, en su
docstring, cuál era el comportamiento roto antes del arreglo.
"""

from datetime import date, time

from app.extensions import db
from app.models import Asignacion, CargaExcel, Candidato, Espacio, LogAsignacion, Reserva


def _crear_candidato(clave="C001"):
    c = Candidato(
        clave_academica=clave, solicitud=1, nombre="Ana", apellidos="Pérez",
        email="ana@example.com", semana_carga="2024-W46",
        primera_opcion="Bormujos", media_estudios=8.5,
    )
    db.session.add(c)
    db.session.commit()
    return c


def _crear_reserva(admin_id):
    espacio = Espacio(nombre="Lunes", descripcion="d", color="#000")
    db.session.add(espacio)
    db.session.commit()
    reserva = Reserva(
        usuario_id=admin_id, espacio_id=espacio.id, fecha=date.today(),
        hora_inicio=time(9, 0), hora_fin=time(10, 0),
    )
    db.session.add(reserva)
    db.session.commit()
    return reserva


def test_enviar_emails_persiste_fecha_email(app, admin_client, admin_user):
    """BUG corregido en app/routes/exportaciones.py::enviar_emails_semana:
    se escribía `asignacion.fecha_envio_email`, un atributo que no existe
    en el modelo (el campo real es `fecha_email`). SQLAlchemy permite
    asignar atributos arbitrarios a una instancia sin fallar, así que el
    valor se perdía en silencio y `fecha_email` se quedaba NULL para
    siempre."""
    with app.app_context():
        _crear_candidato("C001")
        reserva = _crear_reserva(admin_user)
        asign = Asignacion(
            candidato_clave="C001", reserva_id=reserva.id,
            entrevistador_id=admin_user, posicion=1, minuto_inicio=0,
        )
        db.session.add(asign)
        db.session.commit()
        asign_id = asign.id

    resp = admin_client.post(
        "/admin/candidatos/enviar-emails/2024-W46", json={"tipo": "candidatos"}
    )
    assert resp.status_code == 200

    with app.app_context():
        asign = db.session.get(Asignacion, asign_id)
        assert asign.enviado_email is True
        assert asign.fecha_email is not None


def test_eliminar_log_asignacion_404_limpio(app, admin_client):
    """BUG corregido en app/routes/asignaciones.py::eliminar_log_asignacion:
    get_or_404() estaba dentro de un except Exception genérico, así que
    un id inexistente daba un 500 con mensaje de doble envoltura en vez
    de un 404 limpio."""
    resp = admin_client.post("/admin/log-asignacion/99999/eliminar")
    assert resp.status_code == 404


def test_eliminar_log_asignacion_id_real_sigue_funcionando(app, admin_client, admin_user):
    with app.app_context():
        log = LogAsignacion(
            semana_objetivo="2024-W46", ejecutado_por_usuario_id=admin_user,
            candidatos_procesados=0, candidatos_filtrados=0,
            candidatos_asignados=0, candidatos_sin_asignar=0,
            franjas_utilizadas=0, estado="completado",
        )
        db.session.add(log)
        db.session.commit()
        log_id = log.id

    resp = admin_client.post(f"/admin/log-asignacion/{log_id}/eliminar")
    assert resp.status_code == 200


def test_eliminar_carga_404_limpio(admin_client):
    """Mismo patrón que eliminar_log_asignacion, en
    app/routes/logs.py::eliminar_carga."""
    resp = admin_client.post("/admin/cargas/eliminar/99999")
    assert resp.status_code == 404


def test_eliminar_carga_id_real_sigue_funcionando(app, admin_client, admin_user):
    with app.app_context():
        carga = CargaExcel(
            archivo_nombre="test.xlsx", semana_destino="2024-W46",
            cargado_por_usuario_id=admin_user,
            candidatos_totales=0, candidatos_importados=0,
        )
        db.session.add(carga)
        db.session.commit()
        carga_id = carga.id

    resp = admin_client.post(f"/admin/cargas/eliminar/{carga_id}")
    assert resp.status_code == 200


def test_eliminar_candidato_acepta_clave_string(app, admin_client):
    """BUG corregido en app/routes/candidatos.py::eliminar_candidato: la
    ruta declaraba <int:candidato_id>, pero la PK real de Candidato
    (clave_academica) es un string — nunca podía encontrar un candidato
    real. Se cambia el convertidor de ruta a texto plano."""
    with app.app_context():
        _crear_candidato("C001")

    resp = admin_client.post("/admin/candidato/C001/eliminar")
    assert resp.status_code == 200

    with app.app_context():
        assert db.session.get(Candidato, "C001") is None


def test_eliminar_candidato_404_limpio(admin_client):
    resp = admin_client.post("/admin/candidato/NOEXISTE/eliminar")
    assert resp.status_code == 404


def test_info_reserva_con_asignaciones_reales(app, admin_client, admin_user):
    """BUG corregido en app/routes/asignaciones.py::info_reserva: el
    bucle leía `asig.candidato_id`, atributo inexistente (el campo real
    es `candidato_clave`) — lanzaba AttributeError en cuanto la reserva
    tenía alguna asignación, que es el caso normal."""
    with app.app_context():
        _crear_candidato("C002")
        reserva = _crear_reserva(admin_user)
        asign = Asignacion(
            candidato_clave="C002", reserva_id=reserva.id,
            entrevistador_id=admin_user, posicion=1, minuto_inicio=0,
        )
        db.session.add(asign)
        db.session.commit()
        reserva_id = reserva.id

    resp = admin_client.get(f"/admin/candidatos/info-reserva/{reserva_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["num_asignaciones"] == 1
    assert data["asignaciones"][0]["candidato_id"] == "C002"


def test_admin_estadisticas_renderiza_sin_reservas(admin_client):
    """La plantilla admin_estadisticas.html no existía — la ruta daba
    TemplateNotFound. Ahora existe y debe renderizar incluso sin datos."""
    resp = admin_client.get("/admin/estadisticas")
    assert resp.status_code == 200
    assert "Todavía no hay reservas".encode() in resp.data


def test_admin_estadisticas_renderiza_con_reservas(app, admin_client, admin_user):
    with app.app_context():
        espacio = Espacio(nombre="Lunes", descripcion="d", color="#000")
        db.session.add(espacio)
        db.session.commit()
        for _ in range(3):
            db.session.add(Reserva(
                usuario_id=admin_user, espacio_id=espacio.id,
                fecha=date.today(), hora_inicio=time(9, 0), hora_fin=time(10, 0),
            ))
        db.session.commit()

    resp = admin_client.get("/admin/estadisticas")
    assert resp.status_code == 200
    assert b"admin" in resp.data