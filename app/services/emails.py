"""
Envío y generación de los emails de la aplicación: confirmación de
entrevista para el candidato, y resumen semanal de calendario para el
entrevistador. El HTML se genera aquí como f-strings (igual que en el
original) en vez de plantillas Jinja, porque estos correos no se
renderizan a través de Flask — se mandan por Flask-Mail directamente.
"""

from collections import defaultdict

from app.extensions import mail


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

    # Enlace del entrevistador
    enlace_videollamada = (
        entrevistador.enlace_videollamada_personal if entrevistador else None
    )

    # El enlace de entrevista depende del profesor (puede no haberlo
    # configurado). BUG corregido: el enlace de la prueba de inglés vivía
    # anidado dentro de este mismo bloque "seccion_videollamada", así que
    # cuando el profesor no tenía enlace de videollamada, el candidato
    # tampoco recibía el enlace a la prueba de inglés — pero la prueba de
    # inglés es siempre la misma, independientemente del profesor, así
    # que ahora es su propio bloque, que se muestra siempre.
    seccion_videollamada = ""
    if enlace_videollamada:
        seccion_videollamada = f"""
                                        <p style="margin: 0 0 15px 0; font-size: 16px; color: #333333;">
                                            <span style="font-size: 20px;">🎥</span>
                                            <strong>Enlace entrevista:</strong><br>
                                            <span style="margin-left: 30px;">
                                                <a href="{enlace_videollamada}"
                                                   style="color: #0066B3; text-decoration: none; font-weight: 600;"
                                                   target="_blank">
                                                    Únete en la web
                                                </a>
                                            </span>
                                        </p>
        """

    seccion_prueba_ingles = f"""
                                        <p style="margin: 0 0 15px 0; font-size: 16px; color: #333333;">
                                            <span style="font-size: 20px;">🇬🇧</span>
                                            <strong>Prueba de inglés:</strong><br>
                                            <span style="margin-left: 30px;">
                                                <a href="http://www.comillas.edu/ingleseuef"
                                                   style="color: #0066B3; text-decoration: none; font-weight: 600;"
                                                   target="_blank">
                                                    Enlace a prueba de inglés
                                                </a>
                                            </span>
                                        </p>
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

                <!-- Contenedor principal -->
                <table width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff"
                       style="border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

                    <!-- HEADER CON LOGO -->
                    <tr>
                        <td style="background-color: #00A1DF; padding: 40px 20px; text-align: center;">
                                <!-- COMILLAS (gris claro) -->
                                <div style="font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; font-size: 12px; color: #ffffff; letter-spacing: 3px; font-weight: 300; margin-bottom: 8px;">
                                    COMILLAS
                                </div>

                                        <!-- ESCUELA DE ENFERMERÍA Y FISIOTERAPIA (azul claro) -->
                                <div style="font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; font-size: 20px; font-weight: bold; color: #ffffff; letter-spacing: 1.5px; line-height: 1.2; margin-bottom: 20px;">
                                    ESCUELA DE ENFERMERÍA<br>Y FISIOTERAPIA
                                </div>

                                <!-- Línea separadora decorativa -->
                                <div style="width: 100px; height: 3px; background: linear-gradient(to right, transparent, #00A1DF, transparent); margin: 0 auto 20px auto;"></div>


                                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 600; text-shadow: 0 2px 4px rgba(0,0,0,0.2); font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;">
                                    Confirmación de Entrevista
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
                                Para poder valorar su admisión en los estudios GRADO EN ENFERMERIA, además de su expediente académico tendrá que realizar una entrevista personal y una prueba de nivel de inglés.
                            <br>
                                A continuación le indicamos día, hora y el enlace para realizar la entrevista personal online.

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

                                        {seccion_videollamada}

                                        {seccion_prueba_ingles}

                                        <p style="margin: 0; font-size: 16px; color: #333333;">
                                            <span style="font-size: 20px;">👤</span>
                                            <strong>Entrevistador:</strong><br>
                                            <span style="color: #666666; margin-left: 30px;">{entrevistador.nombre_completo if entrevistador else 'A confirmar'}</span>
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
                                    <li style="margin: 5px 0;">Es recomendable que utilice <strong>CHROME</strong> como navegador y lo haga desde un ordenador.</li>
                                    {"<li style='margin: 5px 0;'>Haz click sobre el icono “únete en la web” e indica tu nombre cuando te pida “indica tu nombre”.</li>" if enlace_videollamada else "<li style='margin: 5px 0;'>Por favor, llegue <strong>10 minutos antes</strong> de la hora indicada.</li>"}
                                    <li style="margin: 5px 0;">Para realizar la prueba de nivel de inglés online deberá acceder a través del enlace proporcionado anteriormente indicando su usuario seguido de @alu.comillas.edu (ejemplo: 202300000@alu.comillas.edu).</li>
                                </ul>
                            </div>

                            <!-- Nota adicional -->
                            <p style="font-size: 14px; color: #999999; line-height: 1.6; margin: 0 0 20px 0;">
                                Si no puede asistir a la entrevista, por favor envíe un correo a enfermeriafisioterapia@comillas.edu
                                con la mayor brevedad posible para poder reasignar la cita.
                            </p>

                            <!-- Firma -->
                            <div style="border-top: 2px solid #e0e0e0; padding-top: 20px; margin-top: 30px;">
                                <p style="margin: 0 0 5px 0; font-size: 16px; color: #333333; font-weight: 600;">
                                    Atentamente
                                </p>

                            </div>

                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td bgcolor="#f8f9fa" style="padding: 20px 30px; text-align: center; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; font-size: 12px; color: #999999; line-height: 1.5;">
                                Este es un mensaje automático, por favor no responda directamente a este correo.<br>
                                Para cualquier consulta, contacte con el correo indicado anteriormente.
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
        meses_esp = {
            1: "Enero",
            2: "Febrero",
            3: "Marzo",
            4: "Abril",
            5: "Mayo",
            6: "Junio",
            7: "Julio",
            8: "Agosto",
            9: "Septiembre",
            10: "Octubre",
            11: "Noviembre",
            12: "Diciembre",
        }
        mes_nombre = meses_esp[primera_fecha.month]
    else:
        semana_num = 0
        mes_nombre = "Enero"
        año = 2026

    subject = f"Calendario de Entrevistas - {mes_nombre} {año}"

    # Generar filas de la tabla con colores diferenciados por día
    filas_html = ""
    colores_dia = ["#F0F8FF", "#F5FFFA"]  # Azul claro y verde muy claro
    indice_color = 0

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

        # Color de fondo para este día
        color_fondo = colores_dia[indice_color % 2]

        # Primera fila del día (con rowspan)
        primera_asig = asigs_dia[0]
        hora = (
            primera_asig.hora_exacta.strftime("%H:%M")
            if primera_asig.hora_exacta
            else primera_asig.reserva.hora_inicio.strftime("%H:%M")
        )

        candidato = primera_asig.candidato
        email_candidato = candidato.email or "No disponible"
        telefono = candidato.telefono or "No proporcionado"

        filas_html += f"""
        <tr style="background-color: {color_fondo}; border-bottom: 2px solid #0B5394;">
            <td rowspan="{len(asigs_dia)}" style="padding: 15px; background-color: #0B5394; color: white; font-weight: 600; text-align: center; border-right: 2px solid white; vertical-align: middle;">
                <strong style="font-size: 16px;">{dia_semana}</strong><br>
                <span style="font-size: 13px; margin-top: 5px; display: block;">{fecha_str}</span>
            </td>
            <td style="padding: 15px; font-weight: 600; color: #0B5394; background-color: {color_fondo};">{hora}</td>
            <td style="padding: 15px; background-color: {color_fondo};">
                <strong>{candidato.nombre} {candidato.apellidos}</strong><br>
                <small style="color: #666;">📧 {email_candidato}</small><br>
                <small style="color: #666;">📞 {telefono}</small>
            </td>
            <td style="padding: 15px; font-size: 12px; color: #666; background-color: {color_fondo};">
                {primera_asig.candidato.primera_opcion[:50] + '...' if primera_asig.candidato.primera_opcion and len(primera_asig.candidato.primera_opcion) > 50 else primera_asig.candidato.primera_opcion or '-'}
            </td>
        </tr>
        """

        for asig in asigs_dia[1:]:
            hora = (
                asig.hora_exacta.strftime("%H:%M")
                if asig.hora_exacta
                else asig.reserva.hora_inicio.strftime("%H:%M")
            )
            candidato = asig.candidato
            email_candidato = candidato.email or "No disponible"
            telefono = candidato.telefono or "No proporcionado"

            filas_html += f"""
        <tr style="background-color: {color_fondo}; border-bottom: 1px solid #ddd;">
            <td style="padding: 15px; font-weight: 600; color: #0B5394; background-color: {color_fondo};">{hora}</td>
            <td style="padding: 15px; background-color: {color_fondo};">
                <strong>{candidato.nombre} {candidato.apellidos}</strong><br>
                <small style="color: #666;">📧 {email_candidato}</small><br>
                <small style="color: #666;">📞 {telefono}</small>
            </td>
            <td style="padding: 15px; font-size: 12px; color: #666; background-color: {color_fondo};">
                {asig.candidato.primera_opcion[:50] + '...' if asig.candidato.primera_opcion and len(asig.candidato.primera_opcion) > 50 else asig.candidato.primera_opcion or '-'}
            </td>
        </tr>
        """

        # Fila de separación entre días
        if fecha != fechas_ordenadas[-1]:  # Si no es el último día
            filas_html += f"""
        <tr style="height: 20px; background-color: #ffffff; border-bottom: 3px solid #0B5394;">
            <td colspan="4" style="text-align: center; font-size: 12px; color: #999; font-weight: bold; padding: 8px;">
                ✓ FIN DEL {dia_semana.upper()}
            </td>
        </tr>
        """

        # Cambiar color para el siguiente día
        indice_color += 1

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

                    <!-- HEADER CON LOGO -->
                    <tr>
                        <td style="background-color: #00A1DF; padding: 40px 20px; text-align: center;">

                            <!-- Logo en texto con mejor tipografía -->
                            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                <tr>
                                    <td align="center">

                                        <!-- COMILLAS (gris claro) -->
                                        <div style="font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; font-size: 12px; color: #ffffff;; letter-spacing: 3px; font-weight: 300; margin-bottom: 8px;">
                                            COMILLAS
                                        </div>

                                        <!-- ESCUELA DE ENFERMERÍA Y FISIOTERAPIA (azul claro) -->
                                        <div style="font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; font-size: 20px; font-weight: bold; color: #ffffff;; letter-spacing: 1.5px; line-height: 1.2; margin-bottom: 20px;">
                                            ESCUELA DE ENFERMERÍA<br>Y FISIOTERAPIA
                                        </div>

                                        <!-- Línea separadora decorativa -->
                                        <div style="width: 100px; height: 3px; background: linear-gradient(to right, transparent, #00A1DF, transparent); margin: 0 auto 20px auto;"></div>

                                        <!-- Título del email -->
                                        <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 600; text-shadow: 0 2px 4px rgba(0,0,0,0.2); font-family: 'Segoe UI', Arial, sans-serif;">
                                            Calendario de Entrevistas - {mes_nombre} {año}
                                        </h1>

                                    </td>
                                </tr>
                            </table>

                        </td>
                    </tr>

                    <!-- Contenido -->
                    <tr>
                        <td style="padding: 40px 30px;">

                            <p style="font-size: 16px; color: #333333; line-height: 1.6; margin: 0 0 10px 0;">
                                Estimado <strong>{entrevistador.username}</strong>,
                            </p>

                            <p style="font-size: 16px; color: #666666; line-height: 1.6; margin: 0 0 30px 0;">
                                Le adjuntamos su calendario de entrevistas para la próxima semana.
                                En total tiene <strong>{len(asignaciones)} entrevistas</strong> programadas.
                            </p>
                            <!--  Enlace de videollamada del profesor -->
                            {"<div style='background-color: #e7f3ff; border-left: 4px solid #2196F3; padding: 20px; margin: 0 0 25px 0; border-radius: 4px;'>" if entrevistador.enlace_videollamada_personal else ""}
                            {f"<p style='margin: 0 0 15px 0; font-size: 16px; color: #0d47a1; font-weight: 600;'>🎥 Tu enlace de videollamada:</p>" if entrevistador.enlace_videollamada_personal else ""}
                            {f"<p style='margin: 0; font-size: 14px; color: #666;'><a href='{entrevistador.enlace_videollamada_personal}' style='color: #2196F3; text-decoration: none; font-weight: 600; word-break: break-all;' target='_blank'>{entrevistador.enlace_videollamada_personal}</a></p>" if entrevistador.enlace_videollamada_personal else ""}
                            {"</div>" if entrevistador.enlace_videollamada_personal else ""}

                            <!-- Tabla de entrevistas -->
                            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                                   style="border: 1px solid #dee2e6; border-radius: 8px; overflow: hidden;">

                                <!-- Header de tabla -->
                                <tr style="background-color: #FFB81C; color: black;">
                                    <th style="padding: 15px; text-align: center; font-weight: 600;">Día</th>
                                    <th style="padding: 15px; text-align: left; font-weight: 600;">Hora</th>
                                    <th style="padding: 15px; text-align: left; font-weight: 600;">Candidato</th>
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
                                </ul>
                            </div>

                            <!-- Nota -->
                            <p style="font-size: 14px; color: #999999; line-height: 1.6; margin: 30px 0 0 0;">
                                Si tiene alguna duda o necesita realizar cambios en el calendario,
                                por favor contacte con <strong>enfermeriafisioterapia@comillas.edu</strong>.
                            </p>

                            <!-- Firma -->
                            <div style="border-top: 2px solid #e0e0e0; padding-top: 20px; margin-top: 30px;">
                                <p style="margin: 0 0 5px 0; font-size: 16px; color: #333333; font-weight: 600;">
                                    Atentamente
                                </p>
                            </div>

                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td bgcolor="#f8f9fa" style="padding: 20px 30px; text-align: center; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; font-size: 12px; color: #999999; line-height: 1.5;">
                                Este es un mensaje automático del sistema de gestión de entrevistas.<br>
                                Para consultas, contacte con el correo mencionado anteriormente.
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