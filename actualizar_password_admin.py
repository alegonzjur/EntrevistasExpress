#!/usr/bin/env python3
"""
Script para actualizar la contraseña del administrador
Ejecutar: python actualizar_password_admin.py
"""

from werkzeug.security import generate_password_hash
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Configuración (usa la misma que tu app.py)
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://usuario:usuario@localhost/reservas_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelo Usuario (simplificado)
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120))
    rol = db.Column(db.String(20))
    activo = db.Column(db.Boolean)

# Script principal
if __name__ == '__main__':
    with app.app_context():
        # Buscar el usuario admin
        admin = Usuario.query.filter_by(username='admin').first()
        
        if not admin:
            print("❌ Usuario 'admin' no encontrado en la base de datos")
            exit(1)
        
        # Nueva contraseña
        nueva_password = 'adminr€s3rv4s'
        
        # Generar hash
        hashed_password = generate_password_hash(nueva_password)
        
        # Actualizar en la base de datos
        admin.password = hashed_password
        db.session.commit()
        
        print("✅ Contraseña actualizada correctamente!")
        print(f"   Usuario: {admin.username}")
        print(f"   Nueva contraseña: {nueva_password}")
        print(f"   Hash generado: {hashed_password[:50]}...")
        print("\n🔐 Ahora puedes iniciar sesión con las nuevas credenciales")