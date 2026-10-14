"""
Smoke tests de navegación real: que las páginas principales renderizan
de verdad (plantilla + static), no solo que la ruta existe.
"""


def test_login_sin_sesion(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_login_correcto_redirige(client, admin_user):
    resp = client.post(
        "/login", data={"username": "admin", "password": "admin123"}
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/reservas")


def test_login_incorrecto_no_redirige(client, admin_user):
    resp = client.post(
        "/login", data={"username": "admin", "password": "mala"}
    )
    assert resp.status_code == 200  # se re-renderiza login.html con error


def test_paginas_admin_autenticadas(admin_client):
    for ruta in ("/reservas", "/admin/usuarios", "/admin/candidatos",
                 "/perfil", "/admin/estadisticas"):
        resp = admin_client.get(ruta)
        assert resp.status_code == 200, f"{ruta} -> {resp.status_code}"


def test_estaticos_se_sirven_desde_app_static(admin_client):
    resp = admin_client.get("/static/css/base.css")
    assert resp.status_code == 200
    assert len(resp.data) > 0

    resp = admin_client.get("/static/images/favicon.jpg")
    assert resp.status_code == 200


def test_nav_enlaza_a_estadisticas(admin_client):
    """Regresión del enlace añadido en base.html al dropdown de admin."""
    resp = admin_client.get("/reservas")
    assert b'href="/admin/estadisticas"' in resp.data


def test_paginas_sin_sesion_no_dan_200_en_rutas_admin(client):
    """Sin login, las rutas de admin no deberían dar 200 directamente
    (deberían redirigir a /login)."""
    resp = client.get("/admin/usuarios", follow_redirects=False)
    assert resp.status_code in (302, 401, 403)