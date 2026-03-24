# ====================================================================
# SISTEMA DE ENVÍO DE EMAILS - OFFICE 365
# Añadir este código a app.py
# ====================================================================

"""
PARTE 1: CONFIGURACIÓN E IMPORTS
Añadir al inicio de app.py, después de los imports existentes
"""

from flask_mail import Mail, Message
from threading import Thread
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ====================================================================
# CONFIGURACIÓN DE FLASK-MAIL
# Añadir después de app = Flask(__name__)
# ====================================================================

# Configuración de email con Office 365
app.config["MAIL_SERVER"] = "smtp.office365.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = "tu_email@tuuniversidad.edu"  # ← CAMBIAR
app.config["MAIL_PASSWORD"] = "tu_contraseña"  # ← CAMBIAR
app.config["MAIL_DEFAULT_SENDER"] = "tu_email@tuuniversidad.edu"  # ← CAMBIAR
app.config["MAIL_MAX_EMAILS"] = 50  # Máximo 50 emails por conexión
app.config["MAIL_ASCII_ATTACHMENTS"] = False

# Inicializar Flask-Mail
mail = Mail(app)


# ====================================================================
# PARTE 2: FUNCIONES AUXILIARES
# ====================================================================


def enviar_email_async(app, msg):
    """Envía email en background (opcional, para no bloquear)"""
    with app.app_context():
        try:
            mail.send(msg)
            return True
        except Exception as e:
            print(f"Error enviando email: {e}")
            return False


