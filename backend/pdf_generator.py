import io
import json
import os
import logging
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage
from reportlab.lib.enums import TA_CENTER, TA_LEFT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DARK_BLUE   = colors.HexColor('#1B3A6B')
LIGHT_BLUE  = colors.HexColor('#2196F3')
RED         = colors.HexColor('#F44336')
ORANGE      = colors.HexColor('#FF9800')
GREEN       = colors.HexColor('#4CAF50')
LIGHT_GRAY  = colors.HexColor('#F5F5F5')
BAND_COLOR  = colors.HexColor('#E3F2FD')

RISK_COLORS = {
    "Low":     GREEN,
    "Medium":  ORANGE,
    "High":    RED,
    "Extreme": colors.HexColor('#9C27B0'),
}


def _make_mei_chart(report_json: dict) -> io.BytesIO | None:
    """Render the MEI trend + forecast as a PNG, return as BytesIO."""
    forecast_block = report_json.get('_forecast')
    if not forecast_block:
        return None

    historical = forecast_block.get('historical', [])
    forecast   = forecast_block.get('forecast', [])
    if not historical:
        return None

    fig, ax = plt.subplots(figsize=(6.2, 2.4))
    fig.patch.set_facecolor('#f8fafc')
    ax.set_facecolor('#f8fafc')

    hist_x  = list(range(len(historical)))
    hist_y  = [d['mei'] for d in historical]
    hist_lb = [d.get('lower') for d in historical]
    hist_ub = [d.get('upper') for d in historical]

    ax.plot(hist_x, hist_y, color='#0077b6', linewidth=1.8, label='Historical')

    if forecast:
        offset   = len(historical)
        fc_x     = list(range(offset, offset + len(forecast)))
        fc_y     = [d['mei'] for d in forecast]
        fc_lower = [d.get('lower', d['mei']) for d in forecast]
        fc_upper = [d.get('upper', d['mei']) for d in forecast]

        ax.plot(fc_x, fc_y, color='#0077b6', linewidth=1.8, linestyle='--', alpha=0.7, label='Forecast')
        ax.fill_between(fc_x, fc_lower, fc_upper, alpha=0.15, color='#0077b6', label='90% CI')

    # Phase threshold lines
    all_len = len(historical) + len(forecast)
    ax.axhline(y=0.5,  color='#f59e0b', linestyle='--', linewidth=0.8, alpha=0.6)
    ax.axhline(y=-0.5, color='#3b82f6', linestyle='--', linewidth=0.8, alpha=0.6)
    ax.axhline(y=0,    color='#94a3b8', linestyle='-',  linewidth=0.5, alpha=0.4)
    ax.text(all_len * 0.98, 0.52,  'El Niño', fontsize=6, color='#b45309', ha='right', va='bottom')
    ax.text(all_len * 0.98, -0.52, 'La Niña', fontsize=6, color='#1d4ed8', ha='right', va='top')

    # X-axis labels
    all_data  = historical + forecast
    step      = max(1, len(all_data) // 7)
    tick_idx  = list(range(0, len(all_data), step))
    tick_lbls = [all_data[i]['month'] for i in tick_idx]
    ax.set_xticks(tick_idx)
    ax.set_xticklabels(tick_lbls, fontsize=6.5, rotation=25, ha='right')
    ax.tick_params(axis='y', labelsize=6.5)
    ax.set_ylabel('MEI', fontsize=7, color='#475569')
    ax.grid(True, alpha=0.18, linestyle='-', linewidth=0.5)
    ax.legend(fontsize=6.5, loc='upper left', framealpha=0.7)
    for spine in ax.spines.values():
        spine.set_alpha(0.2)

    plt.tight_layout(pad=0.4)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_pdf(report_json, output_path=None):
    if output_path is None:
        today = datetime.now().strftime("%Y-%m-%d")
        os.makedirs("outputs", exist_ok=True)
        output_path = f"outputs/ENSO_Report_{today}.pdf"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch
    )

    styles   = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle('Title', parent=styles['Normal'],
        fontSize=22, textColor=DARK_BLUE, spaceAfter=4,
        alignment=TA_CENTER, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
        fontSize=11, textColor=LIGHT_BLUE, spaceAfter=3, alignment=TA_CENTER)
    date_style = ParagraphStyle('Date', parent=styles['Normal'],
        fontSize=9, textColor=colors.gray, spaceAfter=10, alignment=TA_CENTER)
    section_style = ParagraphStyle('Section', parent=styles['Normal'],
        fontSize=13, textColor=DARK_BLUE, spaceBefore=10, spaceAfter=5,
        fontName='Helvetica-Bold')
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
        fontSize=9.5, textColor=colors.black, spaceAfter=6, leading=15)
    small_style = ParagraphStyle('Small', parent=styles['Normal'],
        fontSize=8.5, textColor=colors.HexColor('#475569'), spaceAfter=4, leading=13)

    # ── Header ──────────────────────────────────────────────────────────────────
    elements.append(Paragraph("ENSO Intelligence Platform", title_style))
    elements.append(Paragraph("Climate Risk Intelligence Report", subtitle_style))
    report_date = report_json.get('report_date', datetime.now().strftime('%Y-%m-%d'))
    elements.append(Paragraph(f"Report Date: {report_date}", date_style))
    elements.append(HRFlowable(width="100%", thickness=2, color=DARK_BLUE))
    elements.append(Spacer(1, 0.15 * inch))

    # ── Executive Summary ────────────────────────────────────────────────────────
    elements.append(Paragraph("Executive Summary", section_style))
    elements.append(Paragraph(report_json.get('executive_summary', ''), body_style))
    elements.append(Spacer(1, 0.05 * inch))

    # ── MEI Trend Chart ──────────────────────────────────────────────────────────
    chart_buf = _make_mei_chart(report_json)
    if chart_buf:
        elements.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE))
        elements.append(Paragraph("MEI Index Trend &amp; Forecast", section_style))
        img = RLImage(chart_buf, width=6.2 * inch, height=2.4 * inch)
        elements.append(img)
        elements.append(Spacer(1, 0.1 * inch))

    # ── ENSO Status ──────────────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE))
    elements.append(Paragraph("ENSO Status", section_style))

    enso = report_json.get('enso_status', {})
    phase = enso.get('phase', 'Unknown')
    phase_color = RED if 'nino' in phase.lower() else LIGHT_BLUE if 'nina' in phase.lower() else colors.gray

    enso_data = [
        ['Parameter', 'Value'],
        ['Current Phase', phase],
        ['MEI Value', str(enso.get('mei_value', ''))],
        ['Trend', enso.get('trend', '').capitalize()],
        ['Outlook', enso.get('outlook', '')],
    ]
    enso_table = Table(enso_data, colWidths=[1.8 * inch, 4.7 * inch])
    enso_table.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0), DARK_BLUE),
        ('TEXTCOLOR',   (0, 0), (-1, 0), colors.white),
        ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0), 10),
        ('BACKGROUND',  (0, 2), (-1, 2), LIGHT_GRAY),
        ('GRID',        (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ('FONTSIZE',    (0, 1), (-1, -1), 9),
        ('PADDING',     (0, 0), (-1, -1), 7),
        ('TEXTCOLOR',   (1, 1), (1, 1), phase_color),
        ('FONTNAME',    (1, 1), (1, 1), 'Helvetica-Bold'),
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(enso_table)
    elements.append(Spacer(1, 0.1 * inch))

    # ── Market Risks ─────────────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE))
    elements.append(Paragraph("Commodity Market Risks", section_style))

    market = report_json.get('market_risks', {})
    risk_data = [['Commodity', 'Risk', 'Price Outlook']]
    for commodity, info in market.items():
        risk_data.append([
            commodity.replace('_', ' ').title(),
            info.get('risk_level', '') if isinstance(info, dict) else str(info),
            info.get('outlook', '') if isinstance(info, dict) else '',
        ])

    risk_table = Table(risk_data, colWidths=[1.3 * inch, 0.9 * inch, 4.3 * inch])
    risk_style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 10),
        ('GRID',       (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ('FONTSIZE',   (0, 1), (-1, -1), 8.5),
        ('PADDING',    (0, 0), (-1, -1), 6),
        ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
    ]
    for i, (commodity, info) in enumerate(market.items(), start=1):
        rl = info.get('risk_level', 'Low') if isinstance(info, dict) else 'Low'
        rc = RISK_COLORS.get(rl, GREEN)
        risk_style.append(('TEXTCOLOR', (1, i), (1, i), rc))
        risk_style.append(('FONTNAME',  (1, i), (1, i), 'Helvetica-Bold'))
        if i % 2 == 0:
            risk_style.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GRAY))
    risk_table.setStyle(TableStyle(risk_style))
    elements.append(risk_table)
    elements.append(Spacer(1, 0.1 * inch))

    # ── Recommendations ──────────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE))
    elements.append(Paragraph("Key Recommendations", section_style))
    for i, rec in enumerate(report_json.get('key_recommendations', []), 1):
        elements.append(Paragraph(f"{i}. {rec}", body_style))
    elements.append(Spacer(1, 0.1 * inch))

    # ── Forecast Accuracy ────────────────────────────────────────────────────────
    accuracy = report_json.get('_accuracy')
    if accuracy:
        elements.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE))
        elements.append(Paragraph("Model Forecast Accuracy", section_style))
        acc_data = [
            ['Metric', 'Value'],
            ['Mean Absolute Error (MAE)', str(accuracy.get('mae', '—'))],
            ['Accuracy (±0.3 MEI units)',  f"{accuracy.get('accuracy_pct', '—')}%"],
            ['Direction Accuracy',          f"{accuracy.get('direction_accuracy', '—')}%"],
        ]
        acc_table = Table(acc_data, colWidths=[3 * inch, 3.5 * inch])
        acc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 10),
            ('GRID',       (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ('FONTSIZE',   (0, 1), (-1, -1), 9),
            ('PADDING',    (0, 0), (-1, -1), 7),
            ('BACKGROUND', (0, 2), (-1, 2), LIGHT_GRAY),
        ]))
        elements.append(acc_table)
        elements.append(Spacer(1, 0.1 * inch))

    # ── Risk Score ───────────────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE))
    risk_score = report_json.get('risk_score', 0)
    score_color = RED if risk_score >= 7 else ORANGE if risk_score >= 4 else GREEN
    score_style = ParagraphStyle('Score', parent=styles['Normal'],
        fontSize=15, textColor=score_color, spaceBefore=10,
        alignment=TA_CENTER, fontName='Helvetica-Bold')
    elements.append(Paragraph(f"Overall Risk Score: {risk_score} / 10", score_style))

    # ── News Items ───────────────────────────────────────────────────────────────
    news_items = report_json.get('news_items', [])
    if news_items:
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE))
        elements.append(Paragraph("Latest Climate News", section_style))
        for item in news_items[:6]:
            title  = item.get('title', '')
            source = item.get('source', '')
            date   = (item.get('published_at') or item.get('date') or '')[:10]
            line   = f"<b>{source}</b> · {date} — {title}" if source else title
            elements.append(Paragraph(line, small_style))

    # ── Footer ───────────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 0.25 * inch))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'],
        fontSize=7.5, textColor=colors.gray, alignment=TA_CENTER)
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    elements.append(Paragraph(
        "Generated by ENSO Intelligence Platform · Built by Vansh Rana · For informational purposes only",
        footer_style
    ))

    doc.build(elements)
    logger.info(f"PDF saved to {output_path}")
    return output_path


if __name__ == "__main__":
    import glob as _glob
    files = _glob.glob("outputs/report_*.json")
    if not files:
        print("No report JSON found. Run pipeline.py first!")
    else:
        with open(max(files)) as f:
            report = json.load(f)
        generate_pdf(report)
