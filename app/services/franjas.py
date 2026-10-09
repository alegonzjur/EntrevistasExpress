"""
Parseo de las franjas de disponibilidad que los candidatos indican en el
Excel, y comprobación de si una franja de preferencia coincide con una
reserva (día + hora) ya creada en el calendario.

Es "services" y no "utils" porque, aunque `parsear_franjas_disponibilidad`
es pura, `franja_coincide_con_reserva` ya trabaja con objetos de los
modelos (Reserva, Espacio) — es lógica de negocio del dominio de citas,
no una utilidad genérica.
"""

import re
from datetime import datetime

import pandas as pd

# Mapeo de días a número (0=Lunes ... 6=Domingo), usado para ordenar y
# para comparar con el día de la semana al que corresponde un Espacio.
DIAS_MAP = {
    "LUNES": 0,
    "MARTES": 1,
    "MIERCOLES": 2,
    "MIÉRCOLES": 2,
    "JUEVES": 3,
    "VIERNES": 4,
    "SABADO": 5,
    "SÁBADO": 5,
    "DOMINGO": 6,
}

# Mapeo de nombre de Espacio (que en este proyecto representa el día de
# la semana) a número de día. Es un mapeo distinto y más corto que
# DIAS_MAP porque solo cubre los días laborales que la app agenda.
ESPACIOS_MAP = {"Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3, "Viernes": 4}


def parsear_franjas_disponibilidad(texto_franjas):
    """
    Parsea el texto de franjas de disponibilidad del Excel

    Formato de entrada:
        • Martes - Mañana - de 10 a 11
        • Miércoles - Tarde - de 15 a 16
        • Jueves - Mañana - de 11 a 12

    Args:
        texto_franjas (str): Texto con las franjas del Excel

    Returns:
        list: Lista de diccionarios con franjas parseadas
        [
            {
                'dia': 'Martes',
                'turno': 'Mañana',
                'hora_inicio': '10:00',
                'hora_fin': '11:00',
                'dia_numero': 1  # 0=Lunes, 1=Martes, etc.
            },
            ...
        ]
    """

    if not texto_franjas or pd.isna(texto_franjas) or str(texto_franjas).strip() == "":
        return []

    franjas_parseadas = []

    # Normalizar texto
    texto = str(texto_franjas)

    # Dividir por líneas y bullets
    lineas = re.split(r"[•\n]", texto)

    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue

        # Patrón: "Martes - Mañana - de 10 a 11"
        # Formato flexible para capturar diferentes variaciones
        patron = r"(\w+)\s*-\s*(Mañana|Tarde|mañana|tarde)\s*-\s*de\s*(\d{1,2})\s*a\s*(\d{1,2})"

        match = re.search(patron, linea, re.IGNORECASE)

        if match:
            dia = match.group(1).strip().upper()
            turno = match.group(2).strip().capitalize()
            hora_inicio = int(match.group(3))
            hora_fin = int(match.group(4))

            # Normalizar día (quitar acentos)
            dia_normalizado = dia.replace("É", "E").replace("Á", "A")

            # Obtener número del día
            dia_numero = DIAS_MAP.get(dia_normalizado)

            if dia_numero is not None:
                franja = {
                    "dia": dia.capitalize(),
                    "dia_normalizado": dia_normalizado,
                    "dia_numero": dia_numero,
                    "turno": turno,
                    "hora_inicio": f"{hora_inicio:02d}:00",
                    "hora_fin": f"{hora_fin:02d}:00",
                }

                franjas_parseadas.append(franja)

    return franjas_parseadas


def franja_coincide_con_reserva(franja_parseada, reserva, espacio):
    """
    Verifica si una franja de preferencia del candidato coincide con una reserva

    Args:
        franja_parseada (dict): Franja del candidato parseada
        reserva (Reserva): Objeto reserva de la BD
        espacio (Espacio): Objeto espacio (día de la semana)

    Returns:
        bool: True si coincide, False si no
    """

    # Verificar que el día coincide
    dia_reserva = ESPACIOS_MAP.get(espacio.nombre)

    if dia_reserva != franja_parseada["dia_numero"]:
        return False

    # Verificar que la hora coincide
    hora_inicio_reserva = reserva.hora_inicio.strftime("%H:%M")
    hora_fin_reserva = reserva.hora_fin.strftime("%H:%M")

    # Comparar horas (exactas o dentro del rango)
    if hora_inicio_reserva == franja_parseada["hora_inicio"]:
        return True

    # Alternativa: verificar si la reserva está dentro del rango de la franja
    # (útil si las franjas del Excel son de 1 hora pero las reservas de 30 min)
    try:
        hora_ini_franja = datetime.strptime(
            franja_parseada["hora_inicio"], "%H:%M"
        ).time()
        hora_fin_franja = datetime.strptime(franja_parseada["hora_fin"], "%H:%M").time()

        # Verificar si la hora de inicio de la reserva está dentro de la franja
        if hora_ini_franja <= reserva.hora_inicio < hora_fin_franja:
            return True
    except Exception:
        pass

    return False