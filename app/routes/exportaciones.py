"""
Exportación de informes (candidatos, asignaciones, reservas en xlsx/csv/pdf)
y envío de correos (confirmaciones a candidatos/entrevistadores, y el email
de prueba de configuración SMTP). Cada ruta de exportación es una capa fina
que filtra los datos de la semana y delega el renderizado del fichero a
services/exportacion_*.py, que ya estaba extraído.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from flask import jsonify, request, session
from flask_mail import Message

from app.extensions import db, mail
from app.models import Asignacion, Candidato, Espacio, Reserva, Usuario
from app.services.emails import (
    generar_email_candidato,
    generar_email_entrevistador,
    validar_email,
)
from app.services.exportacion_asignaciones import (
    exportar_asignaciones_csv,
    exportar_asignaciones_pdf,
    exportar_asignaciones_xlsx,
)
from app.services.exportacion_candidatos import (
    exportar_candidatos_csv,
    exportar_candidatos_pdf,
    exportar_candidatos_xlsx,
)
from app.services.exportacion_reservas import exportar_reservas_pdf, exportar_reservas_xlsx
from app.services.logs import registrar_log
from app.utils.decorators import admin_required


def register(app):
    @app.route("/admin/exportar/candidatos/<semana>/<formato>")
    @admin_required
    def exportar_candidatos(semana, formato):
        """Exporta candidatos de una semana en diferentes formatos"""

        # Sin nota (media_estudios None) se ordena como si fuera un 5,
        # igual que en el resto de la app (ver services/candidatos.py).
        candidatos = (
            Candidato.query.filter_by(semana_carga=semana)
            .order_by(db.func.coalesce(Candidato.media_estudios, 5).desc())
            .all()
        )

        if formato == "xlsx":
            return exportar_candidatos_xlsx(candidatos, semana)
        elif formato == "pdf":
            return exportar_candidatos_pdf(candidatos, semana)
        elif formato == "csv":
            return exportar_candidatos_csv(candidatos, semana)
        else:
            return jsonify({"error": "Formato no soportado"}), 400

    @app.route("/admin/exportar/asignaciones/<semana>/<formato>")
    @admin_required
    def exportar_asignaciones(semana, formato):
        """Exporta asignaciones de una semana en diferentes formatos"""

        asignaciones = (
            db.session.query(Asignacion)
            .join(Candidato, Candidato.clave_academica == Asignacion.candidato_clave)
            .join(Reserva)
            .join(Usuario, Asignacion.entrevistador_id == Usuario.id)
            .outerjoin(Espacio, Espacio.id == Reserva.espacio_id)
            .filter(Candidato.semana_carga == semana)
            .order_by(Reserva.fecha, Reserva.hora_inicio, Asignacion.posicion)
            .all()
        )

        if formato == "xlsx":
            return exportar_asignaciones_xlsx(asignaciones, semana)
        elif formato == "pdf":
            return exportar_asignaciones_pdf(asignaciones, semana)
        elif formato == "csv":
            return exportar_asignaciones_csv(asignaciones, semana)
        else:
            return jsonify({"error": "Formato no soportado"}), 400

    @app.route("/admin/exportar/reservas/<semana>/<formato>")
    @admin_required
    def exportar_reservas_semana(semana, formato):
        """Exporta reservas de una semana"""

        # Calcular fechas
        año, semana_num = semana.split("-W")
        primer_dia = datetime.strptime(f"{año}-W{semana_num}-1", "%Y-W%W-%w").date()
        viernes = primer_dia + timedelta(days=4)

        reservas = (
            Reserva.query.filter(Reserva.fecha >= primer_dia)
            .filter(Reserva.fecha <= viernes)
            .order_by(Reserva.fecha, Reserva.hora_inicio)
            .all()
        )

        if formato == "xlsx":
            return exportar_reservas_xlsx(reservas, semana)
        elif formato == "pdf":
            return exportar_reservas_pdf(reservas, semana)
        else:
            return jsonify({"error": "Formato no soportado"}), 400

    @app.route("/admin/candidatos/envio-individual/<semana>")
    @admin_required
    def destinatarios_envio_individual(semana):
        """
        Quiénes se pueden elegir para un envío individual (o de 2-3
        personas) en vez del envío masivo de toda la semana:

        - Candidatos: solo los que ya están cargados Y asignados (tienen
          una Asignacion para esta semana) y cuyo email todavía NO se ha
          enviado — si ya se envió, no tiene sentido ofrecerlo aquí (para
          reenviar a un candidato puntual se sigue usando la opción
          "reenviar" del envío masivo).
        - Profesores: todos los que tengan al menos una asignación esta
          semana, se les haya enviado ya su resumen o no — a diferencia
          de los candidatos, el sistema no guarda si a un profesor ya se
          le envió su resumen semanal (no hay campo para ello), así que
          siempre se ofrecen todos.

        GET /admin/candidatos/envio-individual/2026-W43
        """
        asignaciones_pendientes = (
            Asignacion.query.join(Candidato)
            .filter(
                Candidato.semana_carga == semana,
                Asignacion.enviado_email.isnot(True),
            )
            .order_by(Candidato.apellidos, Candidato.nombre)
            .all()
        )

        candidatos = [
            {
                "asignacion_id": a.id,
                "clave_academica": a.candidato.clave_academica,
                "nombre": f"{a.candidato.nombre} {a.candidato.apellidos}",
                "email": a.candidato.email,
                "entrevistador": (
                    a.entrevistador.nombre_completo or a.entrevistador.username
                    if a.entrevistador
                    else "N/A"
                ),
                "fecha": a.reserva.fecha.strftime("%d/%m/%Y") if a.reserva else "N/A",
                "hora": (
                    a.hora_exacta.strftime("%H:%M")
                    if a.hora_exacta
                    else (a.reserva.hora_inicio.strftime("%H:%M") if a.reserva else "N/A")
                ),
            }
            for a in asignaciones_pendientes
        ]

        profesores_semana = (
            Usuario.query.join(
                Asignacion, Asignacion.entrevistador_id == Usuario.id
            )
            .join(Candidato, Candidato.clave_academica == Asignacion.candidato_clave)
            .filter(Candidato.semana_carga == semana)
            .distinct()
            .order_by(Usuario.username)
            .all()
        )

        profesores = [
            {
                "id": u.id,
                "nombre": u.nombre_completo or u.username,
                "email": u.email,
                "num_asignaciones": Asignacion.query.join(Candidato)
                .filter(
                    Candidato.semana_carga == semana,
                    Asignacion.entrevistador_id == u.id,
                )
                .count(),
            }
            for u in profesores_semana
        ]

        return jsonify({"candidatos": candidatos, "profesores": profesores})

    @app.route("/admin/candidatos/envio-individual/<semana>", methods=["POST"])
    @admin_required
    def enviar_emails_individual(semana):
        """
        Envío individual (o de un grupo pequeño) para una semana: a
        diferencia de /admin/candidatos/enviar-emails/<semana>, aquí el
        admin elige exactamente a quién, en vez de reenviar
        automáticamente a toda la semana — pensado para cuando se
        gestiona manualmente una sola entrevista y solo hace falta
        avisar a esa persona (o a 2-3), sin tocar al resto.

        A un profesor seleccionado se le manda su resumen de TODAS sus
        entrevistas de esta semana (igual que en el envío masivo), no
        solo la que motivó el envío — un profesor no recibe "medio"
        resumen.

        POST /admin/candidatos/envio-individual/2026-W43
        {
            "asignaciones": [12, 15],   // ids de Asignacion (candidatos)
            "profesores": [3, 7]        // ids de Usuario (entrevistadores)
        }
        """
        data = request.json or {}
        asignacion_ids = data.get("asignaciones", [])
        profesor_ids = data.get("profesores", [])

        if not asignacion_ids and not profesor_ids:
            return jsonify({"error": "No se ha seleccionado a nadie"}), 400

        resultados = {
            "candidatos_enviados": 0,
            "candidatos_error": 0,
            "entrevistadores_enviados": 0,
            "entrevistadores_error": 0,
            "errores": [],
        }

        # ===== Candidatos seleccionados =====
        for asignacion_id in asignacion_ids:
            asignacion = (
                Asignacion.query.join(Candidato)
                .filter(
                    Asignacion.id == asignacion_id,
                    Candidato.semana_carga == semana,
                )
                .first()
            )
            if not asignacion:
                resultados["candidatos_error"] += 1
                resultados["errores"].append(
                    {
                        "candidato": f"Asignación #{asignacion_id}",
                        "error": "No encontrada en esta semana",
                    }
                )
                continue

            try:
                if not validar_email(asignacion.candidato.email):
                    resultados["errores"].append(
                        {
                            "candidato": f"{asignacion.candidato.nombre} {asignacion.candidato.apellidos}",
                            "error": "Email inválido o vacío",
                        }
                    )
                    resultados["candidatos_error"] += 1
                    continue

                subject, html = generar_email_candidato(asignacion)
                msg = Message(
                    subject=subject, recipients=[asignacion.candidato.email], html=html
                )
                mail.send(msg)

                asignacion.enviado_email = True
                asignacion.fecha_email = datetime.now()
                resultados["candidatos_enviados"] += 1

                registrar_log(
                    accion="enviar_email",
                    entidad="candidato",
                    entidad_id=asignacion.candidato.clave_academica,
                    descripcion=f"Email individual enviado a: {asignacion.candidato.nombre} {asignacion.candidato.apellidos} ({asignacion.candidato.email})",
                    nivel="info",
                    metadata={
                        "tipo": "confirmacion_entrevista_individual",
                        "asignacion_id": asignacion.id,
                    },
                )

            except Exception as e:
                resultados["candidatos_error"] += 1
                resultados["errores"].append(
                    {
                        "candidato": f"{asignacion.candidato.nombre} {asignacion.candidato.apellidos}",
                        "error": str(e),
                    }
                )
                registrar_log(
                    accion="enviar_email",
                    entidad="candidato",
                    entidad_id=asignacion.candidato.clave_academica,
                    descripcion=f"Error al enviar email individual a: {asignacion.candidato.email} - {str(e)}",
                    nivel="error",
                )

        # ===== Profesores seleccionados =====
        for profesor_id in profesor_ids:
            entrevistador = Usuario.query.get(profesor_id)
            if not entrevistador:
                resultados["entrevistadores_error"] += 1
                resultados["errores"].append(
                    {
                        "entrevistador": f"Usuario #{profesor_id}",
                        "error": "No encontrado",
                    }
                )
                continue

            try:
                if not validar_email(entrevistador.email):
                    resultados["errores"].append(
                        {
                            "entrevistador": entrevistador.nombre_completo
                            or entrevistador.username,
                            "error": "Email inválido o vacío",
                        }
                    )
                    resultados["entrevistadores_error"] += 1
                    continue

                asignaciones_profesor = (
                    Asignacion.query.join(Candidato)
                    .filter(
                        Candidato.semana_carga == semana,
                        Asignacion.entrevistador_id == profesor_id,
                    )
                    .all()
                )

                if not asignaciones_profesor:
                    resultados["entrevistadores_error"] += 1
                    resultados["errores"].append(
                        {
                            "entrevistador": entrevistador.nombre_completo
                            or entrevistador.username,
                            "error": f"No tiene asignaciones en la semana {semana}",
                        }
                    )
                    continue

                subject, html = generar_email_entrevistador(
                    entrevistador, asignaciones_profesor
                )
                msg = Message(
                    subject=subject, recipients=[entrevistador.email], html=html
                )
                mail.send(msg)

                resultados["entrevistadores_enviados"] += 1

                registrar_log(
                    accion="enviar_email",
                    entidad="entrevistador",
                    entidad_id=str(entrevistador.id),
                    descripcion=f"Email individual (resumen semanal) enviado a: {entrevistador.nombre_completo or entrevistador.username} ({entrevistador.email})",
                    nivel="info",
                    metadata={
                        "tipo": "resumen_entrevistador_individual",
                        "semana": semana,
                    },
                )

            except Exception as e:
                resultados["entrevistadores_error"] += 1
                resultados["errores"].append(
                    {
                        "entrevistador": entrevistador.nombre_completo
                        or entrevistador.username,
                        "error": str(e),
                    }
                )

        db.session.commit()

        registrar_log(
            accion="enviar_email_individual",
            entidad="sistema",
            entidad_id=None,
            descripcion=f'Envío individual: {resultados["candidatos_enviados"]} candidatos, {resultados["entrevistadores_enviados"]} entrevistadores',
            datos_nuevos=resultados,
            nivel="info",
            metadata={"semana": semana},
        )

        return jsonify(
            {
                "success": True,
                "candidatos_enviados": resultados["candidatos_enviados"],
                "candidatos_error": resultados["candidatos_error"],
                "entrevistadores_enviados": resultados["entrevistadores_enviados"],
                "entrevistadores_error": resultados["entrevistadores_error"],
                "total_enviados": resultados["candidatos_enviados"]
                + resultados["entrevistadores_enviados"],
                "errores": resultados["errores"],
            }
        )

    @app.route("/admin/candidatos/enviar-emails/<semana>", methods=["POST"])
    @admin_required
    def enviar_emails_semana(semana):
        """
        Envía emails a candidatos y entrevistadores de una semana

        POST /admin/candidatos/enviar-emails/2024-W46
        {
            "tipo": "candidatos" | "entrevistadores" | "ambos",
            "reenviar": false  // Si true, reenvía aunque ya se hayan enviado
        }
        """

        try:
            data = request.json or {}
            tipo = data.get("tipo", "ambos")
            reenviar = data.get("reenviar", False)

            resultados = {
                "candidatos_enviados": 0,
                "candidatos_error": 0,
                "entrevistadores_enviados": 0,
                "entrevistadores_error": 0,
                "errores": [],
            }

            # Obtener asignaciones de la semana
            asignaciones = (
                Asignacion.query.join(Candidato)
                .filter(Candidato.semana_carga == semana)
                .all()
            )

            if not asignaciones:
                return (
                    jsonify({"error": f"No hay asignaciones para la semana {semana}"}),
                    404,
                )

            # ===== ENVÍO A CANDIDATOS =====
            if tipo in ["candidatos", "ambos"]:
                for asignacion in asignaciones:
                    # Saltar si ya se envió (a menos que sea reenvío)
                    if asignacion.enviado_email and not reenviar:
                        continue

                    try:
                        # Validar email
                        if not validar_email(asignacion.candidato.email):
                            resultados["errores"].append(
                                {
                                    "candidato": f"{asignacion.candidato.nombre} {asignacion.candidato.apellidos}",
                                    "error": "Email inválido o vacío",
                                }
                            )
                            resultados["candidatos_error"] += 1
                            continue

                        # Generar email
                        subject, html = generar_email_candidato(asignacion)

                        # Crear mensaje
                        msg = Message(
                            subject=subject,
                            recipients=[asignacion.candidato.email],
                            html=html,
                        )

                        # Enviar
                        mail.send(msg)

                        # Marcar como enviado
                        # BUG corregido: el código original (y esta versión hasta
                        # ahora) escribía `asignacion.fecha_envio_email`, un
                        # atributo que no existe en el modelo Asignacion (el
                        # campo real es `fecha_email`). SQLAlchemy permite
                        # asignar atributos arbitrarios a una instancia, así que
                        # no fallaba: creaba una propiedad Python transitoria
                        # que se perdía al terminar la petición, y `fecha_email`
                        # se quedaba NULL para siempre. Confirmado con un test
                        # que comprobaba el valor tras el commit.
                        asignacion.enviado_email = True
                        asignacion.fecha_email = datetime.now()

                        resultados["candidatos_enviados"] += 1

                        registrar_log(
                            accion="enviar_email",
                            entidad="candidato",
                            entidad_id=asignacion.candidato.clave_academica,
                            descripcion=f"Email enviado a: {asignacion.candidato.nombre} {asignacion.candidato.apellidos} ({asignacion.candidato.email})",
                            nivel="info",
                            metadata={
                                "tipo": "confirmacion_entrevista",
                                "asignacion_id": asignacion.id,
                            },
                        )

                    except Exception as e:
                        resultados["candidatos_error"] += 1
                        resultados["errores"].append(
                            {
                                "candidato": f"{asignacion.candidato.nombre} {asignacion.candidato.apellidos}",
                                "error": str(e),
                            }
                        )
                        registrar_log(
                            accion="enviar_email",
                            entidad="candidato",
                            entidad_id=asignacion.candidato.clave_academica,
                            descripcion=f"Error al enviar email a: {asignacion.candidato.email} - {str(e)}",
                            nivel="error",
                        )
                        print(f"Error enviando a {asignacion.candidato.email}: {e}")

            # ===== ENVÍO A ENTREVISTADORES =====
            if tipo in ["entrevistadores", "ambos"]:
                # Agrupar asignaciones por entrevistador
                por_entrevistador = defaultdict(list)

                for asignacion in asignaciones:
                    if asignacion.entrevistador:
                        por_entrevistador[asignacion.entrevistador.id].append(
                            asignacion
                        )

                # Enviar a cada entrevistador
                for entrevistador_id, asigs_entrevistador in por_entrevistador.items():
                    try:
                        entrevistador = Usuario.query.get(entrevistador_id)

                        # Validar email
                        if not validar_email(entrevistador.email):
                            resultados["errores"].append(
                                {
                                    "entrevistador": entrevistador.username,
                                    "error": "Email inválido o vacío",
                                }
                            )
                            resultados["entrevistadores_error"] += 1
                            continue

                        # Generar email
                        subject, html = generar_email_entrevistador(
                            entrevistador, asigs_entrevistador
                        )

                        # Crear mensaje
                        msg = Message(
                            subject=subject,
                            recipients=[entrevistador.email],
                            html=html,
                        )

                        # Enviar
                        mail.send(msg)

                        resultados["entrevistadores_enviados"] += 1

                    except Exception as e:
                        resultados["entrevistadores_error"] += 1
                        resultados["errores"].append(
                            {
                                "entrevistador": (
                                    entrevistador.username
                                    if "entrevistador" in locals()
                                    else "Desconocido"
                                ),
                                "error": str(e),
                            }
                        )
                        print(f"Error enviando a entrevistador {entrevistador_id}: {e}")

            # Guardar cambios en BD
            db.session.commit()

            registrar_log(
                accion="enviar_email_masivo",
                entidad="sistema",
                entidad_id=None,
                descripcion=f'Envío masivo completado: {resultados["candidatos_enviados"]} candidatos, {resultados["entrevistadores_enviados"]} entrevistadores',
                datos_nuevos=resultados,
                nivel="info",
                metadata={"semana": semana, "tipo": tipo},
            )

            # Preparar respuesta
            return jsonify(
                {
                    "success": True,
                    "mensaje": f"Emails enviados correctamente",
                    "candidatos_enviados": resultados["candidatos_enviados"],
                    "candidatos_error": resultados["candidatos_error"],
                    "entrevistadores_enviados": resultados["entrevistadores_enviados"],
                    "entrevistadores_error": resultados["entrevistadores_error"],
                    "total_enviados": resultados["candidatos_enviados"]
                    + resultados["entrevistadores_enviados"],
                    "errores": resultados["errores"],
                }
            )

        except Exception as e:
            db.session.rollback()
            registrar_log(
                accion="enviar_email_masivo",
                entidad="sistema",
                entidad_id=None,
                descripcion=f"Error en envío masivo: {str(e)}",
                nivel="error",
                metadata={"semana": semana},
            )
            import traceback

            traceback.print_exc()
            return jsonify({"error": f"Error al enviar emails: {str(e)}"}), 500

    @app.route("/admin/candidatos/test-email", methods=["POST"])
    @admin_required
    def test_email():
        """
        Envía un email de prueba al administrador

        POST /admin/candidatos/test-email
        {
            "email": "tu_email@test.com"
        }
        """

        try:
            data = request.json or {}
            email_destino = (
                data.get("email")
                or session.get("email")
                or app.config["MAIL_DEFAULT_SENDER"]
            )

            if not validar_email(email_destino):
                return jsonify({"error": "Email inválido"}), 400

            # Crear mensaje de prueba
            msg = Message(
                subject="🧪 Test de Configuración de Email",
                recipients=[email_destino],
                html="""
                <html>
                <body style="font-family: Arial, sans-serif; padding: 20px;">
                    <h2 style="color: #4472C4;">✅ Configuración de Email Correcta</h2>
                    <p>Si estás recibiendo este email, significa que la configuración de Flask-Mail con Office 365 está funcionando correctamente.</p>
                    <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <strong>Detalles de la prueba:</strong><br>
                        - Servidor: smtp.office365.com<br>
                        - Puerto: 587<br>
                        - TLS: Habilitado<br>
                        - Estado: ✅ Funcionando
                    </div>
                    <p style="color: #666;">Este es un email de prueba automático del Sistema de Gestión de Entrevistas.</p>
                </body>
                </html>
                """,
            )

            # Enviar
            mail.send(msg)

            return jsonify(
                {
                    "success": True,
                    "mensaje": f"Email de prueba enviado correctamente a {email_destino}",
                }
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return jsonify({"error": f"Error al enviar email de prueba: {str(e)}"}), 500