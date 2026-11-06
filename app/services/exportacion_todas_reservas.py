"""
Exportación a Excel de la vista /admin/todas-reservas (las reservas de
todos los profesores, con los filtros que tenga la vista aplicados).
"""

from datetime import date, datetime
from io import BytesIO

from flask import send_file
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

HEADERS = [
    "Fecha", "Curso", "Día", "Hora inicio", "Hora fin",
    "Usuario", "Creada por", "Notas", "Creada",
]
ANCHOS = [12, 11, 12, 11, 10, 28, 24, 40, 17]


def exportar_todas_reservas_xlsx(reservas, filtros=None):
    """Genera el .xlsx y lo devuelve como descarga. `reservas` ya viene
    filtrado y ordenado como en pantalla."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Reservas"

    borde = Border(*(Side(style="thin", color="BBBBBB"),) * 4)
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF", size=12)
        cell.fill = PatternFill(start_color="0B5394", end_color="0B5394", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = borde

    for fila, r in enumerate(reservas, start=2):
        creador = r.creador_admin
        ws.append([
            r.fecha,
            r.curso,
            r.espacio.nombre if r.espacio else "",
            r.hora_inicio,
            r.hora_fin,
            r.usuario.nombre_completo or r.usuario.username,
            (creador.nombre_completo or creador.username) if creador else "",
            r.notas or "",
            r.fecha_creacion,
        ])
        ws.cell(row=fila, column=1).number_format = "DD/MM/YYYY"
        ws.cell(row=fila, column=4).number_format = "HH:MM"
        ws.cell(row=fila, column=5).number_format = "HH:MM"
        ws.cell(row=fila, column=9).number_format = "DD/MM/YYYY HH:MM"
        for col in range(1, len(HEADERS) + 1):
            c = ws.cell(row=fila, column=col)
            c.border = borde
            c.alignment = Alignment(vertical="top", wrap_text=(col == 8))

    for i, ancho in enumerate(ANCHOS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = ancho

    ws.freeze_panes = "A2"
    if reservas:
        ws.auto_filter.ref = f"A1:{ws.cell(row=1, column=len(HEADERS)).column_letter}{len(reservas) + 1}"

    salida = BytesIO()
    wb.save(salida)
    salida.seek(0)
    return send_file(
        salida,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"reservas_{date.today().isoformat()}.xlsx",
    )