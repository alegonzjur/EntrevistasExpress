"""
Algoritmo de asignación automática de candidatos a reservas (entrevistas).

`calcular_score_candidato` es una función de puntuación independiente.
`ejecutar_asignacion_automatica` es el algoritmo completo que antes vivía
dentro de la vista `ejecutar_asignacion` en app.py — se trae aquí tal cual,
separando el algoritmo (negocio, testeable sin Flask) de la vista (HTTP:
parseo de request.json, jsonify, códigos de estado), que queda en
routes/candidatos.py como una capa fina.

IMPORTANTE: `calcular_score_candidato` NO es llamada por
`ejecutar_asignacion_automatica` ni por ningún otro sitio del proyecto —
ya era código muerto en el app.py original (el algoritmo real tiene su
propio cálculo de score, inline, con valores distintos: 1000 por
coincidencia de horario en vez de 500, y sin el bonus de sede). Se
preserva tal cual estaba, sin usarla ni eliminarla.
"""

from datetime import datetime, timedelta

from app.extensions import db
from app.models import (
    Asignacion,
    Candidato,
    DiaBloqueado,
    Espacio,
    LogAsignacion,
    Reserva,
    Usuario,
)
from app.services.franjas import franja_coincide_con_reserva
from app.services.logs import registrar_log


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


