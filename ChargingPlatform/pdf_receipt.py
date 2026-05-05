"""PDF receipt / invoice generator for charging sessions.

Renders a clean, branded A5 single-page PDF the user can download / save.
Used by:
  - Email attachment on send_charging_invoice()
  - GET /api/invoice/{txn_ref}/pdf endpoint (download link)
"""
from __future__ import annotations

import io
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    KeepInFrame,
)


# Brand palette — matches email + app
BRAND_GREEN = colors.HexColor("#22c55e")
BRAND_GREEN_DARK = colors.HexColor("#15803d")
BRAND_BLACK = colors.HexColor("#0b0f14")
BRAND_BG = colors.HexColor("#f0fdf4")
TEXT_DARK = colors.HexColor("#111827")
TEXT_MUTED = colors.HexColor("#6b7280")
BORDER = colors.HexColor("#e5e7eb")

LOGO_CANDIDATES = [
    "/app/static/PLAGSINI LOGO.png",
    "/app/static/plagsini_logo.png",
    "/app/static/logo.png",
    os.path.join(os.path.dirname(__file__), "static", "PLAGSINI LOGO.png"),
    os.path.join(os.path.dirname(__file__), "static", "logo.png"),
]


def _logo_path() -> str | None:
    for p in LOGO_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def _styles():
    s = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "brand", parent=s["Title"], fontSize=17, leading=19,
            textColor=colors.white, fontName="Helvetica-Bold",
            alignment=0, spaceAfter=0,
        ),
        "slogan": ParagraphStyle(
            "slogan", parent=s["Normal"], fontSize=8, leading=10,
            textColor=BRAND_GREEN, fontName="Helvetica-Oblique",
            alignment=0,
        ),
        "doctype": ParagraphStyle(
            "doctype", parent=s["Normal"], fontSize=9, leading=11,
            textColor=colors.white, fontName="Helvetica-Bold",
            alignment=2,
        ),
        "doctype_sub": ParagraphStyle(
            "doctype_sub", parent=s["Normal"], fontSize=7.5, leading=9,
            textColor=colors.HexColor("#bbf7d0"), alignment=2,
        ),
        "h2": ParagraphStyle(
            "h2", parent=s["Heading2"], fontSize=10, leading=12,
            textColor=BRAND_GREEN_DARK, spaceAfter=2, spaceBefore=0,
            fontName="Helvetica-Bold",
        ),
        "label": ParagraphStyle(
            "label", parent=s["Normal"], fontSize=7.5, leading=10,
            textColor=TEXT_MUTED, fontName="Helvetica",
        ),
        "value": ParagraphStyle(
            "value", parent=s["Normal"], fontSize=9, leading=11,
            textColor=TEXT_DARK, fontName="Helvetica-Bold",
        ),
        "value_big": ParagraphStyle(
            "value_big", parent=s["Normal"], fontSize=14, leading=16,
            textColor=BRAND_GREEN_DARK, fontName="Helvetica-Bold",
            alignment=2,
        ),
        "tablehead": ParagraphStyle(
            "tablehead", parent=s["Normal"], fontSize=8, leading=10,
            textColor=BRAND_GREEN_DARK, fontName="Helvetica-Bold",
        ),
        "cell": ParagraphStyle(
            "cell", parent=s["Normal"], fontSize=9, leading=11,
            textColor=TEXT_DARK,
        ),
        "footer_thanks": ParagraphStyle(
            "ft", parent=s["Normal"], fontSize=10, leading=12,
            textColor=BRAND_GREEN_DARK, fontName="Helvetica-Bold",
            alignment=1,
        ),
        "footer_slogan": ParagraphStyle(
            "fs", parent=s["Normal"], fontSize=9, leading=11,
            textColor=BRAND_BLACK, fontName="Helvetica-Oblique",
            alignment=1,
        ),
        "footer_muted": ParagraphStyle(
            "fm", parent=s["Normal"], fontSize=7, leading=9,
            textColor=TEXT_MUTED, alignment=1,
        ),
    }


