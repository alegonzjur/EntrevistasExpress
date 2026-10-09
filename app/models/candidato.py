import json
from datetime import datetime

from app.extensions import db


class Candidato(db.Model):
    __tablename__ = "candidatos"

    clave_academica = db.Column(db.String(20), primary_key=True, nullable=False)
    solicitud = db.Column(db.Integer, nullable=False)
    apellidos = db.Column(db.String(150), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    telefono = db.Column(db.String(20), nullable=True)
    media_estudios = db.Column(db.Numeric(4, 2), nullable=False)
    primera_opcion = db.Column(db.Text)
    sede = db.Column(db.String(50), nullable=True)
    estado = db.Column(db.String(20), default="pendiente", nullable=False)
    fecha_carga = db.Column(db.DateTime, default=datetime.utcnow)
    semana_carga = db.Column(db.String(20))
    archivo_origen = db.Column(db.String(255))

    # Franjas de disponibilidad.
    franjas_disponibilidad = db.Column(db.Text, nullable=True)  # Texto raw del Excel
    franjas_parseadas = db.Column(db.Text, nullable=True)  # JSON con franjas procesadas
    tiene_preferencias = db.Column(db.Boolean, default=False)  # Flag para priorización

    asignacion = db.relationship(
        "Asignacion", backref="candidato", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}"

    @property
    def tiene_email(self):
        return self.email is not None and self.email.strip() != ""

    def to_dict(self):
        return {
            "clave_academica": self.clave_academica,
            "solicitud": self.solicitud,
            "nombre_completo": self.nombre_completo,
            "email": self.email,
            "media_estudios": (
                float(self.media_estudios) if self.media_estudios else None
            ),
            "estado": self.estado,
            "primera_opcion": self.primera_opcion,
            "sede": self.sede,
            "sedes": [s.nombre for s in self.sedes],
            "tiene_preferencias": self.tiene_preferencias,
            "franjas_disponibilidad": self.franjas_disponibilidad,
        }

    def obtener_franjas_preferidas(self):
        """
        Devuelve lista de franjas preferidas parseadas

        Returns:
            List[dict]: [{'dia': 'Martes', 'turno': 'Mañana', 'hora_inicio': '10:00', 'hora_fin': '11:00'}, ...]
        """
        if not self.franjas_parseadas:
            return []

        try:
            return json.loads(self.franjas_parseadas)
        except Exception:
            return []