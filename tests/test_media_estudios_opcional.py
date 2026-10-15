"""
Pruebas de que media_estudios dejó de ser obligatoria: un candidato debe
poder cargarse, verse en todas las vistas y exportarse aunque el Excel
no traiga su nota — mostrando "No disponible" en vez de crashear (como
haría un "%.2f"|format(None) de Jinja) o mostrar un 0 engañoso.

También cubre la política acordada para el algoritmo de asignación y
las demás ordenaciones por nota: un candidato sin nota se ordena como
si tuviera un 5.
"""

from datetime import date, time

import pandas as pd
import pytest

from app.extensions import db
from app.models import Asignacion, Candidato, Espacio, Reserva, Usuario
from app.services.candidatos import (
    obtener_candidatos_pendientes,
    obtener_candidatos_por_semana,
)
from app.services.etl_candidatos import transformar
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

def test_media_estudios_texto_sin_nota(app):
    with app.app_context():
        c = Candidato(
            clave_academica="C001", solicitud=1, apellidos="Pérez", nombre="Ana",
            media_estudios=None, semana_carga="2026-W42",
        )
        assert c.media_estudios_texto == "No disponible"


def test_media_estudios_texto_con_nota(app):
    with app.app_context():
        c = Candidato(
            clave_academica="C001", solicitud=1, apellidos="Pérez", nombre="Ana",
            media_estudios=7.5, semana_carga="2026-W42",
        )
        assert c.media_estudios_texto == "7.50"


def test_candidato_se_puede_crear_sin_nota(app):
    """Antes, media_estudios era NOT NULL y esto habría lanzado un
    IntegrityError al hacer commit."""
    with app.app_context():
        c = Candidato(
            clave_academica="C001", solicitud=1, apellidos="Pérez", nombre="Ana",
            media_estudios=None, semana_carga="2026-W42",
        )
        db.session.add(c)
        db.session.commit()  # no debe lanzar
        assert Candidato.query.get("C001").media_estudios is None


# ---------------------------------------------------------------------------
# ETL
# ---------------------------------------------------------------------------

def _df_crudo(filas):
    registros = []
    for f in filas:
        registros.append(
            {
                "Clave académica": f["clave"],
                "Solicitud": f["solicitud"],
                "Apellidos": "Pérez",
                "Nombre": "Ana",
                "Correo electrónico": "ana@example.com",
                "Media estudios realizados": f.get("media"),
                "Primera opción": "Grado en Enfermería. CCS de Bormujos.",
            }
        )
    return pd.DataFrame(registros)


def test_transformar_carga_candidato_sin_nota(app):
    with app.app_context():
        df = _df_crudo(
            [
                {"clave": "C001", "solicitud": 1, "media": None},
                {"clave": "C002", "solicitud": 2, "media": 8.0},
            ]
        )
        df_filtrado, stats = transformar(
            df, umbral=0, solicitudes_seleccionadas=None,
            semana="2026-W42", archivo_origen="test.xlsx",
        )
        assert stats["candidatos_finales"] == 2
        fila = df_filtrado[df_filtrado["clave_academica"] == "C001"].iloc[0]
        assert fila["media_estudios"] is None


def test_transformar_umbral_no_excluye_a_quien_no_tiene_nota(app):
    """Un candidato sin nota debe pasar el filtro de umbral igual, pase
    lo que pase con el umbral — no hay nota con la que compararlo."""
    with app.app_context():
        df = _df_crudo(
            [
                {"clave": "C001", "solicitud": 1, "media": None},  # sin nota
                {"clave": "C002", "solicitud": 2, "media": 9.0},  # con nota alta
            ]
        )
        df_filtrado, stats = transformar(
            df, umbral=7.0, solicitudes_seleccionadas=None,
            semana="2026-W42", archivo_origen="test.xlsx",
        )
        # C002 queda excluido por el umbral (9.0 no es < 7.0); C001 se
        # carga igualmente, a pesar del umbral, porque no tiene nota.
        assert stats["candidatos_finales"] == 1
        assert list(df_filtrado["clave_academica"]) == ["C001"]


def test_transformar_celda_vacia_en_excel_se_convierte_a_none(app):
    """Una celda realmente vacía en el Excel (NaN tras read_excel) debe
    acabar siendo None, no NaN de numpy (que rompería el to_sql/insert)."""
    with app.app_context():
        df = _df_crudo([{"clave": "C001", "solicitud": 1}])  # sin clave 'media' -> NaN
        df_filtrado, _ = transformar(
            df, umbral=0, solicitudes_seleccionadas=None,
            semana="2026-W42", archivo_origen="test.xlsx",
        )
        valor = df_filtrado.iloc[0]["media_estudios"]
        assert valor is None


# ---------------------------------------------------------------------------
# Orden "sin nota = nota 5"
# ---------------------------------------------------------------------------

