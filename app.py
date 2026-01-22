from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
import hashlib
import subprocess
from datetime import datetime, timedelta, date
from functools import wraps
import os
from flask_mail import Mail, Message
from threading import Thread
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from io import BytesIO, StringIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side    
import csv
import json
import unicodedata


app = Flask(__name__)
app.secret_key = 'a4f8d9e3b2c1a7f6e5d4c3b2a1f9e8d7c6b5a4f3e2d1c9b8a7f6e5d4c3b2a1f0'  # Secret Key de la app (NO MOSTRAR)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:eebormujos?@localhost/reservas_db' # Conexión a la base de datos (AJUSTAR SEGÚN ENTORNO)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.office365.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'entrevistas.euef@comillas.edu'  # Correo remitente.
app.config['MAIL_PASSWORD'] = 'Ent.Enf@2026'  # Contraseña del correo remitente para realizar conexión.
app.config['MAIL_DEFAULT_SENDER'] = 'entrevistas.euef@comillas.edu'  # Correo remitente por defecto.
app.config['MAIL_MAX_EMAILS'] = 50  # Máximo 50 emails por conexión
app.config['MAIL_ASCII_ATTACHMENTS'] = False

# Inicializar Flask-Mail
mail = Mail(app)

db = SQLAlchemy(app)
# ====================================================================
# CONFIGURACIÓN
# ====================================================================
# Configuración de uploads

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Crear carpeta si no existe
import os
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ====================================================================
# MODELOS DE BASE DE DATOS
# ====================================================================




class Sede(db.Model):
    __tablename__ = 'sedes'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    activa = db.Column(db.Boolean, default=True)
    descripcion = db.Column(db.String(255))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Sede {self.nombre}>'

usuario_sede = db.Table('usuario_sede',
    db.Column('usuario_id', db.Integer, db.ForeignKey('usuarios.id', ondelete='CASCADE'), primary_key=True),
    db.Column('sede_id', db.Integer, db.ForeignKey('sedes.id', ondelete='CASCADE'), primary_key=True),
    db.Column('fecha_asignacion', db.DateTime, default=datetime.utcnow)
)
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    rol = db.Column(db.String(20), default='profesor')  # 'admin' o 'profesor'
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    enlace_videollamada_personal = db.Column(db.String(500), nullable=True)
    sede = db.Column(db.String(50), nullable=True)

    sedes = db.relationship('Sede', 
                           secondary=usuario_sede, 
                           lazy='subquery',
                           backref=db.backref('profesores', lazy=True))
    
    # Relación con reservas (especificando foreign_keys para evitar ambigüedad)
    reservas = db.relationship('Reserva', 
                              foreign_keys='Reserva.usuario_id',
                              backref='usuario', 
                              lazy=True)
    
    # Relación con reservas creadas como admin
    reservas_creadas = db.relationship('Reserva',
                                      foreign_keys='Reserva.creado_por_admin',
                                      backref='creador_admin',
                                      lazy=True)
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'rol': self.rol,
            'activo': self.activo,
            'sede': self.sede,  # Sede principal
            'sedes': [s.nombre for s in self.sedes] if self.sedes else [],  
            'enlace_videollamada_personal': self.enlace_videollamada_personal
    }
    def puede_atender_sede(self, sede_nombre):
        """Verifica si el profesor puede atender entrevistas de esta sede"""
        if not sede_nombre:
            return True  # Si no hay sede, puede atender cualquiera
        
        # Si tiene sedes específicas asignadas, verificar
        if self.sedes:
            return any(s.nombre == sede_nombre for s in self.sedes)
        
        # Si no tiene sedes asignadas pero tiene sede principal, usar esa
        if self.sede:
            return self.sede == sede_nombre
        
        # Si no tiene ninguna, puede atender cualquiera
        return True


class Espacio(db.Model):
    __tablename__ = 'espacios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    color = db.Column(db.String(7), default='#667eea')
    reservas = db.relationship('Reserva', backref='espacio', lazy=True)

