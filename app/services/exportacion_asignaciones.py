"""
Exportación de las asignaciones (candidato ↔ reserva ↔ entrevistador) de
una semana a Excel, CSV y PDF.
"""

from io import BytesIO, StringIO
import csv

from flask import send_file
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Traducción de días de la semana (0=Lunes ... 6=Domingo), usada por las
# tres funciones de este fichero.
DIAS_ESP = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


def exportar_asignaciones_xlsx(asignaciones, semana):
    """Exporta asignaciones a Excel con formato"""

    wb = Workbook()
    ws = wb.active
    ws.title = f"Asignaciones S{semana.split('-W')[1]}"

    # Estilos
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(
        start_color="0B5394", end_color="0B5394", fill_type="solid"
    )
    border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # Encabezados
    headers = [
        "#",
        "Clave Académica",
        "Fecha",
        "Día",
        "Hora",
        "Candidato",
        "Email",
        "Teléfono",
        "Nota",
        "Sede",
        "Entrevistador",
        "Espacio",
        "Pos.",
        "Estado",
        "Grado Solicitado",
    ]
    ws.append(headers)

    # Aplicar estilos a encabezados
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    # Datos
    for idx, asignacion in enumerate(asignaciones, start=1):
        candidato = asignacion.candidato
        reserva = asignacion.reserva
        entrevistador = asignacion.entrevistador

        dia_semana = DIAS_ESP[reserva.fecha.weekday()]
        hora_exacta = (
            asignacion.hora_exacta.strftime("%H:%M")
            if asignacion.hora_exacta
            else reserva.hora_inicio.strftime("%H:%M")
        )

        row = [
            idx,
            candidato.clave_academica,
            reserva.fecha.strftime("%d/%m/%Y"),
            dia_semana,
            hora_exacta,
            f"{candidato.nombre} {candidato.apellidos}",
            candidato.email or "N/A",
            candidato.telefono or "N/A",
            float(candidato.media_estudios) if candidato.media_estudios else 0,
            candidato.sede or "N/A",
            entrevistador.username if entrevistador else "N/A",
            reserva.espacio.nombre if reserva.espacio else "N/A",
            asignacion.posicion,
            asignacion.estado.upper(),
            candidato.primera_opcion[:50] if candidato.primera_opcion else "",
        ]
        ws.append(row)

        # Colorear según nota (columna 9)
        nota = float(candidato.media_estudios) if candidato.media_estudios else 0
        color_nota = "FFC7CE" if nota < 5.5 else "FFEB9C" if nota < 6.5 else "C6EFCE"
        ws.cell(row=idx + 1, column=9).fill = PatternFill(
            start_color=color_nota, end_color=color_nota, fill_type="solid"
        )
        ws.cell(row=idx + 1, column=9).font = Font(bold=True)

        # Colorear según estado (columna 14)
        if asignacion.estado == "confirmado":
            ws.cell(row=idx + 1, column=14).fill = PatternFill(
                start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"
            )
            ws.cell(row=idx + 1, column=14).font = Font(bold=True, color="006100")
        elif asignacion.estado == "cancelado":
            ws.cell(row=idx + 1, column=14).fill = PatternFill(
                start_color="F8D7DA", end_color="F8D7DA", fill_type="solid"
            )
            ws.cell(row=idx + 1, column=14).font = Font(bold=True, color="721C24")

        # Aplicar bordes
        for cell in ws[idx + 1]:
            cell.border = border
            cell.alignment = Alignment(vertical="center")

    # Ajustar anchos de columna
    ws.column_dimensions["A"].width = 5  # #
    ws.column_dimensions["B"].width = 18  # Clave Académica
    ws.column_dimensions["C"].width = 12  # Fecha
    ws.column_dimensions["D"].width = 12  # Día
    ws.column_dimensions["E"].width = 10  # Hora
    ws.column_dimensions["F"].width = 30  # Candidato
    ws.column_dimensions["G"].width = 30  # Email
    ws.column_dimensions["H"].width = 15  # Teléfono
    ws.column_dimensions["I"].width = 10  # Nota
    ws.column_dimensions["J"].width = 15  # Sede
    ws.column_dimensions["K"].width = 20  # Entrevistador
    ws.column_dimensions["L"].width = 20  # Espacio
    ws.column_dimensions["M"].width = 6  # Pos.
    ws.column_dimensions["N"].width = 12  # Estado
    ws.column_dimensions["O"].width = 40  # Grado

    # Añadir filtros automáticos
    ws.auto_filter.ref = ws.dimensions

    # Congelar primera fila
    ws.freeze_panes = "A2"

    # Guardar en memoria
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f'asignaciones_semana_{semana.split("-W")[1]}.xlsx',
    )


