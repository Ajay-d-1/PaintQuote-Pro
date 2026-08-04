"""
pdf_generator.py
────────────────
Generate professional A4 quote PDFs using ReportLab.
Includes GST breakdown, client info, terms & conditions, and footer.
"""

import os
import json
import logging
from datetime import datetime

from reportlab.lib            import colors
from reportlab.lib.pagesizes  import A4
from reportlab.lib.units      import inch, mm
from reportlab.lib.styles     import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus       import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable
)
from reportlab.lib.enums      import TA_RIGHT, TA_CENTER, TA_LEFT

logger = logging.getLogger(__name__)

BRAND_BLUE   = colors.HexColor("#1e40af")
BRAND_ORANGE = colors.HexColor("#f97316")
BRAND_GREEN  = colors.HexColor("#059669")
LIGHT_GRAY   = colors.HexColor("#f9fafb")
BORDER_GRAY  = colors.HexColor("#e5e7eb")
TEXT_DARK    = colors.HexColor("#111827")
TEXT_GRAY    = colors.HexColor("#6b7280")
WHITE        = colors.white


def generate_quote_pdf(quote: dict) -> str:
    """
    Generate and save a PDF for the given quote dict.
    Returns the file path (relative to project root).
    """
    out_dir  = os.path.join("static", "pdfs")
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, f"quote_{quote['id']}.pdf")

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm
    )
    styles  = getSampleStyleSheet()
    story   = []

    # ── Styles ────────────────────────────────────────────────────────
    h1 = ParagraphStyle("H1", parent=styles["Normal"],
                         fontSize=26, fontName="Helvetica-Bold",
                         textColor=BRAND_BLUE, spaceAfter=2)
    subtitle = ParagraphStyle("Sub", parent=styles["Normal"],
                               fontSize=11, textColor=TEXT_GRAY, spaceAfter=6)
    label_style = ParagraphStyle("Lbl", parent=styles["Normal"],
                                  fontSize=9, textColor=TEXT_GRAY,
                                  fontName="Helvetica")
    val_style = ParagraphStyle("Val", parent=styles["Normal"],
                                fontSize=10, textColor=TEXT_DARK,
                                fontName="Helvetica-Bold")
    normal = ParagraphStyle("Norm", parent=styles["Normal"],
                             fontSize=10, textColor=TEXT_DARK,
                             leading=16)
    terms_style = ParagraphStyle("Terms", parent=styles["Normal"],
                                  fontSize=9, textColor=TEXT_GRAY,
                                  leading=14)
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"],
                                   fontSize=8, textColor=TEXT_GRAY,
                                   alignment=TA_CENTER)

    # ── Header ────────────────────────────────────────────────────────
    story.append(Paragraph("🎨 PAINTQUOTE PRO", h1))
    story.append(Paragraph("Professional Painting Services — Detailed Quote", subtitle))
    story.append(HRFlowable(width="100%", thickness=2, color=BRAND_BLUE, spaceAfter=14))

    # ── Quote Meta ────────────────────────────────────────────────────
    date_str = datetime.now().strftime("%d %B %Y")
    meta_data = [
        ["Quote Number:", f"#{quote['id']}",
         "Date:", date_str],
        ["Client Name:",  quote.get("client_name", "N/A"),
         "Paint Grade:",  quote.get("paint_grade", "").title()],
        ["Total Area:",   f"{quote.get('total_area', 0):.0f} sq ft",
         "Status:",       quote.get("status", "Pending").title()],
    ]
    meta_table = Table(meta_data, colWidths=[80, 150, 70, 150])
    meta_table.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",   (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",  (0, 0), (0, -1), TEXT_GRAY),
        ("TEXTCOLOR",  (2, 0), (2, -1), TEXT_GRAY),
        ("TEXTCOLOR",  (1, 0), (1, -1), TEXT_DARK),
        ("TEXTCOLOR",  (3, 0), (3, -1), TEXT_DARK),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceAfter=14))

    # ── Cost Breakdown Table ──────────────────────────────────────────
    story.append(Paragraph("Cost Breakdown", ParagraphStyle(
        "SH", parent=styles["Normal"], fontSize=12, fontName="Helvetica-Bold",
        textColor=BRAND_BLUE, spaceAfter=8
    )))

    breakdown = json.loads(quote.get("breakdown", "{}"))
    header_row = [
        Paragraph("<b>Item</b>", ParagraphStyle("TH", parent=styles["Normal"],
                  fontSize=9, fontName="Helvetica-Bold", textColor=WHITE)),
        Paragraph("<b>Amount (₹)</b>", ParagraphStyle("THR", parent=styles["Normal"],
                  fontSize=9, fontName="Helvetica-Bold", textColor=WHITE,
                  alignment=TA_RIGHT)),
    ]
    table_data = [header_row]
    grand_total = 0.0

    for item, amount in breakdown.items():
        is_grand = item in ("Grand Total",)
        is_sub   = item in ("Subtotal", "GST (18%)")
        amt_str  = f"₹{float(amount):>12,.2f}"
        if is_grand:
            row = [
                Paragraph(f"<b>{item}</b>", ParagraphStyle("GT", parent=styles["Normal"],
                          fontSize=11, fontName="Helvetica-Bold", textColor=BRAND_BLUE)),
                Paragraph(f"<b>{amt_str}</b>", ParagraphStyle("GTR", parent=styles["Normal"],
                          fontSize=12, fontName="Helvetica-Bold", textColor=BRAND_BLUE,
                          alignment=TA_RIGHT)),
            ]
            grand_total = float(amount)
        elif is_sub:
            row = [
                Paragraph(item, ParagraphStyle("Sub", parent=styles["Normal"],
                          fontSize=9, textColor=TEXT_GRAY)),
                Paragraph(amt_str, ParagraphStyle("SubR", parent=styles["Normal"],
                          fontSize=9, textColor=TEXT_GRAY, alignment=TA_RIGHT)),
            ]
        else:
            row = [
                Paragraph(item, ParagraphStyle("R", parent=styles["Normal"],
                          fontSize=10, textColor=TEXT_DARK)),
                Paragraph(amt_str, ParagraphStyle("RR", parent=styles["Normal"],
                          fontSize=10, textColor=TEXT_DARK, alignment=TA_RIGHT)),
            ]
        table_data.append(row)

    col_w = (doc.width - 12*mm)
    bd_table = Table(table_data, colWidths=[col_w * 0.65, col_w * 0.35])
    bd_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  BRAND_BLUE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -2), [WHITE, LIGHT_GRAY]),
        ("BACKGROUND",    (0, -1),(-1, -1), colors.HexColor("#dbeafe")),
        ("GRID",          (0, 0), (-1, -1), 0.5, BORDER_GRAY),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("ALIGN",         (1, 0), (1, -1),  "RIGHT"),
    ]))
    story.append(bd_table)
    story.append(Spacer(1, 14))

    # ── Room Breakdown ────────────────────────────────────────────────
    try:
        rooms = json.loads(quote.get("rooms", "[]"))
        if rooms:
            story.append(Paragraph("Room Details", ParagraphStyle(
                "SH2", parent=styles["Normal"], fontSize=12, fontName="Helvetica-Bold",
                textColor=BRAND_BLUE, spaceAfter=8
            )))
            room_header = [
                Paragraph("<b>Room</b>",        ParagraphStyle("TH", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", textColor=WHITE)),
                Paragraph("<b>Dimensions</b>",  ParagraphStyle("TH", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", textColor=WHITE)),
                Paragraph("<b>Wall Area</b>",   ParagraphStyle("TH", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", textColor=WHITE, alignment=TA_RIGHT)),
                Paragraph("<b>Ceiling Area</b>",ParagraphStyle("TH", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", textColor=WHITE, alignment=TA_RIGHT)),
            ]
            room_data = [room_header]
            for r in rooms:
                name = r.get("name", "Room")
                dims = r.get("dimensions", r.get("dimensions", ""))
                room_data.append([
                    Paragraph(name, normal),
                    Paragraph(dims, normal),
                    Paragraph(f"{r.get('wall_area', r.get('area', 0)):.1f} sqft",
                              ParagraphStyle("RR", parent=styles["Normal"], fontSize=10, alignment=TA_RIGHT)),
                    Paragraph(f"{r.get('ceiling_area', 0):.1f} sqft",
                              ParagraphStyle("RR", parent=styles["Normal"], fontSize=10, alignment=TA_RIGHT)),
                ])
            rw = col_w
            room_table = Table(room_data, colWidths=[rw*0.30, rw*0.30, rw*0.20, rw*0.20])
            room_table.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0), BRAND_BLUE),
                ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
                ("GRID",          (0, 0), (-1, -1), 0.5, BORDER_GRAY),
                ("TOPPADDING",    (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
                ("ALIGN",         (2, 0), (-1, -1), "RIGHT"),
            ]))
            story.append(room_table)
            story.append(Spacer(1, 14))
    except Exception as e:
        logger.warning("Could not render rooms table: %s", e)

    # ── Terms & Conditions ────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceAfter=10))
    story.append(Paragraph("Terms & Conditions", ParagraphStyle(
        "SH3", parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold",
        textColor=TEXT_DARK, spaceAfter=6
    )))
    terms = [
        "• 50% advance payment required to confirm booking.",
        "• Balance due on completion and client sign-off.",
        "• 2-year warranty on all workmanship.",
        "• Quote valid for 15 days from date of issue.",
        "• Any additional scope changes will be quoted separately.",
        "• Client to ensure furniture removed or covered before work begins.",
    ]
    for term in terms:
        story.append(Paragraph(term, terms_style))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceAfter=8))
    story.append(Paragraph(
        "Thank you for choosing PaintQuote Pro | Built with ❤️ for Dad",
        footer_style
    ))

    doc.build(story)
    logger.info("PDF generated: %s", filepath)
    return filepath
