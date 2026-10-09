"""
Paquete de modelos. Importar todos los módulos aquí es necesario para que
SQLAlchemy registre cada clase en su metadata ANTES de que se configuren los
mappers (algo que Flask-SQLAlchemy hace automáticamente en la primera
consulta, o `db.create_all()`). Las relaciones que se definen por nombre en
forma de string (p. ej. `db.relationship("Reserva", ...)`) dependen de que
la clase `Reserva` ya se haya importado en algún punto antes de usarse.

Así, en el resto de la aplicación basta con:
    from app.models import Usuario, Sede, Reserva, ...
en vez de importar cada submódulo por separado.
"""

from app.models.asociaciones import usuario_sede
from app.models.sede import Sede
from app.models.usuario import Usuario
from app.models.espacio import Espacio
from app.models.reserva import Reserva
from app.models.candidato import Candidato
from app.models.asignacion import Asignacion
from app.models.carga_excel import CargaExcel
from app.models.log_asignacion import LogAsignacion
from app.models.log_actividad import LogActividad

__all__ = [
    "usuario_sede",
    "Sede",
    "Usuario",
    "Espacio",
    "Reserva",
    "Candidato",
    "Asignacion",
    "CargaExcel",
    "LogAsignacion",
    "LogActividad",
]