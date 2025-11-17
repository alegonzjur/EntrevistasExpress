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

app = Flask(__name__)
app.secret_key = 'a4f8d9e3b2c1a7f6e5d4c3b2a1f9e8d7c6b5a4f3e2d1c9b8a7f6e5d4c3b2a1f0'  # Cambia esto en producción
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:eebormujos?@localhost/reservas_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
    hora_inicio = 9
    hora_fin = 20
    
    for hora in range(hora_inicio, hora_fin):
        for minuto in [0, 30]:
            if hora == 19 and minuto == 30:
                franja_inicio = f"{hora:02d}:30"
                franja_fin = "20:00"
            else:
                franja_inicio = f"{hora:02d}:{minuto:02d}"
                if minuto == 0:
                    franja_fin = f"{hora:02d}:30"
                else:
                    franja_fin = f"{hora + 1:02d}:00"
            
            reserva = Reserva.query.filter_by(
                espacio_id=dia_id,
                fecha=fecha,
                hora_inicio=datetime.strptime(franja_inicio, '%H:%M').time()
            ).first()
            
            franjas.append({
                'hora_inicio': franja_inicio,
                'hora_fin': franja_fin,
                'disponible': reserva is None,
                'reservada_por': reserva.usuario.username if reserva else None,
                'reserva_id': reserva.id if reserva else None,
                'notas': reserva.notas if reserva else None,
                'es_mia': reserva.usuario_id == session.get('user_id') if reserva else False,
                'puede_cancelar': (reserva.usuario_id == session.get('user_id') or session.get('rol') == 'admin') if reserva else False
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
    
    reserva_existente = Reserva.query.filter_by(
        espacio_id=espacio_id,
        fecha=fecha,
        hora_inicio=hora_inicio
    ).first()
    
    if reserva_existente:
        return jsonify({'error': 'Esta franja ya está reservada'}), 400
    
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
        columnas_necesarias = ['Solicitud', 'Apellidos', 'Nombre', 'Media estudios realizados', 'Primera opción']
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
            'Primera opción': 'primera_opcion'
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
        df_filtrado['email'] = None
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
        
        # SOLUCIÓN: Usar la sesión de db directamente, no crear una nueva
        inicio = datetime.now()
        
        # Obtener candidatos ordenados por nota (usando query de Flask-SQLAlchemy)
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
            
            # Máximo 2 candidatos por franja
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
            
            # Crear asignación
            asignacion = Asignacion(
                candidato_id=candidato.id,
                reserva_id=reserva.id,
                entrevistador_id=entrevistador_id,
                posicion=posicion,
                minuto_inicio=minuto_inicio,
                hora_exacta=hora_exacta.time(),
                estado='confirmado',
                fecha_asignacion=datetime.now(),
                asignado_por_admin_id=session['user_id']
            )
            
            db.session.add(asignacion)
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
        
        # Guardar todo en una sola transacción
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