def _crear_candidato(clave, solicitud, media, semana="2026-W42", estado="pendiente"):
    # primera_opcion="Bormujos" a propósito: candidatos_semana.html hace
    # candidato.primera_opcion[:50] sin comprobar None, un bug preexistente
    # y no relacionado con media_estudios (ya podía pasar antes de este
    # cambio, si el Excel no detectaba sede) — se deja fuera del alcance
    # de esta tarea, pero se evita aquí para no mezclar ambos problemas
    # en el mismo test.
    c = Candidato(
        clave_academica=clave, solicitud=solicitud, apellidos="Pérez", nombre="Ana",
        media_estudios=media, semana_carga=semana, estado=estado,
        primera_opcion="Bormujos",
    )
    db.session.add(c)
    return c


def test_obtener_candidatos_pendientes_ordena_sin_nota_como_un_cinco(app):
    with app.app_context():
        _crear_candidato("C_ALTA", 1, 8.0)   # tratado como 8 -> último
        _crear_candidato("C_SIN_NOTA", 2, None)  # tratado como 5 -> en medio
        _crear_candidato("C_BAJA", 3, 3.0)   # tratado como 3 -> primero
        db.session.commit()

        orden = [c.clave_academica for c in obtener_candidatos_pendientes()]
        assert orden == ["C_BAJA", "C_SIN_NOTA", "C_ALTA"]


def test_obtener_candidatos_por_semana_ordena_sin_nota_como_un_cinco(app):
    with app.app_context():
        _crear_candidato("C_ALTA", 1, 9.0)
        _crear_candidato("C_SIN_NOTA", 2, None)
        _crear_candidato("C_BAJA", 3, 2.0)
        db.session.commit()

        orden = [
            c.clave_academica for c in obtener_candidatos_por_semana("2026-W42")
        ]
        assert orden == ["C_BAJA", "C_SIN_NOTA", "C_ALTA"]


# ---------------------------------------------------------------------------
# Integración: las vistas no deben crashear con un candidato sin nota
# ---------------------------------------------------------------------------

def _preparar_semana_con_candidato_sin_nota(app, admin_user):
    with app.app_context():
        _crear_candidato("C_SIN_NOTA", 1, None, semana="2026-W42")

        espacio = Espacio(nombre="Lunes", descripcion="d", color="#000")
        db.session.add(espacio)
        db.session.commit()

        profesor = Usuario(
            username="profe1", email="profe1@example.com",
            password=generate_password_hash("x"), rol="profesor", activo=True,
        )
        db.session.add(profesor)
        db.session.commit()

        reserva = Reserva(
            usuario_id=profesor.id, espacio_id=espacio.id, fecha=date.today(),
            hora_inicio=time(10, 0), hora_fin=time(10, 30),
        )
        db.session.add(reserva)
        db.session.commit()

        asignacion = Asignacion(
            candidato_clave="C_SIN_NOTA", reserva_id=reserva.id,
            entrevistador_id=profesor.id, posicion=1, minuto_inicio=0,
        )
        db.session.add(asignacion)
        db.session.commit()


def test_vista_candidatos_semana_no_crashea_sin_nota(app, admin_client, admin_user):
    _preparar_semana_con_candidato_sin_nota(app, admin_user)
    resp = admin_client.get("/admin/candidatos/semana/2026-W42")
    assert resp.status_code == 200
    assert "No disponible".encode() in resp.data


def test_vista_gestion_manual_no_crashea_sin_nota(app, admin_client, admin_user):
    _preparar_semana_con_candidato_sin_nota(app, admin_user)
    resp = admin_client.get("/admin/candidatos/gestion-manual/2026-W42")
    assert resp.status_code == 200
    assert "No disponible".encode() in resp.data


def test_vista_asignaciones_semana_no_crashea_sin_nota(app, admin_client, admin_user):
    _preparar_semana_con_candidato_sin_nota(app, admin_user)
    resp = admin_client.get("/admin/candidatos/asignaciones/2026-W42")
    assert resp.status_code == 200
    assert "No disponible".encode() in resp.data


@pytest.mark.parametrize("formato", ["xlsx", "csv", "pdf"])
def test_exportar_candidatos_no_crashea_sin_nota(app, admin_client, admin_user, formato):
    _preparar_semana_con_candidato_sin_nota(app, admin_user)
    resp = admin_client.get(f"/admin/exportar/candidatos/2026-W42/{formato}")
    assert resp.status_code == 200
    assert len(resp.data) > 0


@pytest.mark.parametrize("formato", ["xlsx", "csv", "pdf"])
def test_exportar_asignaciones_no_crashea_sin_nota(app, admin_client, admin_user, formato):
    _preparar_semana_con_candidato_sin_nota(app, admin_user)
    resp = admin_client.get(f"/admin/exportar/asignaciones/2026-W42/{formato}")
    assert resp.status_code == 200
    assert len(resp.data) > 0