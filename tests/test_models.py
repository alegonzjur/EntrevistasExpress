"""
Pruebas de regresión a nivel de modelo para los bugs ya documentados y
corregidos en app/models/.
"""

from app.extensions import db
from app.models import Candidato


def _candidato(**overrides):
    datos = dict(
        clave_academica="C001",
        solicitud=1,
        nombre="Ana",
        apellidos="Pérez",
        email="ana@example.com",
        media_estudios=8.5,
        sede="Bormujos",
    )
    datos.update(overrides)
    return Candidato(**datos)


def test_to_dict_no_explota_con_sede(app):
    """BUG corregido: to_dict() hacía `[s.nombre for s in self.sedes]`,
    pero Candidato no tiene relación `sedes` (solo el campo `sede`,
    singular) — eso era un AttributeError garantizado. Confirmado por
    grep que to_dict() no se llama desde ningún sitio del proyecto
    (código muerto), pero se corrige igualmente."""
    with app.app_context():
        c = _candidato()
        db.session.add(c)
        db.session.commit()

        d = c.to_dict()
        assert d["sede"] == "Bormujos"
        assert d["sedes"] == ["Bormujos"]


def test_to_dict_sin_sede_no_explota(app):
    with app.app_context():
        c = _candidato(clave_academica="C002", sede=None)
        db.session.add(c)
        db.session.commit()

        d = c.to_dict()
        assert d["sede"] is None
        assert d["sedes"] == []


def test_nombre_completo_property(app):
    with app.app_context():
        c = _candidato()
        assert c.nombre_completo == "Ana Pérez"


def test_tiene_email_property(app):
    with app.app_context():
        con_email = _candidato()
        sin_email = _candidato(clave_academica="C003", email=None)
        assert con_email.tiene_email is True
        assert sin_email.tiene_email is False