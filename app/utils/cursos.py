"""
Cálculo del curso académico al que pertenece una fecha.

Convención de negocio (confirmada por el usuario): el curso académico va
del 1 de septiembre al 31 de agosto del año siguiente — p. ej. el 1 de
septiembre de 2026 empieza el curso "2026/2027", que termina el 31 de
agosto de 2027.

Es "utils" y no "services" por la misma razón que semanas.py: son
funciones puras sobre fechas, sin tocar la base de datos. Las usa
Reserva.curso (app/models/reserva.py) y la vista de administración de
"Todas las Reservas" (routes/reservas.py), para poder filtrar y mostrar
a qué curso pertenece cada reserva.
"""

from datetime import date


def obtener_curso_academico(fecha):
    """Curso académico (1 sep - 31 ago) de una fecha, como 'AAAA/AAAA+1'."""
    año_inicio = fecha.year if fecha.month >= 9 else fecha.year - 1
    return f"{año_inicio}/{año_inicio + 1}"


def rango_fechas_curso(curso):
    """Convierte 'AAAA/AAAA+1' (p. ej. '2026/2027') en el rango de fechas
    (fecha_inicio, fecha_fin) de ese curso: 1 de septiembre de AAAA al 31
    de agosto de AAAA+1."""
    año_inicio = int(curso.split("/")[0])
    inicio = date(año_inicio, 9, 1)
    fin = date(año_inicio + 1, 8, 31)
    return inicio, fin


def obtener_cursos_disponibles(fechas):
    """A partir de una colección de fechas (p. ej. las de todas las
    reservas existentes), devuelve la lista de cursos académicos
    distintos a los que pertenecen, del más reciente al más antiguo —
    pensada para rellenar un selector de filtro."""
    cursos = {obtener_curso_academico(f) for f in fechas}
    return sorted(cursos, reverse=True)