from datetime import datetime, timedelta

from app.extensions import db


class Asignacion(db.Model):
    __tablename__ = "asignaciones"

    id = db.Column(db.Integer, primary_key=True)
    candidato_clave = db.Column(
        db.String(20),
        db.ForeignKey("candidatos.clave_academica", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    reserva_id = db.Column(
        db.Integer, db.ForeignKey("reservas.id", ondelete="CASCADE"), nullable=False
    )
    entrevistador_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=False
    )
    posicion = db.Column(db.SmallInteger, nullable=False)
    minuto_inicio = db.Column(db.SmallInteger, nullable=False)
    estado = db.Column(db.String(20), default="confirmado", nullable=False)
    enviado_email = db.Column(db.Boolean, default=False)
    fecha_email = db.Column(db.DateTime, nullable=True)
    resultado = db.Column(db.Text, nullable=True)
    notas_entrevista = db.Column(db.Text, nullable=True)
    fecha_asignacion = db.Column(db.DateTime, default=datetime.utcnow)
    asignado_por_admin_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"), nullable=True
    )

    reserva = db.relationship("Reserva", backref="asignaciones")
    entrevistador = db.relationship(
        "Usuario", foreign_keys=[entrevistador_id], backref="entrevistas_asignadas"
    )
    asignado_por = db.relationship(
        "Usuario", foreign_keys=[asignado_por_admin_id], backref="asignaciones_creadas"
    )

    @property
    def hora_exacta(self):
        if self.reserva and self.reserva.hora_inicio:
            hora_base = datetime.combine(datetime.today(), self.reserva.hora_inicio)
            hora_exacta = hora_base + timedelta(minutes=self.minuto_inicio)
            return hora_exacta.time()
        return None