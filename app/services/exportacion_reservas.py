"""
Exportación del calendario de reservas de una semana a Excel y PDF (esta
entidad no tenía exportación a CSV en el original).
"""

from io import BytesIO

from flask import send_file
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Asignacion


def exportar_reservas_xlsx(reservas, semana):
    """Exporta reservas a Excel"""

    wb = Workbook()
    ws = wb.active
    ws.title = f"Reservas S{semana.split('-W')[1]}"

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
        "Fecha",
        "Día",
        "Hora Inicio",
        "Hora Fin",
        "Entrevistador",
        "Espacio",
        "Asignaciones",
        "Notas",
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    # Datos
    for idx, reserva in enumerate(reservas, start=2):
        asignaciones = Asignacion.query.filter_by(reserva_id=reserva.id).all()
        num_asignaciones = len(asignaciones)

        candidatos_nombres = ", ".join(
            [f"{a.candidato.nombre} {a.candidato.apellidos}" for a in asignaciones]
        )

        row = [
            reserva.fecha.strftime("%d/%m/%Y"),
            reserva.fecha.strftime("%A"),
            reserva.hora_inicio.strftime("%H:%M"),
            reserva.hora_fin.strftime("%H:%M"),
            reserva.usuario.username,
            reserva.espacio.nombre if reserva.espacio else "N/A",
            (
                f"{num_asignaciones}/2 - {candidatos_nombres}"
                if num_asignaciones > 0
                else "0/2"
            ),
            reserva.notas or "",
        ]
        ws.append(row)

        # Colorear según ocupación
        color = (
            "C6EFCE"
            if num_asignaciones == 0
            else "FFEB9C" if num_asignaciones == 1 else "FFC7CE"
        )
        for col in range(1, 9):
            cell = ws.cell(row=idx, column=col)
            cell.fill = PatternFill(
                start_color=color, end_color=color, fill_type="solid"
            )
            cell.border = border
            cell.alignment = Alignment(vertical="center")

    # Ajustar anchos
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["D"].width = 10
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 15
    ws.column_dimensions["G"].width = 40
    ws.column_dimensions["H"].width = 25

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f'reservas_semana_{semana.split("-W")[1]}.xlsx',
    )


def exportar_reservas_pdf(reservas, semana):
    """Exporta reservas a PDF"""

    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4), topMargin=1 * cm, bottomMargin=1 * cm
    )
    elements = []
    styles = getSampleStyleSheet()

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
            f"Calendario de Reservas - Semana {semana.split('-W')[1]}", title_style
        )
    )
    elements.append(Spacer(1, 0.5 * cm))

    data = [["Fecha", "Día", "Hora", "Entrevistador", "Espacio", "Ocupación"]]

    for reserva in reservas:
        asignaciones = Asignacion.query.filter_by(reserva_id=reserva.id).count()

        data.append(
            [
                reserva.fecha.strftime("%d/%m"),
                reserva.fecha.strftime("%A")[:3],
                reserva.hora_inicio.strftime("%H:%M"),
                reserva.usuario.username[:15],
                (reserva.espacio.nombre if reserva.espacio else "N/A")[:12],
                f"{asignaciones}/2",
            ]
        )

    table = Table(data, colWidths=[2.5 * cm, 2 * cm, 2 * cm, 4 * cm, 3.5 * cm, 2 * cm])

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5394")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]
        )
    )

    elements.append(table)
    doc.build(elements)
    output.seek(0)

    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f'reservas_semana_{semana.split("-W")[1]}.pdf',
    )