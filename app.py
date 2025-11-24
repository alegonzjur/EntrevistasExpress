from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
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



app = Flask(__name__)
app.secret_key = 'a4f8d9e3b2c1a7f6e5d4c3b2a1f9e8d7c6b5a4f3e2d1c9b8a7f6e5d4c3b2a1f0'  # Cambia esto en producción
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:eebormujos?@localhost/reservas_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.office365.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'aroman.gonzalez@sjd.edu.es'  # ← CAMBIAR
app.config['MAIL_PASSWORD'] = '48190803F'  # ← CAMBIAR
app.config['MAIL_DEFAULT_SENDER'] = 'aroman.gonzalez@sjd.edu.es'  # ← CAMBIAR
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

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    rol = db.Column(db.String(20), default='profesor')  # 'admin' o 'profesor'
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
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


# ====================================================================
# NUEVOS MODELOS PARA CANDIDATOS
# ====================================================================

class Candidato(db.Model):
    __tablename__ = 'candidatos'
    
    id = db.Column(db.Integer, primary_key=True)
    solicitud = db.Column(db.Integer, nullable=False)
    apellidos = db.Column(db.String(150), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    media_estudios = db.Column(db.Numeric(4, 2), nullable=False)
    primera_opcion = db.Column(db.Text)
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
    
    def to_dict(self):
        return {
            'id': self.id,
            'solicitud': self.solicitud,
            'nombre_completo': self.nombre_completo,
            'email': self.email,
            'media_estudios': float(self.media_estudios) if self.media_estudios else None,
            'estado': self.estado,
            'primera_opcion': self.primera_opcion
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
                                Le confirmamos su entrevista personal para el proceso de selección:
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
                                        
                                        <p style="margin: 0 0 15px 0; font-size: 16px; color: #333333;">
                                            <span style="font-size: 20px;">📍</span> 
                                            <strong>Lugar:</strong><br>
                                            <span style="color: #666666; margin-left: 30px;">{reserva.espacio.nombre if reserva.espacio else 'A confirmar'}</span>
                                        </p>
                                        
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
                                    <li style="margin: 5px 0;">Por favor, llegue <strong>10 minutos antes</strong> de la hora indicada.</li>
                                    <li style="margin: 5px 0;">Traiga consigo su <strong>DNI o NIE</strong> original.</li>
                                    <li style="margin: 5px 0;">Se recomienda llevar su <strong>expediente académico</strong>.</li>
                                </ul>
                            </div>
                            
                            <!-- Nota adicional -->
                            <p style="font-size: 14px; color: #999999; line-height: 1.6; margin: 0 0 20px 0;">
                                Si no puede asistir a la entrevista, por favor responda a este correo 
                                con la mayor brevedad posible para poder reasignar la cita.
                            </p>
                            
                            <!-- Firma -->
                            <div style="border-top: 2px solid #e0e0e0; padding-top: 20px; margin-top: 30px;">
                                <p style="margin: 0 0 5px 0; font-size: 16px; color: #333333; font-weight: 600;">
                                    Atentamente,
                                </p>
                                <p style="margin: 0; font-size: 14px; color: #666666;">
                                    Sistema de Gestión de Entrevistas<br>
                                    {entrevistador.email if entrevistador and entrevistador.email else 'entrevistas@universidad.edu'}
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
        
        filas_html += f"""
        <tr style="border-bottom: 1px solid #e0e0e0;">
            <td rowspan="{len(asigs_dia)}" style="padding: 15px; background-color: #f8f9fa; font-weight: 600; text-align: center; border-right: 2px solid #dee2e6;">
                {dia_semana}<br>
                <span style="font-size: 12px; color: #666; font-weight: normal;">{fecha_str}</span>
            </td>
            <td style="padding: 15px; font-weight: 600; color: #4472C4;">{hora}</td>
            <td style="padding: 15px;">{primera_asig.candidato.nombre} {primera_asig.candidato.apellidos}</td>
            <td style="padding: 15px; text-align: center;">
                <span style="background-color: {'#ffc7ce' if primera_asig.candidato.media_estudios < 5.5 else '#ffeb9c' if primera_asig.candidato.media_estudios < 6.5 else '#c6efce'}; 
                             padding: 4px 8px; border-radius: 4px; font-weight: 600;">
                    {primera_asig.candidato.media_estudios:.2f}
                </span>
            </td>
            <td style="padding: 15px; font-size: 12px; color: #666;">
                {primera_asig.candidato.primera_opcion[:50] + '...' if primera_asig.candidato.primera_opcion and len(primera_asig.candidato.primera_opcion) > 50 else primera_asig.candidato.primera_opcion or '-'}
            </td>
        </tr>
        """
        
        # Filas adicionales del mismo día
        for asig in asigs_dia[1:]:
            hora = asig.hora_exacta.strftime('%H:%M') if asig.hora_exacta else asig.reserva.hora_inicio.strftime('%H:%M')
            filas_html += f"""
        <tr style="border-bottom: 1px solid #e0e0e0;">
            <td style="padding: 15px; font-weight: 600; color: #4472C4;">{hora}</td>
            <td style="padding: 15px;">{asig.candidato.nombre} {asig.candidato.apellidos}</td>
            <td style="padding: 15px; text-align: center;">
                <span style="background-color: {'#ffc7ce' if asig.candidato.media_estudios < 5.5 else '#ffeb9c' if asig.candidato.media_estudios < 6.5 else '#c6efce'}; 
                             padding: 4px 8px; border-radius: 4px; font-weight: 600;">
                    {asig.candidato.media_estudios:.2f}
                </span>
            </td>
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
                                    <th style="padding: 15px; text-align: center; font-weight: 600;">Nota</th>
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
                            
                            <!-- Leyenda de colores -->
                            <div style="margin: 20px 0;">
                                <p style="font-size: 14px; color: #666; margin: 0 0 10px 0;">
                                    <strong>Leyenda de colores (nota media):</strong>
                                </p>
                                <div style="display: inline-block; margin-right: 15px;">
                                    <span style="background-color: #ffc7ce; padding: 4px 12px; border-radius: 4px; font-size: 12px;">< 5.5</span>
                                </div>
                                <div style="display: inline-block; margin-right: 15px;">
                                    <span style="background-color: #ffeb9c; padding: 4px 12px; border-radius: 4px; font-size: 12px;">5.5 - 6.5</span>
                                </div>
                                <div style="display: inline-block;">
                                    <span style="background-color: #c6efce; padding: 4px 12px; border-radius: 4px; font-size: 12px;">> 6.5</span>
                                </div>
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
            flash(f'¡Bienvenido, {usuario.username}!', 'success')
            return redirect(url_for('reservas'))
        else:
            if usuario and not usuario.activo:
                error = 'Tu cuenta ha sido desactivada. Contacta con el administrador.'
            else:
                error = 'Usuario o contraseña incorrectos'
            return render_template('login.html', error=error)
    
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
@admin_required
def registro():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        rol = request.form.get('rol', 'profesor')
        
        if Usuario.query.filter_by(username=username).first():
            flash('El usuario ya existe', 'error')
            return render_template('registro.html')
        
        if Usuario.query.filter_by(email=email).first():
            flash('El email ya está registrado', 'error')
            return render_template('registro.html')
        
        hashed_password = generate_password_hash(password)
        nuevo_usuario = Usuario(
            username=username, 
            email=email, 
            password=hashed_password,
            rol=rol
        )
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        flash(f'Usuario {username} creado correctamente como {rol}', 'success')
        return redirect(url_for('admin_usuarios'))
    
    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente', 'success')
    return redirect(url_for('login'))


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
    
    # Combinar todas las franjas
    todas_franjas = franjas_manana + franjas_tarde
    
    for franja_inicio, franja_fin in todas_franjas:
        # Obtener TODAS las reservas para esta franja horaria
        reservas = Reserva.query.filter_by(
            espacio_id=dia_id,
            fecha=fecha,
            hora_inicio=datetime.strptime(franja_inicio, '%H:%M').time()
        ).all()
        
        num_reservas = len(reservas)
        
        # Verificar si alguna de las reservas es del usuario actual
        mis_reservas = [r for r in reservas if r.usuario_id == session.get('user_id')]
        tiene_mi_reserva = len(mis_reservas) > 0
        
        # Obtener información de las reservas
        reservas_info = []
        for r in reservas:
            reservas_info.append({
                'id': r.id,
                'usuario': r.usuario.username,
                'notas': r.notas,
                'es_mia': r.usuario_id == session.get('user_id')
            })
        
        franjas.append({
            'hora_inicio': franja_inicio,
            'hora_fin': franja_fin,
            'num_reservas': num_reservas,
            'disponible': num_reservas == 0,
            'parcial': num_reservas == 1,
            'completa': num_reservas >= 2,
            'tiene_mi_reserva': tiene_mi_reserva,
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
    
    usuario_id_destino = data.get('usuario_id', session['user_id'])
    
    if usuario_id_destino != session['user_id'] and session.get('rol') != 'admin':
        return jsonify({'error': 'No tienes permiso para reservar en nombre de otros usuarios'}), 403
    
    fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time()
    hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time()
    
    # ✅ NUEVA VALIDACIÓN: Verificar que no existan más de 2 reservas
    reservas_existentes = Reserva.query.filter_by(
        espacio_id=espacio_id,
        fecha=fecha,
        hora_inicio=hora_inicio
    ).all()
    
    if len(reservas_existentes) >= 2:
        return jsonify({'error': 'Esta franja ya tiene el máximo de 2 reservas'}), 400
    
    # ✅ Verificar que el usuario no tenga ya una reserva en esta franja
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
        creado_por_admin=session['user_id'] if usuario_id_destino != session['user_id'] else None
    )
    
    db.session.add(nueva_reserva)
    db.session.commit()
    
    if usuario_id_destino != session['user_id']:
        usuario_destino = Usuario.query.get(usuario_id_destino)
        mensaje = f'Reserva creada correctamente para {usuario_destino.username}'
    else:
        mensaje = 'Reserva realizada correctamente'
    
    return jsonify({'success': True, 'mensaje': mensaje})

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
                         username=session['username'])

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
        columnas_necesarias = ['Solicitud', 'Apellidos', 'Nombre', 'Media estudios realizados', 'Primera opción','Email']
        columnas_faltantes = [col for col in columnas_necesarias if col not in df.columns]
        
        if columnas_faltantes:
            os.remove(filepath)
            return jsonify({'error': f'Columnas faltantes: {", ".join(columnas_faltantes)}'}), 400
        
        # Procesar datos
        df_procesado = df[columnas_necesarias].copy()
        df_procesado.rename(columns={
            'Solicitud': 'solicitud',
            'Apellidos': 'apellidos',
            'Nombre': 'nombre',
            'Media estudios realizados': 'media_estudios',
            'Primera opción': 'primera_opcion',
            'Email': 'email'
        }, inplace=True)
        
        # Limpiar datos
        df_procesado = df_procesado.dropna(subset=['solicitud', 'apellidos', 'nombre', 'media_estudios'])
        df_procesado['solicitud'] = pd.to_numeric(df_procesado['solicitud'], errors='coerce')
        df_procesado['media_estudios'] = pd.to_numeric(df_procesado['media_estudios'], errors='coerce')
        df_procesado = df_procesado.dropna(subset=['solicitud', 'media_estudios'])
        
        total_leidos = len(df)
        total_validos = len(df_procesado)
        
        # Filtrar por umbral
        df_filtrado = df_procesado[df_procesado['media_estudios'] < umbral].copy()
        
        # Añadir campos de gestión
        # df_filtrado['email'] = None
        
        df_filtrado['estado'] = 'pendiente'
        df_filtrado['fecha_carga'] = datetime.now()
        df_filtrado['semana_carga'] = semana
        df_filtrado['archivo_origen'] = filename
        
        candidatos_finales = len(df_filtrado)
        
        if candidatos_finales == 0:
            os.remove(filepath)
            return jsonify({
                'error': f'No hay candidatos con nota inferior a {umbral}',
                'total_leidos': total_leidos,
                'total_validos': total_validos
            }), 400
        
        # Guardar en base de datos
        for col in ['apellidos', 'nombre', 'primera_opcion', 'archivo_origen']:
            if col in df_filtrado.columns:
                df_filtrado[col] = df_filtrado[col].apply(
                    lambda x: str(x).encode('utf-8', 'ignore').decode('utf-8') if x is not None and str(x) != 'nan' else x
                )
        
        df_filtrado.to_sql('candidatos', db.engine, if_exists='append', index=False, method='multi', chunksize=100)
        
        # Registrar carga
        carga = CargaExcel(
            archivo_nombre=filename,
            archivo_hash=archivo_hash,
            candidatos_totales=total_leidos,
            candidatos_importados=candidatos_finales,
            candidatos_duplicados=0,
            cargado_por_usuario_id=session['user_id'],
            semana_destino=semana,
            estado='completado',
            mensaje=f'Importación exitosa. {candidatos_finales} candidatos con nota < {umbral}'
        )
        db.session.add(carga)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensaje': f'{candidatos_finales} candidatos importados correctamente',
            'total_leidos': total_leidos,
            'total_validos': total_validos,
            'candidatos_finales': candidatos_finales,
            'umbral': umbral,
            'semana': semana
        })
        
    except Exception as e:
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': f'Error al procesar el archivo: {str(e)}'}), 500


@app.route('/admin/candidatos/ejecutar-asignacion', methods=['POST'])
@admin_required
def ejecutar_asignacion():
    """Ejecuta el algoritmo de asignación automática"""
    
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
        
        # Obtener reservas con espacios
        reservas_obj = Reserva.query\
            .filter(Reserva.fecha >= primer_dia_ent)\
            .filter(Reserva.fecha <= viernes_ent)\
            .order_by(Reserva.fecha, Reserva.hora_inicio)\
            .all()
        
        franjas_disponibles = []
        for reserva in reservas_obj:
            asignaciones_existentes = Asignacion.query\
                .filter_by(reserva_id=reserva.id)\
                .count()
            
            espacios_libres = 2 - asignaciones_existentes
            if espacios_libres > 0:
                franjas_disponibles.append({
                    'reserva': reserva,
                    'espacios_libres': espacios_libres,
                    'asignaciones_actuales': asignaciones_existentes
                })
        
        # Asignar candidatos
        asignaciones_creadas = []
        idx_candidato = 0
        idx_franja = 0
        
        asignaciones_por_profesor = {}
        
        while idx_candidato < len(candidatos) and idx_franja < len(franjas_disponibles):
            candidato = candidatos[idx_candidato]
            franja = franjas_disponibles[idx_franja]
            reserva = franja['reserva']
            entrevistador_id = reserva.usuario_id
            
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
            
            # ✅ CREAR ASIGNACIÓN SIN hora_exacta EN EL CONSTRUCTOR
            asignacion = Asignacion(
                candidato_id=candidato.id,
                reserva_id=reserva.id,
                entrevistador_id=entrevistador_id,
                posicion=posicion,
                minuto_inicio=minuto_inicio,
                # NO incluir hora_exacta aquí
                estado='confirmado',
                fecha_asignacion=datetime.now(),
                asignado_por_admin_id=session['user_id']
            )
            
            db.session.add(asignacion)
            
        
            try:
                # Verificar si hora_exacta es una columna o una propiedad
                if hasattr(type(asignacion), 'hora_exacta'):
                    attr = getattr(type(asignacion), 'hora_exacta')
                    # Si NO es una propiedad calculada, asignarla
                    if not isinstance(attr, property):
                        asignacion.hora_exacta = hora_exacta.time()
            except Exception as e:
                # Si hay error al asignar, continuar sin ella
                print(f"Advertencia: No se pudo asignar hora_exacta: {e}")
            
            asignaciones_creadas.append({
                'candidato_id': candidato.id,
                'reserva_id': reserva.id
            })
            
            # Actualizar estado del candidato
            candidato.estado = 'asignado'
            
            # Actualizar contadores
            asignaciones_por_profesor[entrevistador_id] = asignaciones_por_profesor.get(entrevistador_id, 0) + 1
            franja['espacios_libres'] -= 1
            franja['asignaciones_actuales'] += 1
            
            idx_candidato += 1
            
            if franja['espacios_libres'] == 0:
                idx_franja += 1
        
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
            algoritmo_usado='balanceado',
            tiempo_ejecucion_segundos=round(tiempo_total, 2),
            estado='exito' if len(asignaciones_creadas) == len(candidatos) else 'parcial',
            mensaje=f'Asignación desde interfaz web. Candidatos W{semana_carga.split("-W")[1]} → Entrevistas W{semana_entrevistas.split("-W")[1]}',
            ejecutado_por_usuario_id=session['user_id']
        )
        
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensaje': f'{len(asignaciones_creadas)} candidatos asignados correctamente',
            'candidatos_asignados': len(asignaciones_creadas),
            'candidatos_sin_asignar': len(candidatos) - len(asignaciones_creadas),
            'franjas_utilizadas': len(set([a['reserva_id'] for a in asignaciones_creadas])),
            'semana_carga': semana_carga,
            'semana_entrevistas': semana_entrevistas,
            'tiempo_segundos': round(tiempo_total, 2)
        })
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error al ejecutar asignación: {str(e)}'}), 500


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
                    
                except Exception as e:
                    resultados['candidatos_error'] += 1
                    resultados['errores'].append({
                        'candidato': f"{asignacion.candidato.nombre} {asignacion.candidato.apellidos}",
                        'error': str(e)
                    })
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
