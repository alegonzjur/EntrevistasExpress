"""
Cálculo de semanas ISO y del rango de fechas lunes-viernes de cada una.

Es "utils" y no "services" porque no toca la base de datos ni ningún
modelo: son funciones puras sobre fechas (entrada → salida, sin
dependencias). Lo usan services/candidatos.py, routes/reservas.py y
routes/candidatos.py, entre otros.
"""

from datetime import date, datetime, timedelta


def calcular_semana_iso(fecha):
    """Calcula la semana ISO de una fecha"""
    return fecha.strftime("%Y-W%W")


def parsear_semana_iso(semana_iso):
    """Convierte semana ISO a rango de fechas (lunes-viernes)"""
    año, semana = semana_iso.split("-W")
    primer_dia = datetime.strptime(f"{año}-W{semana}-1", "%Y-W%W-%w").date()
    viernes = primer_dia + timedelta(days=4)
    return primer_dia, viernes


def obtener_semanas_disponibles():
    """Obtiene lista de semanas para el selector"""
    hoy = date.today()
    semanas = []

    # 2 semanas atrás hasta 8 semanas adelante
    for i in range(-2, 9):
        fecha = hoy + timedelta(weeks=i)
        # Calcular lunes de esa semana
        dias_hasta_lunes = fecha.weekday()
        lunes = fecha - timedelta(days=dias_hasta_lunes)
        viernes = lunes + timedelta(days=4)

        semana_iso = calcular_semana_iso(lunes)

        semanas.append(
            {
                "iso": semana_iso,
                "lunes": lunes.strftime("%d/%m/%Y"),
                "viernes": viernes.strftime("%d/%m/%Y"),
                "label": f"Semana {semana_iso.split('-W')[1]} ({lunes.strftime('%d/%m')} - {viernes.strftime('%d/%m')})",
                "es_actual": i == 0,
            }
        )

    return semanas