class Reserva(db.Model):
    __tablename__ = 'reservas'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    espacio_id = db.Column(db.Integer, db.ForeignKey('espacios.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    notas = db.Column(db.Text)
    creado_por_admin = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    prioridad = db.Column(db.String(20), default='normal', nullable=False)


# ====================================================================
# MODELOS PARA CANDIDATOS
# ====================================================================

class Candidato(db.Model):
    __tablename__ = 'candidatos'
    
    id = db.Column(db.Integer, primary_key=True)
    solicitud = db.Column(db.Integer, nullable=False)
    apellidos = db.Column(db.String(150), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    telefono = db.Column(db.String(20), nullable=True)
    media_estudios = db.Column(db.Numeric(4, 2), nullable=False)
    primera_opcion = db.Column(db.Text)
    sede = db.Column(db.String(50), nullable=True)
    estado = db.Column(db.String(20), default='pendiente', nullable=False)
    fecha_carga = db.Column(db.DateTime, default=datetime.utcnow)
    semana_carga = db.Column(db.String(20))
    archivo_origen = db.Column(db.String(255))
    
    asignacion = db.relationship('Asignacion', backref='candidato', uselist=False, cascade='all, delete-orphan')
    
    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}"
    
    @property
    def tiene_email(self):
        return self.email is not None and self.email.strip() != ''

    @property
    def tiene_telefono(self): 
        return self.telefono is not None and self.telefono.strip() != ''
    
    def to_dict(self):
        return {
            'id': self.id,
            'solicitud': self.solicitud,
            'nombre_completo': self.nombre_completo,
            'email': self.email,
            'telefono': self.telefono,
            'media_estudios': float(self.media_estudios) if self.media_estudios else None,
            'estado': self.estado,
            'primera_opcion': self.primera_opcion,
            'sede': self.sede,
            'sedes': [s.nombre for s in self.sedes]
        }


class Asignacion(db.Model):
    __tablename__ = 'asignaciones'
    
    id = db.Column(db.Integer, primary_key=True)
    candidato_id = db.Column(db.Integer, db.ForeignKey('candidatos.id', ondelete='CASCADE'), nullable=False, unique=True)
    reserva_id = db.Column(db.Integer, db.ForeignKey('reservas.id', ondelete='CASCADE'), nullable=False)
    entrevistador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    posicion = db.Column(db.SmallInteger, nullable=False)
    minuto_inicio = db.Column(db.SmallInteger, nullable=False)
    estado = db.Column(db.String(20), default='confirmado', nullable=False)
    enviado_email = db.Column(db.Boolean, default=False)
    fecha_email = db.Column(db.DateTime, nullable=True)
    resultado = db.Column(db.Text, nullable=True)
    notas_entrevista = db.Column(db.Text, nullable=True)
    fecha_asignacion = db.Column(db.DateTime, default=datetime.utcnow)
    asignado_por_admin_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    
    reserva = db.relationship('Reserva', backref='asignaciones')
    entrevistador = db.relationship('Usuario', foreign_keys=[entrevistador_id], backref='entrevistas_asignadas')
    asignado_por = db.relationship('Usuario', foreign_keys=[asignado_por_admin_id], backref='asignaciones_creadas')
    
    @property
    def hora_exacta(self):
        if self.reserva and self.reserva.hora_inicio:
            hora_base = datetime.combine(datetime.today(), self.reserva.hora_inicio)
            hora_exacta = hora_base + timedelta(minutes=self.minuto_inicio)
            return hora_exacta.time()
        return None


class LogAsignacion(db.Model):
    __tablename__ = 'logs_asignacion'
    
    id = db.Column(db.Integer, primary_key=True)
    fecha_ejecucion = db.Column(db.DateTime, default=datetime.utcnow)
    semana_objetivo = db.Column(db.String(20), nullable=False)
    candidatos_procesados = db.Column(db.Integer, nullable=False)
    candidatos_filtrados = db.Column(db.Integer, nullable=False)
    candidatos_asignados = db.Column(db.Integer, nullable=False)
    candidatos_sin_asignar = db.Column(db.Integer, nullable=False)
    franjas_utilizadas = db.Column(db.Integer, nullable=False)
    algoritmo_usado = db.Column(db.String(50), default='balanceado')
    tiempo_ejecucion_segundos = db.Column(db.Numeric(6, 2))
    estado = db.Column(db.String(20), nullable=False)
    mensaje = db.Column(db.Text)
    ejecutado_por_usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    archivo_origen = db.Column(db.String(255))
    
    ejecutado_por = db.relationship('Usuario', backref='logs_asignaciones')


class CargaExcel(db.Model):
    __tablename__ = 'cargas_excel'
    
    id = db.Column(db.Integer, primary_key=True)
    archivo_nombre = db.Column(db.String(255), nullable=False)
    archivo_hash = db.Column(db.String(64))
    fecha_carga = db.Column(db.DateTime, default=datetime.utcnow)
    candidatos_totales = db.Column(db.Integer, nullable=False)
    candidatos_importados = db.Column(db.Integer, nullable=False)
    candidatos_duplicados = db.Column(db.Integer, default=0)
    cargado_por_usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    semana_destino = db.Column(db.String(20))
    estado = db.Column(db.String(20), default='completado')
    mensaje = db.Column(db.Text)
    
    cargado_por = db.relationship('Usuario', backref='cargas_excel')

# ====================================================================
# MODELO DE LOGS Y AUDITORÍA
# ====================================================================

class LogActividad(db.Model):
    __tablename__ = 'logs_actividad'
    
    id = db.Column(db.Integer, primary_key=True)
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    usuario_username = db.Column(db.String(80), nullable=True)  
    accion = db.Column(db.String(50), nullable=False, index=True)  
    entidad = db.Column(db.String(50), nullable=False, index=True)  
    entidad_id = db.Column(db.Integer, nullable=True)
    descripcion = db.Column(db.Text, nullable=False)
    datos_anteriores = db.Column(db.Text, nullable=True)  
    datos_nuevos = db.Column(db.Text, nullable=True)  
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    nivel = db.Column(db.String(20), default='info', nullable=False)  
    metadata_extra = db.Column(db.Text, nullable=True) 
    
    usuario = db.relationship('Usuario', backref='logs_actividad', foreign_keys=[usuario_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'fecha_hora': self.fecha_hora.strftime('%d/%m/%Y %H:%M:%S'),
            'usuario': self.usuario_username,
            'accion': self.accion,
            'entidad': self.entidad,
            'entidad_id': self.entidad_id,
            'descripcion': self.descripcion,
            'nivel': self.nivel
        }
    
# ====================================================================
# CONSTANTES
# ====================================================================

# Sedes disponibles
SEDES_DISPONIBLES = [
    'Bormujos',
    'Ciempozuelos',
    'Pº de la Habana'
]

# ====================================================================
# FUNCIONES AUXILIARES PARA SEDES
# ====================================================================

def detectar_sede_desde_primera_opcion(primera_opcion):
    """
    Detecta la sede a partir del campo 'primera_opcion'
    
    Busca las palabras clave en el texto:
    - "Bormujos" -> Bormujos
    - "Pº de la Habana" o "Paseo de la Habana" -> Pº de la Habana
    - "Ciempozuelos" -> Ciempozuelos
    
    Args:
        primera_opcion: String con la primera opción del candidato
    
    Returns:
        String con el nombre de la sede o None si no se detecta
    """
    if not primera_opcion:
        return None
    
    def normalizar_texto(texto):
    # Quitar acentos
        texto_sin_acentos = ''.join(
            c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    # Convertir a mayúsculas
        return texto_sin_acentos.upper()

    texto_normalizado = normalizar_texto(primera_opcion)
    texto_limpio = texto_normalizado.replace('º', '').replace('°', '').replace('O', '')
    # Convertir a mayúsculas para facilitar la búsqueda
    # Buscar patrones de "Pº de la Habana", "Paseo de la Habana", "P de la Habana"
    if any(patron in texto_limpio for patron in ['P DE LA HABANA', 'PASEO DE LA HABANA', 'PDELA HABANA']):
        return 'Pº de la Habana'
    
    # También buscar en texto original por si acaso
    if 'HABANA' in texto_normalizado:
        return 'Pº de la Habana'
    
    if 'BORMUJOS' in texto_normalizado:
        return 'Bormujos'
    
    if 'CIEMPOZUELOS' in texto_normalizado:
        return 'Ciempozuelos'
    
    # Si no se detecta ninguna sede
    return None
# ====================================================================
# FUNCIONES AUXILIARES PARA CARGA Y ASIGNACIÓN
# ====================================================================

def allowed_file(filename):
    """Verifica si el archivo tiene extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calcular_semana_iso(fecha):
    """Calcula la semana ISO de una fecha"""
    return fecha.strftime('%Y-W%W')

def parsear_semana_iso(semana_iso):
    """Convierte semana ISO a rango de fechas (lunes-viernes)"""
    año, semana = semana_iso.split('-W')
    primer_dia = datetime.strptime(f'{año}-W{semana}-1', '%Y-W%W-%w').date()
    viernes = primer_dia + timedelta(days=4)
    return primer_dia, viernes

def obtener_semanas_disponibles():
    """Obtiene lista de semanas para el selector"""
    hoy = date.today()
    semanas = []
    
    # 2 semanas atrás hasta 8 semanas adelante
    for i in range(-2, 9):
        fecha = hoy + timedelta(weeks=i)
        # Calcular lunes de esa semana
        dias_hasta_lunes = fecha.weekday()
        lunes = fecha - timedelta(days=dias_hasta_lunes)
        viernes = lunes + timedelta(days=4)
        
        semana_iso = calcular_semana_iso(lunes)
        
        semanas.append({
            'iso': semana_iso,
            'lunes': lunes.strftime('%d/%m/%Y'),
            'viernes': viernes.strftime('%d/%m/%Y'),
            'label': f"Semana {semana_iso.split('-W')[1]} ({lunes.strftime('%d/%m')} - {viernes.strftime('%d/%m')})",
            'es_actual': i == 0
        })
    
    return semanas

# ====================================================================
# FUNCIONES AUXILIARES PARA CANDIDATOS
# ====================================================================

def obtener_candidatos_pendientes():
    """Obtiene candidatos pendientes ordenados por nota"""
    return Candidato.query.filter_by(estado='pendiente')\
        .order_by(Candidato.media_estudios.asc())\
        .all()


def obtener_candidatos_por_semana(semana):
    """Obtiene candidatos de una semana específica"""
    return Candidato.query.filter_by(semana_carga=semana)\
        .order_by(Candidato.media_estudios.asc())\
        .all()


def obtener_estadisticas_semana_candidatos(semana):
    """Obtiene estadísticas de candidatos de una semana"""
    candidatos = Candidato.query.filter_by(semana_carga=semana).all()
    
    total = len(candidatos)
    asignados = len([c for c in candidatos if c.estado == 'asignado'])
    pendientes = len([c for c in candidatos if c.estado == 'pendiente'])
    entrevistados = len([c for c in candidatos if c.estado == 'entrevistado'])
    
    return {
        'total_candidatos': total,
        'candidatos_asignados': asignados,
        'candidatos_pendientes': pendientes,
        'candidatos_entrevistados': entrevistados,
        'tasa_asignacion': round((asignados / total * 100) if total > 0 else 0, 2)
    }

# ====================================================================
# FUNCIONES AUXILIARES EMAIL
# ====================================================================

def enviar_email_async(app, msg):
    """Envía email en background (opcional, para no bloquear)"""
    with app.app_context():
        try:
            mail.send(msg)
            return True
        except Exception as e:
            print(f"Error enviando email: {e}")
            return False


def validar_email(email):
    """Valida que un email tenga formato correcto"""
    import re
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def generar_email_candidato(asignacion):
    """
    Genera el HTML del email para un candidato
    
    Args:
        asignacion: Objeto Asignacion con candidato, reserva, entrevistador
    
    Returns:
        tuple: (subject, html_body)
    """
    candidato = asignacion.candidato
    reserva = asignacion.reserva
    entrevistador = asignacion.entrevistador
    
    # Formatear fecha
    fecha_str = reserva.fecha.strftime('%A %d de %B de %Y')
    # Traducir día de la semana al español
    dias = {
        'Monday': 'Lunes',
        'Tuesday': 'Martes', 
        'Wednesday': 'Miércoles',
        'Thursday': 'Jueves',
        'Friday': 'Viernes',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }
    for eng, esp in dias.items():
        fecha_str = fecha_str.replace(eng, esp)
    
    # Meses en español
    meses = {
        'January': 'enero', 'February': 'febrero', 'March': 'marzo',
        'April': 'abril', 'May': 'mayo', 'June': 'junio',
        'July': 'julio', 'August': 'agosto', 'September': 'septiembre',
        'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'
    }
    for eng, esp in meses.items():
        fecha_str = fecha_str.replace(eng, esp)
    
    # Hora exacta
    hora_str = asignacion.hora_exacta.strftime('%H:%M') if asignacion.hora_exacta else reserva.hora_inicio.strftime('%H:%M')
    
    subject = f"Confirmación de Entrevista - {candidato.nombre} {candidato.apellidos}"
    
    # ✅ MODIFICADO: Obtener enlace del entrevistador
    enlace_videollamada = entrevistador.enlace_videollamada_personal if entrevistador else None
    
    seccion_videollamada = ""
    if enlace_videollamada:
        seccion_videollamada = f"""
                                        <p style="margin: 0 0 15px 0; font-size: 16px; color: #333333;">
                                            <span style="font-size: 20px;">🎥</span> 
                                            <strong>Enlace de Videollamada:</strong><br>
                                            <span style="margin-left: 30px;">
                                                <a href="{enlace_videollamada}" 
                                                   style="color: #0066B3; text-decoration: none; font-weight: 600;"
                                                   target="_blank">
                                                    Unirse a la entrevista virtual
                                                </a>
                                            </span>
                                        </p>
        """
    
    html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f4f4f4">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                
                <!-- Contenedor principal -->
                <table width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff" 
                       style="border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td bgcolor="#4472C4" style="padding: 40px 30px; text-align: center; border-radius: 8px 8px 0 0;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 600;">
                                📋 Confirmación de Entrevista
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Contenido -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            
                            <p style="font-size: 16px; color: #333333; line-height: 1.6; margin: 0 0 20px 0;">
                                Estimado/a <strong>{candidato.nombre} {candidato.apellidos}</strong>,
                            </p>
                            
                            <p style="font-size: 16px; color: #666666; line-height: 1.6; margin: 0 0 30px 0;">
                                Como ya le hemos informado por teléfono, para poder valorar su admisión en los estudios de GRADO EN ENFERMERÍA, además de su expediente académico tendrá que realizar una entrevista personal y una prueba de nivel de inglés. De no realizar alguna de estas pruebas su solicitud no podrá ser valorada.
                            <br>
                                A continuación le indicamos día, hora y el enlace para realizar la entrevista personal online. La plataforma a través de la cual se realiza es por Comillas Class. Es recomendable que utilice <strong>CHROME</strong> como navegador y lo haga desde un ordenador.

                            </p>
                            
                            <!-- Caja de información -->
                            <table width="100%" cellpadding="20" cellspacing="0" border="0" bgcolor="#f8f9fa" 
                                   style="border-radius: 8px; margin: 0 0 30px 0; border-left: 4px solid #4472C4;">
                                <tr>
                                    <td>
                                        <p style="margin: 0 0 15px 0; font-size: 16px; color: #333333;">
                                            <span style="font-size: 20px;">📅</span> 
                                            <strong>Fecha:</strong><br>
                                            <span style="color: #666666; margin-left: 30px;">{fecha_str}</span>
                                        </p>
                                        
                                        <p style="margin: 0 0 15px 0; font-size: 16px; color: #333333;">
                                            <span style="font-size: 20px;">🕐</span> 
                                            <strong>Hora:</strong><br>
                                            <span style="color: #666666; margin-left: 30px; font-size: 20px; font-weight: 600;">{hora_str}h</span>
                                        </p>                                      
                                        
                                        {seccion_videollamada}
                                        
                                        <p style="margin: 0; font-size: 16px; color: #333333;">
                                            <span style="font-size: 20px;">👤</span> 
                                            <strong>Entrevistador:</strong><br>
                                            <span style="color: #666666; margin-left: 30px;">{entrevistador.username if entrevistador else 'A confirmar'}</span>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Instrucciones -->
                            <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px 20px; margin: 0 0 30px 0; border-radius: 4px;">
                                <p style="margin: 0 0 10px 0; font-size: 16px; color: #856404; font-weight: 600;">
                                    ⚠️ Instrucciones importantes:
                                </p>
                                <ul style="margin: 0; padding-left: 20px; color: #856404;">
                                    {"<li style='margin: 5px 0;'>Accede al enlace de videollamada <strong>5 minutos antes</strong> de la hora indicada.</li>" if enlace_videollamada else "<li style='margin: 5px 0;'>Por favor, llegue <strong>10 minutos antes</strong> de la hora indicada.</li>"}
                                    <li style="margin: 5px 0;">Para realizar la prueba de nivel de inglés online deberá acceder a través del siguiente enlace:  http://www.comillas.edu/ingleseuef indicando su usuario seguido de @alu.comillas.edu (ejemplo: 202300000@alu.comillas.edu).</li>
                                </ul>
                            </div>
                            
                            <!-- Nota adicional -->
                            <p style="font-size: 14px; color: #999999; line-height: 1.6; margin: 0 0 20px 0;">
                                Si no puede asistir a la entrevista, por favor envíe un correo a entrevistas@comillas.edu
                                o llame al 987654321 con la mayor brevedad posible para poder reasignar la cita.
                            </p>
                            
                            <!-- Firma -->
                            <div style="border-top: 2px solid #e0e0e0; padding-top: 20px; margin-top: 30px;">
                                <p style="margin: 0 0 5px 0; font-size: 16px; color: #333333; font-weight: 600;">
                                    Atentamente,
                                </p>
                                <p style="margin: 0; font-size: 14px; color: #666666;">
                                    Sistema de Gestión de Entrevistas<br>
                                    {entrevistador.email if entrevistador and entrevistador.email else 'entrevistas@comillas.edu'}
                                </p>
                            </div>
                            
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td bgcolor="#f8f9fa" style="padding: 20px 30px; text-align: center; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; font-size: 12px; color: #999999; line-height: 1.5;">
                                Este es un mensaje automático, por favor no responda directamente a este correo.<br>
                                Para cualquier consulta, contacte con el entrevistador indicado.
                            </p>
                        </td>
                    </tr>
                    
                </table>
                
            </td>
        </tr>
    </table>
</body>
</html>
    """
    
    return subject, html


def generar_email_entrevistador(entrevistador, asignaciones):
    """
    Genera el HTML del email para un entrevistador con su resumen
    
    Args:
        entrevistador: Objeto Usuario (entrevistador)
        asignaciones: Lista de asignaciones del entrevistador
    
    Returns:
        tuple: (subject, html_body)
    """
    
    # Agrupar asignaciones por día
    from collections import defaultdict
    por_dia = defaultdict(list)
    
    for asig in asignaciones:
        fecha = asig.reserva.fecha
        por_dia[fecha].append(asig)
    
    # Ordenar fechas
    fechas_ordenadas = sorted(por_dia.keys())
    
    # Calcular semana
    if asignaciones:
        primera_fecha = min(a.reserva.fecha for a in asignaciones)
        semana_num = primera_fecha.isocalendar()[1]
        año = primera_fecha.year
    else:
        semana_num = 0
        año = 2025
    
    subject = f"Calendario de Entrevistas - Semana {semana_num}"
    
    # Generar filas de la tabla
    filas_html = ""
    dias_esp = {
        0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 
        3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'
    }
    
    for fecha in fechas_ordenadas:
        asigs_dia = sorted(por_dia[fecha], key=lambda x: x.hora_exacta if x.hora_exacta else x.reserva.hora_inicio)
        
        # Nombre del día
        dia_semana = dias_esp[fecha.weekday()]
        fecha_str = fecha.strftime('%d/%m/%Y')
        
        # Primera fila del día (con rowspan)
        primera_asig = asigs_dia[0]
        hora = primera_asig.hora_exacta.strftime('%H:%M') if primera_asig.hora_exacta else primera_asig.reserva.hora_inicio.strftime('%H:%M')

        candidato = primera_asig.candidato
        email_candidato = candidato.email or 'No disponible'
        telefono_candidato = candidato.telefono or 'No disponible'
        
        filas_html += f"""
        <tr style="border-bottom: 1px solid #e0e0e0;">
            <td rowspan="{len(asigs_dia)}" style="padding: 15px; background-color: #f8f9fa; font-weight: 600; text-align: center; border-right: 2px solid #dee2e6;">
                {dia_semana}<br>
                <span style="font-size: 12px; color: #666; font-weight: normal;">{fecha_str}</span>
            </td>
            <td style="padding: 15px; font-weight: 600; color: #4472C4;">{hora}</td>
            <td style="padding: 15px;">
                <strong>{candidato.nombre} {candidato.apellidos}</strong><br>
                <small style="color: #666;">📧 {email_candidato}</small><br>
                <small style="color: #666;">📞 {telefono_candidato}</small>
            </td>
            <td style="padding: 15px; font-size: 12px; color: #666;">
                {primera_asig.candidato.primera_opcion[:50] + '...' if primera_asig.candidato.primera_opcion and len(primera_asig.candidato.primera_opcion) > 50 else primera_asig.candidato.primera_opcion or '-'}
            </td>
        </tr>
        """
        
        # Filas adicionales del mismo día
        for asig in asigs_dia[1:]:
            hora = asig.hora_exacta.strftime('%H:%M') if asig.hora_exacta else asig.reserva.hora_inicio.strftime('%H:%M')
            candidato = asig.candidato
            email_candidato = candidato.email or 'No disponible'
            telefono_candidato = candidato.telefono or 'No disponible'
            filas_html += f"""
        <tr style="border-bottom: 1px solid #e0e0e0;">
            <td style="padding: 15px; font-weight: 600; color: #4472C4;">{hora}</td>
            <td style="padding: 15px;">{asig.candidato.nombre} {asig.candidato.apellidos}</td>
            <td style="padding: 15px;">
                <strong>{candidato.nombre} {candidato.apellidos}</strong><br>
                <small style="color: #666;">📧 {email_candidato}</small><br>
                <small style="color: #666;">📞 {telefono_candidato}</small>
            </td>
            <td style="padding: 15px; text-align: center;">
            <td style="padding: 15px; font-size: 12px; color: #666;">
                {asig.candidato.primera_opcion[:50] + '...' if asig.candidato.primera_opcion and len(asig.candidato.primera_opcion) > 50 else asig.candidato.primera_opcion or '-'}
            </td>
        </tr>
            """
    
    html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f4f4f4">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                
                <table width="800" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff" 
                       style="border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td bgcolor="#70AD47" style="padding: 40px 30px; text-align: center; border-radius: 8px 8px 0 0;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 600;">
                                📅 Calendario de Entrevistas
                            </h1>
                            <p style="color: #ffffff; margin: 10px 0 0 0; font-size: 18px;">
                                Semana {semana_num} - {año}
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Contenido -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            
                            <p style="font-size: 16px; color: #333333; line-height: 1.6; margin: 0 0 10px 0;">
                                Hola <strong>{entrevistador.username}</strong>,
                            </p>
                            
                            <p style="font-size: 16px; color: #666666; line-height: 1.6; margin: 0 0 30px 0;">
                                Le adjuntamos su calendario de entrevistas para la próxima semana. 
                                En total tiene <strong>{len(asignaciones)} entrevistas</strong> programadas.
                            </p>
                            
                            <!-- Tabla de entrevistas -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" 
                                   style="border: 1px solid #dee2e6; border-radius: 8px; overflow: hidden;">
                                
                                <!-- Header de tabla -->
                                <tr style="background-color: #70AD47; color: white;">
                                    <th style="padding: 15px; text-align: center; font-weight: 600;">Día</th>
                                    <th style="padding: 15px; text-align: left; font-weight: 600;">Hora</th>
                                    <th style="padding: 15px; text-align: left; font-weight: 600;">Candidato</th>
                                    <th style="padding: 15px; text-align: left; font-weight: 600;">Grado Solicitado</th>
                                </tr>
                                
                                <!-- Filas de datos -->
                                {filas_html}
                                
                            </table>
                            
                            <!-- Resumen -->
                            <div style="background-color: #e7f3ff; border-left: 4px solid #2196F3; padding: 20px; margin: 30px 0; border-radius: 4px;">
                                <p style="margin: 0 0 10px 0; font-size: 16px; color: #0d47a1; font-weight: 600;">
                                    📊 Resumen:
                                </p>
                                <ul style="margin: 0; padding-left: 20px; color: #1565c0; line-height: 1.8;">
                                    <li>Total de entrevistas: <strong>{len(asignaciones)}</strong></li>
                                    <li>Días con entrevistas: <strong>{len(fechas_ordenadas)}</strong></li>
                                    <li>Primera entrevista: <strong>{fechas_ordenadas[0].strftime('%d/%m/%Y') if fechas_ordenadas else '-'}</strong></li>
                                    <li>Última entrevista: <strong>{fechas_ordenadas[-1].strftime('%d/%m/%Y') if fechas_ordenadas else '-'}</strong></li>
                                </ul>
                            </div>
                            
                            <!-- Nota -->
                            <p style="font-size: 14px; color: #999999; line-height: 1.6; margin: 30px 0 0 0;">
                                Si tiene alguna duda o necesita realizar cambios en el calendario, 
                                por favor contacte con el administrador del sistema.
                            </p>
                            
                            <!-- Firma -->
                            <div style="border-top: 2px solid #e0e0e0; padding-top: 20px; margin-top: 30px;">
                                <p style="margin: 0 0 5px 0; font-size: 16px; color: #333333; font-weight: 600;">
                                    Saludos cordiales,
                                </p>
                                <p style="margin: 0; font-size: 14px; color: #666666;">
                                    Sistema de Gestión de Entrevistas
                                </p>
                            </div>
                            
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td bgcolor="#f8f9fa" style="padding: 20px 30px; text-align: center; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; font-size: 12px; color: #999999; line-height: 1.5;">
                                Este es un mensaje automático del sistema de gestión de entrevistas.<br>
                                Para consultas, responda a este correo.
                            </p>
                        </td>
                    </tr>
                    
                </table>
                
            </td>
        </tr>
    </table>
</body>
</html>
    """
    
    return subject, html

# ====================================================================
# DECORADORES PARA PROTEGER RUTAS
# ====================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión para acceder a esta página', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión para acceder a esta página', 'error')
            return redirect(url_for('login'))
        
        usuario = Usuario.query.get(session['user_id'])
        if not usuario or usuario.rol != 'admin':
            flash('No tienes permisos para acceder a esta página', 'error')
            return redirect(url_for('reservas'))
        return f(*args, **kwargs)
    return decorated_function

# ====================================================================
# FUNCIONES DE LOGGING
# ====================================================================

def registrar_log(accion, entidad, entidad_id, descripcion, datos_anteriores=None, datos_nuevos=None, nivel='info', metadata=None):
    """
    Registra una acción en el log de auditoría
    
    Args:
        accion: 'crear', 'modificar', 'eliminar', 'asignar', 'enviar_email', etc.
        entidad: 'reserva', 'candidato', 'asignacion', 'usuario', etc.
        entidad_id: ID del objeto afectado
        descripcion: Descripción legible de la acción
        datos_anteriores: Dict con datos antes del cambio (se convierte a JSON)
        datos_nuevos: Dict con datos después del cambio (se convierte a JSON)
        nivel: 'info', 'warning', 'error', 'critical'
        metadata: Dict con información adicional
    """
    try:
        
        
        # Obtener usuario actual
        usuario_id = session.get('user_id')
        usuario_username = session.get('username', 'Sistema')
        
        # Obtener IP y User Agent
        ip_address = request.remote_addr if request else None
        user_agent = request.headers.get('User-Agent', '')[:255] if request else None
        
        # Convertir dicts a JSON
        datos_anteriores_json = json.dumps(datos_anteriores, default=str) if datos_anteriores else None
        datos_nuevos_json = json.dumps(datos_nuevos, default=str) if datos_nuevos else None
        metadata_json = json.dumps(metadata, default=str) if metadata else None
        
        log = LogActividad(
            fecha_hora=datetime.utcnow(),
            usuario_id=usuario_id,
            usuario_username=usuario_username,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            descripcion=descripcion,
            datos_anteriores=datos_anteriores_json,
            datos_nuevos=datos_nuevos_json,
            ip_address=ip_address,
            user_agent=user_agent,
            nivel=nivel,
            metadata_extra=metadata_json
        )
        
        db.session.add(log)
        db.session.commit()
        
    except Exception as e:
        print(f"Error al registrar log: {e}")
        # No fallar la operación principal si falla el log
        db.session.rollback()


def obtener_cambios(obj_anterior, obj_nuevo, campos):
    """
    Compara dos objetos y devuelve un dict con los cambios
    
    Args:
        obj_anterior: Objeto antes del cambio
        obj_nuevo: Objeto después del cambio
        campos: Lista de nombres de campos a comparar
    
    Returns:
        Tuple (datos_anteriores, datos_nuevos) con solo los campos que cambiaron
    """
    datos_anteriores = {}
    datos_nuevos = {}
    
    for campo in campos:
        valor_anterior = getattr(obj_anterior, campo, None)
        valor_nuevo = getattr(obj_nuevo, campo, None)
        
        # Convertir a string para comparación
        valor_anterior_str = str(valor_anterior) if valor_anterior is not None else None
        valor_nuevo_str = str(valor_nuevo) if valor_nuevo is not None else None
        
        if valor_anterior_str != valor_nuevo_str:
            datos_anteriores[campo] = valor_anterior_str
            datos_nuevos[campo] = valor_nuevo_str
    
    return datos_anteriores if datos_anteriores else None, datos_nuevos if datos_nuevos else None


# ====================================================================
# RUTAS PRINCIPALES
# ====================================================================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('reservas'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('reservas'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        usuario = Usuario.query.filter_by(username=username).first()
        
        if usuario and usuario.activo and check_password_hash(usuario.password, password):
            session['user_id'] = usuario.id
            session['username'] = usuario.username
            session['rol'] = usuario.rol
            registrar_log(
                accion='login',
                entidad='usuario',
                entidad_id=usuario.id,
                descripcion=f'Usuario {usuario.username} inició sesión',
                nivel='info'
            )

            flash(f'¡Bienvenido, {usuario.username}!', 'success')
            return redirect(url_for('reservas'))
        else:
            registrar_log(
                accion='login_fallido',
                entidad='usuario',
                entidad_id=None,
                descripcion=f'Intento de login fallido para usuario: {username}',
                nivel='warning'
            )
            if usuario and not usuario.activo:
                error = 'Tu cuenta ha sido desactivada. Contacta con el administrador.'
            else:
                error = 'Usuario o contraseña incorrectos'
            return render_template('login.html', error=error)
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Cerrar sesión del usuario"""
    
    # Registrar en logs antes de limpiar la sesión
    if 'user_id' in session:
        registrar_log(
            accion='logout',
            entidad='usuario',
            entidad_id=session.get('user_id'),
            descripcion=f'Usuario cerró sesión: {session.get("username")}',
            nivel='info'
        )
    
    # Limpiar sesión
    session.clear()
    
    flash('Sesión cerrada correctamente', 'success')
    return redirect(url_for('login'))

@app.route('/registro', methods=['GET', 'POST'])
@admin_required
def registro():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        rol = request.form.get('rol', 'profesor')
        sedes_seleccionadas = request.form.getlist('sedes[]')
        
        # Validaciones
        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'error')
            return render_template('registro.html', sedes=SEDES_DISPONIBLES)  # ✅ MODIFICADO
        
        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'error')
            return render_template('registro.html', sedes=SEDES_DISPONIBLES)
        
        # Verificar si ya existe
        if Usuario.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe', 'error')
            return render_template('registro.html', sedes=SEDES_DISPONIBLES)  # ✅ MODIFICADO
        
        if Usuario.query.filter_by(email=email).first():
            flash('El email ya está registrado', 'error')
            return render_template('registro.html', sedes=SEDES_DISPONIBLES)  # ✅ MODIFICADO
        
        # ✅ NUEVO: Validar sede si es profesor
        if rol == 'profesor' and not sedes_seleccionadas:
            flash('Debes seleccionar al menos una sede para el profesor', 'error')
            return render_template('registro.html', 
                                 username=session['username'],
                                 sedes=SEDES_DISPONIBLES)
        
        # Crear usuario
        nuevo_usuario = Usuario(
            username=username,
            email=email,
            password=generate_password_hash(password),
            rol=rol,
            sede=sedes_seleccionadas[0] if sedes_seleccionadas else None  # Primera como principal
        )
        
        db.session.add(nuevo_usuario)
        db.session.flush()  # Para obtener el ID
        
        # ✅ NUEVO: Asignar sedes al profesor
        if rol == 'profesor' and sedes_seleccionadas:
            for sede_nombre in sedes_seleccionadas:
                sede = Sede.query.filter_by(nombre=sede_nombre).first()
                if sede:
                    nuevo_usuario.sedes.append(sede)
        
        db.session.commit()
        
        # Registrar en logs
        registrar_log(
            accion='crear',
            entidad='usuario',
            entidad_id=nuevo_usuario.id,
            descripcion=f'Usuario creado: {username} ({rol}) - Sedes: {", ".join(sedes_seleccionadas)}',
            datos_nuevos={
                'username': username,
                'email': email,
                'rol': rol,
                'sedes': sedes_seleccionadas
            },
            nivel='info'
        )
        
        flash(f'Usuario {username} creado correctamente', 'success')
        return redirect(url_for('admin_usuarios'))
    
    return render_template('registro.html', 
                         username=session['username'], 
                         sedes=SEDES_DISPONIBLES)


# ====================================================================
# RUTAS DE RESERVAS
# ====================================================================

@app.route('/reservas')
@login_required
def reservas():
    fecha_str = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    fecha_base = datetime.strptime(fecha_str, '%Y-%m-%d')
    
    dias_hasta_lunes = fecha_base.weekday()
    lunes = fecha_base - timedelta(days=dias_hasta_lunes)
    
    espacios_db = Espacio.query.order_by(Espacio.id).limit(5).all()
    
    dias_semana = []
    nombres_dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
    
    for i, espacio in enumerate(espacios_db):
        dia = lunes + timedelta(days=i)
        dias_semana.append({
            'id': espacio.id,
            'nombre': nombres_dias[i] if i < len(nombres_dias) else espacio.nombre,
            'fecha': dia.strftime('%Y-%m-%d'),
            'fecha_completa': dia.strftime('%d/%m/%Y'),
            'color': espacio.color if espacio.color else '#667eea'
        })
    
    semana_anterior = (lunes - timedelta(days=7)).strftime('%Y-%m-%d')
    semana_siguiente = (lunes + timedelta(days=7)).strftime('%Y-%m-%d')
    
    usuarios_lista = []
    if session.get('rol') == 'admin':
        usuarios_lista = Usuario.query.filter_by(activo=True).order_by(Usuario.username).all()
        usuarios_lista = [{'id': u.id, 'username': u.username, 'email': u.email} for u in usuarios_lista]
    
    return render_template('reservas.html', 
                         espacios=dias_semana,
                         fecha_seleccionada=fecha_str,
                         semana_anterior=semana_anterior,
                         semana_siguiente=semana_siguiente,
                         fecha_inicio_semana=lunes.strftime('%d/%m/%Y'),
                         fecha_fin_semana=(lunes + timedelta(days=4)).strftime('%d/%m/%Y'),
                         username=session['username'],
                         es_admin=session.get('rol') == 'admin',
                         usuarios_lista=usuarios_lista)

@app.route('/api/franjas/<int:dia_id>')
@login_required
def obtener_franjas(dia_id):
    fecha_str = request.args.get('fecha')
    if not fecha_str:
        return jsonify({'error': 'Fecha no proporcionada'}), 400
    
    fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    
    franjas = []
    
    # Franjas de mañana: 10:00 - 13:00
    franjas_manana = [
        ('10:00', '10:30'),
        ('10:30', '11:00'),
        ('11:00', '11:30'),
        ('11:30', '12:00'),
        ('12:00', '12:30'),
        ('12:30', '13:00')
    ]
    
    # Franjas de tarde: 15:00 - 19:00
    franjas_tarde = [
        ('15:00', '15:30'),
        ('15:30', '16:00'),
        ('16:00', '16:30'),
        ('16:30', '17:00'),
        ('17:00', '17:30'),
        ('17:30', '18:00'),
        ('18:00', '18:30'),
        ('18:30', '19:00')
    ]
    
    todas_franjas = franjas_manana + franjas_tarde
    
    for franja_inicio, franja_fin in todas_franjas:
        reservas = Reserva.query.filter_by(
            espacio_id=dia_id,
            fecha=fecha,
            hora_inicio=datetime.strptime(franja_inicio, '%H:%M').time()
        ).all()
        
        num_reservas = len(reservas)
        
        tiene_secundaria = any(r.prioridad == 'secundaria' for r in reservas)
        solo_secundarias = all(r.prioridad == 'secundaria' for r in reservas) if num_reservas > 0 else False
        
        mis_reservas = [r for r in reservas if r.usuario_id == session.get('user_id')]
        tiene_mi_reserva = len(mis_reservas) > 0
        
        reservas_info = []
        for r in reservas:
            reservas_info.append({
                'id': r.id,
                'usuario': r.usuario.username,
                'notas': r.notas,
                'es_mia': r.usuario_id == session.get('user_id'),
                'prioridad': r.prioridad
            })
        
        franjas.append({
            'hora_inicio': franja_inicio,
            'hora_fin': franja_fin,
            'num_reservas': num_reservas,
            'disponible': num_reservas == 0,
            'parcial': num_reservas == 1,
            'completa': num_reservas >= 2,
            'tiene_mi_reserva': tiene_mi_reserva,
            'tiene_secundaria': tiene_secundaria,
            'solo_secundarias': solo_secundarias,
            'reservas': reservas_info,
            'puede_reservar': num_reservas < 2
        })
    
    return jsonify(franjas)

@app.route('/api/reservar', methods=['POST'])
@login_required
def hacer_reserva():
    data = request.json
    espacio_id = data['espacio_id']
    fecha_str = data['fecha']
    hora_inicio_str = data['hora_inicio']
    hora_fin_str = data['hora_fin']
    notas = data.get('notas', '')
    prioridad = data.get('prioridad', 'normal')  # ✅ NUEVO
    
    usuario_id_destino = data.get('usuario_id', session['user_id'])
    
    if usuario_id_destino != session['user_id'] and session.get('rol') != 'admin':
        return jsonify({'error': 'No tienes permiso para reservar en nombre de otros usuarios'}), 403
    
    fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time()
    hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time()
    
    # Verificar que no existan más de 2 reservas
    reservas_existentes = Reserva.query.filter_by(
        espacio_id=espacio_id,
        fecha=fecha,
        hora_inicio=hora_inicio
    ).all()
    
    if len(reservas_existentes) >= 2:
        return jsonify({'error': 'Esta franja ya tiene el máximo de 2 reservas'}), 400
    
    # Verificar que el usuario no tenga ya una reserva en esta franja
    reserva_usuario = Reserva.query.filter_by(
        usuario_id=usuario_id_destino,
        espacio_id=espacio_id,
        fecha=fecha,
        hora_inicio=hora_inicio
    ).first()
    
    if reserva_usuario:
        return jsonify({'error': 'Ya tienes una reserva en esta franja'}), 400
    
    nueva_reserva = Reserva(
        usuario_id=usuario_id_destino,
        espacio_id=espacio_id,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        notas=notas,
        prioridad=prioridad,
        creado_por_admin=session['user_id'] if usuario_id_destino != session['user_id'] else None
    )
    
    db.session.add(nueva_reserva)
    db.session.commit()

    # ✅ NUEVO: Registrar creación de reserva
    usuario_destino = Usuario.query.get(usuario_id_destino)
    espacio = Espacio.query.get(espacio_id)
    
    registrar_log(
        accion='crear',
        entidad='reserva',
        entidad_id=nueva_reserva.id,
        descripcion=f'Reserva creada: {usuario_destino.username} - {espacio.nombre if espacio else "N/A"} - {fecha_str} {hora_inicio_str}',
        datos_nuevos={
            'usuario': usuario_destino.username,
            'fecha': fecha_str,
            'hora_inicio': hora_inicio_str,
            'hora_fin': hora_fin_str,
            'prioridad': prioridad,
            'notas': notas
        },
        nivel='info'
    )
    
    if usuario_id_destino != session['user_id']:
        usuario_destino = Usuario.query.get(usuario_id_destino)
        mensaje = f'Reserva creada correctamente para {usuario_destino.username}'
    else:
        prioridad_texto = "secundaria" if prioridad == 'secundaria' else "normal"
        mensaje = f'Reserva {prioridad_texto} realizada correctamente'
    
    return jsonify({'success': True, 'mensaje': mensaje})

@app.route('/api/actualizar-enlace-personal', methods=['POST'])
@login_required
def actualizar_enlace_personal():
    """Actualiza el enlace personal de videollamada del usuario"""
    
    try:
        data = request.json
        enlace = data.get('enlace', '').strip()
        
        # Obtener usuario actual
        usuario = Usuario.query.get(session['user_id'])
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Validar formato de URL
        if enlace and not (enlace.startswith('http://') or enlace.startswith('https://')):
            enlace = 'https://' + enlace
        
        # Actualizar enlace
        usuario.enlace_videollamada_personal = enlace if enlace else None
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensaje': 'Enlace personal actualizado correctamente',
            'enlace': usuario.enlace_videollamada_personal
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error al actualizar enlace: {str(e)}'}), 500


@app.route('/perfil')
@login_required
def mi_perfil():
    """Vista del perfil del usuario"""
    
    usuario = Usuario.query.get(session['user_id'])
    
    if not usuario:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('login'))
    
    # Calcular estadísticas
    from datetime import date
    
    # Total de reservas del usuario
    total_reservas = Reserva.query.filter_by(usuario_id=usuario.id).count()
    
    # Reservas futuras (fecha >= hoy)
    hoy = date.today()
    reservas_futuras = Reserva.query.filter(
        Reserva.usuario_id == usuario.id,
        Reserva.fecha >= hoy
    ).count()
    
    # Entrevistas realizadas (asignaciones donde el usuario es entrevistador)
    entrevistas_realizadas = Asignacion.query.filter_by(
        entrevistador_id=usuario.id
    ).count()
    
    stats = {
        'total_reservas': total_reservas,
        'reservas_futuras': reservas_futuras,
        'entrevistas_realizadas': entrevistas_realizadas
    }
    
    return render_template('perfil.html',
                         usuario=usuario,
                         username=usuario.username,
                         email=usuario.email,
                         rol=usuario.rol,
                         fecha_creacion=usuario.fecha_creacion,
                         enlace_videollamada=usuario.enlace_videollamada_personal,
                         sede=usuario.sede,
                         stats=stats)

@app.route('/api/cancelar', methods=['POST'])
@login_required
def cancelar_reserva():
    data = request.json
    reserva_id = data.get('reserva_id')
    
    if reserva_id:
        reserva = Reserva.query.get(reserva_id)
    else:
        espacio_id = data['espacio_id']
        fecha_str = data['fecha']
        hora_inicio_str = data['hora_inicio']
        
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time()
        
        reserva = Reserva.query.filter_by(
            espacio_id=espacio_id,
            fecha=fecha,
            hora_inicio=hora_inicio
        ).first()
    
    if not reserva:
        return jsonify({'error': 'Reserva no encontrada'}), 404
    
    if reserva.usuario_id != session['user_id'] and session.get('rol') != 'admin':
        return jsonify({'error': 'No tienes permiso para cancelar esta reserva'}), 403
    datos_reserva = {
        'id': reserva.id,
        'usuario': reserva.usuario.username,
        'fecha': reserva.fecha.strftime('%d/%m/%Y'),
        'hora_inicio': reserva.hora_inicio.strftime('%H:%M'),
        'prioridad': reserva.prioridad,
        'espacio': reserva.espacio.nombre if reserva.espacio else 'N/A'
    }
    
    registrar_log(
        accion='eliminar',
        entidad='reserva',
        entidad_id=reserva.id,
        descripcion=f'Reserva cancelada: {datos_reserva["usuario"]} - {datos_reserva["espacio"]} - {datos_reserva["fecha"]} {datos_reserva["hora_inicio"]}',
        datos_anteriores=datos_reserva,
        nivel='info'
    )

    db.session.delete(reserva)
    db.session.commit()
    
    return jsonify({'success': True, 'mensaje': 'Reserva cancelada correctamente'})

@app.route('/mis-reservas')
@login_required
def mis_reservas():
    hoy = datetime.now().date()
    reservas_futuras = Reserva.query.filter(
        Reserva.usuario_id == session['user_id'],
        Reserva.fecha >= hoy
    ).order_by(Reserva.fecha, Reserva.hora_inicio).all()
    
    reservas_pasadas = Reserva.query.filter(
        Reserva.usuario_id == session['user_id'],
        Reserva.fecha < hoy
    ).order_by(Reserva.fecha.desc(), Reserva.hora_inicio.desc()).limit(10).all()
    
    return render_template('mis_reservas.html', 
                         reservas_futuras=reservas_futuras,
                         reservas_pasadas=reservas_pasadas,
                         username=session['username'],
                         es_admin=session.get('rol') == 'admin')


# ====================================================================
# RUTAS DE ADMINISTRACIÓN
# ====================================================================

@app.route('/admin/usuarios')
@admin_required
def admin_usuarios():
    usuarios = Usuario.query.order_by(Usuario.fecha_creacion.desc()).all()
    return render_template('admin_usuarios.html', 
                         usuarios=usuarios,
                         username=session['username'],
                         sedes=SEDES_DISPONIBLES)

@app.route('/admin/usuario/toggle/<int:usuario_id>', methods=['POST'])
@admin_required
def toggle_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    
    if usuario.id == session['user_id']:
        return jsonify({'error': 'No puedes desactivar tu propia cuenta'}), 400
    
    usuario.activo = not usuario.activo
    db.session.commit()
    
    estado = 'activado' if usuario.activo else 'desactivado'
    return jsonify({
        'success': True, 
        'mensaje': f'Usuario {usuario.username} {estado}',
        'activo': usuario.activo
    })

@app.route('/admin/usuarios/editar/<int:usuario_id>', methods=['GET', 'POST'])
@admin_required
def editar_usuario(usuario_id):
    """Editar información de un usuario"""
    
    usuario = Usuario.query.get_or_404(usuario_id)
    
    if request.method == 'POST':
        email_nuevo = request.form.get('email')
        rol_nuevo = request.form.get('rol')
        sedes_seleccionadas = request.form.getlist('sedes')  # ✅ CAMBIO: obtener lista de sedes
        
        # Guardar valores anteriores para el log
        datos_anteriores = {
            'email': usuario.email,
            'rol': usuario.rol,
            'sedes': [s.nombre for s in usuario.sedes]
        }
        
        # Actualizar email y rol
        usuario.email = email_nuevo
        usuario.rol = rol_nuevo
        
        # ✅ CAMBIO: Actualizar sedes (relación muchos-a-muchos)
        if rol_nuevo == 'profesor' and sedes_seleccionadas:
            # Limpiar sedes actuales
            usuario.sedes = []
            
            # Añadir las nuevas sedes seleccionadas
            for sede_nombre in sedes_seleccionadas:
                sede = Sede.query.filter_by(nombre=sede_nombre).first()
                if sede:
                    usuario.sedes.append(sede)
        else:
            # Si es admin, limpiar sedes
            usuario.sedes = []
        
        db.session.commit()
        
        # ✅ Registrar cambio
        datos_nuevos = {
            'email': email_nuevo,
            'rol': rol_nuevo,
            'sedes': [s.nombre for s in usuario.sedes] if rol_nuevo == 'profesor' else []
        }
        
        registrar_log(
            accion='modificar',
            entidad='usuario',
            entidad_id=usuario.id,
            descripcion=f'Usuario modificado: {usuario.username}',
            datos_anteriores=datos_anteriores,
            datos_nuevos=datos_nuevos,
            nivel='info'
        )
        
        flash(f'Usuario {usuario.username} actualizado correctamente', 'success')
        return redirect(url_for('admin_usuarios'))
    
    # ✅ CAMBIO: Pasar todas las sedes disponibles
    todas_sedes = Sede.query.filter_by(activa=True).all()
    
    return render_template('editar_usuario.html', 
                         usuario=usuario, 
                         username=session['username'],
                         todas_sedes=todas_sedes)

@app.route('/admin/usuario/eliminar/<int:usuario_id>', methods=['POST'])
@admin_required
def eliminar_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    
    if usuario.id == session['user_id']:
        return jsonify({'error': 'No puedes eliminar tu propia cuenta'}), 400
    
    Reserva.query.filter_by(usuario_id=usuario_id).delete()
    
    db.session.delete(usuario)
    db.session.commit()
    
    return jsonify({'success': True, 'mensaje': f'Usuario {usuario.username} eliminado correctamente'})

@app.route('/admin/usuario/cambiar-rol/<int:usuario_id>', methods=['POST'])
@admin_required
def cambiar_rol_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    
    if usuario.id == session['user_id']:
        return jsonify({'error': 'No puedes cambiar tu propio rol'}), 400
    
    nuevo_rol = 'admin' if usuario.rol == 'profesor' else 'profesor'
    usuario.rol = nuevo_rol
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'mensaje': f'Rol de {usuario.username} cambiado a {nuevo_rol}',
        'rol': nuevo_rol
    })

