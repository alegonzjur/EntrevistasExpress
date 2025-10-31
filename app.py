from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
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
    reservas = db.relationship('Reserva', backref='usuario', lazy=True)

class Espacio(db.Model):
    __tablename__ = 'espacios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    color = db.Column(db.String(7), default='#667eea')  # Color en hexadecimal para cada día
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
    notas = db.Column(db.Text)  # Campo para notas adicionales

# Rutas
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('reservas'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        usuario = Usuario.query.filter_by(username=username).first()
        
        if usuario and check_password_hash(usuario.password, password):
            session['user_id'] = usuario.id
            session['username'] = usuario.username
            return redirect(url_for('reservas'))
        else:
            return render_template('login.html', error='Usuario o contraseña incorrectos')
    
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if Usuario.query.filter_by(username=username).first():
            return render_template('registro.html', error='El usuario ya existe')
        
        if Usuario.query.filter_by(email=email).first():
            return render_template('registro.html', error='El email ya está registrado')
        
        hashed_password = generate_password_hash(password)
        nuevo_usuario = Usuario(username=username, email=email, password=hashed_password)
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        return redirect(url_for('login'))
    
    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/reservas')
def reservas():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
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
    
    return render_template('reservas.html', 
                         espacios=dias_semana,
                         fecha_seleccionada=fecha_str,
                         semana_anterior=semana_anterior,
                         semana_siguiente=semana_siguiente,
                         fecha_inicio_semana=lunes.strftime('%d/%m/%Y'),
                         fecha_fin_semana=(lunes + timedelta(days=4)).strftime('%d/%m/%Y'),
                         username=session['username'])

@app.route('/api/franjas/<int:dia_id>')
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
            if hora == 19 and minuto == 30:  # Última franja
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
                'es_mia': reserva.usuario_id == session.get('user_id') if reserva else False
            })
    
    return jsonify(franjas)

@app.route('/api/reservar', methods=['POST'])
def hacer_reserva():
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    data = request.json
    espacio_id = data['espacio_id']
    fecha_str = data['fecha']
    hora_inicio_str = data['hora_inicio']
    hora_fin_str = data['hora_fin']
    notas = data.get('notas', '')
    
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
        usuario_id=session['user_id'],
        espacio_id=espacio_id,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        notas=notas
    )
    
    db.session.add(nueva_reserva)
    db.session.commit()
    
    return jsonify({'success': True, 'mensaje': 'Reserva realizada correctamente'})

@app.route('/api/cancelar', methods=['POST'])
def cancelar_reserva():
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
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
            hora_inicio=hora_inicio,
            usuario_id=session['user_id']
        ).first()
    
    if not reserva:
        return jsonify({'error': 'Reserva no encontrada'}), 404
    
    if reserva.usuario_id != session['user_id']:
        return jsonify({'error': 'No tienes permiso para cancelar esta reserva'}), 403
    
    db.session.delete(reserva)
    db.session.commit()
    
    return jsonify({'success': True, 'mensaje': 'Reserva cancelada correctamente'})

@app.route('/mis-reservas')
def mis_reservas():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
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
                         username=session['username'])

@app.route('/api/estadisticas')
def estadisticas():
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    # Estadísticas del usuario
    total_reservas = Reserva.query.filter_by(usuario_id=session['user_id']).count()
    
    # Reservas por día de la semana
    reservas_usuario = Reserva.query.filter_by(usuario_id=session['user_id']).all()
    reservas_por_dia = {}
    nombres_dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    
    for reserva in reservas_usuario:
        dia_semana = nombres_dias[reserva.fecha.weekday()]
        reservas_por_dia[dia_semana] = reservas_por_dia.get(dia_semana, 0) + 1
    
    return jsonify({
        'total_reservas': total_reservas,
        'reservas_por_dia': reservas_por_dia
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Actualizar la tabla espacios si existe para añadir el campo color
        # Esto es una migración simple, en producción usarías Alembic
        
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
            db.session.commit()
            print("Días de la semana creados correctamente")
    
    app.run(debug=True)
