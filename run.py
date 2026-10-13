#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Punto de entrada único de la aplicación.

Sustituye a los dos puntos de entrada que tenía el proyecto original:

- El bloque `if __name__ == "__main__":` al final de app.py (modo
  desarrollo: `app.run(debug=True, ...)`).
- serve.py (modo "producción": Waitress).

Ambos hacían exactamente lo mismo antes de arrancar el servidor (crear
tablas, sembrar admin + 5 Espacios — ver app/seed.py) y solo diferían en
qué servidor usaban y en que serve.py envolvía la siembra en un
try/except con sys.exit(1). Aquí se unifican en un solo script,
controlado por la variable de entorno FLASK_ENV:

    FLASK_ENV=development python run.py   -> servidor de desarrollo de
                                              Flask, con debug=True y
                                              autoreload
    FLASK_ENV=production  python run.py   -> Waitress (por defecto si no
                                              se define FLASK_ENV; es el
                                              modo pensado para el
                                              despliegue real en Windows)

Uso: python run.py
"""

import os
import sys

from app import create_app
from app.seed import inicializar_datos

HOST = "0.0.0.0"
PORT = 5000


def main():
    app = create_app()
    # FLASK_ENV es una decisión de "cómo arrancar este script", no de
    # configuración de la app en sí, así que se lee directamente del
    # entorno (no de app.config, que viene de app/config.py).
    modo = os.environ.get("FLASK_ENV", "production").lower()

    print("=" * 70)
    print("🔄 VERIFICANDO DATOS INICIALES...")
    print("=" * 70)
    try:
        inicializar_datos(app)
    except Exception as e:
        print("=" * 70)
        print("❌ ERROR AL INICIALIZAR DATOS:")
        print(f"   {e}")
        print("=" * 70)
        print("\n🔍 Verifica:")
        print("   1. PostgreSQL está en ejecución")
        print("   2. Las credenciales en .env son correctas")
        print("   3. La base de datos (DB_NAME) existe")
        print("=" * 70)
        sys.exit(1)

    if modo == "development":
        print("=" * 70)
        print("🔧 MODO DESARROLLO - SERVIDOR FLASK")
        print("=" * 70)
        print("⚠️  Este modo es SOLO para desarrollo")
        print(f"⚠️  Para producción, ejecuta: FLASK_ENV=production python {sys.argv[0]}")
        print("=" * 70)
        app.run(debug=True, host=HOST, port=PORT)
        return

    # --- Modo producción: Waitress ---
    from waitress import serve

    print("\n")
    print("=" * 70)
    print("🚀 INICIANDO ENTREVISTASEXPRESS - SERVIDOR DE PRODUCCIÓN")
    print("=" * 70)
    print("📡 CONFIGURACIÓN DEL SERVIDOR")
    print(f"   Host: {HOST}")
    print(f"   Puerto: {PORT}")
    print("   Threads: 4")
    print(f"   URL: http://localhost:{PORT}")
    print("=" * 70)
    print("\n⏳ Esperando conexiones...")
    print("💡 Presiona CTRL+C para detener el servidor")
    print("=" * 70 + "\n")

    try:
        serve(
            app,
            host=HOST,
            port=PORT,
            threads=4,
            url_scheme="http",
            connection_limit=1000,
            cleanup_interval=30,
            channel_timeout=120,
        )
    except KeyboardInterrupt:
        print("\n" + "=" * 70)
        print("🛑 SERVIDOR DETENIDO CORRECTAMENTE")
        print("=" * 70)
        sys.exit(0)
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ ERROR AL INICIAR EL SERVIDOR:")
        print(f"   {e}")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()  