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
    # Desde la migración de 2026-10-15: deja de ser obligatoria. El Excel
    # semanal puede traer esta celda vacía para algún alumno, y eso ya no
    # impide cargarlo — simplemente queda sin nota (ver
    # `media_estudios_texto` más abajo, y services/etl_candidatos.py).
    media_estudios = db.Column(db.Numeric(4, 2), nullable=True)
    # Desde la migración de 2026-10-15: ya no es el texto libre completo
    # del Excel ("Grado en Enfermería. CCS de Bormujos..."), sino solo el
    # centro detectado (Bormujos / Ciempozuelos / Pº de la Habana) — el
    # mismo valor que `sede`. Se mantienen ambas columnas porque `sede`
    # es la que usa la lógica de asignación (ver services/asignacion.py),
    # y conviene no acoplar esa lógica al nombre de una columna que, por
    # su nombre, un futuro cambio del Excel podría llevar a reinterpretar.
    primera_opcion = db.Column(db.Text)
    sede = db.Column(db.String(50), nullable=True)
    forma_acceso = db.Column(db.String(50), nullable=True)
    tipo_bachillerato = db.Column(db.String(100), nullable=True)
    tipo_fpii_cgs = db.Column(db.String(100), nullable=True)
    convocatoria = db.Column(db.Integer, nullable=True)
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

    @property
    def media_estudios_texto(self):
        """
        Representación legible de la nota para plantillas y exportaciones:
        "No disponible" si no se cargó, en vez de dejar que un
        `"%.2f"|format(None)` falle, o mostrar un 0 que parecería una nota
        real (y se vería, erróneamente, como la peor nota posible).
        """
        if self.media_estudios is None:
            return "No disponible"
        return f"{float(self.media_estudios):.2f}"

    def to_dict(self):
        # BUG corregido: la línea original ("sedes": [s.nombre for s in
        # self.sedes]) daba AttributeError, porque Candidato no tiene
        # ninguna relación `sedes` — esa relación existe en Usuario (ver
        # app/models/usuario.py), de donde parece que se copió por error.
        # Candidato solo tiene el campo `sede` (string simple). Como
        # to_dict() nunca se llama desde ningún sitio del proyecto
        # (confirmado por grep: ninguna ruta ni servicio lo usa), nunca se
        # había detectado en producción. Se corrige devolviendo `sede`
        # también como lista de un elemento, que es lo que el nombre de la
        # clave ("sedes", en plural) sugiere que se pretendía.
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
            "sedes": [self.sede] if self.sede else [],
            "tiene_preferencias": self.tiene_preferencias,
            "franjas_disponibilidad": self.franjas_disponibilidad,
        }

    @property
    def disponibilidad_resumen(self):
        """
        Disponibilidad del candidato en formato corto para mostrar y filtrar:
        solo día + turno, sin horas ("Jueves tarde", "Viernes mañana"...),
        sin repetidos y ordenada de lunes a viernes (mañana antes que tarde).

        Cada elemento es un dict:
            {"dia_numero": 3, "turno": "tarde", "texto": "Jueves tarde",
             "clave": "3-tarde"}
        `clave` (día-turno, sin acentos) es lo que usa el filtro de la
        gestión manual para comparar en el navegador.
        """
        resumen = {}
        for franja in self.obtener_franjas_preferidas():
            dia_numero = franja.get("dia_numero")
            dia = franja.get("dia")
            turno = (franja.get("turno") or "").strip().lower()
            if dia_numero is None or not dia or not turno:
                continue
            turno_slug = turno.replace("ñ", "n")
            resumen[(dia_numero, turno_slug)] = {
                "dia_numero": dia_numero,
                "turno": turno_slug,
                "texto": f"{dia} {turno}",
                "clave": f"{dia_numero}-{turno_slug}",
            }
        return [resumen[k] for k in sorted(resumen)]

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