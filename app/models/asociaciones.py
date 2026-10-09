"""
Tablas de asociación (muchos-a-muchos) que no necesitan su propia clase
de modelo porque no tienen comportamiento propio, solo las claves foráneas
(y, en este caso, una columna de auditoría).

Sacarlas a su propio fichero evita el problema de orden de import: tanto
`usuario.py` como `sede.py` pueden importar `usuario_sede` desde aquí sin
depender el uno del otro.
"""

from datetime import datetime

from app.extensions import db

usuario_sede = db.Table(
    "usuario_sede",
    db.Column(
        "usuario_id",
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "sede_id",
        db.Integer,
        db.ForeignKey("sedes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column("fecha_asignacion", db.DateTime, default=datetime.utcnow),
)