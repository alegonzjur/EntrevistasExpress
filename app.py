from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'a4f8d9e3b2c1a7f6e5d4c3b2a1f9e8d7c6b5a4f3e2d1c9b8a7f6e5d4c3b2a1f0'  # Cambia esto en producción
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://usuario:usuario@localhost/reservas_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelos de base de datos
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

# Decoradores para proteger rutas
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

# Rutas
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('reservas'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya está logueado, redirigir
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

@app.route('/reservas')
@login_required
def reservas():
    # Obtener la semana actual o la semana seleccionada
    fecha_str = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    fecha_base = datetime.strptime(fecha_str, '%Y-%m-%d')
    
    # Calcular el lunes de esa semana
    dias_hasta_lunes = fecha_base.weekday()
    lunes = fecha_base - timedelta(days=dias_hasta_lunes)
    
    # Generar los 5 días de la semana (Lunes a Viernes)
    dias_semana = []
    nombres_dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
    colores_dias = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b']
    
    for i in range(5):
        dia = lunes + timedelta(days=i)
        dias_semana.append({
            'id': i + 1,
            'nombre': nombres_dias[i],
            'fecha': dia.strftime('%Y-%m-%d'),
            'fecha_completa': dia.strftime('%d/%m/%Y'),
            'color': colores_dias[i]
        })
    
    # Calcular semana anterior y siguiente
    semana_anterior = (lunes - timedelta(days=7)).strftime('%Y-%m-%d')
    semana_siguiente = (lunes + timedelta(days=7)).strftime('%Y-%m-%d')
    
    # Si es admin, obtener lista de todos los usuarios para el selector
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
    
    # Generar franjas horarias de media hora (de 9:00 a 19:30)
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
            
            # Verificar si está reservada
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
    
    # NUEVO: Permitir al admin reservar para otro usuario
    usuario_id_destino = data.get('usuario_id', session['user_id'])
    
    # Solo admins pueden reservar para otros usuarios
    if usuario_id_destino != session['user_id'] and session.get('rol') != 'admin':
        return jsonify({'error': 'No tienes permiso para reservar en nombre de otros usuarios'}), 403
    
    fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M').time()
    hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time()
    
    # Verificar si ya está reservada
    reserva_existente = Reserva.query.filter_by(
        espacio_id=espacio_id,
        fecha=fecha,
        hora_inicio=hora_inicio
    ).first()
    
    if reserva_existente:
        return jsonify({'error': 'Esta franja ya está reservada'}), 400
    
    # Crear nueva reserva
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
    
    # Mensaje diferente si es admin reservando para otro
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
    
    # Los admins pueden cancelar cualquier reserva, los profesores solo las suyas
    if reserva.usuario_id != session['user_id'] and session.get('rol') != 'admin':
        return jsonify({'error': 'No tienes permiso para cancelar esta reserva'}), 403
    
    db.session.delete(reserva)
    db.session.commit()
    
    return jsonify({'success': True, 'mensaje': 'Reserva cancelada correctamente'})

@app.route('/mis-reservas')
@login_required
def mis_reservas():
    # Obtener reservas futuras y pasadas
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

# ==================== RUTAS DE ADMINISTRACIÓN ====================

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
    
    # No permitir desactivar al propio usuario admin
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
    
    # No permitir eliminar al propio usuario admin
    if usuario.id == session['user_id']:
        return jsonify({'error': 'No puedes eliminar tu propia cuenta'}), 400
    
    # Eliminar todas las reservas del usuario
    Reserva.query.filter_by(usuario_id=usuario_id).delete()
    
    db.session.delete(usuario)
    db.session.commit()
    
    return jsonify({'success': True, 'mensaje': f'Usuario {usuario.username} eliminado correctamente'})

@app.route('/admin/usuario/cambiar-rol/<int:usuario_id>', methods=['POST'])
@admin_required
def cambiar_rol_usuario(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    
    # No permitir cambiar el rol del propio usuario
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
    # Estadísticas generales
    total_usuarios = Usuario.query.count()
    total_profesores = Usuario.query.filter_by(rol='profesor').count()
    total_admins = Usuario.query.filter_by(rol='admin').count()
    usuarios_activos = Usuario.query.filter_by(activo=True).count()
    
    total_reservas = Reserva.query.count()
    
    # Reservas por usuario
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Crear usuario administrador por defecto si no existe
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
        
        # Crear espacios (días de la semana) si no existen
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
