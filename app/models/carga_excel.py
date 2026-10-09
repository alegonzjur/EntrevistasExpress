from datetime import datetime

from app.extensions import db


class CargaExcel(db.Model):
    __tablename__ = "cargas_excel"

    id = db.Column(db.Integer, primary_key=True)
    archivo_nombre = db.Column(db.String(255), nullable=False)
    archivo_hash = db.Column(db.String(64))
    fecha_carga = db.Column(db.DateTime, default=datetime.utcnow)
    candidatos_totales = db.Column(db.Integer, nullable=False)
    candidatos_importados = db.Column(db.Integer, nullable=False)
    candidatos_duplicados = db.Column(db.Integer, default=0)
    cargado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    semana_destino = db.Column(db.String(20))
    estado = db.Column(db.String(20), default="completado")
    mensaje = db.Column(db.Text)

    cargado_por = db.relationship("Usuario", backref="cargas_excel")