def ejecutar_asignacion_automatica(semana_carga, usuario_id, max_por_profesor=None):
    """
    Ejecuta el algoritmo de asignación automática (v4, por niveles)

    Se hace por PASADAS sobre todos los candidatos (de menor a mayor
    nota dentro de cada pasada), no candidato a candidato, para que un
    nivel "amplio" nunca le quite el hueco exacto a otro candidato:

    1. NIVEL 1 — candidatos con preferencias: coincidencia de día + turno
       + hora con una reserva.
    2. NIVEL 2 — los que sigan pendientes: coincidencia solo de TURNO
       (mañana/tarde, el que indicaron), en cualquier día.
    3. SIN PREFERENCIAS — cualquier hueco compatible (como antes).
    4. TRASPASO — todo candidato que siga sin hueco pasa a la semana de
       carga siguiente (sigue `pendiente`); allí se asignará cuando se
       ejecute la asignación de esa semana.

    En todas las pasadas se respeta la sede del profesor, el máximo por
    profesor y los días bloqueados (`DiaBloqueado`: fecha + sede del
    candidato). Entre huecos válidos gana el profesor con menos sedes.

        No captura excepciones: si algo falla (BD, datos inconsistentes...),
    se propaga tal cual al llamador, que debe hacer db.session.rollback()
    y traducirlo a una respuesta HTTP — exactamente lo que hacía el único
    try/except que envolvía toda la vista `ejecutar_asignacion` original.

    Args:
        semana_carga (str): semana ISO ("AAAA-Wss") de la que se cargaron
            los candidatos pendientes a asignar.
        usuario_id (int): id del usuario (admin) que ejecuta la asignación,
            para registrar quién la creó (antes se leía de `session["user_id"]`
            directamente dentro de la vista).
        max_por_profesor (int | str | None): límite opcional de asignaciones
            por entrevistador.

    Returns:
        tuple(dict, int): el cuerpo de la respuesta (listo para `jsonify`)
            y el código de estado HTTP sugerido.
    """

    # Calcular semana de entrevistas (siguiente)
    año, semana_num = semana_carga.split("-W")
    primer_dia = datetime.strptime(f"{año}-W{semana_num}-1", "%Y-W%W-%w").date()
    siguiente_lunes = primer_dia + timedelta(days=7)
    semana_entrevistas = siguiente_lunes.strftime("%Y-W%W")

    # Verificar candidatos pendientes
    candidatos_total = Candidato.query.filter_by(
        semana_carga=semana_carga, estado="pendiente"
    ).count()

    if candidatos_total == 0:
        return (
            {
                "error": f"No hay candidatos pendientes para la semana {semana_carga}",
                "candidatos_pendientes": 0,
            },
            400,
        )

    # Calcular rango de fechas para semana de entrevistas
    año_ent, semana_num_ent = semana_entrevistas.split("-W")
    primer_dia_ent = datetime.strptime(
        f"{año_ent}-W{semana_num_ent}-1", "%Y-W%W-%w"
    ).date()
    viernes_ent = primer_dia_ent + timedelta(days=4)

    # Verificar reservas disponibles
    reservas_count = (
        Reserva.query.filter(Reserva.fecha >= primer_dia_ent)
        .filter(Reserva.fecha <= viernes_ent)
        .count()
    )

    if reservas_count == 0:
        return (
            {
                "error": f"No hay reservas para la semana de entrevistas {semana_entrevistas}",
                "reservas_disponibles": 0,
            },
            400,
        )

    inicio = datetime.now()

    # ========================================
    # FASE 1: CANDIDATOS Y CLASIFICACIÓN
    # ========================================

    # Un candidato sin nota (media_estudios None) se trata, a efectos de
    # este orden, como si tuviera un 5 — ni al principio ni al final.
    candidatos_todos = (
        Candidato.query.filter_by(semana_carga=semana_carga, estado="pendiente")
        .order_by(db.func.coalesce(Candidato.media_estudios, 5).asc())
        .all()
    )

    def _nota(c):
        return c.media_estudios if c.media_estudios is not None else 5

    # "Con preferencias" = tiene alguna franja con turno legible. Un
    # candidato marcado con preferencias pero cuyas franjas no se pudieron
    # interpretar se trata como sin preferencias (antes tampoco podía
    # coincidir con nada y acababa en cualquier hueco).
    turnos_por_candidato = {c.clave_academica: _turnos_preferidos(c) for c in candidatos_todos}
    candidatos_con_preferencias = [
        c for c in candidatos_todos if turnos_por_candidato[c.clave_academica]
    ]
    candidatos_sin_preferencias = [
        c for c in candidatos_todos if not turnos_por_candidato[c.clave_academica]
    ]

    # ========================================
    # FASE 2: HUECOS DISPONIBLES Y DÍAS BLOQUEADOS
    # ========================================

    reservas_obj = (
        Reserva.query.filter(Reserva.fecha >= primer_dia_ent)
        .filter(Reserva.fecha <= viernes_ent)
        .order_by(Reserva.prioridad.desc(), Reserva.fecha, Reserva.hora_inicio)
        .all()
    )

    franjas_disponibles = []
    for reserva in reservas_obj:
        espacio = db.session.get(Espacio, reserva.espacio_id)
        entrevistador = db.session.get(Usuario, reserva.usuario_id)
        asignaciones_existentes = Asignacion.query.filter_by(reserva_id=reserva.id).count()
        espacios_libres = 2 - asignaciones_existentes
        if espacios_libres > 0:
            franjas_disponibles.append(
                {
                    "reserva": reserva,
                    "espacio": espacio,
                    "espacios_libres": espacios_libres,
                    "asignaciones_actuales": asignaciones_existentes,
                    "entrevistador_id": reserva.usuario_id,
                    "entrevistador": entrevistador,
                    "num_sedes": len(entrevistador.sedes) if entrevistador else 0,
                }
            )

    bloqueados = {
        (d.fecha, d.sede)
        for d in DiaBloqueado.query.filter(
            DiaBloqueado.fecha >= primer_dia_ent, DiaBloqueado.fecha <= viernes_ent
        ).all()
    }

    # ========================================
    # FASE 3: ASIGNACIÓN POR NIVELES
    # ========================================

    asignaciones_creadas = []
    asignaciones_por_profesor = {}
    contadores = {"nivel1": 0, "nivel2": 0, "sin_preferencia": 0}

    def _hueco_valido(candidato, franja_info):
        """Condiciones comunes a todos los niveles."""
        if franja_info["espacios_libres"] <= 0:
            return False
        if max_por_profesor:
            actual = asignaciones_por_profesor.get(franja_info["entrevistador_id"], 0)
            if actual >= int(max_por_profesor):
                return False
        if candidato.sede and franja_info["entrevistador"]:
            if not franja_info["entrevistador"].puede_atender_sede(candidato.sede):
                return False
        if candidato.sede and (franja_info["reserva"].fecha, candidato.sede) in bloqueados:
            return False
        return True

    def _asignar(candidato, franja_info, tipo, contador):
        reserva = franja_info["reserva"]
        if franja_info["asignaciones_actuales"] == 0:
            posicion, minuto_inicio = 1, 0
        else:
            posicion, minuto_inicio = 2, 15

        db.session.add(
            Asignacion(
                candidato_clave=candidato.clave_academica,
                reserva_id=reserva.id,
                entrevistador_id=franja_info["entrevistador_id"],
                posicion=posicion,
                minuto_inicio=minuto_inicio,
                estado="confirmado",
                fecha_asignacion=datetime.now(),
                asignado_por_admin_id=usuario_id,
            )
        )
        candidato.estado = "asignado"
        asignaciones_creadas.append(
            {"candidato_clave": candidato.clave_academica, "reserva_id": reserva.id, "tipo": tipo}
        )
        asignaciones_por_profesor[franja_info["entrevistador_id"]] = (
            asignaciones_por_profesor.get(franja_info["entrevistador_id"], 0) + 1
        )
        franja_info["espacios_libres"] -= 1
        franja_info["asignaciones_actuales"] += 1
        contadores[contador] += 1

    def _pasada(candidatos, filtro_extra, clave_orden, tipo, contador):
        """Una pasada: cada candidato pendiente toma el mejor hueco válido."""
        for candidato in candidatos:
            if candidato.estado != "pendiente":
                continue
            opciones = [
                f
                for f in franjas_disponibles
                if _hueco_valido(candidato, f) and filtro_extra(candidato, f)
            ]
            if opciones:
                opciones.sort(key=clave_orden)
                _asignar(candidato, opciones[0], tipo, contador)

    def _orden_nivel1(f):
        return (f["num_sedes"], f["reserva"].id)

    def _orden_fecha(f):
        return (f["num_sedes"], f["reserva"].fecha, f["reserva"].hora_inicio)

    def _coincide_dia_turno_hora(candidato, f):
        return any(
            franja_coincide_con_reserva(fp, f["reserva"], f["espacio"])
            for fp in candidato.obtener_franjas_preferidas()
        )

    def _coincide_turno(candidato, f):
        return f["reserva"].turno in turnos_por_candidato[candidato.clave_academica]

    # NIVEL 1: día + turno + hora
    _pasada(candidatos_con_preferencias, _coincide_dia_turno_hora, _orden_nivel1,
            "con_preferencia", "nivel1")
    # NIVEL 2: solo turno (cualquier día)
    _pasada(candidatos_con_preferencias, _coincide_turno, _orden_fecha,
            "con_preferencia_turno", "nivel2")
    # SIN PREFERENCIAS: cualquier hueco compatible
    _pasada(candidatos_sin_preferencias, lambda c, f: True, _orden_fecha,
            "sin_preferencia", "sin_preferencia")

    # ========================================
    # FASE 4: TRASPASO A LA SEMANA SIGUIENTE
    # ========================================

    trasladados = [c for c in candidatos_todos if c.estado == "pendiente"]
    for candidato in trasladados:
        candidato.semana_carga = semana_entrevistas
    claves_trasladadas = [c.clave_academica for c in trasladados]

    # ========================================
    # FASE 5: GUARDAR Y REPORTAR
    # ========================================

    db.session.flush()

    tiempo_total = (datetime.now() - inicio).total_seconds()
    total_asignados = len(asignaciones_creadas)
    n_nivel1 = contadores["nivel1"]
    n_nivel2 = contadores["nivel2"]
    n_sin_pref = contadores["sin_preferencia"]

    log = LogAsignacion(
        fecha_ejecucion=datetime.now(),
        semana_objetivo=semana_carga,
        candidatos_procesados=len(candidatos_todos),
        candidatos_filtrados=0,
        candidatos_asignados=total_asignados,
        candidatos_sin_asignar=len(trasladados),
        franjas_utilizadas=len(set(a["reserva_id"] for a in asignaciones_creadas)),
        algoritmo_usado="asignacion_niveles_v4",
        tiempo_ejecucion_segundos=round(tiempo_total, 2),
        estado="exito" if total_asignados == len(candidatos_todos) else "parcial",
        mensaje=(
            f"Asignación por niveles. {n_nivel1} día+turno+hora, {n_nivel2} solo turno, "
            f"{n_sin_pref} sin preferencias, {len(trasladados)} trasladados a {semana_entrevistas}"
        ),
        ejecutado_por_usuario_id=usuario_id,
    )
    db.session.add(log)
    db.session.commit()

    registrar_log(
        accion="asignacion_automatica",
        entidad="sistema",
        entidad_id=None,
        descripcion=(
            f"Asignación por niveles: {total_asignados} asignados "
            f"({n_nivel1} nivel 1, {n_nivel2} nivel 2, {n_sin_pref} sin preferencias), "
            f"{len(trasladados)} trasladados a la semana {semana_entrevistas}"
        ),
        datos_nuevos={
            "semana_carga": semana_carga,
            "semana_entrevistas": semana_entrevistas,
            "total_asignados": total_asignados,
            "nivel1_dia_turno_hora": n_nivel1,
            "nivel2_turno": n_nivel2,
            "sin_preferencia": n_sin_pref,
            "trasladados_semana_siguiente": len(trasladados),
            "claves_trasladadas": claves_trasladadas,
            "dias_bloqueados_aplicados": sorted(f"{f.isoformat()} {s}" for f, s in bloqueados),
            "tiempo_segundos": round(tiempo_total, 2),
        },
        nivel="info",
    )

    return (
        {
            "success": True,
            "mensaje": f"{total_asignados} candidatos asignados correctamente",
            "candidatos_asignados": total_asignados,
            # Los no asignados no se pierden: pasan a la semana siguiente.
            "candidatos_sin_asignar": len(trasladados),
            "trasladados_semana_siguiente": len(trasladados),
            "con_preferencia_match": n_nivel1,
            "asignados_nivel2_turno": n_nivel2,
            "sin_preferencia_o_sin_match": n_nivel2 + n_sin_pref,
            "franjas_utilizadas": len(set(a["reserva_id"] for a in asignaciones_creadas)),
            "semana_carga": semana_carga,
            "semana_entrevistas": semana_entrevistas,
            "tiempo_segundos": round(tiempo_total, 2),
        },
        200,
    )


def _turnos_preferidos(candidato):
    """Turnos ("manana"/"tarde") que el candidato indicó en sus franjas.
    Mismo formato que `Reserva.turno` para poder compararlos."""
    turnos = set()
    for franja in candidato.obtener_franjas_preferidas():
        turno = (franja.get("turno") or "").strip().lower().replace("ñ", "n")
        if turno in ("manana", "tarde"):
            turnos.add(turno)
    return turnos