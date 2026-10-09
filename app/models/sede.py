from datetime import datetime

from app.extensions import db


class Sede(db.Model):
    __tablename__ = "sedes"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    activa = db.Column(db.Boolean, default=True)
    descripcion = db.Column(db.String(255))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Sede {self.nombre}>"