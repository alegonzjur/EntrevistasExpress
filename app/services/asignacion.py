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
from app.models import Asignacion, Candidato, Espacio, LogAsignacion, Reserva, Usuario
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
    Ejecuta el algoritmo de asignación automática MEJORADO

    PRIORIZACIÓN:
    1. Candidatos CON preferencias que coinciden con reservas disponibles
    2. Candidatos SIN preferencias (asignación por nota)
    3. Candidatos CON preferencias pero sin coincidencias (asignación por nota)

    MEJORA: Prioriza profesores con menos sedes asignadas

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
    # FASE 1: OBTENER CANDIDATOS Y CLASIFICAR
    # ========================================

    # Obtener TODOS los candidatos pendientes. Un candidato sin nota
    # (media_estudios None, desde que esa celda del Excel dejó de ser
    # obligatoria) se trata, a efectos de este orden, como si tuviera
    # una nota de 5 — ni al principio ni al final de la cola.
    candidatos_todos = (
        Candidato.query.filter_by(semana_carga=semana_carga, estado="pendiente")
        .order_by(db.func.coalesce(Candidato.media_estudios, 5).asc())
        .all()
    )

    # Clasificar candidatos
    candidatos_con_preferencias = [c for c in candidatos_todos if c.tiene_preferencias]
    candidatos_sin_preferencias = [
        c for c in candidatos_todos if not c.tiene_preferencias
    ]

    print(f"📊 Candidatos totales: {len(candidatos_todos)}")
    print(f"   - Con preferencias: {len(candidatos_con_preferencias)}")
    print(f"   - Sin preferencias: {len(candidatos_sin_preferencias)}")

    # ========================================
    # FASE 2: OBTENER RESERVAS DISPONIBLES
    # ========================================

    reservas_obj = (
        Reserva.query.filter(Reserva.fecha >= primer_dia_ent)
        .filter(Reserva.fecha <= viernes_ent)
        .order_by(Reserva.prioridad.desc(), Reserva.fecha, Reserva.hora_inicio)
        .all()
    )

    # Crear estructura de franjas con espacios
    franjas_disponibles = []

    for reserva in reservas_obj:
        espacio = Espacio.query.get(reserva.espacio_id)
        entrevistador = Usuario.query.get(reserva.usuario_id)

        asignaciones_existentes = Asignacion.query.filter_by(
            reserva_id=reserva.id
        ).count()
        espacios_libres = 2 - asignaciones_existentes

        if espacios_libres > 0:
            franja_info = {
                "reserva": reserva,
                "espacio": espacio,
                "espacios_libres": espacios_libres,
                "asignaciones_actuales": asignaciones_existentes,
                "entrevistador_id": reserva.usuario_id,
                "entrevistador": entrevistador,
            }
            franjas_disponibles.append(franja_info)

    print(f"📅 Franjas disponibles: {len(franjas_disponibles)}")

    # ========================================
    # FASE 3: ASIGNACIÓN CON PREFERENCIAS (MEJORADA)
    # ========================================

    asignaciones_creadas = []
    asignaciones_por_profesor = {}
    candidatos_asignados_con_preferencia = 0

    print("\n🎯 FASE 1: Asignando candidatos CON preferencias...")

    for candidato in candidatos_con_preferencias:
        if candidato.estado != "pendiente":
            continue

        franjas_preferidas = candidato.obtener_franjas_preferidas()

        # Lista de franjas candidatas con sus scores
        franjas_candidatas = []

        # Buscar todas las coincidencias posibles
        for franja_info in franjas_disponibles:
            if franja_info["espacios_libres"] <= 0:
                continue

            # Verificar límite por profesor
            if max_por_profesor:
                actual = asignaciones_por_profesor.get(
                    franja_info["entrevistador_id"], 0
                )
                if actual >= int(max_por_profesor):
                    continue

            # Verificar sede
            if candidato.sede and franja_info["entrevistador"]:
                if not franja_info["entrevistador"].puede_atender_sede(
                    candidato.sede
                ):
                    continue

            # Calcular score base
            score = 0

            # Verificar coincidencia con preferencias
            coincide_horario = False
            for franja_pref in franjas_preferidas:
                if franja_coincide_con_reserva(
                    franja_pref, franja_info["reserva"], franja_info["espacio"]
                ):
                    score = 1000  # Máxima prioridad por coincidencia de horario
                    coincide_horario = True
                    break

            # Si coincide el horario, añadir a candidatas
            if coincide_horario:
                # Calcular número de sedes del entrevistador
                num_sedes = len(franja_info["entrevistador"].sedes)

                franjas_candidatas.append(
                    {"franja": franja_info, "score": score, "num_sedes": num_sedes}
                )

        # Si hay franjas candidatas, elegir la mejor
        mejor_franja = None
        mejor_score = -1

        if franjas_candidatas:
            # Ordenar por:
            # 1. Score (descendente) - prioridad de coincidencia
            # 2. Número de sedes (ascendente) - menos sedes = mejor
            # 3. ID de reserva (para consistencia)
            franjas_candidatas.sort(
                key=lambda x: (
                    -x["score"],  # Mayor score primero
                    x["num_sedes"],  # Menos sedes primero
                    x["franja"]["reserva"].id,  # ID menor primero (desempate)
                )
            )

            mejor_candidata = franjas_candidatas[0]
            mejor_franja = mejor_candidata["franja"]
            mejor_score = mejor_candidata["score"]

            # DEBUG: Mostrar decisión (solo si hay múltiples opciones)
            if len(franjas_candidatas) > 1:
                print(
                    f"   📋 Candidato: {candidato.nombre} {candidato.apellidos} (Sede: {candidato.sede})"
                )
                print(f"      Opciones compatibles: {len(franjas_candidatas)}")
                print(
                    f"      → Elegido: {mejor_franja['entrevistador'].username} ({mejor_candidata['num_sedes']} sede(s))"
                )

        # Si encontró coincidencia, asignar
        if mejor_franja and mejor_score >= 1000:
            reserva = mejor_franja["reserva"]
            entrevistador_id = mejor_franja["entrevistador_id"]

            # Determinar posición
            if mejor_franja["asignaciones_actuales"] == 0:
                posicion = 1
                minuto_inicio = 0
            else:
                posicion = 2
                minuto_inicio = 15

            # Crear asignación
            asignacion = Asignacion(
                candidato_clave=candidato.clave_academica,
                reserva_id=reserva.id,
                entrevistador_id=entrevistador_id,
                posicion=posicion,
                minuto_inicio=minuto_inicio,
                estado="confirmado",
                fecha_asignacion=datetime.now(),
                asignado_por_admin_id=usuario_id,
            )

            db.session.add(asignacion)
            candidato.estado = "asignado"

            asignaciones_creadas.append(
                {
                    "candidato_clave": candidato.clave_academica,
                    "reserva_id": reserva.id,
                    "tipo": "con_preferencia",
                }
            )

            asignaciones_por_profesor[entrevistador_id] = (
                asignaciones_por_profesor.get(entrevistador_id, 0) + 1
            )
            mejor_franja["espacios_libres"] -= 1
            mejor_franja["asignaciones_actuales"] += 1
            candidatos_asignados_con_preferencia += 1

    print(f"   ✅ Asignados con preferencia: {candidatos_asignados_con_preferencia}")

    # ========================================
    # FASE 4: ASIGNACIÓN SIN PREFERENCIAS (MEJORADA)
    # ========================================

    print("\n📝 FASE 2: Asignando candidatos SIN preferencias...")

    # Combinar candidatos sin preferencias + candidatos con preferencias no asignados
    candidatos_restantes = [c for c in candidatos_todos if c.estado == "pendiente"]
    # Ordenar por nota; sin nota -> se trata como un 5 (ver Fase 1).
    candidatos_restantes.sort(
        key=lambda x: x.media_estudios if x.media_estudios is not None else 5
    )

    candidatos_asignados_sin_preferencia = 0

    for candidato in candidatos_restantes:
        if candidato.estado != "pendiente":
            continue

        # Buscar TODAS las franjas compatibles y elegir la mejor
        franjas_compatibles = []

        for franja_info in franjas_disponibles:
            if franja_info["espacios_libres"] <= 0:
                continue

            # Verificar límite por profesor
            if max_por_profesor:
                actual = asignaciones_por_profesor.get(
                    franja_info["entrevistador_id"], 0
                )
                if actual >= int(max_por_profesor):
                    continue

            # Verificar sede
            if candidato.sede and franja_info["entrevistador"]:
                if not franja_info["entrevistador"].puede_atender_sede(
                    candidato.sede
                ):
                    continue

            # Añadir a franjas compatibles
            num_sedes = len(franja_info["entrevistador"].sedes)
            franjas_compatibles.append({"franja": franja_info, "num_sedes": num_sedes})

        # Si hay franjas compatibles, elegir la mejor
        franja_asignada = None

        if franjas_compatibles:
            # Ordenar por:
            # 1. Número de sedes (menos sedes = mejor)
            # 2. Fecha más temprana
            # 3. Hora más temprana
            franjas_compatibles.sort(
                key=lambda x: (
                    x["num_sedes"],  # Menos sedes primero
                    x["franja"]["reserva"].fecha,  # Fecha más temprana
                    x["franja"]["reserva"].hora_inicio,  # Hora más temprana
                )
            )

            franja_asignada = franjas_compatibles[0]["franja"]

            # DEBUG: Mostrar decisión (solo si hay múltiples opciones)
            if len(franjas_compatibles) > 1:
                print(
                    f"   📋 Candidato: {candidato.nombre} {candidato.apellidos} (Sede: {candidato.sede})"
                )
                print(f"      Opciones compatibles: {len(franjas_compatibles)}")
                print(
                    f"      → Elegido: {franja_asignada['entrevistador'].username} ({franjas_compatibles[0]['num_sedes']} sede(s))"
                )

        if franja_asignada:
            reserva = franja_asignada["reserva"]
            entrevistador_id = franja_asignada["entrevistador_id"]

            # Determinar posición
            if franja_asignada["asignaciones_actuales"] == 0:
                posicion = 1
                minuto_inicio = 0
            else:
                posicion = 2
                minuto_inicio = 15

            # Crear asignación
            asignacion = Asignacion(
                candidato_clave=candidato.clave_academica,
                reserva_id=reserva.id,
                entrevistador_id=entrevistador_id,
                posicion=posicion,
                minuto_inicio=minuto_inicio,
                estado="confirmado",
                fecha_asignacion=datetime.now(),
                asignado_por_admin_id=usuario_id,
            )

            db.session.add(asignacion)
            candidato.estado = "asignado"

            asignaciones_creadas.append(
                {
                    "candidato_clave": candidato.clave_academica,
                    "reserva_id": reserva.id,
                    "tipo": (
                        "sin_preferencia"
                        if not candidato.tiene_preferencias
                        else "con_preferencia_sin_match"
                    ),
                }
            )

            asignaciones_por_profesor[entrevistador_id] = (
                asignaciones_por_profesor.get(entrevistador_id, 0) + 1
            )
            franja_asignada["espacios_libres"] -= 1
            franja_asignada["asignaciones_actuales"] += 1
            candidatos_asignados_sin_preferencia += 1

    print(f"   ✅ Asignados sin preferencia: {candidatos_asignados_sin_preferencia}")

    # ========================================
    # FASE 5: GUARDAR Y REPORTAR
    # ========================================

    db.session.flush()

    tiempo_total = (datetime.now() - inicio).total_seconds()

    # Crear log
    log = LogAsignacion(
        fecha_ejecucion=datetime.now(),
        semana_objetivo=semana_carga,
        candidatos_procesados=len(candidatos_todos),
        candidatos_filtrados=0,
        candidatos_asignados=len(asignaciones_creadas),
        candidatos_sin_asignar=len(candidatos_todos) - len(asignaciones_creadas),
        franjas_utilizadas=len(set([a["reserva_id"] for a in asignaciones_creadas])),
        algoritmo_usado="asignacion_pref_sedes_v3",
        tiempo_ejecucion_segundos=round(tiempo_total, 2),
        estado=(
            "exito" if len(asignaciones_creadas) == len(candidatos_todos) else "parcial"
        ),
        mensaje=f"Asignación con preferencias y priorización por sedes. {candidatos_asignados_con_preferencia} con match, {candidatos_asignados_sin_preferencia} sin preferencia/match",
        ejecutado_por_usuario_id=usuario_id,
    )

    db.session.add(log)
    db.session.commit()

    # Registrar en logs
    registrar_log(
        accion="asignacion_automatica",
        entidad="sistema",
        entidad_id=None,
        descripcion=f"Asignación con preferencias y priorización por sedes: {len(asignaciones_creadas)} asignados ({candidatos_asignados_con_preferencia} con match)",
        datos_nuevos={
            "semana_carga": semana_carga,
            "semana_entrevistas": semana_entrevistas,
            "total_asignados": len(asignaciones_creadas),
            "con_preferencia_match": candidatos_asignados_con_preferencia,
            "sin_preferencia": candidatos_asignados_sin_preferencia,
            "sin_asignar": len(candidatos_todos) - len(asignaciones_creadas),
            "tiempo_segundos": round(tiempo_total, 2),
        },
        nivel="info",
    )

    print(f"\n✅ ASIGNACIÓN COMPLETADA:")
    print(f"   Total asignados: {len(asignaciones_creadas)}/{len(candidatos_todos)}")
    print(f"   Con preferencia match: {candidatos_asignados_con_preferencia}")
    print(f"   Sin preferencia/sin match: {candidatos_asignados_sin_preferencia}")
    print(f"   Tiempo: {round(tiempo_total, 2)}s")

    return (
        {
            "success": True,
            "mensaje": f"{len(asignaciones_creadas)} candidatos asignados correctamente",
            "candidatos_asignados": len(asignaciones_creadas),
            "candidatos_sin_asignar": len(candidatos_todos) - len(asignaciones_creadas),
            "con_preferencia_match": candidatos_asignados_con_preferencia,
            "sin_preferencia_o_sin_match": candidatos_asignados_sin_preferencia,
            "franjas_utilizadas": len(
                set([a["reserva_id"] for a in asignaciones_creadas])
            ),
            "semana_carga": semana_carga,
            "semana_entrevistas": semana_entrevistas,
            "tiempo_segundos": round(tiempo_total, 2),
        },
        200,
    )