def exportar_asignaciones_csv(asignaciones, semana):
    """Exporta asignaciones a CSV"""

    output = StringIO()
    writer = csv.writer(output, delimiter=";")

    # Encabezados
    writer.writerow(
        [
            "Clave Académica",
            "Fecha",
            "Día",
            "Hora",
            "Candidato",
            "Email",
            "Teléfono",
            "Nota",
            "Sede",
            "Entrevistador",
            "Espacio",
            "Posición",
            "Estado",
            "Grado Solicitado",
        ]
    )

    # Datos
    for asignacion in asignaciones:
        candidato = asignacion.candidato
        reserva = asignacion.reserva
        entrevistador = asignacion.entrevistador

        dia_semana = DIAS_ESP[reserva.fecha.weekday()]
        hora_exacta = (
            asignacion.hora_exacta.strftime("%H:%M")
            if asignacion.hora_exacta
            else reserva.hora_inicio.strftime("%H:%M")
        )

        writer.writerow(
            [
                candidato.clave_academica,
                reserva.fecha.strftime("%d/%m/%Y"),
                dia_semana,
                hora_exacta,
                f"{candidato.nombre} {candidato.apellidos}",
                candidato.email or "N/A",
                candidato.telefono or "N/A",
                float(candidato.media_estudios) if candidato.media_estudios else 0,
                candidato.sede or "N/A",
                entrevistador.username if entrevistador else "N/A",
                reserva.espacio.nombre if reserva.espacio else "N/A",
                asignacion.posicion,
                asignacion.estado.upper(),
                candidato.primera_opcion if candidato.primera_opcion else "",
            ]
        )

    output.seek(0)

    return send_file(
        BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f'asignaciones_semana_{semana.split("-W")[1]}.csv',
    )


def exportar_asignaciones_pdf(asignaciones, semana):
    """Exporta asignaciones a PDF"""

    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4), topMargin=1 * cm, bottomMargin=1 * cm
    )
    elements = []
    styles = getSampleStyleSheet()

    # Título
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#0B5394"),
        spaceAfter=30,
        alignment=1,
    )

    elements.append(
        Paragraph(
            f"Asignaciones de Entrevistas - Semana {semana.split('-W')[1]}", title_style
        )
    )
    elements.append(Spacer(1, 0.5 * cm))

    # Tabla
    data = [
        ["Clave", "Fecha", "Hora", "Candidato", "Email", "Tel.", "Nota", "Entrev.", "Esp."]
    ]

    for asignacion in asignaciones:
        candidato = asignacion.candidato
        reserva = asignacion.reserva
        entrevistador = asignacion.entrevistador

        hora_exacta = (
            asignacion.hora_exacta.strftime("%H:%M")
            if asignacion.hora_exacta
            else reserva.hora_inicio.strftime("%H:%M")
        )

        data.append(
            [
                candidato.clave_academica[:10],
                reserva.fecha.strftime("%d/%m"),
                hora_exacta,
                f"{candidato.nombre[:10]} {candidato.apellidos[:10]}",
                (candidato.email or "N/A")[:18],
                (candidato.telefono or "N/A")[:10],
                (
                    f"{candidato.media_estudios:.2f}"
                    if candidato.media_estudios
                    else "N/A"
                ),
                (entrevistador.username if entrevistador else "N/A")[:10],
                (reserva.espacio.nombre if reserva.espacio else "N/A")[:8],
            ]
        )

    table = Table(
        data,
        colWidths=[
            1.8 * cm,  # Clave
            1.5 * cm,  # Fecha
            1.3 * cm,  # Hora
            3 * cm,  # Candidato
            3.5 * cm,  # Email
            2 * cm,  # Teléfono
            1.2 * cm,  # Nota
            2.5 * cm,  # Entrevistador
            1.5 * cm,  # Espacio
        ],
    )

    # Estilos de tabla
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5394")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]
        )
    )

    elements.append(table)

    # Resumen
    elements.append(Spacer(1, 0.8 * cm))
    resumen_style = ParagraphStyle(
        "Resumen",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#333333"),
    )
    elements.append(
        Paragraph(
            f"<b>Total de asignaciones:</b> {len(asignaciones)} entrevistas programadas",
            resumen_style,
        )
    )

    # Construir PDF
    doc.build(elements)
    output.seek(0)

    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f'asignaciones_semana_{semana.split("-W")[1]}.pdf',
    )