"""
run.py — el punto de entrada único (sustituye al bloque __main__ de
app.py y a serve.py). Se prueba importando el módulo y llamando a
main() con create_app, app.run y waitress.serve parcheados, para no
arrancar un servidor real durante los tests.
"""

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def run_module(monkeypatch, app):
    """Importa run.py de forma aislada, con create_app() parcheado para
    devolver la `app` de test (SQLite en memoria) en vez de conectar a
    PostgreSQL real."""
    import run as _run

    monkeypatch.setattr(_run, "create_app", lambda config_class=None: app)
    return _run


def test_modo_development_llama_a_app_run_debug(run_module, app, monkeypatch):
    llamadas = {}

    def fake_run(*args, **kwargs):
        llamadas["kwargs"] = kwargs

    monkeypatch.setattr(app, "run", fake_run)
    monkeypatch.setenv("FLASK_ENV", "development")

    run_module.main()

    assert llamadas["kwargs"]["debug"] is True
    assert llamadas["kwargs"]["host"] == "0.0.0.0"
    assert llamadas["kwargs"]["port"] == 5000


def test_modo_production_por_defecto_llama_a_waitress(run_module, monkeypatch):
    llamadas = {}

    fake_waitress = types.ModuleType("waitress")

    def fake_serve(app_arg, **kwargs):
        llamadas["kwargs"] = kwargs

    fake_waitress.serve = fake_serve
    monkeypatch.setitem(sys.modules, "waitress", fake_waitress)
    monkeypatch.delenv("FLASK_ENV", raising=False)

    run_module.main()

    assert llamadas["kwargs"]["host"] == "0.0.0.0"
    assert llamadas["kwargs"]["port"] == 5000
    assert llamadas["kwargs"]["threads"] == 4
    assert llamadas["kwargs"]["connection_limit"] == 1000
    assert llamadas["kwargs"]["channel_timeout"] == 120