"""
Auditoría: registrar_log escribe una entrada en logs_actividad por cada
acción relevante (crear/modificar/eliminar/asignar/...), y obtener_cambios
calcula el diff entre dos estados de un objeto para pasárselo como
datos_anteriores/datos_nuevos.
"""

import json
from datetime import datetime

from flask import request, session

from app.extensions import db
from app.models import LogActividad


def registrar_log(
    accion,
    entidad,
    entidad_id,
    descripcion,
    datos_anteriores=None,
    datos_nuevos=None,
    nivel="info",
    metadata=None,
):
    """
    Registra una acción en el log de auditoría

    Args:
        accion: 'crear', 'modificar', 'eliminar', 'asignar', 'enviar_email', etc.
        entidad: 'reserva', 'candidato', 'asignacion', 'usuario', etc.
        entidad_id: ID del objeto afectado
        descripcion: Descripción legible de la acción
        datos_anteriores: Dict con datos antes del cambio (se convierte a JSON)
        datos_nuevos: Dict con datos después del cambio (se convierte a JSON)
        nivel: 'info', 'warning', 'error', 'critical'
        metadata: Dict con información adicional
    """
    try:

        # Obtener usuario actual
        usuario_id = session.get("user_id")
        usuario_username = session.get("username", "Sistema")

        # Obtener IP y User Agent
        ip_address = request.remote_addr if request else None
        user_agent = request.headers.get("User-Agent", "")[:255] if request else None

        # Convertir dicts a JSON
        datos_anteriores_json = (
            json.dumps(datos_anteriores, default=str) if datos_anteriores else None
        )
        datos_nuevos_json = (
            json.dumps(datos_nuevos, default=str) if datos_nuevos else None
        )
        metadata_json = json.dumps(metadata, default=str) if metadata else None

        log = LogActividad(
            fecha_hora=datetime.utcnow(),
            usuario_id=usuario_id,
            usuario_username=usuario_username,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            descripcion=descripcion,
            datos_anteriores=datos_anteriores_json,
            datos_nuevos=datos_nuevos_json,
            ip_address=ip_address,
            user_agent=user_agent,
            nivel=nivel,
            metadata_extra=metadata_json,
        )

        db.session.add(log)
        db.session.commit()

    except Exception as e:
        print(f"Error al registrar log: {e}")
        # No fallar la operación principal si falla el log
        db.session.rollback()


def obtener_cambios(obj_anterior, obj_nuevo, campos):
    """
    Compara dos objetos y devuelve un dict con los cambios

    Args:
        obj_anterior: Objeto antes del cambio
        obj_nuevo: Objeto después del cambio
        campos: Lista de nombres de campos a comparar

    Returns:
        Tuple (datos_anteriores, datos_nuevos) con solo los campos que cambiaron
    """
    datos_anteriores = {}
    datos_nuevos = {}

    for campo in campos:
        valor_anterior = getattr(obj_anterior, campo, None)
        valor_nuevo = getattr(obj_nuevo, campo, None)

        # Convertir a string para comparación
        valor_anterior_str = str(valor_anterior) if valor_anterior is not None else None
        valor_nuevo_str = str(valor_nuevo) if valor_nuevo is not None else None

        if valor_anterior_str != valor_nuevo_str:
            datos_anteriores[campo] = valor_anterior_str
            datos_nuevos[campo] = valor_nuevo_str

    return datos_anteriores if datos_anteriores else None, (
        datos_nuevos if datos_nuevos else None
    )