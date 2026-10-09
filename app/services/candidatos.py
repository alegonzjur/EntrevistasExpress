"""
Consultas y utilidades de negocio sobre Candidato: detección de sede a
partir del texto libre del Excel, y los listados/estadísticas que usan
las vistas de administración de candidatos.
"""

import unicodedata

from app.models import Candidato


def detectar_sede_desde_primera_opcion(primera_opcion):
    """
    Detecta la sede a partir del campo 'primera_opcion'

    Busca las palabras clave en el texto:
    - "Bormujos" -> Bormujos
    - "Pº de la Habana" o "Paseo de la Habana" -> Pº de la Habana
    - "Ciempozuelos" -> Ciempozuelos

    Args:
        primera_opcion: String con la primera opción del candidato

    Returns:
        String con el nombre de la sede o None si no se detecta
    """
    if not primera_opcion:
        return None

    def normalizar_texto(texto):
        # Quitar acentos
        texto_sin_acentos = "".join(
            c
            for c in unicodedata.normalize("NFD", texto)
            if unicodedata.category(c) != "Mn"
        )
        # Convertir a mayúsculas
        return texto_sin_acentos.upper()

    texto_normalizado = normalizar_texto(primera_opcion)
    texto_limpio = texto_normalizado.replace("º", "").replace("°", "").replace("O", "")
    # Convertir a mayúsculas para facilitar la búsqueda
    # Buscar patrones de "Pº de la Habana", "Paseo de la Habana", "P de la Habana"
    if any(
        patron in texto_limpio
        for patron in ["P DE LA HABANA", "PASEO DE LA HABANA", "PDELA HABANA"]
    ):
        return "Pº de la Habana"

    # También buscar en texto original por si acaso
    if "HABANA" in texto_normalizado:
        return "Pº de la Habana"

    if "BORMUJOS" in texto_normalizado:
        return "Bormujos"

    if "CIEMPOZUELOS" in texto_normalizado:
        return "Ciempozuelos"

    # Si no se detecta ninguna sede
    return None


def obtener_candidatos_pendientes():
    """Obtiene candidatos pendientes ordenados por nota"""
    return (
        Candidato.query.filter_by(estado="pendiente")
        .order_by(Candidato.media_estudios.asc())
        .all()
    )


def obtener_candidatos_por_semana(semana):
    """Obtiene candidatos de una semana específica"""
    return (
        Candidato.query.filter_by(semana_carga=semana)
        .order_by(Candidato.media_estudios.asc())
        .all()
    )


def obtener_estadisticas_semana_candidatos(semana):
    """Obtiene estadísticas de candidatos de una semana"""
    candidatos = Candidato.query.filter_by(semana_carga=semana).all()

    total = len(candidatos)
    asignados = len([c for c in candidatos if c.estado == "asignado"])
    pendientes = len([c for c in candidatos if c.estado == "pendiente"])
    entrevistados = len([c for c in candidatos if c.estado == "entrevistado"])

    return {
        "total_candidatos": total,
        "candidatos_asignados": asignados,
        "candidatos_pendientes": pendientes,
        "candidatos_entrevistados": entrevistados,
        "tasa_asignacion": round((asignados / total * 100) if total > 0 else 0, 2),
    }