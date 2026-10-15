"""
Exportación de la lista de candidatos de una semana a Excel, CSV y PDF.

Cada función recibe la lista de `Candidato` ya consultada por la ruta (no
hace queries aquí) y devuelve directamente una respuesta `send_file` de
Flask — por eso siguen viviendo en `services/` y no en `utils/`: están a
medio camino entre lógica de negocio (qué columnas, qué colores según
nota/estado) y la capa HTTP (el `send_file` final).
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


def exportar_candidatos_xlsx(candidatos, semana):
    """Exporta candidatos a Excel con formato"""

    wb = Workbook()
    ws = wb.active
    ws.title = f"Candidatos S{semana.split('-W')[1]}"

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
        "Solicitud",
        "Apellidos",
        "Nombre",
        "Email",
        "Teléfono",
        "Nota Media",
        "Sede",
        "Primera Opción",
        "Estado",
        "Fecha Carga",
    ]
    ws.append(headers)

    # Aplicar estilos a encabezados
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    # Datos
    for idx, candidato in enumerate(candidatos, start=1):
        row = [
            idx,
            candidato.clave_academica,
            candidato.solicitud,
            candidato.apellidos,
            candidato.nombre,
            candidato.email or "N/A",
            candidato.telefono or "N/A",
            candidato.media_estudios_texto,
            candidato.sede or "Sin detectar",
            candidato.primera_opcion or "",
            candidato.estado.upper(),
            candidato.fecha_carga.strftime("%d/%m/%Y %H:%M"),
        ]
        ws.append(row)

        # Colorear según nota (columna 8). Sin nota -> gris neutro, nunca
        # rojo: un candidato sin nota no es lo mismo que uno con nota baja.
        if candidato.media_estudios is None:
            color = "E2E3E5"
        else:
            nota = float(candidato.media_estudios)
            color = "FFC7CE" if nota < 5.5 else "FFEB9C" if nota < 6.5 else "C6EFCE"
        ws.cell(row=idx + 1, column=8).fill = PatternFill(
            start_color=color, end_color=color, fill_type="solid"
        )

        # Colorear sede (columna 9)
        if candidato.sede:
            color_sede = "D1ECF1"
            ws.cell(row=idx + 1, column=9).fill = PatternFill(
                start_color=color_sede, end_color=color_sede, fill_type="solid"
            )
            ws.cell(row=idx + 1, column=9).font = Font(bold=True)

        # Colorear según estado (columna 11)
        if candidato.estado == "asignado":
            ws.cell(row=idx + 1, column=11).fill = PatternFill(
                start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"
            )
            ws.cell(row=idx + 1, column=11).font = Font(bold=True, color="006100")
        elif candidato.estado == "pendiente":
            ws.cell(row=idx + 1, column=11).fill = PatternFill(
                start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"
            )
            ws.cell(row=idx + 1, column=11).font = Font(bold=True, color="9C6500")

        # Aplicar bordes
        for cell in ws[idx + 1]:
            cell.border = border
            cell.alignment = Alignment(vertical="center")

    # Ajustar anchos de columna
    ws.column_dimensions["A"].width = 5  # #
    ws.column_dimensions["B"].width = 18  # Clave Académica
    ws.column_dimensions["C"].width = 10  # Solicitud
    ws.column_dimensions["D"].width = 20  # Apellidos
    ws.column_dimensions["E"].width = 15  # Nombre
    ws.column_dimensions["F"].width = 30  # Email
    ws.column_dimensions["G"].width = 15  # Teléfono
    ws.column_dimensions["H"].width = 12  # Nota
    ws.column_dimensions["I"].width = 15  # Sede
    ws.column_dimensions["J"].width = 40  # Primera Opción
    ws.column_dimensions["K"].width = 12  # Estado
    ws.column_dimensions["L"].width = 18  # Fecha

    # Guardar en memoria
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f'candidatos_semana_{semana.split("-W")[1]}.xlsx',
    )


def exportar_candidatos_csv(candidatos, semana):
    """Exporta candidatos a CSV"""

    output = StringIO()
    writer = csv.writer(output, delimiter=";")

    # Encabezados
    writer.writerow(
        [
            "Clave Académica",
            "Solicitud",
            "Apellidos",
            "Nombre",
            "Email",
            "Teléfono",
            "Nota Media",
            "Sede",
            "Primera Opción",
            "Estado",
            "Fecha Carga",
        ]
    )

    # Datos
    for candidato in candidatos:
        writer.writerow(
            [
                candidato.clave_academica,
                candidato.solicitud,
                candidato.apellidos,
                candidato.nombre,
                candidato.email or "N/A",
                candidato.telefono or "N/A",
                candidato.media_estudios_texto,
                candidato.sede or "Sin detectar",
                candidato.primera_opcion or "",
                candidato.estado.upper(),
                candidato.fecha_carga.strftime("%d/%m/%Y %H:%M"),
            ]
        )

    output.seek(0)

    return send_file(
        BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f'candidatos_semana_{semana.split("-W")[1]}.csv',
    )


def exportar_candidatos_pdf(candidatos, semana):
    """Exporta candidatos a PDF"""

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
        Paragraph(f"Candidatos - Semana {semana.split('-W')[1]}", title_style)
    )
    elements.append(Spacer(1, 0.5 * cm))

    # Tabla
    data = [["#", "Clave", "Apellidos", "Nombre", "Email", "Tel.", "Nota", "Sede", "Estado"]]

    for idx, candidato in enumerate(candidatos, start=1):
        data.append(
            [
                str(idx),
                candidato.clave_academica[:12],
                candidato.apellidos[:15],
                candidato.nombre[:12],
                (candidato.email or "N/A")[:20],
                (candidato.telefono or "N/A")[:12],
                candidato.media_estudios_texto,
                (candidato.sede or "N/A")[:10],
                candidato.estado.upper(),
            ]
        )

    table = Table(
        data,
        colWidths=[1 * cm, 2.5 * cm, 3.5 * cm, 2.5 * cm, 4 * cm, 2.5 * cm, 1.5 * cm, 1.8 * cm, 1.8 * cm],
    )

    # Estilos de tabla
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

    # Construir PDF
    doc.build(elements)
    output.seek(0)

    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f'candidatos_semana_{semana.split("-W")[1]}.pdf',
    )