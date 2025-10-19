# inventory/pdf_utils.py

import io
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from django.conf import settings
from reportlab.lib.fonts import addMapping
import os

def generate_pdf_response(filename, title, headers, data):
    """
    Створює PDF-файл з таблицею даних і повертає його як HttpResponse.
    Модифіковано для роботи з об'єктами Paragraph для коректного перенесення рядків.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=30, bottomMargin=30)

    font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'DejaVuSans.ttf')
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_path, 'DejaVuSans-Bold.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Oblique', font_path, 'DejaVuSans-Oblique.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSans-BoldOblique', font_path, 'DejaVuSans-BoldOblique.ttf'))

        addMapping('DejaVuSans', 0, 0, 'DejaVuSans')  # norma
        addMapping('DejaVuSans', 0, 1, 'DejaVuSans-Oblique')  # italic
        addMapping('DejaVuSans', 1, 0, 'DejaVuSans-Bold')  # bold
        addMapping('DejaVuSans', 1, 1, 'DejaVuSans-BoldOblique')  # bold italic
        font_name = 'DejaVuSans'
    else:
        font_name = 'Helvetica'

    styles = getSampleStyleSheet()
    style_title = styles['h1']
    style_title.fontName = font_name
    style_title.alignment = 1

    style_body = styles['BodyText']
    style_body.fontName = font_name
    style_body.leading = 14 # Міжрядковий інтервал

    # Перетворюємо всі дані, включаючи заголовки, на об'єкти Paragraph
    # Це дозволяє автоматично обробляти перенесення рядків
    formatted_data = []
    # Заголовки
    formatted_headers = [Paragraph(str(header), style_body) for header in headers]
    formatted_data.append(formatted_headers)

    # Дані
    for row in data:
        formatted_row = [Paragraph(str(item).replace('\n', '<br/>'), style_body) for item in row]
        formatted_data.append(formatted_row)

    table = Table(formatted_data, hAlign='LEFT')
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), # Вертикальне вирівнювання
        ('FONTNAME', (0, 0), (-1, 0), f'{font_name}-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ])
    table.setStyle(style)

    elements = [Paragraph(title, style_title), Spacer(1, 20), table]
    doc.build(elements)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
