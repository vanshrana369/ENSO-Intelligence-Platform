import json
import os
import logging
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Color scheme
DARK_BLUE = colors.HexColor('#1B3A6B')
LIGHT_BLUE = colors.HexColor('#2196F3')
RED = colors.HexColor('#F44336')
ORANGE = colors.HexColor('#FF9800')
GREEN = colors.HexColor('#4CAF50')
LIGHT_GRAY = colors.HexColor('#F5F5F5')

RISK_COLORS = {
    "Low": GREEN,
    "Medium": ORANGE,
    "High": RED,
    "Extreme": colors.HexColor('#9C27B0')
}

def generate_pdf(report_json, output_path=None):
    if output_path is None:
        today = datetime.now().strftime("%Y-%m-%d")
        os.makedirs("outputs", exist_ok=True)
        output_path = f"outputs/ENSO_Report_{today}.pdf"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    styles = getSampleStyleSheet()
    elements = []

    # --- HEADER ---
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Normal'],
        fontSize=24,
        textColor=DARK_BLUE,
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=LIGHT_BLUE,
        spaceAfter=4,
        alignment=TA_CENTER
    )
    date_style = ParagraphStyle(
        'Date',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.gray,
        spaceAfter=12,
        alignment=TA_CENTER
    )

    elements.append(Paragraph("ENSO Intelligence Platform", title_style))
    elements.append(Paragraph("Climate Risk Intelligence Report", subtitle_style))
    elements.append(Paragraph(f"Report Date: {report_json.get('report_date', datetime.now().strftime('%Y-%m-%d'))}", date_style))
    elements.append(HRFlowable(width="100%", thickness=2, color=DARK_BLUE))
    elements.append(Spacer(1, 0.2*inch))

    # --- EXECUTIVE SUMMARY ---
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Normal'],
        fontSize=14,
        textColor=DARK_BLUE,
        spaceBefore=12,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        spaceAfter=8,
        leading=16
    )

    elements.append(Paragraph("Executive Summary", section_style))
    elements.append(Paragraph(report_json.get('executive_summary', ''), body_style))
    elements.append(Spacer(1, 0.1*inch))

    # --- ENSO STATUS ---
    elements.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE))
    elements.append(Paragraph("ENSO Status", section_style))

    enso = report_json.get('enso_status', {})
    phase = enso.get('phase', 'Unknown')
    phase_color = RED if phase == 'El Nino' else LIGHT_BLUE if phase == 'La Nina' else colors.gray

    enso_data = [
        ['Parameter', 'Value'],
        ['Current Phase', phase],
        ['MEI Value', str(enso.get('mei_value', ''))],
        ['Trend', enso.get('trend', '').capitalize()],
        ['Outlook', enso.get('outlook', '')]
    ]

    enso_table = Table(enso_data, colWidths=[2*inch, 4.5*inch])
    enso_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BACKGROUND', (0, 2), (-1, 2), LIGHT_GRAY),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (1, 1), (1, 1), phase_color),
        ('FONTNAME', (1, 1), (1, 1), 'Helvetica-Bold'),
    ]))
    elements.append(enso_table)
    elements.append(Spacer(1, 0.15*inch))

    # --- MARKET RISKS ---
    elements.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE))
    elements.append(Paragraph("Commodity Market Risks", section_style))

    market = report_json.get('market_risks', {})
    risk_data = [['Commodity', 'Risk Level', 'Price Outlook']]
    for commodity, info in market.items():
        risk_data.append([
            commodity.replace('_', ' ').title(),
            info.get('risk_level', ''),
            info.get('outlook', '')
        ])

    risk_table = Table(risk_data, colWidths=[1.5*inch, 1.2*inch, 3.8*inch])
    risk_table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]
    for i, (commodity, info) in enumerate(market.items(), start=1):
        risk_level = info.get('risk_level', 'Low')
        risk_color = RISK_COLORS.get(risk_level, GREEN)
        risk_table_style.append(('TEXTCOLOR', (1, i), (1, i), risk_color))
        risk_table_style.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))
        if i % 2 == 0:
            risk_table_style.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GRAY))

    risk_table.setStyle(TableStyle(risk_table_style))
    elements.append(risk_table)
    elements.append(Spacer(1, 0.15*inch))

    # --- RECOMMENDATIONS ---
    elements.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE))
    elements.append(Paragraph("Key Recommendations", section_style))

    recommendations = report_json.get('key_recommendations', [])
    for i, rec in enumerate(recommendations, 1):
        elements.append(Paragraph(f"{i}. {rec}", body_style))

    elements.append(Spacer(1, 0.2*inch))

    # --- RISK SCORE ---
    elements.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE))
    risk_score = report_json.get('risk_score', 0)
    score_color = RED if risk_score >= 7 else ORANGE if risk_score >= 4 else GREEN
    score_style = ParagraphStyle(
        'Score',
        parent=styles['Normal'],
        fontSize=16,
        textColor=score_color,
        spaceBefore=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    elements.append(Paragraph(f"Overall Risk Score: {risk_score}/10", score_style))

    # --- FOOTER ---
    elements.append(Spacer(1, 0.3*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.gray,
        alignment=TA_CENTER
    )
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    elements.append(Paragraph("Generated by ENSO Intelligence Platform | For informational purposes only", footer_style))

    doc.build(elements)
    logger.info(f"PDF saved to {output_path}")
    print(f"\nPDF generated: {output_path}")
    return output_path

if __name__ == "__main__":
    # Load latest report JSON
    import glob
    files = glob.glob("outputs/report_*.json")
    if not files:
        print("No report JSON found. Run pipeline.py first!")
    else:
        latest = max(files)
        with open(latest) as f:
            report = json.load(f)
        generate_pdf(report)