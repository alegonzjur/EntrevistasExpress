from datetime import datetime

from app.extensions import db


class LogActividad(db.Model):
    __tablename__ = "logs_actividad"

    id = db.Column(db.Integer, primary_key=True)
    fecha_hora = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    usuario_username = db.Column(db.String(80), nullable=True)
    accion = db.Column(db.String(50), nullable=False, index=True)
    entidad = db.Column(db.String(50), nullable=False, index=True)
    entidad_id = db.Column(db.Integer, nullable=True)
    descripcion = db.Column(db.Text, nullable=False)
    datos_anteriores = db.Column(db.Text, nullable=True)
    datos_nuevos = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    nivel = db.Column(db.String(20), default="info", nullable=False)
    metadata_extra = db.Column(db.Text, nullable=True)

    usuario = db.relationship(
        "Usuario", backref="logs_actividad", foreign_keys=[usuario_id]
    )

    def to_dict(self):
        return {
            "id": self.id,
            "fecha_hora": self.fecha_hora.strftime("%d/%m/%Y %H:%M:%S"),
            "usuario": self.usuario_username,
            "accion": self.accion,
            "entidad": self.entidad,
            "entidad_id": self.entidad_id,
            "descripcion": self.descripcion,
            "nivel": self.nivel,
        }