def render_invoice_pdf(
    *,
    transaction_ref: str,
    charger_id: str,
    connector_id: int,
    started_at_str: str,
    stopped_at_str: str,
    duration_str: str,
    energy_kwh: float,
    amount_paid: float,
    stop_reason: str = "Local",
    customer_email: str | None = None,
    issued_at: str | None = None,
) -> bytes:
    """Return PDF bytes for the charging invoice (single A5 page)."""
    if issued_at is None:
        issued_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A5,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=10 * mm, bottomMargin=10 * mm,
        title=f"PlagSini Invoice {transaction_ref}",
        author="PlagSini Charging",
    )
    st = _styles()
    story = []

    # ---------- HEADER (logo + brand + doctype) — flat 3-col table ----------
    logo = _logo_path()
    if logo:
        logo_img = Image(logo, width=16 * mm, height=16 * mm)
    else:
        logo_img = Paragraph("&#9889;", st["brand"])

    # 2 rows (top: brand + doctype label, bottom: slogan + ref#)
    # 3 cols (logo spans both rows, brand, doctype)
    header = Table(
        [
            [logo_img,
             Paragraph("PlagSini", st["brand"]),
             Paragraph("CHARGING RECEIPT", st["doctype"])],
            ["",
             Paragraph("&#171; Charge your journey &#187;", st["slogan"]),
             Paragraph(f"#{transaction_ref}", st["doctype_sub"])],
        ],
        colWidths=[20 * mm, 50 * mm, 54 * mm],
        rowHeights=[10 * mm, 8 * mm],
    )
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_BLACK),
        ("SPAN", (0, 0), (0, 1)),  # logo spans both rows
        ("VALIGN", (0, 0), (0, 1), "MIDDLE"),
        ("VALIGN", (1, 0), (1, 0), "BOTTOM"),
        ("VALIGN", (1, 1), (1, 1), "TOP"),
        ("VALIGN", (2, 0), (2, 0), "BOTTOM"),
        ("VALIGN", (2, 1), (2, 1), "TOP"),
        ("ALIGN", (0, 0), (0, 1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (0, 1), 6),   # left pad on logo cell
        ("RIGHTPADDING", (2, 0), (2, 1), 8),  # right pad on doctype cell
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
    ]))
    story.append(header)
    # accent strip under header
    accent = Table([[""]], colWidths=[124 * mm], rowHeights=[2 * mm])
    accent.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_GREEN),
    ]))
    story.append(accent)
    story.append(Spacer(1, 5 * mm))

    # ---------- META + SESSION (two columns) ----------
    invoice_meta = Table(
        [
            [Paragraph("INVOICE", st["h2"])],
            [Paragraph("Issued", st["label"])],
            [Paragraph(issued_at, st["value"])],
            [Spacer(1, 2)],
            [Paragraph("Customer", st["label"])],
            [Paragraph(customer_email or "—", st["value"])],
            [Spacer(1, 2)],
            [Paragraph("Payment", st["label"])],
            [Paragraph("TNG eWallet", st["value"])],
        ],
        colWidths=[58 * mm],
    )

    session_meta = Table(
        [
            [Paragraph("SESSION", st["h2"])],
            [Paragraph("Charger", st["label"])],
            [Paragraph(f"{charger_id}  •  Connector {connector_id}", st["value"])],
            [Spacer(1, 2)],
            [Paragraph("Started", st["label"])],
            [Paragraph(started_at_str, st["value"])],
            [Spacer(1, 2)],
            [Paragraph("Stopped", st["label"])],
            [Paragraph(f"{stopped_at_str}  ({stop_reason})", st["value"])],
        ],
        colWidths=[63 * mm],
    )

    two_col = Table([[invoice_meta, session_meta]],
                    colWidths=[58 * mm, 63 * mm])
    two_col.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(two_col)
    story.append(Spacer(1, 5 * mm))

    # ---------- CHARGES TABLE ----------
    charges = Table(
        [
            [Paragraph("DESCRIPTION", st["tablehead"]),
             Paragraph("DURATION", st["tablehead"]),
             Paragraph("ENERGY", st["tablehead"]),
             Paragraph("AMOUNT", st["tablehead"])],
            [Paragraph("Charging session", st["cell"]),
             Paragraph(duration_str, st["cell"]),
             Paragraph(f"{energy_kwh:.2f} kWh", st["cell"]),
             Paragraph(f"RM {amount_paid:.2f}", st["cell"])],
        ],
        colWidths=[45 * mm, 28 * mm, 24 * mm, 24 * mm],
    )
    charges.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, BRAND_GREEN),
        ("LINEBELOW", (0, 1), (-1, 1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (1, 0), (2, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(charges)

    # ---------- TOTAL ----------
    total = Table(
        [[Paragraph("TOTAL PAID", st["tablehead"]),
          Paragraph(f"RM {amount_paid:.2f}", st["value_big"])]],
        colWidths=[97 * mm, 24 * mm],
    )
    total.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_BLACK),
        ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "RIGHT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    # override total label colour to white via paragraph
    total = Table(
        [[Paragraph('<font color="white">TOTAL PAID</font>',
                    ParagraphStyle("th_white", fontSize=10,
                                   fontName="Helvetica-Bold",
                                   textColor=colors.white,
                                   alignment=2)),
          Paragraph(f'<font color="#22c55e">RM&#160;{amount_paid:.2f}</font>',
                    ParagraphStyle("vb_w", fontSize=14,
                                   fontName="Helvetica-Bold",
                                   alignment=2,
                                   wordWrap=None))]],
        colWidths=[85 * mm, 36 * mm],
    )
    total.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_BLACK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(total)
    story.append(Spacer(1, 8 * mm))

    # ---------- FOOTER ----------
    # divider with green dot
    divider = Table([[""]], colWidths=[125 * mm], rowHeights=[0.6 * mm])
    divider.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BRAND_GREEN)]))
    story.append(divider)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Thank you for charging with PlagSini &#187;",
                           st["footer_thanks"]))
    story.append(Spacer(1, 1 * mm))
    story.append(Paragraph("&#171; Charge your journey &#187;", st["footer_slogan"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "This is a computer-generated receipt. No signature required.",
        st["footer_muted"]))
    story.append(Paragraph(
        "Need help? Email us at noreply@plagsini.com or visit plagsini.com",
        st["footer_muted"]))

    # Use KeepInFrame to force everything onto one page
    frame_w = A5[0] - 24 * mm
    frame_h = A5[1] - 20 * mm
    page = KeepInFrame(frame_w, frame_h, story, mode="shrink")
    doc.build([page])
    return buf.getvalue()


if __name__ == "__main__":
    pdf = render_invoice_pdf(
        transaction_ref="PLAGS-2026-0428-001",
        charger_id="CP-DEMO-01",
        connector_id=1,
        started_at_str="2026-04-28 17:00:12",
        stopped_at_str="2026-04-28 17:42:38",
        duration_str="42 min 26 sec",
        energy_kwh=12.34,
        amount_paid=15.50,
        stop_reason="Local",
        customer_email="aqidishak28@gmail.com",
    )
    with open("sample_invoice.pdf", "wb") as f:
        f.write(pdf)
    print("Wrote", len(pdf), "bytes")
