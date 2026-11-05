"""
Gestión de candidatos repetidos de una carga de Excel.

Al cargar un Excel, los candidatos cuya clave ya existe en la base de
datos se omiten (normalmente es lo correcto: el Excel semanal acumula a
los de semanas anteriores). Pero a veces un candidato no llegó a tener su
entrevista y hay que traerlo a la semana actual. Para poder decidirlo
después de la carga, las filas omitidas se guardan en un JSON dentro de
UPLOAD_FOLDER/repetidos/carga_<id>.json (sin tabla nueva ni migración).

Los datos de las filas salen siempre de ese fichero guardado por el
servidor, nunca de lo que envíe el navegador: el cliente solo indica
*qué claves* quiere recargar.
"""

import json
import os
import time
from datetime import datetime

from flask import current_app

from app.extensions import db
from app.models import Candidato, CargaExcel

DIAS_CADUCIDAD = 60

# Campos de la fila guardada que se copian al nuevo Candidato.
CAMPOS_CANDIDATO = [
    "clave_academica", "solicitud", "apellidos", "nombre", "email",
    "telefono", "media_estudios", "primera_opcion", "sede", "forma_acceso",
    "tipo_bachillerato", "tipo_fpii_cgs", "convocatoria",
    "franjas_disponibilidad", "franjas_parseadas", "tiene_preferencias",
]


def _directorio():
    ruta = os.path.join(current_app.config["UPLOAD_FOLDER"], "repetidos")
    os.makedirs(ruta, exist_ok=True)
    return ruta


def _ruta(carga_id):
    return os.path.join(_directorio(), f"carga_{int(carga_id)}.json")


def _limpiar_caducados():
    limite = time.time() - DIAS_CADUCIDAD * 86400
    for nombre in os.listdir(_directorio()):
        ruta = os.path.join(_directorio(), nombre)
        try:
            if os.path.getmtime(ruta) < limite:
                os.remove(ruta)
        except OSError:
            pass


def guardar_repetidos(carga_id, filas):
    """Guarda las filas omitidas de una carga (no hace nada si no hay)."""
    if not filas:
        return
    _limpiar_caducados()
    with open(_ruta(carga_id), "w", encoding="utf-8") as f:
        json.dump({"carga_id": carga_id, "filas": filas}, f, ensure_ascii=False)


def cargar_repetidos(carga_id):
    """Filas guardadas de la carga ([] si no hay)."""
    try:
        with open(_ruta(carga_id), encoding="utf-8") as f:
            return json.load(f).get("filas", [])
    except (OSError, ValueError):
        return []


def borrar_repetidos(carga_id):
    try:
        os.remove(_ruta(carga_id))
    except OSError:
        pass


def cargas_con_repetidos(ids):
    """Subconjunto de `ids` que todavía tiene repetidos pendientes."""
    return {i: len(cargar_repetidos(i)) for i in ids if cargar_repetidos(i)}


def listar_repetidos(carga_id):
    """Filas guardadas enriquecidas con el estado *actual* del candidato."""
    resultado = []
    for fila in cargar_repetidos(carga_id):
        actual = db.session.get(Candidato, fila["clave_academica"])
        asig = actual.asignacion if actual else None
        resultado.append({
            "clave": fila["clave_academica"],
            "nombre": f"{fila.get('nombre') or ''} {fila.get('apellidos') or ''}".strip(),
            "solicitud": fila.get("solicitud"),
            "sede": fila.get("sede"),
            "existe": actual is not None,
            "semana_actual": actual.semana_carga if actual else None,
            "estado_actual": actual.estado if actual else None,
            "asignado": asig is not None,
            "email_enviado": bool(asig and asig.enviado_email),
            "entrevistado": bool(
                actual and (actual.estado == "entrevistado"
                            or (asig and (asig.resultado or asig.notas_entrevista)))
            ),
        })
    return resultado


def recargar_repetidos(carga, claves):
    """
    Mueve los candidatos indicados a la semana de `carga`: borra el
    candidato anterior (y su asignación) y crea uno nuevo en estado
    pendiente. Todo en una única transacción: si algo falla no se pierde
    nada. Devuelve la lista de claves recargadas.
    """
    claves = list(dict.fromkeys(claves))
    por_clave = {f["clave_academica"]: f for f in cargar_repetidos(carga.id)}
    elegidas = [c for c in claves if c in por_clave]
    if not elegidas:
        return []

    ahora = datetime.utcnow()
    try:
        for clave in elegidas:
            anterior = db.session.get(Candidato, clave)
            if anterior is not None:
                db.session.delete(anterior)   # la asignación cae en cascada
        db.session.flush()

        for clave in elegidas:
            fila = por_clave[clave]
            datos = {k: fila.get(k) for k in CAMPOS_CANDIDATO}
            db.session.add(Candidato(
                **datos, estado="pendiente", fecha_carga=ahora,
                semana_carga=carga.semana_destino,
                archivo_origen=carga.archivo_nombre,
            ))

        carga.candidatos_importados = (carga.candidatos_importados or 0) + len(elegidas)
        carga.candidatos_duplicados = max(0, (carga.candidatos_duplicados or 0) - len(elegidas))
        carga.mensaje = (carga.mensaje or "") + f" · {len(elegidas)} repetidos recargados"
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    restantes = [f for c, f in por_clave.items() if c not in elegidas]
    if restantes:
        with open(_ruta(carga.id), "w", encoding="utf-8") as f:
            json.dump({"carga_id": carga.id, "filas": restantes}, f, ensure_ascii=False)
    else:
        borrar_repetidos(carga.id)
    return elegidas


def descartar_repetidos(carga_id, claves=None):
    """
    Elimina de lo guardado los repetidos indicados (todos si `claves` es
    None), sin cargarlos. No toca la tabla de candidatos. Devuelve cuántos
    se descartaron.
    """
    filas = cargar_repetidos(carga_id)
    if claves is None:
        borrar_repetidos(carga_id)
        return len(filas)
    claves = set(claves)
    restantes = [f for f in filas if f["clave_academica"] not in claves]
    descartados = len(filas) - len(restantes)
    if not restantes:
        borrar_repetidos(carga_id)
    elif descartados:
        with open(_ruta(carga_id), "w", encoding="utf-8") as f:
            json.dump({"carga_id": carga_id, "filas": restantes}, f, ensure_ascii=False)
    return descartados