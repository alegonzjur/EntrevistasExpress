#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Servidor de producción con Waitress para Windows
Ejecutar: python serve.py
"""

import sys
from waitress import serve
from werkzeug.security import generate_password_hash

# Importar la aplicación Flask
from app import app, db, Usuario, Espacio


def inicializar_datos():
    """Inicializa los datos básicos si es necesario"""
    print("=" * 70)
    print("🔄 VERIFICANDO DATOS INICIALES...")
    print("=" * 70)

    with app.app_context():
        try:
            # Crear todas las tablas si no existen
            db.create_all()
            print("✅ Tablas de base de datos verificadas")

            # Crear usuario admin si no existe
            admin = Usuario.query.filter_by(username="admin").first()
            if not admin:
                hashed_password = generate_password_hash("admin123")
                admin = Usuario(
                    username="admin",
                    email="admin@ejemplo.com",
                    password=hashed_password,
                    rol="admin",
                )
                db.session.add(admin)
                print("✅ Usuario administrador creado: admin / admin123")
                print(
                    "   ⚠️  IMPORTANTE: Cambia esta contraseña después del primer login"
                )
            else:
                print("ℹ️  Usuario administrador ya existe")

            # Crear espacios (días de la semana) si no existen
            if Espacio.query.count() == 0:
                dias_semana = [
                    Espacio(
                        nombre="Lunes",
                        descripcion="Primer día de la semana",
                        color="#667eea",
                    ),
                    Espacio(
                        nombre="Martes",
                        descripcion="Segundo día de la semana",
                        color="#764ba2",
                    ),
                    Espacio(
                        nombre="Miércoles",
                        descripcion="Tercer día de la semana",
                        color="#f093fb",
                    ),
                    Espacio(
                        nombre="Jueves",
                        descripcion="Cuarto día de la semana",
                        color="#4facfe",
                    ),
                    Espacio(
                        nombre="Viernes",
                        descripcion="Quinto día de la semana",
                        color="#43e97b",
                    ),
                ]
                for dia in dias_semana:
                    db.session.add(dia)
                print("✅ Días de la semana creados correctamente")
            else:
                print("ℹ️  Espacios (días) ya existen")

            db.session.commit()
            print("=" * 70)
            print("✅ INICIALIZACIÓN COMPLETADA")
            print("=" * 70)

        except Exception as e:
            print("=" * 70)
            print(f"❌ ERROR AL INICIALIZAR DATOS:")
            print(f"   {str(e)}")
            print("=" * 70)
            print("\n🔍 Verifica:")
            print("   1. PostgreSQL está ejecutándose")
            print("   2. Credenciales correctas en app.py")
            print("   3. La base de datos existe")
            print("=" * 70)
            sys.exit(1)


def main():
    """Función principal para ejecutar el servidor"""

    # Configuración del servidor
    host = "0.0.0.0"  # Escuchar en todas las interfaces
    port = 5000  # Puerto de escucha
    threads = 4  # Número de hilos

    print("\n")
    print("=" * 70)
    print("🚀 INICIANDO BOOKING SYSTEM - SERVIDOR DE PRODUCCIÓN")
    print("=" * 70)

    # Inicializar datos básicos
    inicializar_datos()

    print("\n")
    print("=" * 70)
    print("📡 CONFIGURACIÓN DEL SERVIDOR")
    print("=" * 70)
    print(f"   Host: {host}")
    print(f"   Puerto: {port}")
    print(f"   Threads: {threads}")
    print(f"   URL: http://localhost:{port}")
    print("=" * 70)
    print("\n⏳ Esperando conexiones...")
    print("💡 Presiona CTRL+C para detener el servidor")
    print("=" * 70)
    print("\n")

    try:
        # Iniciar servidor Waitress
        serve(
            app,
            host=host,
            port=port,
            threads=threads,
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
        print(f"❌ ERROR AL INICIAR EL SERVIDOR:")
        print(f"   {str(e)}")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
