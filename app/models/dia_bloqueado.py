from datetime import datetime

from app.extensions import db


class DiaBloqueado(db.Model):
    """
    Día en el que NO se asignan entrevistas a los candidatos de un campus
    (p. ej. un festivo local). La asignación automática ignora esa
    combinación fecha + sede. `sede` guarda el nombre del campus, igual
    que `Candidato.sede`, que es con lo que se compara.
    """

    __tablename__ = "dias_bloqueados"
    __table_args__ = (db.UniqueConstraint("fecha", "sede", name="uq_dia_bloqueado_fecha_sede"),)

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, index=True)
    sede = db.Column(db.String(50), nullable=False)
    motivo = db.Column(db.String(255))
    creado_por_usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    creado_por = db.relationship("Usuario", foreign_keys=[creado_por_usuario_id])