def validar_email(email):
    """Valida que un email tenga formato correcto"""
    import re

    if not email:
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def generar_email_candidato(asignacion):
    """
    Genera el HTML del email para un candidato

    Args:
        asignacion: Objeto Asignacion con candidato, reserva, entrevistador

    Returns:
        tuple: (subject, html_body)
    """
    candidato = asignacion.candidato
    reserva = asignacion.reserva
    entrevistador = asignacion.entrevistador

    # Formatear fecha
    fecha_str = reserva.fecha.strftime("%A %d de %B de %Y")
    # Traducir día de la semana al español
    dias = {
        "Monday": "Lunes",
        "Tuesday": "Martes",
        "Wednesday": "Miércoles",
        "Thursday": "Jueves",
        "Friday": "Viernes",
        "Saturday": "Sábado",
        "Sunday": "Domingo",
    }
    for eng, esp in dias.items():
        fecha_str = fecha_str.replace(eng, esp)

    # Meses en español
    meses = {
        "January": "enero",
        "February": "febrero",
        "March": "marzo",
        "April": "abril",
        "May": "mayo",
        "June": "junio",
        "July": "julio",
        "August": "agosto",
        "September": "septiembre",
        "October": "octubre",
        "November": "noviembre",
        "December": "diciembre",
    }
    for eng, esp in meses.items():
        fecha_str = fecha_str.replace(eng, esp)

    # Hora exacta
    hora_str = (
        asignacion.hora_exacta.strftime("%H:%M")
        if asignacion.hora_exacta
        else reserva.hora_inicio.strftime("%H:%M")
    )

    subject = f"Confirmación de Entrevista - {candidato.nombre} {candidato.apellidos}"

    html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f4f4f4">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                
                <!-- Contenedor principal -->
                <table width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff" 
                       style="border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td bgcolor="#4472C4" style="padding: 40px 30px; text-align: center; border-radius: 8px 8px 0 0;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 600;">
                                📋 Confirmación de Entrevista
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Contenido -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            
                            <p style="font-size: 16px; color: #333333; line-height: 1.6; margin: 0 0 20px 0;">
                                Estimado/a <strong>{candidato.nombre} {candidato.apellidos}</strong>,
                            </p>
                            
                            <p style="font-size: 16px; color: #666666; line-height: 1.6; margin: 0 0 30px 0;">
                                Le confirmamos su entrevista personal para el proceso de selección:
                            </p>
                            
                            <!-- Caja de información -->
                            <table width="100%" cellpadding="20" cellspacing="0" border="0" bgcolor="#f8f9fa" 
                                   style="border-radius: 8px; margin: 0 0 30px 0; border-left: 4px solid #4472C4;">
                                <tr>
                                    <td>
                                        <p style="margin: 0 0 15px 0; font-size: 16px; color: #333333;">
                                            <span style="font-size: 20px;">📅</span> 
                                            <strong>Fecha:</strong><br>
                                            <span style="color: #666666; margin-left: 30px;">{fecha_str}</span>
                                        </p>
                                        
                                        <p style="margin: 0 0 15px 0; font-size: 16px; color: #333333;">
                                            <span style="font-size: 20px;">🕐</span> 
                                            <strong>Hora:</strong><br>
                                            <span style="color: #666666; margin-left: 30px; font-size: 20px; font-weight: 600;">{hora_str}h</span>
                                        </p>
                                        
                                        <p style="margin: 0 0 15px 0; font-size: 16px; color: #333333;">
                                            <span style="font-size: 20px;">📍</span> 
                                            <strong>Lugar:</strong><br>
                                            <span style="color: #666666; margin-left: 30px;">{reserva.espacio.nombre if reserva.espacio else 'A confirmar'}</span>
                                        </p>
                                        
                                        <p style="margin: 0; font-size: 16px; color: #333333;">
                                            <span style="font-size: 20px;">👤</span> 
                                            <strong>Entrevistador:</strong><br>
                                            <span style="color: #666666; margin-left: 30px;">{entrevistador.username if entrevistador else 'A confirmar'}</span>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Instrucciones -->
                            <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px 20px; margin: 0 0 30px 0; border-radius: 4px;">
                                <p style="margin: 0 0 10px 0; font-size: 16px; color: #856404; font-weight: 600;">
                                    ⚠️ Instrucciones importantes:
                                </p>
                                <ul style="margin: 0; padding-left: 20px; color: #856404;">
                                    <li style="margin: 5px 0;">Por favor, llegue <strong>10 minutos antes</strong> de la hora indicada.</li>
                                    <li style="margin: 5px 0;">Traiga consigo su <strong>DNI o NIE</strong> original.</li>
                                    <li style="margin: 5px 0;">Se recomienda llevar su <strong>expediente académico</strong>.</li>
                                </ul>
                            </div>
                            
                            <!-- Nota adicional -->
                            <p style="font-size: 14px; color: #999999; line-height: 1.6; margin: 0 0 20px 0;">
                                Si no puede asistir a la entrevista, por favor responda a este correo 
                                con la mayor brevedad posible para poder reasignar la cita.
                            </p>
                            
                            <!-- Firma -->
                            <div style="border-top: 2px solid #e0e0e0; padding-top: 20px; margin-top: 30px;">
                                <p style="margin: 0 0 5px 0; font-size: 16px; color: #333333; font-weight: 600;">
                                    Atentamente,
                                </p>
                                <p style="margin: 0; font-size: 14px; color: #666666;">
                                    Sistema de Gestión de Entrevistas<br>
                                    {entrevistador.email if entrevistador and entrevistador.email else 'entrevistas@universidad.edu'}
                                </p>
                            </div>
                            
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td bgcolor="#f8f9fa" style="padding: 20px 30px; text-align: center; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; font-size: 12px; color: #999999; line-height: 1.5;">
                                Este es un mensaje automático, por favor no responda directamente a este correo.<br>
                                Para cualquier consulta, contacte con el entrevistador indicado.
                            </p>
                        </td>
                    </tr>
                    
                </table>
                
            </td>
        </tr>
    </table>
