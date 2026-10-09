from datetime import datetime

from app.extensions import db


class Reserva(db.Model):
    __tablename__ = "reservas"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    espacio_id = db.Column(db.Integer, db.ForeignKey("espacios.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    notas = db.Column(db.Text)
    creado_por_admin = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=True
    )
    prioridad = db.Column(db.String(20), default="normal", nullable=False)