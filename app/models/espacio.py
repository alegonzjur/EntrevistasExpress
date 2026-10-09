from app.extensions import db


class Espacio(db.Model):
    __tablename__ = "espacios"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    color = db.Column(db.String(7), default="#667eea")
    reservas = db.relationship("Reserva", backref="espacio", lazy=True)