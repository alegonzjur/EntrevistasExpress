"""
Configuración de la aplicación, leída de variables de entorno.

Antes vivían como literales sueltos en la cabecera de app.py: la
`secret_key` de Flask, las credenciales de PostgreSQL y las de la cuenta
de correo de Office 365 — las tres en texto plano dentro del código
Se mueven aquí y se leen del entorno, con un `.env` local (no versionado — ver
`.env.example` en la raíz del proyecto) para desarrollo.

SECRET_KEY es obligatoria: si falta, la app se niega a arrancar con un
error claro, en vez de caer de vuelta a un valor hardcodeado en silencio
— es la única manera de que deje de estar realmente en el código. El
resto de contraseñas (BD, correo) tampoco tienen valor por defecto, pero
no son obligatorias al arrancar: su ausencia falla más tarde, al primer
intento real de conexión, con un error de psycopg2/smtplib igual de claro.
"""

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


class Config:
    # --- Flask ---
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError(
            "Falta la variable de entorno SECRET_KEY. Copia .env.example a "
            ".env en la raíz del proyecto y rellena un valor (puedes generar "
            "uno con: python -c \"import secrets; print(secrets.token_hex(32))\")."
        )

    # --- Base de datos (PostgreSQL) ---
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5432")
    DB_NAME = os.environ.get("DB_NAME", "entrevistas_db")

    # quote_plus sobre la contraseña: el app.py original importaba
    # `quote_plus` de urllib.parse pero nunca llegó a usarlo (import
    # muerto, verificado por grep) — su contraseña de entonces no tenía
    # caracteres que rompieran la URI. Al construir la URI igualmente a
    # partir de piezas sueltas, lo aplicamos de verdad: así una contraseña
    # futura con ':', '@', '/' o similares no rompe la cadena de conexión.
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Correo (Office 365 / SMTP) ---
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.office365.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or MAIL_USERNAME
    MAIL_MAX_EMAILS = 50
    MAIL_ASCII_ATTACHMENTS = False

    # --- Uploads ---
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")