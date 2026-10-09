from datetime import datetime

from app.extensions import db
from app.models.asociaciones import usuario_sede


class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    nombre_completo = db.Column(db.String(150), nullable=True)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    rol = db.Column(db.String(20), default="profesor")  # 'admin' o 'profesor'
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    enlace_videollamada_personal = db.Column(db.String(500), nullable=True)
    sede = db.Column(db.String(50), nullable=True)

    sedes = db.relationship(
        "Sede",
        secondary=usuario_sede,
        lazy="subquery",
        backref=db.backref("profesores", lazy=True),
    )

    # Relación con reservas (especificando foreign_keys para evitar ambigüedad)
    reservas = db.relationship(
        "Reserva", foreign_keys="Reserva.usuario_id", backref="usuario", lazy=True
    )

    # Relación con reservas creadas como admin
    reservas_creadas = db.relationship(
        "Reserva",
        foreign_keys="Reserva.creado_por_admin",
        backref="creador_admin",
        lazy=True,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "rol": self.rol,
            "activo": self.activo,
            "sede": self.sede,  # Sede principal
            "sedes": [s.nombre for s in self.sedes] if self.sedes else [],
            "enlace_videollamada_personal": self.enlace_videollamada_personal,
        }

    def puede_atender_sede(self, sede_nombre):
        """Verifica si el profesor puede atender entrevistas de esta sede"""
        if not sede_nombre:
            return True  # Si no hay sede, puede atender cualquiera

        # Si tiene sedes específicas asignadas, verificar
        if self.sedes:
            return any(s.nombre == sede_nombre for s in self.sedes)

        # Si no tiene sedes asignadas pero tiene sede principal, usar esa
        if self.sede:
            return self.sede == sede_nombre

        # Si no tiene ninguna, puede atender cualquiera
        return True