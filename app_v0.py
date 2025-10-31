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
    
    espacios = Espacio.query.all()
    fecha_seleccionada = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    
    return render_template('reservas.html', 
                         espacios=espacios, 
                         fecha_seleccionada=fecha_seleccionada,
                         username=session['username'])

@app.route('/api/franjas/<int:espacio_id>')
def obtener_franjas(espacio_id):
    fecha_str = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
    fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    
    # Generar franjas horarias (de 8:00 a 20:00, cada hora)
    franjas = []
    hora_inicio = 8
    hora_fin = 20
    
    for hora in range(hora_inicio, hora_fin):
        franja_inicio = f"{hora:02d}:00"
        franja_fin = f"{hora + 1:02d}:00"
        
        # Verificar si está reservada
        reserva = Reserva.query.filter_by(
            espacio_id=espacio_id,
            fecha=fecha,
            hora_inicio=datetime.strptime(franja_inicio, '%H:%M').time()
        ).first()
        
        franjas.append({
            'hora_inicio': franja_inicio,
            'hora_fin': franja_fin,
            'disponible': reserva is None,
            'reservada_por': reserva.usuario.username if reserva else None
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
        hora_fin=hora_fin
    )
    
    db.session.add(nueva_reserva)
    db.session.commit()
    
    return jsonify({'success': True, 'mensaje': 'Reserva realizada correctamente'})

@app.route('/api/cancelar', methods=['POST'])
def cancelar_reserva():
    if 'user_id' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    data = request.json
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
        return jsonify({'error': 'No tienes permiso para cancelar esta reserva'}), 403
    
    db.session.delete(reserva)
    db.session.commit()
    
    return jsonify({'success': True, 'mensaje': 'Reserva cancelada correctamente'})

@app.route('/mis-reservas')
def mis_reservas():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    reservas = Reserva.query.filter_by(usuario_id=session['user_id']).order_by(Reserva.fecha.desc()).all()
    return render_template('mis_reservas.html', reservas=reservas, username=session['username'])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Crear espacios de ejemplo si no existen
        if Espacio.query.count() == 0:
            espacios_ejemplo = [
                Espacio(nombre='Sala de Reuniones A', descripcion='Capacidad para 10 personas'),
                Espacio(nombre='Sala de Reuniones B', descripcion='Capacidad para 6 personas'),
                Espacio(nombre='Espacio Coworking', descripcion='Escritorios compartidos'),
            ]
            for espacio in espacios_ejemplo:
                db.session.add(espacio)
            db.session.commit()
    
    app.run(debug=True)