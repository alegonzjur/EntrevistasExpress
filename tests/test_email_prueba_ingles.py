"""
BUG corregido en app/services/emails.py::generar_email_candidato: el
enlace a la prueba de inglés vivía anidado dentro del bloque que solo se
mostraba si el profesor había configurado su enlace de videollamada
personal. La prueba de inglés es siempre la misma para todos los
candidatos, independientemente del profesor, así que debe aparecer
siempre en el correo, tenga o no el profesor su enlace configurado.
"""

from datetime import date, time

from app.models import Asignacion, Candidato, Espacio, Reserva, Usuario
from app.services.emails import generar_email_candidato


ENLACE_INGLES = "http://www.comillas.edu/ingleseuef"


def _asignacion_con_entrevistador(enlace_videollamada):
    candidato = Candidato(
        clave_academica="C001", solicitud=1, nombre="Ana", apellidos="Pérez",
        email="ana@example.com", semana_carga="2026-W43",
    )
    entrevistador = Usuario(
        id=1, username="profe1", nombre_completo="Profesor Uno",
        email="profe1@example.com", rol="profesor",
        enlace_videollamada_personal=enlace_videollamada,
    )
    espacio = Espacio(id=1, nombre="Lunes")
    reserva = Reserva(
        id=1, usuario_id=1, espacio_id=1, fecha=date(2026, 10, 19),
        hora_inicio=time(10, 0), hora_fin=time(10, 30),
    )
    reserva.espacio = espacio
    asignacion = Asignacion(
        id=1, candidato_clave="C001", reserva_id=1, entrevistador_id=1,
        posicion=1, minuto_inicio=0,
    )
    asignacion.candidato = candidato
    asignacion.reserva = reserva
    asignacion.entrevistador = entrevistador
    return asignacion


def test_enlace_ingles_aparece_aunque_el_profesor_no_tenga_videollamada():
    asignacion = _asignacion_con_entrevistador(enlace_videollamada=None)
    _, html = generar_email_candidato(asignacion)
    assert ENLACE_INGLES in html


def test_enlace_ingles_aparece_tambien_si_el_profesor_tiene_videollamada():
    asignacion = _asignacion_con_entrevistador(
        enlace_videollamada="https://meet.example.com/sala-profe1"
    )
    _, html = generar_email_candidato(asignacion)
    assert ENLACE_INGLES in html
    assert "https://meet.example.com/sala-profe1" in html


def test_enlace_videollamada_no_aparece_si_el_profesor_no_lo_configuro():
    """El enlace de entrevista sigue dependiendo del profesor — eso ya
    era correcto y no debe cambiar."""
    asignacion = _asignacion_con_entrevistador(enlace_videollamada=None)
    _, html = generar_email_candidato(asignacion)
    assert "Enlace entrevista" not in html