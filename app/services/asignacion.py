"""
Algoritmo de prioridad para la asignación de candidatos a reservas.

De momento solo contiene `calcular_score_candidato`, la función de
puntuación. El resto del algoritmo de asignación (la función de ruta
`ejecutar_asignacion`, que recorre candidatos y reservas disponibles y
usa este score para decidir el emparejamiento) vive todavía dentro de
`app.py` como parte de una vista — se traerá aquí cuando lleguemos a
`routes/`, separando la vista (HTTP) del algoritmo (negocio).
"""

from app.services.franjas import franja_coincide_con_reserva


def calcular_score_candidato(candidato, reserva, espacio):
    """
    Calcula un score de prioridad para asignar un candidato a una reserva

    Score más alto = mayor prioridad

    Args:
        candidato (Candidato): Candidato a evaluar
        reserva (Reserva): Reserva disponible
        espacio (Espacio): Día de la semana

    Returns:
        int: Score de prioridad (0-1000)
    """

    score = 0

    # PRIORIDAD 1: Tiene preferencias y coincide con alguna (MÁXIMA PRIORIDAD)
    if candidato.tiene_preferencias:
        franjas = candidato.obtener_franjas_preferidas()

        for franja in franjas:
            if franja_coincide_con_reserva(franja, reserva, espacio):
                score += 500  # Bonus enorme por coincidencia de preferencia
                break

    # PRIORIDAD 2: Nota más baja (para ser justos)
    # Escala de 0 a 10 → invertir para que nota baja = score alto
    if candidato.media_estudios:
        nota_invertida = 10 - float(candidato.media_estudios)
        score += int(nota_invertida * 20)  # Hasta 200 puntos

    # PRIORIDAD 3: Sede coincidente (si el entrevistador tiene sede específica)
    if candidato.sede and reserva.usuario:
        entrevistador = reserva.usuario

        if entrevistador.puede_atender_sede(candidato.sede):
            score += 100  # Bonus por coincidencia de sede

    return score