</body>
</html>
    """

    return subject, html


def generar_email_entrevistador(entrevistador, asignaciones):
    """
    Genera el HTML del email para un entrevistador con su resumen

    Args:
        entrevistador: Objeto Usuario (entrevistador)
        asignaciones: Lista de asignaciones del entrevistador

    Returns:
        tuple: (subject, html_body)
    """

    # Agrupar asignaciones por día
    from collections import defaultdict

    por_dia = defaultdict(list)

    for asig in asignaciones:
        fecha = asig.reserva.fecha
        por_dia[fecha].append(asig)

    # Ordenar fechas
    fechas_ordenadas = sorted(por_dia.keys())

    # Calcular semana
    if asignaciones:
        primera_fecha = min(a.reserva.fecha for a in asignaciones)
        semana_num = primera_fecha.isocalendar()[1]
        año = primera_fecha.year
    else:
        semana_num = 0
        año = 2025

    subject = f"Calendario de Entrevistas - Semana {semana_num}"

    # Generar filas de la tabla
    filas_html = ""
    dias_esp = {
        0: "Lunes",
        1: "Martes",
        2: "Miércoles",
        3: "Jueves",
        4: "Viernes",
        5: "Sábado",
        6: "Domingo",
    }

    for fecha in fechas_ordenadas:
        asigs_dia = sorted(
            por_dia[fecha],
            key=lambda x: x.hora_exacta if x.hora_exacta else x.reserva.hora_inicio,
        )

        # Nombre del día
        dia_semana = dias_esp[fecha.weekday()]
        fecha_str = fecha.strftime("%d/%m/%Y")

        # Primera fila del día (con rowspan)
        primera_asig = asigs_dia[0]
        hora = (
            primera_asig.hora_exacta.strftime("%H:%M")
            if primera_asig.hora_exacta
            else primera_asig.reserva.hora_inicio.strftime("%H:%M")
        )

        filas_html += f"""
        <tr style="border-bottom: 1px solid #e0e0e0;">
            <td rowspan="{len(asigs_dia)}" style="padding: 15px; background-color: #f8f9fa; font-weight: 600; text-align: center; border-right: 2px solid #dee2e6;">
                {dia_semana}<br>
                <span style="font-size: 12px; color: #666; font-weight: normal;">{fecha_str}</span>
            </td>
            <td style="padding: 15px; font-weight: 600; color: #4472C4;">{hora}</td>
            <td style="padding: 15px;">{primera_asig.candidato.nombre} {primera_asig.candidato.apellidos}</td>
            <td style="padding: 15px; text-align: center;">
                <span style="background-color: {'#ffc7ce' if primera_asig.candidato.media_estudios < 5.5 else '#ffeb9c' if primera_asig.candidato.media_estudios < 6.5 else '#c6efce'}; 
                             padding: 4px 8px; border-radius: 4px; font-weight: 600;">
                    {primera_asig.candidato.media_estudios:.2f}
                </span>
            </td>
            <td style="padding: 15px; font-size: 12px; color: #666;">
                {primera_asig.candidato.primera_opcion[:50] + '...' if primera_asig.candidato.primera_opcion and len(primera_asig.candidato.primera_opcion) > 50 else primera_asig.candidato.primera_opcion or '-'}
            </td>
        </tr>
        """

        # Filas adicionales del mismo día
        for asig in asigs_dia[1:]:
            hora = (
                asig.hora_exacta.strftime("%H:%M")
                if asig.hora_exacta
                else asig.reserva.hora_inicio.strftime("%H:%M")
            )
            filas_html += f"""
        <tr style="border-bottom: 1px solid #e0e0e0;">
            <td style="padding: 15px; font-weight: 600; color: #4472C4;">{hora}</td>
            <td style="padding: 15px;">{asig.candidato.nombre} {asig.candidato.apellidos}</td>
            <td style="padding: 15px; text-align: center;">
                <span style="background-color: {'#ffc7ce' if asig.candidato.media_estudios < 5.5 else '#ffeb9c' if asig.candidato.media_estudios < 6.5 else '#c6efce'}; 
                             padding: 4px 8px; border-radius: 4px; font-weight: 600;">
                    {asig.candidato.media_estudios:.2f}
                </span>
            </td>
            <td style="padding: 15px; font-size: 12px; color: #666;">
                {asig.candidato.primera_opcion[:50] + '...' if asig.candidato.primera_opcion and len(asig.candidato.primera_opcion) > 50 else asig.candidato.primera_opcion or '-'}
            </td>
        </tr>
            """

    html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f4;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f4f4f4">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                
                <table width="800" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff" 
                       style="border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td bgcolor="#70AD47" style="padding: 40px 30px; text-align: center; border-radius: 8px 8px 0 0;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 600;">
                                📅 Calendario de Entrevistas
                            </h1>
                            <p style="color: #ffffff; margin: 10px 0 0 0; font-size: 18px;">
                                Semana {semana_num} - {año}
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Contenido -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            
                            <p style="font-size: 16px; color: #333333; line-height: 1.6; margin: 0 0 10px 0;">
                                Hola <strong>{entrevistador.username}</strong>,
                            </p>
                            
                            <p style="font-size: 16px; color: #666666; line-height: 1.6; margin: 0 0 30px 0;">
                                Le adjuntamos su calendario de entrevistas para la próxima semana. 
                                En total tiene <strong>{len(asignaciones)} entrevistas</strong> programadas.
                            </p>
                            
                            <!-- Tabla de entrevistas -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" 
                                   style="border: 1px solid #dee2e6; border-radius: 8px; overflow: hidden;">
                                
                                <!-- Header de tabla -->
                                <tr style="background-color: #70AD47; color: white;">
                                    <th style="padding: 15px; text-align: center; font-weight: 600;">Día</th>
                                    <th style="padding: 15px; text-align: left; font-weight: 600;">Hora</th>
                                    <th style="padding: 15px; text-align: left; font-weight: 600;">Candidato</th>
                                    <th style="padding: 15px; text-align: center; font-weight: 600;">Nota</th>
                                    <th style="padding: 15px; text-align: left; font-weight: 600;">Grado Solicitado</th>
                                </tr>
                                
                                <!-- Filas de datos -->
                                {filas_html}
                                
                            </table>
                            
                            <!-- Resumen -->
                            <div style="background-color: #e7f3ff; border-left: 4px solid #2196F3; padding: 20px; margin: 30px 0; border-radius: 4px;">
                                <p style="margin: 0 0 10px 0; font-size: 16px; color: #0d47a1; font-weight: 600;">
                                    📊 Resumen:
                                </p>
                                <ul style="margin: 0; padding-left: 20px; color: #1565c0; line-height: 1.8;">
                                    <li>Total de entrevistas: <strong>{len(asignaciones)}</strong></li>
                                    <li>Días con entrevistas: <strong>{len(fechas_ordenadas)}</strong></li>
                                    <li>Primera entrevista: <strong>{fechas_ordenadas[0].strftime('%d/%m/%Y') if fechas_ordenadas else '-'}</strong></li>
                                    <li>Última entrevista: <strong>{fechas_ordenadas[-1].strftime('%d/%m/%Y') if fechas_ordenadas else '-'}</strong></li>
                                </ul>
                            </div>
                            
                            <!-- Leyenda de colores -->
                            <div style="margin: 20px 0;">
                                <p style="font-size: 14px; color: #666; margin: 0 0 10px 0;">
                                    <strong>Leyenda de colores (nota media):</strong>
                                </p>
                                <div style="display: inline-block; margin-right: 15px;">
                                    <span style="background-color: #ffc7ce; padding: 4px 12px; border-radius: 4px; font-size: 12px;">< 5.5</span>
                                </div>
                                <div style="display: inline-block; margin-right: 15px;">
                                    <span style="background-color: #ffeb9c; padding: 4px 12px; border-radius: 4px; font-size: 12px;">5.5 - 6.5</span>
                                </div>
                                <div style="display: inline-block;">
                                    <span style="background-color: #c6efce; padding: 4px 12px; border-radius: 4px; font-size: 12px;">> 6.5</span>
                                </div>
                            </div>
                            
                            <!-- Nota -->
                            <p style="font-size: 14px; color: #999999; line-height: 1.6; margin: 30px 0 0 0;">
                                Si tiene alguna duda o necesita realizar cambios en el calendario, 
                                por favor contacte con el administrador del sistema.
                            </p>
                            
                            <!-- Firma -->
                            <div style="border-top: 2px solid #e0e0e0; padding-top: 20px; margin-top: 30px;">
                                <p style="margin: 0 0 5px 0; font-size: 16px; color: #333333; font-weight: 600;">
                                    Saludos cordiales,
                                </p>
                                <p style="margin: 0; font-size: 14px; color: #666666;">
                                    Sistema de Gestión de Entrevistas
                                </p>
                            </div>
                            
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td bgcolor="#f8f9fa" style="padding: 20px 30px; text-align: center; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; font-size: 12px; color: #999999; line-height: 1.5;">
                                Este es un mensaje automático del sistema de gestión de entrevistas.<br>
                                Para consultas, responda a este correo.
                            </p>
                        </td>
                    </tr>
                    
                </table>
                
            </td>
        </tr>
    </table>
</body>
</html>
    """

    return subject, html


# ====================================================================
# PARTE 3: RUTAS DE ENVÍO
# ====================================================================


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
                    asignacion.enviado_email = True
                    asignacion.fecha_envio_email = datetime.now()

                    resultados["candidatos_enviados"] += 1

                except Exception as e:
                    resultados["candidatos_error"] += 1
                    resultados["errores"].append(
                        {
                            "candidato": f"{asignacion.candidato.nombre} {asignacion.candidato.apellidos}",
                            "error": str(e),
                        }
                    )
                    print(f"Error enviando a {asignacion.candidato.email}: {e}")

        # ===== ENVÍO A ENTREVISTADORES =====
        if tipo in ["entrevistadores", "ambos"]:
            # Agrupar asignaciones por entrevistador
            from collections import defaultdict

            por_entrevistador = defaultdict(list)

            for asignacion in asignaciones:
                if asignacion.entrevistador:
                    por_entrevistador[asignacion.entrevistador.id].append(asignacion)

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
                        subject=subject, recipients=[entrevistador.email], html=html
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
