from datetime import datetime

from app.extensions import db


class LogAsignacion(db.Model):
    __tablename__ = "logs_asignacion"

    id = db.Column(db.Integer, primary_key=True)
    fecha_ejecucion = db.Column(db.DateTime, default=datetime.utcnow)
    semana_objetivo = db.Column(db.String(20), nullable=False)
    candidatos_procesados = db.Column(db.Integer, nullable=False)
    candidatos_filtrados = db.Column(db.Integer, nullable=False)
    candidatos_asignados = db.Column(db.Integer, nullable=False)
    candidatos_sin_asignar = db.Column(db.Integer, nullable=False)
    franjas_utilizadas = db.Column(db.Integer, nullable=False)
    algoritmo_usado = db.Column(db.String(50), default="balanceado")
    tiempo_ejecucion_segundos = db.Column(db.Numeric(6, 2))
    estado = db.Column(db.String(20), nullable=False)
    mensaje = db.Column(db.Text)
    ejecutado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    archivo_origen = db.Column(db.String(255))

    ejecutado_por = db.relationship("Usuario", backref="logs_asignaciones")