@app.route('/admin/estadisticas')
@admin_required
def admin_estadisticas():
    total_usuarios = Usuario.query.count()
    total_profesores = Usuario.query.filter_by(rol='profesor').count()
    total_admins = Usuario.query.filter_by(rol='admin').count()
    usuarios_activos = Usuario.query.filter_by(activo=True).count()
    
    total_reservas = Reserva.query.count()
    
    from sqlalchemy import func
    reservas_por_usuario = db.session.query(
        Usuario.username,
        func.count(Reserva.id).label('total')
    ).join(Reserva).group_by(Usuario.username).order_by(func.count(Reserva.id).desc()).limit(10).all()
    
    return render_template('admin_estadisticas.html',
                         total_usuarios=total_usuarios,
                         total_profesores=total_profesores,
                         total_admins=total_admins,
                         usuarios_activos=usuarios_activos,
                         total_reservas=total_reservas,
                         reservas_por_usuario=reservas_por_usuario,
                         username=session['username'])

@app.route('/admin/todas-reservas')
@admin_required
def todas_reservas():
    usuario_filtro = request.args.get('usuario', '')
    dia_filtro = request.args.get('dia', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    
    query = Reserva.query
    
    if usuario_filtro:
        query = query.filter(Reserva.usuario_id == int(usuario_filtro))
    
    if dia_filtro:
        query = query.filter(Reserva.espacio_id == int(dia_filtro))
    
    if fecha_desde:
        fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        query = query.filter(Reserva.fecha >= fecha_desde_obj)
    
    if fecha_hasta:
        fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
        query = query.filter(Reserva.fecha <= fecha_hasta_obj)
    
    reservas = query.order_by(Reserva.fecha.desc(), Reserva.hora_inicio.desc()).all()
    
    usuarios = Usuario.query.filter_by(activo=True).order_by(Usuario.username).all()
    espacios = Espacio.query.order_by(Espacio.id).all()
    
    total_reservas = len(reservas)
    usuarios_unicos = len(set(r.usuario_id for r in reservas))
    dias_con_reservas = len(set(r.espacio_id for r in reservas))
    
    return render_template('todas_reservas.html',
                         reservas=reservas,
                         usuarios=usuarios,
                         espacios=espacios,
                         total_reservas=total_reservas,
                         usuarios_unicos=usuarios_unicos,
                         dias_con_reservas=dias_con_reservas,
                         usuario_filtro=usuario_filtro,
                         dia_filtro=dia_filtro,
                         fecha_desde=fecha_desde,
                         fecha_hasta=fecha_hasta,
                         username=session['username'])

# ====================================================================

# RUTAS DE ASIGNACIÓN Y CARGA DE FICHEROS

# ====================================================================

@app.route('/admin/candidatos')
@admin_required
def admin_candidatos():
    """Vista principal de gestión de candidatos"""
    # Obtener estadísticas generales
    total_candidatos = Candidato.query.count()
    candidatos_pendientes = Candidato.query.filter_by(estado='pendiente').count()
    candidatos_asignados = Candidato.query.filter_by(estado='asignado').count()
    candidatos_entrevistados = Candidato.query.filter_by(estado='entrevistado').count()
    
    # Obtener semanas con candidatos
    from sqlalchemy import func
    semanas_con_candidatos = db.session.query(
        Candidato.semana_carga,
        func.count(Candidato.id).label('total'),
        func.sum(db.case((Candidato.estado == 'pendiente', 1), else_=0)).label('pendientes'),
        func.sum(db.case((Candidato.estado == 'asignado', 1), else_=0)).label('asignados')
    ).group_by(Candidato.semana_carga)\
     .order_by(Candidato.semana_carga.desc())\
     .all()
    
    # Últimas cargas de Excel
    ultimas_cargas = CargaExcel.query.order_by(CargaExcel.fecha_carga.desc()).limit(5).all()
    
    # Últimos logs de asignación
    ultimos_logs = LogAsignacion.query.order_by(LogAsignacion.fecha_ejecucion.desc()).limit(5).all()
    
    # Lista de semanas disponibles para selector
    semanas_disponibles = obtener_semanas_disponibles()
    
    return render_template('admin_candidatos.html',
                         total_candidatos=total_candidatos,
                         candidatos_pendientes=candidatos_pendientes,
                         candidatos_asignados=candidatos_asignados,
                         candidatos_entrevistados=candidatos_entrevistados,
                         semanas_con_candidatos=semanas_con_candidatos,
                         ultimas_cargas=ultimas_cargas,
                         ultimos_logs=ultimos_logs,
                         semanas_disponibles=semanas_disponibles,
                         username=session['username'])

@app.route('/admin/candidatos/ejecutar-asignacion', methods=['POST'])
@admin_required
def ejecutar_asignacion():
    """Ejecuta el algoritmo de asignación automática con filtrado por sedes"""
    
    try:
        data = request.json
        semana_carga = data.get('semana_carga')
        max_por_profesor = data.get('max_por_profesor')
        
        if not semana_carga:
            return jsonify({'error': 'Debe especificar una semana de carga'}), 400
        
        # Calcular semana de entrevistas (siguiente)
        año, semana_num = semana_carga.split('-W')
        primer_dia = datetime.strptime(f'{año}-W{semana_num}-1', '%Y-W%W-%w').date()
        siguiente_lunes = primer_dia + timedelta(days=7)
        semana_entrevistas = siguiente_lunes.strftime('%Y-W%W')
        
        # Verificar candidatos pendientes
        candidatos_pendientes = Candidato.query\
            .filter_by(semana_carga=semana_carga, estado='pendiente')\
            .count()
        
        if candidatos_pendientes == 0:
            return jsonify({
                'error': f'No hay candidatos pendientes para la semana {semana_carga}',
                'candidatos_pendientes': 0
            }), 400
        
        # Calcular rango de fechas para semana de entrevistas
        año_ent, semana_num_ent = semana_entrevistas.split('-W')
        primer_dia_ent = datetime.strptime(f'{año_ent}-W{semana_num_ent}-1', '%Y-W%W-%w').date()
        viernes_ent = primer_dia_ent + timedelta(days=4)
        
        # Verificar reservas disponibles
        reservas = Reserva.query\
            .filter(Reserva.fecha >= primer_dia_ent)\
            .filter(Reserva.fecha <= viernes_ent)\
            .count()
        
        if reservas == 0:
            return jsonify({
                'error': f'No hay reservas para la semana de entrevistas {semana_entrevistas} ({primer_dia_ent.strftime("%d/%m")} - {viernes_ent.strftime("%d/%m")})',
                'reservas_disponibles': 0
            }), 400
        
        inicio = datetime.now()
        
        # Obtener candidatos ordenados por nota
        candidatos = Candidato.query\
            .filter_by(semana_carga=semana_carga, estado='pendiente')\
            .order_by(Candidato.media_estudios.asc())\
            .all()
        
        # ✅ Agrupar candidatos por sede
        candidatos_por_sede = {}
        candidatos_sin_sede = []
        
        for candidato in candidatos:
            if candidato.sede:
                if candidato.sede not in candidatos_por_sede:
                    candidatos_por_sede[candidato.sede] = []
                candidatos_por_sede[candidato.sede].append(candidato)
            else:
                candidatos_sin_sede.append(candidato)
        
        # Obtener reservas con espacios
        reservas_obj = Reserva.query\
            .filter(Reserva.fecha >= primer_dia_ent)\
            .filter(Reserva.fecha <= viernes_ent)\
            .order_by(
                Reserva.prioridad.desc(),  # 'normal' antes que 'secundaria'
                Reserva.fecha, 
                Reserva.hora_inicio
            )\
            .all()
        
        # ✅ Agrupar reservas por sede del entrevistador
        reservas_por_sede = {}
        reservas_sin_sede = []
        
        for reserva in reservas_obj:
            entrevistador = Usuario.query.get(reserva.usuario_id)
            
            asignaciones_existentes = Asignacion.query.filter_by(reserva_id=reserva.id).count()
            espacios_libres = 2 - asignaciones_existentes
            
            if espacios_libres > 0:
                franja_info = {
                    'reserva': reserva,
                    'espacios_libres': espacios_libres,
                    'asignaciones_actuales': asignaciones_existentes,
                    'entrevistador_id': reserva.usuario_id
                }
                
                if entrevistador:
            # Obtener sedes del profesor (usando relación many-to-many)
                    if entrevistador.sedes:
                        sedes_profesor = [s.nombre for s in entrevistador.sedes]
                    elif entrevistador.sede:
                        sedes_profesor = [entrevistador.sede]
                    else:
                        sedes_profesor = []
                    
                    if sedes_profesor:
                        # Añadir esta franja a TODAS las sedes del profesor
                        for sede_nombre in sedes_profesor:
                            if sede_nombre not in reservas_por_sede:
                                reservas_por_sede[sede_nombre] = []
                            reservas_por_sede[sede_nombre].append(franja_info)
                    else:
                        reservas_sin_sede.append(franja_info)
                else:
                    reservas_sin_sede.append(franja_info)
        
        # Variables para tracking
        asignaciones_creadas = []
        asignaciones_por_profesor = {}
        stats_por_sede = {}
        
        # ✅ Asignar por sede
        for sede in SEDES_DISPONIBLES:
            candidatos_sede = candidatos_por_sede.get(sede, [])
            franjas_sede = reservas_por_sede.get(sede, [])
            
            if not candidatos_sede:
                stats_por_sede[sede] = {
                    'total_candidatos': 0,
                    'asignados': 0,
                    'sin_asignar': 0
                }
                continue
            
            if not franjas_sede:
                stats_por_sede[sede] = {
                    'total_candidatos': len(candidatos_sede),
                    'asignados': 0,
                    'sin_asignar': len(candidatos_sede)
                }
                continue
            
            asignados_sede = 0
            idx_candidato = 0
            idx_franja = 0
            
            # Asignar candidatos de esta sede
            while idx_candidato < len(candidatos_sede) and idx_franja < len(franjas_sede):
                candidato = candidatos_sede[idx_candidato]
                franja = franjas_sede[idx_franja]
                reserva = franja['reserva']
                entrevistador_id = franja['entrevistador_id']
                
                # Verificar límite por profesor
                if max_por_profesor:
                    actual = asignaciones_por_profesor.get(entrevistador_id, 0)
                    if actual >= int(max_por_profesor):
                        idx_franja += 1
                        continue
                
                # Determinar posición y minuto de inicio
                if franja['asignaciones_actuales'] == 0:
                    posicion = 1
                    minuto_inicio = 0
                else:
                    posicion = 2
                    minuto_inicio = 15
                
                # Calcular hora exacta
                hora_base = datetime.combine(reserva.fecha, reserva.hora_inicio)
                hora_exacta = hora_base + timedelta(minutes=minuto_inicio)
                
                # Crear asignación
                asignacion = Asignacion(
                    candidato_id=candidato.id,
                    reserva_id=reserva.id,
                    entrevistador_id=entrevistador_id,
                    posicion=posicion,
                    minuto_inicio=minuto_inicio,
                    estado='confirmado',
                    fecha_asignacion=datetime.now(),
                    asignado_por_admin_id=session['user_id']
                )
                
                db.session.add(asignacion)
                
                # Intentar asignar hora_exacta si existe como columna
                try:
                    if hasattr(type(asignacion), 'hora_exacta'):
                        attr = getattr(type(asignacion), 'hora_exacta')
                        if not isinstance(attr, property):
                            asignacion.hora_exacta = hora_exacta.time()
                except Exception as e:
                    print(f"Advertencia: No se pudo asignar hora_exacta: {e}")
                
                asignaciones_creadas.append({
                    'candidato_id': candidato.id,
                    'reserva_id': reserva.id,
                    'sede': sede
                })
                
                # Actualizar estado del candidato
                candidato.estado = 'asignado'
                
                # Actualizar contadores
                asignaciones_por_profesor[entrevistador_id] = asignaciones_por_profesor.get(entrevistador_id, 0) + 1
                franja['espacios_libres'] -= 1
                franja['asignaciones_actuales'] += 1
                asignados_sede += 1
                
                idx_candidato += 1
                
                if franja['espacios_libres'] == 0:
                    idx_franja += 1
            
            # Guardar estadísticas de esta sede
            stats_por_sede[sede] = {
                'total_candidatos': len(candidatos_sede),
                'asignados': asignados_sede,
                'sin_asignar': len(candidatos_sede) - asignados_sede
            }
        
        # ✅ Asignar candidatos sin sede a reservas sin sede (fallback)
        if candidatos_sin_sede and reservas_sin_sede:
            asignados_sin_sede = 0
            idx_candidato = 0
            idx_franja = 0
            
            while idx_candidato < len(candidatos_sin_sede) and idx_franja < len(reservas_sin_sede):
                candidato = candidatos_sin_sede[idx_candidato]
                franja = reservas_sin_sede[idx_franja]
                reserva = franja['reserva']
                entrevistador_id = franja['entrevistador_id']
                
                # Verificar límite por profesor
                if max_por_profesor:
                    actual = asignaciones_por_profesor.get(entrevistador_id, 0)
                    if actual >= int(max_por_profesor):
                        idx_franja += 1
                        continue
                
                # Determinar posición y minuto de inicio
                if franja['asignaciones_actuales'] == 0:
                    posicion = 1
                    minuto_inicio = 0
                else:
                    posicion = 2
                    minuto_inicio = 15
                
                # Calcular hora exacta
                hora_base = datetime.combine(reserva.fecha, reserva.hora_inicio)
                hora_exacta = hora_base + timedelta(minutes=minuto_inicio)
                
                # Crear asignación
                asignacion = Asignacion(
                    candidato_id=candidato.id,
                    reserva_id=reserva.id,
                    entrevistador_id=entrevistador_id,
                    posicion=posicion,
                    minuto_inicio=minuto_inicio,
                    estado='confirmado',
                    fecha_asignacion=datetime.now(),
                    asignado_por_admin_id=session['user_id']
                )
                
                db.session.add(asignacion)
                
                try:
                    if hasattr(type(asignacion), 'hora_exacta'):
                        attr = getattr(type(asignacion), 'hora_exacta')
                        if not isinstance(attr, property):
                            asignacion.hora_exacta = hora_exacta.time()
                except Exception as e:
                    print(f"Advertencia: No se pudo asignar hora_exacta: {e}")
                
                asignaciones_creadas.append({
                    'candidato_id': candidato.id,
                    'reserva_id': reserva.id,
                    'sede': 'Sin sede'
                })
                
                candidato.estado = 'asignado'
                asignaciones_por_profesor[entrevistador_id] = asignaciones_por_profesor.get(entrevistador_id, 0) + 1
                franja['espacios_libres'] -= 1
                franja['asignaciones_actuales'] += 1
                asignados_sin_sede += 1
                
                idx_candidato += 1
                
                if franja['espacios_libres'] == 0:
                    idx_franja += 1
            
            # Estadísticas de candidatos sin sede
            stats_por_sede['Sin sede'] = {
                'total_candidatos': len(candidatos_sin_sede),
                'asignados': asignados_sin_sede,
                'sin_asignar': len(candidatos_sin_sede) - asignados_sin_sede
            }
        elif candidatos_sin_sede:
            # Hay candidatos sin sede pero no hay reservas sin sede
            stats_por_sede['Sin sede'] = {
                'total_candidatos': len(candidatos_sin_sede),
                'asignados': 0,
                'sin_asignar': len(candidatos_sin_sede)
            }
        
        # Guardar cambios
        db.session.flush()
        
        # Crear log
        tiempo_total = (datetime.now() - inicio).total_seconds()
        
        log = LogAsignacion(
            fecha_ejecucion=datetime.now(),
            semana_objetivo=semana_carga,
            candidatos_procesados=len(candidatos),
            candidatos_filtrados=0,
            candidatos_asignados=len(asignaciones_creadas),
            candidatos_sin_asignar=len(candidatos) - len(asignaciones_creadas),
            franjas_utilizadas=len(set([a['reserva_id'] for a in asignaciones_creadas])),
            algoritmo_usado='asignacion_por_sedes',
            tiempo_ejecucion_segundos=round(tiempo_total, 2),
            estado='exito' if len(asignaciones_creadas) == len(candidatos) else 'parcial',
            mensaje=f'Asignación por sedes. Candidatos W{semana_carga.split("-W")[1]} → Entrevistas W{semana_entrevistas.split("-W")[1]}',
            ejecutado_por_usuario_id=session['user_id']
        )
        
        db.session.add(log)
        db.session.commit()
        
        # Registrar en logs de auditoría
        registrar_log(
            accion='asignacion_automatica',
            entidad='sistema',
            entidad_id=None,
            descripcion=f'Asignación automática por sedes ejecutada: {len(asignaciones_creadas)} candidatos asignados',
            datos_nuevos={
                'semana_carga': semana_carga,
                'semana_entrevistas': semana_entrevistas,
                'candidatos_asignados': len(asignaciones_creadas),
                'candidatos_sin_asignar': len(candidatos) - len(asignaciones_creadas),
                'stats_por_sede': stats_por_sede,
                'tiempo_segundos': round(tiempo_total, 2)
            },
            nivel='info'
        )
        
        return jsonify({
            'success': True,
            'mensaje': f'{len(asignaciones_creadas)} candidatos asignados correctamente',
            'candidatos_asignados': len(asignaciones_creadas),
            'candidatos_sin_asignar': len(candidatos) - len(asignaciones_creadas),
            'franjas_utilizadas': len(set([a['reserva_id'] for a in asignaciones_creadas])),
            'semana_carga': semana_carga,
            'semana_entrevistas': semana_entrevistas,
            'tiempo_segundos': round(tiempo_total, 2),
            'stats_por_sede': stats_por_sede
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error al ejecutar asignación: {str(e)}'}), 500

@app.route('/admin/candidatos/cargar-excel', methods=['POST'])
@admin_required
def cargar_excel_candidatos():
    """Procesa y carga un archivo Excel de candidatos"""
    
    # Verificar que se subió un archivo
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se ha seleccionado ningún archivo'}), 400
    
    file = request.files['archivo']
    
    if file.filename == '':
        return jsonify({'error': 'No se ha seleccionado ningún archivo'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Tipo de archivo no permitido. Solo se aceptan .xlsx y .xls'}), 400
    
    try:
        # Obtener parámetros
        semana = request.form.get('semana')
        umbral = float(request.form.get('umbral', 7.0))
        
        if not semana:
            return jsonify({'error': 'Debe especificar una semana'}), 400
        
        # Guardar archivo temporalmente
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_final = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename_final)
        file.save(filepath)
        
        # Calcular hash del archivo
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        archivo_hash = hash_md5.hexdigest()
        
        # Verificar si ya se cargó este archivo
        carga_existente = CargaExcel.query.filter_by(archivo_hash=archivo_hash).first()
        if carga_existente:
            os.remove(filepath)  # Eliminar archivo duplicado
            return jsonify({
                'error': f'Este archivo ya fue cargado el {carga_existente.fecha_carga.strftime("%d/%m/%Y %H:%M")}',
                'duplicado': True
            }), 400
        
        # Procesar Excel
        df = pd.read_excel(filepath, header=23)  # Fila 24 = índice 23
        
        # Verificar columnas necesarias
        columnas_necesarias = ['Solicitud', 'Apellidos', 'Nombre', 'Media estudios realizados', 'Primera opción','Email','Telefono']
        columnas_faltantes = [col for col in columnas_necesarias if col not in df.columns]
        
        if columnas_faltantes:
            os.remove(filepath)
            return jsonify({'error': f'Columnas faltantes: {", ".join(columnas_faltantes)}'}), 400
        
        # Procesar datos
        df_procesado = df[columnas_necesarias].copy()
        df_procesado.columns = [
            'solicitud',
            'apellidos',
            'nombre',
            'media_estudios',
            'primera_opcion',
            'email',
            'telefono'
        ]
        
        # Limpiar datos
        df_procesado = df_procesado.dropna(subset=['solicitud', 'apellidos', 'nombre', 'media_estudios'])
        df_procesado['solicitud'] = pd.to_numeric(df_procesado['solicitud'], errors='coerce')
        df_procesado['media_estudios'] = pd.to_numeric(df_procesado['media_estudios'], errors='coerce')
        df_procesado = df_procesado.dropna(subset=['solicitud', 'media_estudios'])
        
        # Convertir teléfono a string
        df_procesado['telefono'] = df_procesado['telefono'].apply(
            lambda x: str(int(x)) if pd.notna(x) and x != '' else None
        )
        
        # ✅ CORRECCIÓN: Detectar sede AQUÍ en df_procesado (antes de filtrar)
        df_procesado['sede'] = df_procesado['primera_opcion'].apply(detectar_sede_desde_primera_opcion)
        
        total_leidos = len(df)
        total_validos = len(df_procesado)
        
        # Filtrar por umbral (AHORA df_filtrado ya tiene la columna 'sede')
        df_filtrado = df_procesado[df_procesado['media_estudios'] < umbral].copy()
        
        # Añadir campos de gestión
        df_filtrado['estado'] = 'pendiente'
        df_filtrado['fecha_carga'] = datetime.now()
        df_filtrado['semana_carga'] = semana
        df_filtrado['archivo_origen'] = filename
        
        candidatos_finales = len(df_filtrado)
        
        if candidatos_finales == 0:
            os.remove(filepath)
            return jsonify({
                'error': f'No hay candidatos con nota inferior a {umbral}',
                'total_leidos': int(total_leidos),
                'total_validos': int(total_validos)
            }), 400
        
        # ✅ Contar candidatos por sede - CONVERTIR A TIPOS NATIVOS
        candidatos_por_sede_raw = df_filtrado['sede'].value_counts().to_dict()
        candidatos_por_sede = {
            str(k) if k is not None else 'Sin detectar': int(v) 
            for k, v in candidatos_por_sede_raw.items()
        }
        candidatos_sin_sede = int(df_filtrado['sede'].isna().sum())
        
        # Verificar duplicados antes de insertar
        solicitudes_en_df = df_filtrado['solicitud'].tolist()
        candidatos_existentes = Candidato.query.filter(
            Candidato.solicitud.in_(solicitudes_en_df),
            Candidato.semana_carga == semana
        ).all()
        
        candidatos_duplicados = len(candidatos_existentes)
        
        if candidatos_duplicados > 0:
            # Obtener solicitudes duplicadas
            solicitudes_duplicadas = [c.solicitud for c in candidatos_existentes]
            
            # Filtrar el DataFrame para excluir duplicados
            df_filtrado = df_filtrado[~df_filtrado['solicitud'].isin(solicitudes_duplicadas)].copy()
            
            candidatos_finales = len(df_filtrado)
            
            if candidatos_finales == 0:
                os.remove(filepath)
                return jsonify({
                    'error': f'Todos los candidatos ({candidatos_duplicados}) ya están cargados en la semana {semana}',
                    'duplicados': candidatos_duplicados,
                    'total_leidos': int(total_leidos)
                }), 400
            
            # ✅ Recalcular estadísticas después de eliminar duplicados
            candidatos_por_sede_raw = df_filtrado['sede'].value_counts().to_dict()
            candidatos_por_sede = {
                str(k) if k is not None else 'Sin detectar': int(v) 
                for k, v in candidatos_por_sede_raw.items()
            }
            candidatos_sin_sede = int(df_filtrado['sede'].isna().sum())
        
        # Codificar campos de texto
        for col in ['apellidos', 'nombre', 'primera_opcion', 'archivo_origen', 'email', 'telefono', 'sede']:
            if col in df_filtrado.columns:
                df_filtrado[col] = df_filtrado[col].apply(
                    lambda x: str(x).encode('utf-8', 'ignore').decode('utf-8') if x is not None and str(x) not in ['nan', 'None'] else None
                )
        
        # Guardar en base de datos
        df_filtrado.to_sql('candidatos', db.engine, if_exists='append', index=False, method='multi', chunksize=100)
        
        # Registrar carga
        carga = CargaExcel(
            archivo_nombre=filename,
            archivo_hash=archivo_hash,
            candidatos_totales=total_leidos,
            candidatos_importados=candidatos_finales,
            candidatos_duplicados=candidatos_duplicados,
            cargado_por_usuario_id=session['user_id'],
            semana_destino=semana,
            estado='completado',
            mensaje=f'Importación exitosa. {candidatos_finales} candidatos con nota < {umbral}' + 
                    (f' ({candidatos_duplicados} duplicados omitidos)' if candidatos_duplicados > 0 else '')
        )
        db.session.add(carga)
        db.session.commit()
        
        # ✅ Registrar en logs de auditoría
        registrar_log(
            accion='cargar_excel',
            entidad='candidatos',
            entidad_id=None,
            descripcion=f'Carga de Excel: {candidatos_finales} candidatos importados para semana {semana}',
            datos_nuevos={
                'archivo': filename,
                'semana': semana,
                'candidatos_importados': candidatos_finales,
                'candidatos_duplicados': candidatos_duplicados,
                'umbral': umbral,
                'candidatos_por_sede': candidatos_por_sede
            },
            nivel='info'
        )
        
        # Mensaje con información de sedes
        mensaje_sedes = ''
        if candidatos_por_sede:
            mensaje_sedes = '<br><strong>📍 Por sede:</strong><br>'
            for sede, cantidad in candidatos_por_sede.items():
                mensaje_sedes += f'• {sede}: {cantidad}<br>'
        if candidatos_sin_sede > 0:
            mensaje_sedes += f'• ⚠️ Sin sede detectada: {candidatos_sin_sede}<br>'
        
        # Advertencia sobre duplicados
        mensaje_duplicados = ''
        if candidatos_duplicados > 0:
            mensaje_duplicados = f'<br><strong>⚠️ Duplicados omitidos:</strong> {candidatos_duplicados} candidatos ya existían<br>'
        
        # Eliminar archivo temporal
        os.remove(filepath)
        
        # ✅ CRÍTICO: Convertir TODOS los valores a tipos nativos de Python
        return jsonify({
            'success': True,
            'mensaje': f'{candidatos_finales} candidatos importados correctamente',
            'total_leidos': int(total_leidos),
            'total_validos': int(total_validos),
            'candidatos_finales': int(candidatos_finales),
            'candidatos_duplicados': int(candidatos_duplicados),
            'umbral': float(umbral),
            'semana': str(semana),
            'candidatos_por_sede': candidatos_por_sede,
            'candidatos_sin_sede': int(candidatos_sin_sede),
            'mensaje_sedes': mensaje_sedes,
            'mensaje_duplicados': mensaje_duplicados
        })
        
    except Exception as e:
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error al procesar el archivo: {str(e)}'}), 500


@app.route('/admin/candidatos/semana/<semana>')
@admin_required
def ver_candidatos_semana(semana):
    """Ver candidatos de una semana específica"""
    
    candidatos = Candidato.query.filter_by(semana_carga=semana)\
        .order_by(Candidato.media_estudios.asc())\
        .all()
    
    # Obtener estadísticas
    stats = obtener_estadisticas_semana_candidatos(semana)
    
    return render_template('candidatos_semana.html',
                         candidatos=candidatos,
                         semana=semana,
                         stats=stats,
                         username=session['username'])


@app.route('/admin/candidatos/asignaciones/<semana>')
@admin_required
def ver_asignaciones_semana(semana):
    """Ver asignaciones de una semana específica"""
    
    asignaciones = db.session.query(Asignacion)\
        .join(Candidato)\
        .join(Reserva)\
        .join(Usuario, Asignacion.entrevistador_id == Usuario.id)\
        .filter(Candidato.semana_carga == semana)\
        .order_by(Reserva.fecha, Reserva.hora_inicio, Asignacion.posicion)\
        .all()
    
    return render_template('asignaciones_semana.html',
                         asignaciones=asignaciones,
                         semana=semana,
                         username=session['username'])

# ====================================================================
# RUTAS DE ENVÍO DE CORREOS
# ====================================================================

@app.route('/admin/candidatos/enviar-emails/<semana>', methods=['POST'])
@admin_required
def enviar_emails_semana(semana):
    """
    Envía emails a candidatos y entrevistadores de una semana
    
    POST /admin/candidatos/enviar-emails/2024-W46
    {
        "tipo": "candidatos" | "entrevistadores" | "ambos",
        "reenviar": false  // Si true, reenvía aunque ya se hayan enviado
    }
    """
    
    try:
        data = request.json or {}
        tipo = data.get('tipo', 'ambos')
        reenviar = data.get('reenviar', False)
        
        resultados = {
            'candidatos_enviados': 0,
            'candidatos_error': 0,
            'entrevistadores_enviados': 0,
            'entrevistadores_error': 0,
            'errores': []
        }
        
        # Obtener asignaciones de la semana
        asignaciones = Asignacion.query\
            .join(Candidato)\
            .filter(Candidato.semana_carga == semana)\
            .all()
        
        if not asignaciones:
            return jsonify({
                'error': f'No hay asignaciones para la semana {semana}'
            }), 404
        
        # ===== ENVÍO A CANDIDATOS =====
        if tipo in ['candidatos', 'ambos']:
            for asignacion in asignaciones:
                # Saltar si ya se envió (a menos que sea reenvío)
                if asignacion.enviado_email and not reenviar:
                    continue
                
                try:
                    # Validar email
                    if not validar_email(asignacion.candidato.email):
                        resultados['errores'].append({
                            'candidato': f"{asignacion.candidato.nombre} {asignacion.candidato.apellidos}",
                            'error': 'Email inválido o vacío'
                        })
                        resultados['candidatos_error'] += 1
                        continue
                    
                    # Generar email
                    subject, html = generar_email_candidato(asignacion)
                    
                    # Crear mensaje
                    msg = Message(
                        subject=subject,
                        recipients=[asignacion.candidato.email],
                        html=html
                    )
                    
                    # Enviar
                    mail.send(msg)
                    
                    # Marcar como enviado
                    asignacion.enviado_email = True
                    asignacion.fecha_envio_email = datetime.now()
                    
                    resultados['candidatos_enviados'] += 1

                    registrar_log(
                        accion='enviar_email',
                        entidad='candidato',
                        entidad_id=asignacion.candidato.id,
                        descripcion=f'Email enviado a: {asignacion.candidato.nombre} {asignacion.candidato.apellidos} ({asignacion.candidato.email})',
                        nivel='info',
                        metadata={'tipo': 'confirmacion_entrevista', 'asignacion_id': asignacion.id}
                    )
                    
                except Exception as e:
                    resultados['candidatos_error'] += 1
                    resultados['errores'].append({
                        'candidato': f"{asignacion.candidato.nombre} {asignacion.candidato.apellidos}",
                        'error': str(e)
                    })
                    registrar_log(
                        accion='enviar_email',
                        entidad='candidato',
                        entidad_id=asignacion.candidato.id,
                        descripcion=f'Error al enviar email a: {asignacion.candidato.email} - {str(e)}',
                        nivel='error'
                    )
                    print(f"Error enviando a {asignacion.candidato.email}: {e}")
        
        # ===== ENVÍO A ENTREVISTADORES =====
        if tipo in ['entrevistadores', 'ambos']:
            # Agrupar asignaciones por entrevistador
            from collections import defaultdict
            por_entrevistador = defaultdict(list)
            
            for asignacion in asignaciones:
                if asignacion.entrevistador:
                    por_entrevistador[asignacion.entrevistador.id].append(asignacion)
            
            # Enviar a cada entrevistador
            for entrevistador_id, asigs_entrevistador in por_entrevistador.items():
                try:
                    entrevistador = Usuario.query.get(entrevistador_id)
                    
                    # Validar email
                    if not validar_email(entrevistador.email):
                        resultados['errores'].append({
                            'entrevistador': entrevistador.username,
                            'error': 'Email inválido o vacío'
                        })
                        resultados['entrevistadores_error'] += 1
                        continue
                    
                    # Generar email
                    subject, html = generar_email_entrevistador(entrevistador, asigs_entrevistador)
                    
                    # Crear mensaje
                    msg = Message(
                        subject=subject,
                        recipients=[entrevistador.email],
                        html=html
                    )
                    
                    # Enviar
                    mail.send(msg)
                    
                    resultados['entrevistadores_enviados'] += 1
                    
                except Exception as e:
                    resultados['entrevistadores_error'] += 1
                    resultados['errores'].append({
                        'entrevistador': entrevistador.username if 'entrevistador' in locals() else 'Desconocido',
                        'error': str(e)
                    })
                    print(f"Error enviando a entrevistador {entrevistador_id}: {e}")
        
        # Guardar cambios en BD
        db.session.commit()

        registrar_log(
            accion='enviar_email_masivo',
            entidad='sistema',
            entidad_id=None,
            descripcion=f'Envío masivo completado: {resultados["candidatos_enviados"]} candidatos, {resultados["entrevistadores_enviados"]} entrevistadores',
            datos_nuevos=resultados,
            nivel='info',
            metadata={'semana': semana, 'tipo': tipo}
        )
        
        # Preparar respuesta
        return jsonify({
            'success': True,
            'mensaje': f'Emails enviados correctamente',
            'candidatos_enviados': resultados['candidatos_enviados'],
            'candidatos_error': resultados['candidatos_error'],
            'entrevistadores_enviados': resultados['entrevistadores_enviados'],
            'entrevistadores_error': resultados['entrevistadores_error'],
            'total_enviados': resultados['candidatos_enviados'] + resultados['entrevistadores_enviados'],
            'errores': resultados['errores']
        })
        
    except Exception as e:
        db.session.rollback()
        registrar_log(
            accion='enviar_email_masivo',
            entidad='sistema',
            entidad_id=None,
            descripcion=f'Error en envío masivo: {str(e)}',
            nivel='error',
            metadata={'semana': semana}
        )
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': f'Error al enviar emails: {str(e)}'
        }), 500


@app.route('/admin/candidatos/test-email', methods=['POST'])
@admin_required
def test_email():
    """
    Envía un email de prueba al administrador
    
    POST /admin/candidatos/test-email
    {
        "email": "tu_email@test.com"
    }
    """
    
    try:
        data = request.json or {}
        email_destino = data.get('email') or session.get('email') or app.config['MAIL_DEFAULT_SENDER']
        
        if not validar_email(email_destino):
            return jsonify({'error': 'Email inválido'}), 400
        
        # Crear mensaje de prueba
        msg = Message(
            subject='🧪 Test de Configuración de Email',
            recipients=[email_destino],
            html="""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #4472C4;">✅ Configuración de Email Correcta</h2>
                <p>Si estás recibiendo este email, significa que la configuración de Flask-Mail con Office 365 está funcionando correctamente.</p>
                <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <strong>Detalles de la prueba:</strong><br>
                    - Servidor: smtp.office365.com<br>
                    - Puerto: 587<br>
                    - TLS: Habilitado<br>
                    - Estado: ✅ Funcionando
                </div>
                <p style="color: #666;">Este es un email de prueba automático del Sistema de Gestión de Entrevistas.</p>
            </body>
            </html>
            """
        )
        
        # Enviar
        mail.send(msg)
        
        return jsonify({
            'success': True,
            'mensaje': f'Email de prueba enviado correctamente a {email_destino}'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': f'Error al enviar email de prueba: {str(e)}'
        }), 500

# ====================================================================
# RUTAS DE GESTIÓN MANUAL DE ASIGNACIONES
# ====================================================================

@app.route('/admin/candidatos/gestion-manual/<semana>')
@admin_required
def gestion_manual_candidatos(semana):
    """Vista de gestión manual de candidatos y asignaciones"""
    
    # Obtener candidatos de la semana
    candidatos = Candidato.query.filter_by(semana_carga=semana)\
        .order_by(Candidato.media_estudios.asc())\
        .all()
    
    # Calcular semana de entrevistas (siguiente semana)
    año, semana_num = semana.split('-W')
    primer_dia = datetime.strptime(f'{año}-W{semana_num}-1', '%Y-W%W-%w').date()
    siguiente_lunes = primer_dia + timedelta(days=7)
    viernes = siguiente_lunes + timedelta(days=4)
    semana_entrevistas = siguiente_lunes.strftime('%Y-W%W')
    
    # Obtener reservas de la semana de entrevistas
    reservas = Reserva.query\
        .filter(Reserva.fecha >= siguiente_lunes)\
        .filter(Reserva.fecha <= viernes)\
        .order_by(Reserva.fecha, Reserva.hora_inicio)\
        .all()
    
    # Preparar datos de reservas con ocupación
    reservas_info = []
    for reserva in reservas:
        asignaciones = Asignacion.query.filter_by(reserva_id=reserva.id).all()
        num_asignaciones = len(asignaciones)
        
        reservas_info.append({
            'reserva': reserva,
            'num_asignaciones': num_asignaciones,
            'espacios_libres': 2 - num_asignaciones,
            'asignaciones': asignaciones,
            'color_estado': 'success' if num_asignaciones == 0 else 'warning' if num_asignaciones == 1 else 'danger'
        })
    
    # Estadísticas
    stats = obtener_estadisticas_semana_candidatos(semana)
    
    # Obtener lista de entrevistadores
    entrevistadores = Usuario.query.filter_by(activo=True).order_by(Usuario.username).all()
    
    return render_template('gestion_manual.html',
                         candidatos=candidatos,
                         reservas_info=reservas_info,
                         semana=semana,
                         semana_entrevistas=semana_entrevistas,
                         stats=stats,
                         entrevistadores=entrevistadores,
                         lunes=siguiente_lunes,
                         viernes=viernes,
                         username=session['username'])


@app.route('/admin/candidatos/asignar-manual', methods=['POST'])
@admin_required
def asignar_candidato_manual():
    """Asigna un candidato a una reserva manualmente"""
    
    try:
        data = request.json
        candidato_id = data.get('candidato_id')
        reserva_id = data.get('reserva_id')
        posicion = data.get('posicion')  # 1 o 2
        
        if not all([candidato_id, reserva_id, posicion]):
            return jsonify({'error': 'Faltan datos requeridos'}), 400
        
        # Validar candidato
        candidato = Candidato.query.get(candidato_id)
        if not candidato:
            return jsonify({'error': 'Candidato no encontrado'}), 404
        
        # Validar reserva
        reserva = Reserva.query.get(reserva_id)
        if not reserva:
            return jsonify({'error': 'Reserva no encontrada'}), 404
        
        # Verificar que el candidato no tenga ya una asignación
        asignacion_existente = Asignacion.query.filter_by(candidato_id=candidato_id).first()
        if asignacion_existente:
            return jsonify({
                'error': f'El candidato ya tiene una asignación en {asignacion_existente.reserva.fecha.strftime("%d/%m/%Y")} a las {asignacion_existente.hora_exacta.strftime("%H:%M") if asignacion_existente.hora_exacta else "N/A"}'
            }), 400
        
        # Verificar espacios disponibles
        asignaciones_actuales = Asignacion.query.filter_by(reserva_id=reserva_id).count()
        if asignaciones_actuales >= 2:
            return jsonify({'error': 'Esta reserva ya tiene 2 asignaciones'}), 400
        
        # Verificar que la posición no esté ocupada
        posicion_ocupada = Asignacion.query.filter_by(reserva_id=reserva_id, posicion=posicion).first()
        if posicion_ocupada:
            return jsonify({'error': f'La posición {posicion} ya está ocupada'}), 400
        
        # Calcular minuto de inicio según posición
        minuto_inicio = 0 if posicion == 1 else 15
        
        # Crear asignación
        asignacion = Asignacion(
            candidato_id=candidato_id,
            reserva_id=reserva_id,
            entrevistador_id=reserva.usuario_id,
            posicion=posicion,
            minuto_inicio=minuto_inicio,
            estado='confirmado',
            fecha_asignacion=datetime.now(),
            asignado_por_admin_id=session['user_id']
        )
        
        db.session.add(asignacion)
        
        # Actualizar estado del candidato
        candidato.estado = 'asignado'
        
        db.session.commit()
        
        registrar_log(
            accion='asignar',
            entidad='asignacion',
            entidad_id=asignacion.id,
            descripcion=f'Asignación manual: {candidato.nombre} {candidato.apellidos} → {reserva.fecha.strftime("%d/%m/%Y")} {reserva.hora_inicio.strftime("%H:%M")}',
            datos_nuevos={
                'candidato': f"{candidato.nombre} {candidato.apellidos}",
                'candidato_nota': float(candidato.media_estudios) if candidato.media_estudios else None,
                'fecha': reserva.fecha.strftime('%d/%m/%Y'),
                'hora': asignacion.hora_exacta.strftime('%H:%M') if asignacion.hora_exacta else None,
                'entrevistador': reserva.usuario.username,
                'posicion': posicion
            },
            nivel='info',
            metadata={'tipo': 'manual'}
        )

        return jsonify({
            'success': True,
            'mensaje': f'Candidato {candidato.nombre} {candidato.apellidos} asignado correctamente',
            'asignacion_id': asignacion.id,
            'hora_exacta': asignacion.hora_exacta.strftime('%H:%M') if asignacion.hora_exacta else None
        })
        
    except Exception as e:
        db.session.rollback()

        registrar_log(
            accion='asignar',
            entidad='asignacion',
            entidad_id=None,
            descripcion=f'Error al asignar candidato: {str(e)}',
            nivel='error'
        )
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error al asignar candidato: {str(e)}'}), 500


@app.route('/admin/candidatos/desasignar-manual', methods=['POST'])
@admin_required
def desasignar_candidato_manual():
    """Desasigna un candidato de una entrevista"""
    
    try:
        data = request.json
        asignacion_id = data.get('asignacion_id')
        
        if not asignacion_id:
            return jsonify({'error': 'ID de asignación no proporcionado'}), 400
        
        # Buscar asignación
        asignacion = Asignacion.query.get(asignacion_id)
        if not asignacion:
            return jsonify({'error': 'Asignación no encontrada'}), 404
        
        # Guardar datos del candidato antes de eliminar
        candidato = asignacion.candidato
        candidato_nombre = f"{candidato.nombre} {candidato.apellidos}"
        
        # Actualizar estado del candidato
        candidato.estado = 'pendiente'
        
        # Eliminar asignación
        db.session.delete(asignacion)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensaje': f'Asignación de {candidato_nombre} eliminada correctamente',
            'candidato_id': candidato.id
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error al desasignar candidato: {str(e)}'}), 500


@app.route('/admin/candidatos/reasignar-manual', methods=['POST'])
@admin_required
def reasignar_candidato_manual():
    """Reasigna un candidato a otra reserva"""
    
    try:
        data = request.json
        asignacion_id = data.get('asignacion_id')
        nueva_reserva_id = data.get('nueva_reserva_id')
        nueva_posicion = data.get('nueva_posicion')
        
        if not all([asignacion_id, nueva_reserva_id, nueva_posicion]):
            return jsonify({'error': 'Faltan datos requeridos'}), 400
        
        # Buscar asignación actual
        asignacion = Asignacion.query.get(asignacion_id)
        if not asignacion:
            return jsonify({'error': 'Asignación no encontrada'}), 404
        
        # Validar nueva reserva
        nueva_reserva = Reserva.query.get(nueva_reserva_id)
        if not nueva_reserva:
            return jsonify({'error': 'Nueva reserva no encontrada'}), 404
        
        # Verificar espacios disponibles en nueva reserva
        asignaciones_nuevas = Asignacion.query.filter_by(reserva_id=nueva_reserva_id).count()
        if asignaciones_nuevas >= 2:
            return jsonify({'error': 'La nueva reserva ya tiene 2 asignaciones'}), 400
        
        # Verificar que la posición no esté ocupada
        posicion_ocupada = Asignacion.query.filter_by(
            reserva_id=nueva_reserva_id, 
            posicion=nueva_posicion
        ).first()
        if posicion_ocupada:
            return jsonify({'error': f'La posición {nueva_posicion} ya está ocupada'}), 400
        
        # Actualizar asignación
        asignacion.reserva_id = nueva_reserva_id
        asignacion.entrevistador_id = nueva_reserva.usuario_id
        asignacion.posicion = nueva_posicion
        asignacion.minuto_inicio = 0 if nueva_posicion == 1 else 15
        asignacion.fecha_asignacion = datetime.now()
        asignacion.asignado_por_admin_id = session['user_id']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensaje': f'Candidato reasignado correctamente',
            'nueva_hora': asignacion.hora_exacta.strftime('%H:%M') if asignacion.hora_exacta else None
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error al reasignar candidato: {str(e)}'}), 500


@app.route('/admin/candidatos/info-reserva/<int:reserva_id>')
@admin_required
def info_reserva(reserva_id):
    """Obtiene información detallada de una reserva"""
    
    reserva = Reserva.query.get_or_404(reserva_id)
    asignaciones = Asignacion.query.filter_by(reserva_id=reserva_id).all()
    
    asignaciones_data = []
    for asig in asignaciones:
        asignaciones_data.append({
            'id': asig.id,
            'candidato_id': asig.candidato_id,
            'candidato_nombre': f"{asig.candidato.nombre} {asig.candidato.apellidos}",
            'candidato_nota': float(asig.candidato.media_estudios) if asig.candidato.media_estudios else None,
            'posicion': asig.posicion,
            'hora_exacta': asig.hora_exacta.strftime('%H:%M') if asig.hora_exacta else None,
            'estado': asig.estado
        })
    
    return jsonify({
        'reserva_id': reserva.id,
        'fecha': reserva.fecha.strftime('%d/%m/%Y'),
        'dia_semana': reserva.fecha.strftime('%A'),
        'hora_inicio': reserva.hora_inicio.strftime('%H:%M'),
        'hora_fin': reserva.hora_fin.strftime('%H:%M'),
        'entrevistador': reserva.usuario.username,
        'espacio': reserva.espacio.nombre if reserva.espacio else 'N/A',
        'num_asignaciones': len(asignaciones),
        'espacios_libres': 2 - len(asignaciones),
        'asignaciones': asignaciones_data
    })

# ====================================================================
# RUTAS DE EXPORTACIÓN
# ====================================================================

@app.route('/admin/exportar/candidatos/<semana>/<formato>')
@admin_required
def exportar_candidatos(semana, formato):
    """Exporta candidatos de una semana en diferentes formatos"""
    
    candidatos = Candidato.query.filter_by(semana_carga=semana)\
        .order_by(Candidato.media_estudios.asc())\
        .all()
    
    if formato == 'xlsx':
        return exportar_candidatos_xlsx(candidatos, semana)
    elif formato == 'pdf':
        return exportar_candidatos_pdf(candidatos, semana)
    elif formato == 'csv':
        return exportar_candidatos_csv(candidatos, semana)
    else:
        return jsonify({'error': 'Formato no soportado'}), 400


def exportar_candidatos_xlsx(candidatos, semana):
    """Exporta candidatos a Excel con formato"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from io import BytesIO
    
    wb = Workbook()
    ws = wb.active
    ws.title = f"Candidatos S{semana.split('-W')[1]}"
    
    # Estilos
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="0066B3", end_color="0066B3", fill_type="solid")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Encabezados
    headers = ['#', 'Solicitud', 'Apellidos', 'Nombre', 'Email','Telefono', 'Nota Media', 'Sede','Primera Opción', 'Estado', 'Fecha Carga']
    ws.append(headers)
    
    # Aplicar estilos a encabezados
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Datos
    for idx, candidato in enumerate(candidatos, start=1):
        row = [
            idx,
            candidato.solicitud,
            candidato.apellidos,
            candidato.nombre,
            candidato.email or 'N/A',
            candidato.telefono or 'N/A',
            float(candidato.media_estudios) if candidato.media_estudios else 0,
            candidato.sede or 'Sin detectar',
            candidato.primera_opcion or '',
            candidato.estado.upper(),
            candidato.fecha_carga.strftime('%d/%m/%Y %H:%M')
        ]
        ws.append(row)
        
        # Colorear según nota
        nota = float(candidato.media_estudios) if candidato.media_estudios else 0
        color = "FFC7CE" if nota < 5.5 else "FFEB9C" if nota < 6.5 else "C6EFCE"
        ws.cell(row=idx+1, column=6).fill = PatternFill(start_color=color, end_color=color, fill_type="solid")

        if candidato.sede:
            color_sede = "D1ECF1"  # Azul claro
            ws.cell(row=idx+1, column=8).fill = PatternFill(start_color=color_sede, end_color=color_sede, fill_type="solid")
            ws.cell(row=idx+1, column=8).font = Font(bold=True)
        
        # Colorear según estado
        if candidato.estado == 'asignado':
            ws.cell(row=idx+1, column=8).fill = PatternFill(start_color="D1ECF1", end_color="D1ECF1", fill_type="solid")
            ws.cell(row=idx+1, column=8).font = Font(bold=True, color="0C5460")
        elif candidato.estado == 'pendiente':
            ws.cell(row=idx+1, column=8).fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
            ws.cell(row=idx+1, column=8).font = Font(bold=True, color="856404")
        
        # Aplicar bordes
        for cell in ws[idx+1]:
            cell.border = border
            cell.alignment = Alignment(vertical='center')
    
    # Ajustar anchos de columna
    ws.column_dimensions['A'].width = 5
    ws.column_dimensions['B'].width = 10
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 25
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 12
    ws.column_dimensions['H'].width = 18
    ws.column_dimensions['I'].width = 40
    ws.column_dimensions['J'].width = 12
    ws.column_dimensions['K'].width = 18
    
    # Guardar en memoria
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'candidatos_semana_{semana.split("-W")[1]}.xlsx'
    )


def exportar_candidatos_csv(candidatos, semana):
    """Exporta candidatos a CSV"""
    from io import StringIO
    import csv
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Encabezados
    writer.writerow(['Solicitud', 'Apellidos', 'Nombre', 'Email', 'Nota Media', 'Primera Opción', 'Estado', 'Fecha Carga'])
    
    # Datos
    for candidato in candidatos:
        writer.writerow([
            candidato.solicitud,
            candidato.apellidos,
            candidato.nombre,
            candidato.email or 'N/A',
            float(candidato.media_estudios) if candidato.media_estudios else 0,
            candidato.primera_opcion or '',
            candidato.estado.upper(),
            candidato.fecha_carga.strftime('%d/%m/%Y %H:%M')
        ])
    
    output.seek(0)
    
    return send_file(
        BytesIO(output.getvalue().encode('utf-8-sig')),  # UTF-8 con BOM para Excel
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'candidatos_semana_{semana.split("-W")[1]}.csv'
    )


def exportar_candidatos_pdf(candidatos, semana):
    """Exporta candidatos a PDF"""
    
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), topMargin=1*cm, bottomMargin=1*cm)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0066B3'),
        spaceAfter=30,
        alignment=1  # Centrado
    )
    
    elements.append(Paragraph(f"Candidatos - Semana {semana.split('-W')[1]}", title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # Tabla
    data = [['#', 'Solicitud', 'Apellidos', 'Nombre', 'Email', 'Nota', 'Estado']]
    
    for idx, candidato in enumerate(candidatos, start=1):
        data.append([
            str(idx),
            str(candidato.solicitud),
            candidato.apellidos[:15],
            candidato.nombre[:12],
            (candidato.email or 'N/A')[:20],
            f"{candidato.media_estudios:.2f}" if candidato.media_estudios else 'N/A',
            candidato.estado.upper()
        ])
    
    table = Table(data, colWidths=[1*cm, 2*cm, 4*cm, 3*cm, 5*cm, 2*cm, 2.5*cm])
    
    # Estilos de tabla
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066B3')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(table)
    
    # Construir PDF
    doc.build(elements)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'candidatos_semana_{semana.split("-W")[1]}.pdf'
    )

# Ruta de exportación de asignaciones.
# ====================================================================
# RUTAS DE EXPORTACIÓN DE ASIGNACIONES
# ====================================================================

@app.route('/admin/exportar/asignaciones/<semana>/<formato>')
@admin_required
def exportar_asignaciones(semana, formato):
    """Exporta asignaciones de una semana en diferentes formatos"""
    
    # Obtener asignaciones de la semana
    asignaciones = db.session.query(Asignacion)\
        .join(Candidato)\
        .join(Reserva)\
        .join(Usuario, Asignacion.entrevistador_id == Usuario.id)\
        .filter(Candidato.semana_carga == semana)\
        .order_by(Reserva.fecha, Reserva.hora_inicio, Asignacion.posicion)\
        .all()
    
    if formato == 'xlsx':
        return exportar_asignaciones_xlsx(asignaciones, semana)
    elif formato == 'pdf':
        return exportar_asignaciones_pdf(asignaciones, semana)
    elif formato == 'csv':
        return exportar_asignaciones_csv(asignaciones, semana)
    else:
        return jsonify({'error': 'Formato no soportado'}), 400


def exportar_asignaciones_xlsx(asignaciones, semana):
    """Exporta asignaciones a Excel con formato"""

    
    wb = Workbook()
    ws = wb.active
    ws.title = f"Asignaciones S{semana.split('-W')[1]}"
    
    # Estilos
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="0066B3", end_color="0066B3", fill_type="solid")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Encabezados
    headers = [
        '#', 'Fecha', 'Día', 'Hora', 'Candidato', 'Email', 'Teléfono', 
        'Nota', 'Entrevistador', 'Espacio', 'Pos.', 'Estado', 'Grado Solicitado'
    ]
    ws.append(headers)
    
    # Aplicar estilos a encabezados
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Traducción de días
    dias_esp = {
        0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 
        3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'
    }
    
    # Datos
    for idx, asignacion in enumerate(asignaciones, start=1):
        candidato = asignacion.candidato
        reserva = asignacion.reserva
        entrevistador = asignacion.entrevistador
        
        dia_semana = dias_esp[reserva.fecha.weekday()]
        hora_exacta = asignacion.hora_exacta.strftime('%H:%M') if asignacion.hora_exacta else reserva.hora_inicio.strftime('%H:%M')
        
        row = [
            idx,
            reserva.fecha.strftime('%d/%m/%Y'),
            dia_semana,
            hora_exacta,
            f"{candidato.nombre} {candidato.apellidos}",
            candidato.email or 'N/A',
            candidato.telefono or 'N/A',
            float(candidato.media_estudios) if candidato.media_estudios else 0,
            entrevistador.username if entrevistador else 'N/A',
            reserva.espacio.nombre if reserva.espacio else 'N/A',
            asignacion.posicion,
            asignacion.estado.upper(),
            candidato.primera_opcion[:50] if candidato.primera_opcion else ''
        ]
        ws.append(row)
        
        # Colorear según nota
        nota = float(candidato.media_estudios) if candidato.media_estudios else 0
        color_nota = "FFC7CE" if nota < 5.5 else "FFEB9C" if nota < 6.5 else "C6EFCE"
        ws.cell(row=idx+1, column=8).fill = PatternFill(start_color=color_nota, end_color=color_nota, fill_type="solid")
        ws.cell(row=idx+1, column=8).font = Font(bold=True)
        
        # Colorear según estado
        if asignacion.estado == 'confirmado':
            ws.cell(row=idx+1, column=12).fill = PatternFill(start_color="D1ECF1", end_color="D1ECF1", fill_type="solid")
            ws.cell(row=idx+1, column=12).font = Font(bold=True, color="0C5460")
        elif asignacion.estado == 'cancelado':
            ws.cell(row=idx+1, column=12).fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")
            ws.cell(row=idx+1, column=12).font = Font(bold=True, color="721C24")
        
        # Aplicar bordes
        for cell in ws[idx+1]:
            cell.border = border
            cell.alignment = Alignment(vertical='center')
    
    # Ajustar anchos de columna
    ws.column_dimensions['A'].width = 5
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 10
    ws.column_dimensions['E'].width = 25
    ws.column_dimensions['F'].width = 25
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 10
    ws.column_dimensions['I'].width = 18
    ws.column_dimensions['J'].width = 15
    ws.column_dimensions['K'].width = 6
    ws.column_dimensions['L'].width = 12
    ws.column_dimensions['M'].width = 40
    
    # Añadir filtros automáticos
    ws.auto_filter.ref = ws.dimensions
    
    # Congelar primera fila
    ws.freeze_panes = 'A2'
    
    # Guardar en memoria
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'asignaciones_semana_{semana.split("-W")[1]}.xlsx'
    )


def exportar_asignaciones_csv(asignaciones, semana):
    """Exporta asignaciones a CSV"""
    output = StringIO()
    writer = csv.writer(output)
    
    # Traducción de días
    dias_esp = {
        0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 
        3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'
    }
    
    # Encabezados
    writer.writerow([
        'Fecha', 'Día', 'Hora', 'Candidato', 'Email', 'Teléfono', 
        'Nota', 'Entrevistador', 'Espacio', 'Posición', 'Estado', 'Grado Solicitado'
    ])
    
    # Datos
    for asignacion in asignaciones:
        candidato = asignacion.candidato
        reserva = asignacion.reserva
        entrevistador = asignacion.entrevistador
        
        dia_semana = dias_esp[reserva.fecha.weekday()]
        hora_exacta = asignacion.hora_exacta.strftime('%H:%M') if asignacion.hora_exacta else reserva.hora_inicio.strftime('%H:%M')
        
        writer.writerow([
            reserva.fecha.strftime('%d/%m/%Y'),
            dia_semana,
            hora_exacta,
            f"{candidato.nombre} {candidato.apellidos}",
            candidato.email or 'N/A',
            candidato.telefono or 'N/A',
            float(candidato.media_estudios) if candidato.media_estudios else 0,
            entrevistador.username if entrevistador else 'N/A',
            reserva.espacio.nombre if reserva.espacio else 'N/A',
            asignacion.posicion,
            asignacion.estado.upper(),
            candidato.primera_opcion if candidato.primera_opcion else ''
        ])
    
    output.seek(0)
    
    return send_file(
        BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'asignaciones_semana_{semana.split("-W")[1]}.csv'
    )


def exportar_asignaciones_pdf(asignaciones, semana):
    """Exporta asignaciones a PDF"""
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), topMargin=1*cm, bottomMargin=1*cm)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0066B3'),
        spaceAfter=30,
        alignment=1
    )
    
    elements.append(Paragraph(f"Asignaciones de Entrevistas - Semana {semana.split('-W')[1]}", title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # Traducción de días
    dias_esp = {
        0: 'Lun', 1: 'Mar', 2: 'Mié', 
        3: 'Jue', 4: 'Vie', 5: 'Sáb', 6: 'Dom'
    }
    
    # Tabla
    data = [['Fecha', 'Día', 'Hora', 'Candidato', 'Email', 'Nota', 'Entrevistador', 'Esp.']]
    
    for asignacion in asignaciones:
        candidato = asignacion.candidato
        reserva = asignacion.reserva
        entrevistador = asignacion.entrevistador
        
        dia_semana = dias_esp[reserva.fecha.weekday()]
        hora_exacta = asignacion.hora_exacta.strftime('%H:%M') if asignacion.hora_exacta else reserva.hora_inicio.strftime('%H:%M')
        
        data.append([
            reserva.fecha.strftime('%d/%m'),
            dia_semana,
            hora_exacta,
            f"{candidato.nombre[:12]} {candidato.apellidos[:12]}",
            (candidato.email or 'N/A')[:20],
            f"{candidato.media_estudios:.2f}" if candidato.media_estudios else 'N/A',
            (entrevistador.username if entrevistador else 'N/A')[:12],
            (reserva.espacio.nombre if reserva.espacio else 'N/A')[:8]
        ])
    
    table = Table(data, colWidths=[2*cm, 1.5*cm, 1.5*cm, 4*cm, 4.5*cm, 1.5*cm, 3*cm, 2*cm])
    
    # Estilos de tabla
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066B3')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(table)
    
    # Resumen
    elements.append(Spacer(1, 0.8*cm))
    resumen_style = ParagraphStyle(
        'Resumen',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#333333')
    )
    elements.append(Paragraph(
        f"<b>Total de asignaciones:</b> {len(asignaciones)} entrevistas programadas", 
        resumen_style
    ))
    
    # Construir PDF
    doc.build(elements)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'asignaciones_semana_{semana.split("-W")[1]}.pdf'
    )

@app.route('/admin/exportar/reservas/<semana>/<formato>')
@admin_required
def exportar_reservas_semana(semana, formato):
    """Exporta reservas de una semana"""
    
    # Calcular fechas
    año, semana_num = semana.split('-W')
    primer_dia = datetime.strptime(f'{año}-W{semana_num}-1', '%Y-W%W-%w').date()
    viernes = primer_dia + timedelta(days=4)
    
    reservas = Reserva.query\
        .filter(Reserva.fecha >= primer_dia)\
        .filter(Reserva.fecha <= viernes)\
        .order_by(Reserva.fecha, Reserva.hora_inicio)\
        .all()
    
    if formato == 'xlsx':
        return exportar_reservas_xlsx(reservas, semana)
    elif formato == 'pdf':
        return exportar_reservas_pdf(reservas, semana)
    else:
        return jsonify({'error': 'Formato no soportado'}), 400


def exportar_reservas_xlsx(reservas, semana):
    """Exporta reservas a Excel"""
    
    wb = Workbook()
    ws = wb.active
    ws.title = f"Reservas S{semana.split('-W')[1]}"
    
    # Estilos
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="0066B3", end_color="0066B3", fill_type="solid")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Encabezados
    headers = ['Fecha', 'Día', 'Hora Inicio', 'Hora Fin', 'Entrevistador', 'Espacio', 'Asignaciones', 'Notas']
    ws.append(headers)
    
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Datos
    for idx, reserva in enumerate(reservas, start=2):
        asignaciones = Asignacion.query.filter_by(reserva_id=reserva.id).all()
        num_asignaciones = len(asignaciones)
        
        candidatos_nombres = ', '.join([f"{a.candidato.nombre} {a.candidato.apellidos}" for a in asignaciones])
        
        row = [
            reserva.fecha.strftime('%d/%m/%Y'),
            reserva.fecha.strftime('%A'),
            reserva.hora_inicio.strftime('%H:%M'),
            reserva.hora_fin.strftime('%H:%M'),
            reserva.usuario.username,
            reserva.espacio.nombre if reserva.espacio else 'N/A',
            f"{num_asignaciones}/2 - {candidatos_nombres}" if num_asignaciones > 0 else "0/2",
            reserva.notas or ''
        ]
        ws.append(row)
        
        # Colorear según ocupación
        color = "C6EFCE" if num_asignaciones == 0 else "FFEB9C" if num_asignaciones == 1 else "FFC7CE"
        for col in range(1, 9):
            cell = ws.cell(row=idx, column=col)
            cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
            cell.border = border
            cell.alignment = Alignment(vertical='center')
    
    # Ajustar anchos
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 10
    ws.column_dimensions['E'].width = 18
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 40
    ws.column_dimensions['H'].width = 25
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'reservas_semana_{semana.split("-W")[1]}.xlsx'
    )


def exportar_reservas_pdf(reservas, semana):
    """Exporta reservas a PDF"""

    
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), topMargin=1*cm, bottomMargin=1*cm)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0066B3'),
        spaceAfter=30,
        alignment=1
    )
    
    elements.append(Paragraph(f"Calendario de Reservas - Semana {semana.split('-W')[1]}", title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    data = [['Fecha', 'Día', 'Hora', 'Entrevistador', 'Espacio', 'Ocupación']]
    
    for reserva in reservas:
        asignaciones = Asignacion.query.filter_by(reserva_id=reserva.id).count()
        
        data.append([
            reserva.fecha.strftime('%d/%m'),
            reserva.fecha.strftime('%A')[:3],
            reserva.hora_inicio.strftime('%H:%M'),
            reserva.usuario.username[:15],
            (reserva.espacio.nombre if reserva.espacio else 'N/A')[:12],
            f"{asignaciones}/2"
        ])
    
    table = Table(data, colWidths=[2.5*cm, 2*cm, 2*cm, 4*cm, 3.5*cm, 2*cm])
    
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0066B3')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(table)
    doc.build(elements)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'reservas_semana_{semana.split("-W")[1]}.pdf'
    )

# ====================================================================
# RUTA DE CAMBIO DE CONTRASEÑA.
# ====================================================================

@app.route('/api/cambiar-contrasena', methods=['POST'])
@login_required
def cambiar_contrasena():
    """Permite al usuario cambiar su contraseña"""
    
    try:
        data = request.json
        contrasena_actual = data.get('contrasena_actual', '')
        contrasena_nueva = data.get('contrasena_nueva', '')
        contrasena_confirmacion = data.get('contrasena_confirmacion', '')
        
        # Validaciones
        if not all([contrasena_actual, contrasena_nueva, contrasena_confirmacion]):
            return jsonify({'error': 'Todos los campos son obligatorios'}), 400
        
        if contrasena_nueva != contrasena_confirmacion:
            return jsonify({'error': 'Las contraseñas nuevas no coinciden'}), 400
        
        if len(contrasena_nueva) < 6:
            return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400
        
        # Obtener usuario actual
        usuario = Usuario.query.get(session['user_id'])
        
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Verificar contraseña actual
        if not check_password_hash(usuario.password, contrasena_actual):
            # ✅ Registrar intento fallido
            registrar_log(
                accion='cambiar_contrasena',
                entidad='usuario',
                entidad_id=usuario.id,
                descripcion=f'Intento fallido de cambio de contraseña: contraseña actual incorrecta',
                nivel='warning'
            )
            return jsonify({'error': 'La contraseña actual es incorrecta'}), 403
        
        # Cambiar contraseña
        usuario.password = generate_password_hash(contrasena_nueva)
        db.session.commit()
        
        # ✅ Registrar cambio exitoso
        registrar_log(
            accion='cambiar_contrasena',
            entidad='usuario',
            entidad_id=usuario.id,
            descripcion=f'Contraseña cambiada exitosamente para {usuario.username}',
            nivel='info'
        )
        
        return jsonify({
            'success': True,
            'mensaje': 'Contraseña cambiada correctamente'
        })
        
    except Exception as e:
        db.session.rollback()
        
        registrar_log(
            accion='cambiar_contrasena',
            entidad='usuario',
            entidad_id=session.get('user_id'),
            descripcion=f'Error al cambiar contraseña: {str(e)}',
            nivel='error'
        )
        
        return jsonify({'error': f'Error al cambiar la contraseña: {str(e)}'}), 500

# ====================================================================
# RUTAS DE LOGS DE AUDITORÍA
# ====================================================================

@app.route('/admin/logs')
@admin_required
def ver_logs():
    """Vista de logs de auditoría"""
    
    # Parámetros de filtro
    pagina = request.args.get('pagina', 1, type=int)
    por_pagina = request.args.get('por_pagina', 50, type=int)
    
    filtro_usuario = request.args.get('usuario', '')
    filtro_accion = request.args.get('accion', '')
    filtro_entidad = request.args.get('entidad', '')
    filtro_nivel = request.args.get('nivel', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    buscar = request.args.get('buscar', '')
    
    # Query base
    query = LogActividad.query
    
    # Aplicar filtros
    if filtro_usuario:
        query = query.filter(LogActividad.usuario_username.ilike(f'%{filtro_usuario}%'))
    
    if filtro_accion:
        query = query.filter(LogActividad.accion == filtro_accion)
    
    if filtro_entidad:
        query = query.filter(LogActividad.entidad == filtro_entidad)
    
    if filtro_nivel:
        query = query.filter(LogActividad.nivel == filtro_nivel)
    
    if fecha_desde:
        fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d')
        query = query.filter(LogActividad.fecha_hora >= fecha_desde_obj)
    
    if fecha_hasta:
        fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d')
        fecha_hasta_obj = fecha_hasta_obj.replace(hour=23, minute=59, second=59)
        query = query.filter(LogActividad.fecha_hora <= fecha_hasta_obj)
    
    if buscar:
        query = query.filter(LogActividad.descripcion.ilike(f'%{buscar}%'))
    
    # Ordenar por fecha descendente
    query = query.order_by(LogActividad.fecha_hora.desc())
    
    # Paginación
    paginacion = query.paginate(page=pagina, per_page=por_pagina, error_out=False)
    logs = paginacion.items
    
    # Obtener valores únicos para filtros
    acciones_disponibles = db.session.query(LogActividad.accion)\
        .distinct()\
        .order_by(LogActividad.accion)\
        .all()
    acciones_disponibles = [a[0] for a in acciones_disponibles]
    
    entidades_disponibles = db.session.query(LogActividad.entidad)\
        .distinct()\
        .order_by(LogActividad.entidad)\
        .all()
    entidades_disponibles = [e[0] for e in entidades_disponibles]
    
    usuarios_disponibles = db.session.query(LogActividad.usuario_username)\
        .distinct()\
        .filter(LogActividad.usuario_username.isnot(None))\
        .order_by(LogActividad.usuario_username)\
        .all()
    usuarios_disponibles = [u[0] for u in usuarios_disponibles]
    
    # Estadísticas rápidas
    total_logs = LogActividad.query.count()
    logs_hoy = LogActividad.query.filter(
        LogActividad.fecha_hora >= datetime.now().replace(hour=0, minute=0, second=0)
    ).count()
    logs_error = LogActividad.query.filter(LogActividad.nivel.in_(['error', 'critical'])).count()
    
    return render_template('admin_logs.html',
                         logs=logs,
                         paginacion=paginacion,
                         acciones_disponibles=acciones_disponibles,
                         entidades_disponibles=entidades_disponibles,
                         usuarios_disponibles=usuarios_disponibles,
                         total_logs=total_logs,
                         logs_hoy=logs_hoy,
                         logs_error=logs_error,
                         filtro_usuario=filtro_usuario,
                         filtro_accion=filtro_accion,
                         filtro_entidad=filtro_entidad,
                         filtro_nivel=filtro_nivel,
                         fecha_desde=fecha_desde,
                         fecha_hasta=fecha_hasta,
                         buscar=buscar,
                         por_pagina=por_pagina,
                         username=session['username'])

@app.route('/admin/logs/<int:log_id>/detalle')
@admin_required
def detalle_log(log_id):
    """Obtiene el detalle completo de un log"""
    
    log = LogActividad.query.get_or_404(log_id)
    
    return jsonify({
        'id': log.id,
        'fecha_hora': log.fecha_hora.strftime('%d/%m/%Y %H:%M:%S'),
        'usuario': log.usuario_username,
        'accion': log.accion,
        'entidad': log.entidad,
        'entidad_id': log.entidad_id,
        'descripcion': log.descripcion,
        'datos_anteriores': log.datos_anteriores,
        'datos_nuevos': log.datos_nuevos,
        'ip_address': log.ip_address,
        'user_agent': log.user_agent,
        'nivel': log.nivel,
        'metadata': log.metadata_extra
    })


@app.route('/admin/logs/exportar')
@admin_required
def exportar_logs():
    """Exporta logs filtrados a Excel"""
    
    # Aplicar los mismos filtros que en la vista
    filtro_usuario = request.args.get('usuario', '')
    filtro_accion = request.args.get('accion', '')
    filtro_entidad = request.args.get('entidad', '')
    filtro_nivel = request.args.get('nivel', '')
    fecha_desde = request.args.get('fecha_desde', '')
    fecha_hasta = request.args.get('fecha_hasta', '')
    buscar = request.args.get('buscar', '')
    
    query = LogActividad.query
    
    if filtro_usuario:
        query = query.filter(LogActividad.usuario_username.ilike(f'%{filtro_usuario}%'))
    
    if filtro_accion:
        query = query.filter(LogActividad.accion == filtro_accion)
    
    if filtro_entidad:
        query = query.filter(LogActividad.entidad == filtro_entidad)
    
    if filtro_nivel:
        query = query.filter(LogActividad.nivel == filtro_nivel)
    
    if fecha_desde:
        fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d')
        query = query.filter(LogActividad.fecha_hora >= fecha_desde_obj)
    
    if fecha_hasta:
        fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d')
        fecha_hasta_obj = fecha_hasta_obj.replace(hour=23, minute=59, second=59)
        query = query.filter(LogActividad.fecha_hora <= fecha_hasta_obj)
    
    if buscar:
        query = query.filter(LogActividad.descripcion.ilike(f'%{buscar}%'))
    
    logs = query.order_by(LogActividad.fecha_hora.desc()).limit(1000).all()  # Límite de 1000
    
    # Crear Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Logs de Auditoría"
    
    # Estilos
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="0066B3", end_color="0066B3", fill_type="solid")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Encabezados
    headers = ['ID', 'Fecha/Hora', 'Usuario', 'Acción', 'Entidad', 'ID Entidad', 'Descripción', 'Nivel', 'IP']
    ws.append(headers)
    
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Datos
    for log in logs:
        row = [
            log.id,
            log.fecha_hora.strftime('%d/%m/%Y %H:%M:%S'),
            log.usuario_username or 'Sistema',
            log.accion,
            log.entidad,
            log.entidad_id or '',
            log.descripcion,
            log.nivel.upper(),
            log.ip_address or ''
        ]
        ws.append(row)
        
        # Aplicar bordes
        for cell in ws[ws.max_row]:
            cell.border = border
            cell.alignment = Alignment(vertical='center')
    
    # Ajustar anchos
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 10
    ws.column_dimensions['G'].width = 60
    ws.column_dimensions['H'].width = 10
    ws.column_dimensions['I'].width = 15
    
    # Filtros automáticos
    ws.auto_filter.ref = ws.dimensions
    
    # Guardar
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    # Registrar la exportación
    registrar_log(
        accion='exportar',
        entidad='logs',
        entidad_id=None,
        descripcion=f'Exportación de {len(logs)} logs de auditoría',
        nivel='info',
        metadata={'cantidad': len(logs), 'filtros_aplicados': True}
    )
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'logs_auditoria_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    )


# ====================================================================
# RUTAS DE GESTIÓN Y ELIMINACIÓN
# ====================================================================

@app.route('/admin/cargas/eliminar/<int:carga_id>', methods=['POST'])
@admin_required
def eliminar_carga(carga_id):
    """Elimina una carga de Excel y todos sus candidatos asociados"""
    
    try:
        carga = CargaExcel.query.get_or_404(carga_id)
        
        # Obtener candidatos de esta carga
        candidatos = Candidato.query.filter_by(
            archivo_origen=carga.archivo_nombre,
            semana_carga=carga.semana_destino
        ).all()
        
        num_candidatos = len(candidatos)
        
        # Verificar si hay asignaciones
        candidatos_ids = [c.id for c in candidatos]
        asignaciones = Asignacion.query.filter(Asignacion.candidato_id.in_(candidatos_ids)).all()
        num_asignaciones = len(asignaciones)
        
        # Eliminar asignaciones primero (por FK)
        if num_asignaciones > 0:
            for asignacion in asignaciones:
                db.session.delete(asignacion)
        
        # Eliminar candidatos
        for candidato in candidatos:
            db.session.delete(candidato)
        
        # Eliminar registro de carga
        db.session.delete(carga)
        db.session.commit()
        
        # Registrar en logs
        registrar_log(
            accion='eliminar',
            entidad='carga_excel',
            entidad_id=carga_id,
            descripcion=f'Carga eliminada: {carga.archivo_nombre} ({num_candidatos} candidatos, {num_asignaciones} asignaciones)',
            datos_anteriores={
                'archivo': carga.archivo_nombre,
                'semana': carga.semana_destino,
                'candidatos': num_candidatos,
                'asignaciones': num_asignaciones
            },
            nivel='warning'
        )
        
        return jsonify({
            'success': True,
            'mensaje': f'Carga eliminada correctamente',
            'candidatos_eliminados': num_candidatos,
            'asignaciones_eliminadas': num_asignaciones
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar carga: {str(e)}'}), 500


@app.route('/admin/candidatos/semana/<semana>/eliminar-todos', methods=['POST'])
@admin_required
def eliminar_candidatos_semana(semana):
    """Elimina todos los candidatos de una semana específica"""
    
    try:
        # Obtener candidatos
        candidatos = Candidato.query.filter_by(semana_carga=semana).all()
        num_candidatos = len(candidatos)
        
        if num_candidatos == 0:
            return jsonify({'error': 'No hay candidatos en esta semana'}), 404
        
        # Obtener asignaciones
        candidatos_ids = [c.id for c in candidatos]
        asignaciones = Asignacion.query.filter(Asignacion.candidato_id.in_(candidatos_ids)).all()
        num_asignaciones = len(asignaciones)
        
        # Eliminar asignaciones primero
        for asignacion in asignaciones:
            db.session.delete(asignacion)
        
        # Eliminar candidatos
        for candidato in candidatos:
            db.session.delete(candidato)
        
        db.session.commit()
        
        # Registrar en logs
        registrar_log(
            accion='eliminar',
            entidad='candidatos_semana',
            entidad_id=None,
            descripcion=f'Candidatos eliminados de semana {semana}: {num_candidatos} candidatos, {num_asignaciones} asignaciones',
            datos_anteriores={
                'semana': semana,
                'candidatos': num_candidatos,
                'asignaciones': num_asignaciones
            },
            nivel='warning'
        )
        
        return jsonify({
            'success': True,
            'mensaje': f'Todos los candidatos eliminados correctamente',
            'candidatos_eliminados': num_candidatos,
            'asignaciones_eliminadas': num_asignaciones
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar candidatos: {str(e)}'}), 500


@app.route('/admin/candidato/<int:candidato_id>/eliminar', methods=['POST'])
@admin_required
def eliminar_candidato(candidato_id):
    """Elimina un candidato individual y su asignación si existe"""
    
    try:
        candidato = Candidato.query.get_or_404(candidato_id)
        
        # Eliminar asignación si existe
        asignacion = Asignacion.query.filter_by(candidato_id=candidato_id).first()
        if asignacion:
            db.session.delete(asignacion)
        
        nombre_completo = candidato.nombre_completo
        
        # Eliminar candidato
        db.session.delete(candidato)
        db.session.commit()
        
        # Registrar en logs
        registrar_log(
            accion='eliminar',
            entidad='candidato',
            entidad_id=candidato_id,
            descripcion=f'Candidato eliminado: {nombre_completo}',
            datos_anteriores={
                'nombre': nombre_completo,
                'solicitud': candidato.solicitud,
                'estado': candidato.estado
            },
            nivel='warning'
        )
        
        return jsonify({
            'success': True,
            'mensaje': f'Candidato eliminado correctamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar candidato: {str(e)}'}), 500


@app.route('/admin/asignaciones/semana/<semana>/eliminar-todas', methods=['POST'])
@admin_required
def eliminar_asignaciones_semana(semana):
    """Elimina todas las asignaciones de una semana y resetea candidatos a pendiente"""
    
    try:
        # Obtener candidatos de la semana
        candidatos = Candidato.query.filter_by(semana_carga=semana).all()
        candidatos_ids = [c.id for c in candidatos]
        
        # Obtener asignaciones
        asignaciones = Asignacion.query.filter(Asignacion.candidato_id.in_(candidatos_ids)).all()
        num_asignaciones = len(asignaciones)
        
        if num_asignaciones == 0:
            return jsonify({'error': 'No hay asignaciones en esta semana'}), 404
        
        # Eliminar asignaciones
        for asignacion in asignaciones:
            db.session.delete(asignacion)
        
        # Resetear estado de candidatos a pendiente
        for candidato in candidatos:
            if candidato.estado == 'asignado':
                candidato.estado = 'pendiente'
        
        db.session.commit()
        
        # Registrar en logs
        registrar_log(
            accion='eliminar',
            entidad='asignaciones_semana',
            entidad_id=None,
            descripcion=f'Asignaciones eliminadas de semana {semana}: {num_asignaciones} asignaciones',
            datos_anteriores={
                'semana': semana,
                'asignaciones': num_asignaciones
            },
            nivel='warning'
        )
        
        return jsonify({
            'success': True,
            'mensaje': f'Todas las asignaciones eliminadas correctamente',
            'asignaciones_eliminadas': num_asignaciones
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar asignaciones: {str(e)}'}), 500


@app.route('/admin/log-asignacion/<int:log_id>/eliminar', methods=['POST'])
@admin_required
def eliminar_log_asignacion(log_id):
    """Elimina un registro de log de asignación"""
    
    try:
        log = LogAsignacion.query.get_or_404(log_id)
        
        semana = log.semana_objetivo
        
        db.session.delete(log)
        db.session.commit()
        
        # Registrar en logs de auditoría
        registrar_log(
            accion='eliminar',
            entidad='log_asignacion',
            entidad_id=log_id,
            descripcion=f'Log de asignación eliminado: semana {semana}',
            nivel='info'
        )
        
        return jsonify({
            'success': True,
            'mensaje': 'Log eliminado correctamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar log: {str(e)}'}), 500

# ====================================================================
# INICIALIZACIÓN
# ====================================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        admin = Usuario.query.filter_by(username='admin').first()
        if not admin:
            hashed_password = generate_password_hash('admin123')
            admin = Usuario(
                username='admin',
                email='admin@ejemplo.com',
                password=hashed_password,
                rol='admin'
            )
            db.session.add(admin)
            print("✓ Usuario administrador creado: admin / admin123")
        
        if Espacio.query.count() == 0:
            dias_semana = [
                Espacio(nombre='Lunes', descripcion='Primer día de la semana', color='#667eea'),
                Espacio(nombre='Martes', descripcion='Segundo día de la semana', color='#764ba2'),
                Espacio(nombre='Miércoles', descripcion='Tercer día de la semana', color='#f093fb'),
                Espacio(nombre='Jueves', descripcion='Cuarto día de la semana', color='#4facfe'),
                Espacio(nombre='Viernes', descripcion='Quinto día de la semana', color='#43e97b'),
            ]
            for dia in dias_semana:
                db.session.add(dia)
            print("✓ Días de la semana creados correctamente")
        
        db.session.commit()
    
    app.run(debug=True)
