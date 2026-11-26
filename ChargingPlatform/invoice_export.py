"""Build the file a finance team actually receives.

A CSV is plain text. It cannot carry a logo, a column width, a number
format or a page layout, so the export that went out of the dashboard
opened in Excel as a wall of truncated columns with `####` where the money
should be. That is not a defect in the CSV writer; it is what CSV is. The
CSV stays, for anyone importing into a system, and the two formats below
exist for the two things people actually do with the file: open it, and
send it.

  * a workbook, for finance to filter, sort and reconcile against
  * a PDF invoice in PlagSini's own layout, for sending out

Both carry the logo and the tagline. Everything about the company is a
constant here rather than a literal in the layout code, because a company
address appears five times across the two formats and the next person to
change it must not have to find all five.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

# ── The company, as it appears on paper ────────────────────────────────
COMPANY_NAME = os.getenv("INVOICE_COMPANY_NAME", "PLAG SINI SDN BHD")
COMPANY_ADDRESS = os.getenv(
    "INVOICE_COMPANY_ADDRESS",
    "LOT 2, JALAN GERGAJI 15/14, SEKSYEN 15, 40200 SHAH ALAM, "
    "SELANGOR DARUL EHSAN",
)
COMPANY_TEL = os.getenv("INVOICE_COMPANY_TEL", "03-55247844")
TAGLINE = os.getenv("INVOICE_TAGLINE", "Charge Your Journey")
PAYMENT_TERMS = os.getenv("INVOICE_TERMS", "Net 30 days")

BANK_NAME = os.getenv("INVOICE_BANK_NAME", "Public Bank Berhad")
BANK_ADDRESS = os.getenv(
    "INVOICE_BANK_ADDRESS",
    "No.2, Jalan Pahat G 15/G, Section 15, 40200 Shah Alam, Selangor.",
)
BANK_ACCOUNT = os.getenv("INVOICE_BANK_ACCOUNT", "3245670634")

_HERE = Path(__file__).resolve().parent
LOGO_PATH = _HERE / "static" / "invoice_logo.png"

# Brand green, the same one the dashboard uses.
GREEN = "#00A651"
INK = "#1A1A1A"
MUTED = "#6B7280"
RULE = "#D1D5DB"

# The session table, in the order a finance team reads it. The width is in
# characters for the workbook; the weight is a share of the page for the PDF,
# so one definition drives both and the two cannot drift apart.
# The heading is spelled out for the workbook, where there is room, and
# abbreviated for the PDF, where there is not: a heading wider than its
# column ran into its neighbour and the row read as one word.
#
# The weights are shares of the page and are normalised before use. They
# were hand-written to sum to 1.0 and summed to 1.06, which pushed the last
# column off the right edge and silently truncated every total on it.
COLUMNS = [
    # (key,            heading,             pdf heading,  width, weight, kind)
    ("session_id",     "Session ID",        "Session",       13, 0.080, "text"),
    ("start_time",     "Start Time",        "Start",         18, 0.115, "datetime"),
    ("end_time",       "End Time",          "End",           18, 0.115, "datetime"),
    ("charger",        "Charger",           "Charger",       18, 0.115, "text"),
    ("location",       "Location",          "Location",      34, 0.205, "text"),
    ("energy_kwh",     "Energy (kWh)",      "kWh",           13, 0.060, "kwh"),
    ("rate_per_kwh",   "Rate (RM/kWh)",     "Rate",          13, 0.060, "money"),
    ("energy_cost",    "Energy Cost (RM)",  "Energy RM",     16, 0.085, "money"),
    ("idle_minutes",   "Idle (min)",        "Idle min",      10, 0.055, "int"),
    ("idle_cost",      "Idling Cost (RM)",  "Idling RM",     16, 0.085, "money"),
    ("total",          "Total (RM)",        "Total RM",      13, 0.085, "money"),
]


def _pdf_widths(page_width: float) -> list:
    """Shares of the page, normalised, so the table always fits exactly."""
    total = sum(c[4] for c in COLUMNS)
    return [c[4] / total * page_width for c in COLUMNS]

BREAKDOWN_COLUMNS = [
    ("charger",      "Charger",           "Charger",     18, 0.14, "text"),
    ("location",     "Location",          "Location",    34, 0.26, "text"),
    ("sessions",     "Sessions",          "Sessions",    10, 0.09, "int"),
    ("energy_kwh",   "Energy (kWh)",      "kWh",         13, 0.11, "kwh"),
    ("hours",        "Duration (hrs)",    "Hours",       14, 0.11, "kwh"),
    ("energy_cost",  "Energy Cost (RM)",  "Energy RM",   16, 0.095, "money"),
    ("idle_cost",    "Idling Cost (RM)",  "Idling RM",   16, 0.095, "money"),
    ("revenue",      "Revenue (RM)",      "Revenue RM",  14, 0.10, "money"),
]


def _dt(value) -> str:
    """A timestamp a Malaysian reader recognises, from whatever we hold."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    return value.strftime("%d/%m/%Y %H:%M")


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


_ONES = ["", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT",
         "NINE", "TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN",
         "SIXTEEN", "SEVENTEEN", "EIGHTEEN", "NINETEEN"]
_TENS = ["", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY",
         "EIGHTY", "NINETY"]


def _under_thousand(n: int) -> str:
    out = []
    if n >= 100:
        out.append(_ONES[n // 100] + " HUNDRED")
        n %= 100
        if n:
            out.append("AND")
    if n >= 20:
        word = _TENS[n // 10]
        if n % 10:
            word += "-" + _ONES[n % 10]
        out.append(word)
    elif n:
        out.append(_ONES[n])
    return " ".join(out)


def amount_in_words(amount: float) -> str:
    """The figure spelled out, as a Malaysian invoice states it.

    Not decoration: it is what makes a total hard to alter after the fact,
    which is why the format carries it.
    """
    amount = round(_num(amount), 2)
    ringgit = int(amount)
    sen = int(round((amount - ringgit) * 100))

    if ringgit == 0:
        words = "ZERO"
    else:
        parts = []
        for scale, name in ((1_000_000, "MILLION"), (1_000, "THOUSAND")):
            if ringgit >= scale:
                parts.append(_under_thousand(ringgit // scale) + " " + name)
                ringgit %= scale
        if ringgit:
            if parts:
                parts.append("AND" if ringgit < 100 else "")
            parts.append(_under_thousand(ringgit))
        words = " ".join(p for p in parts if p)

    text = "RINGGIT MALAYSIA " + words
    if sen:
        text += " AND " + _under_thousand(sen) + " SEN"
    return text + " ONLY"


def _totals(rows: Iterable[dict]) -> dict:
    rows = list(rows)
    return {
        "count": len(rows),
        "energy_kwh": round(sum(_num(r.get("energy_kwh")) for r in rows), 2),
        "energy_cost": round(sum(_num(r.get("energy_cost")) for r in rows), 2),
        "idle_minutes": int(sum(_num(r.get("idle_minutes")) for r in rows)),
        "idle_cost": round(sum(_num(r.get("idle_cost")) for r in rows), 2),
        "total": round(sum(_num(r.get("total")) for r in rows), 2),
    }


# ════════════════════════════════════════════════════════════════════════
#  Workbook
# ════════════════════════════════════════════════════════════════════════
def build_xlsx(meta: dict, rows: list, breakdown: Optional[list] = None) -> bytes:
    """A workbook that opens ready to read.

    Columns are sized to their contents, money is formatted as money, the
    header row is frozen and filterable, and the totals are a real row
    rather than a line of text. This is the part a CSV cannot do.
    """
    import xlsxwriter

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True,
                                   "default_date_format": "dd/mm/yyyy hh:mm"})

    f_title = wb.add_format({"bold": True, "font_size": 16, "font_color": GREEN})
    f_tag = wb.add_format({"italic": True, "font_size": 10, "font_color": MUTED})
    f_addr = wb.add_format({"font_size": 9, "font_color": MUTED, "text_wrap": True})
    f_lbl = wb.add_format({"bold": True, "font_size": 9, "font_color": MUTED})
    f_val = wb.add_format({"font_size": 10})
    f_head = wb.add_format({
        "bold": True, "font_size": 9, "font_color": "#FFFFFF",
        "bg_color": GREEN, "border": 1, "border_color": GREEN,
        "align": "center", "valign": "vcenter", "text_wrap": True,
    })
    f_text = wb.add_format({"font_size": 9, "border": 1, "border_color": RULE})
    f_int = wb.add_format({"font_size": 9, "border": 1, "border_color": RULE,
                           "num_format": "0", "align": "right"})
    f_kwh = wb.add_format({"font_size": 9, "border": 1, "border_color": RULE,
                           "num_format": "0.00", "align": "right"})
    f_money = wb.add_format({"font_size": 9, "border": 1, "border_color": RULE,
                             "num_format": "#,##0.00", "align": "right"})
    f_tot_text = wb.add_format({"bold": True, "font_size": 9, "border": 1,
                                "border_color": RULE, "bg_color": "#EAF7EF"})
    f_tot_kwh = wb.add_format({"bold": True, "font_size": 9, "border": 1,
                               "border_color": RULE, "bg_color": "#EAF7EF",
                               "num_format": "0.00", "align": "right"})
    f_tot_money = wb.add_format({"bold": True, "font_size": 9, "border": 1,
                                 "border_color": RULE, "bg_color": "#EAF7EF",
                                 "num_format": "#,##0.00", "align": "right"})
    f_tot_int = wb.add_format({"bold": True, "font_size": 9, "border": 1,
                               "border_color": RULE, "bg_color": "#EAF7EF",
                               "num_format": "0", "align": "right"})

    pick = {"text": f_text, "datetime": f_text, "int": f_int,
            "kwh": f_kwh, "money": f_money}
    pick_tot = {"text": f_tot_text, "datetime": f_tot_text, "int": f_tot_int,
                "kwh": f_tot_kwh, "money": f_tot_money}

    def sheet_header(ws, title, first_col_width):
        """Logo, company and the document's own details, above the table."""
        ws.set_row(0, 46)
        if LOGO_PATH.exists():
            # Scaled to sit inside the first row rather than spilling over the
            # table. x_offset keeps it clear of the cell border.
            ws.insert_image(0, 0, str(LOGO_PATH), {
                "x_scale": 0.22, "y_scale": 0.22,
                "x_offset": 4, "y_offset": 4, "object_position": 1,
            })
        ws.write(0, 2, COMPANY_NAME, f_title)
        ws.write(1, 2, TAGLINE, f_tag)
        ws.write(2, 2, COMPANY_ADDRESS, f_addr)
        ws.write(3, 2, "Tel: " + COMPANY_TEL, f_addr)

        pairs = [
            ("Document No", meta.get("document_no", "")),
            ("Generated", meta.get("generated", "")),
            ("Billing Period", meta.get("period", "")),
            (meta.get("scope_label", "Scope"), meta.get("scope_value", "")),
            ("Sessions", meta.get("count", 0)),
        ]
        for i, (k, v) in enumerate(pairs):
            ws.write(5 + i, 0, k, f_lbl)
            ws.write(5 + i, 1, v, f_val)
        ws.set_column(0, 0, first_col_width)
        return 5 + len(pairs) + 1

    # ── Sessions ───────────────────────────────────────────────────────
    ws = wb.add_worksheet("Sessions")
    ws.set_paper(9)            # A4
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.repeat_rows(0)
    top = sheet_header(ws, "Sessions", COLUMNS[0][2])

    for ci, (_key, head, _ph, width, _w, _kind) in enumerate(COLUMNS):
        ws.set_column(ci, ci, width)
        ws.write(top, ci, head, f_head)
    ws.set_row(top, 28)
    ws.freeze_panes(top + 1, 0)

    r = top + 1
    for row in rows:
        for ci, (key, _h, _ph, _w1, _w2, kind) in enumerate(COLUMNS):
            v = row.get(key)
            if kind == "datetime":
                ws.write_string(r, ci, _dt(v), f_text)
            elif kind in ("money", "kwh"):
                ws.write_number(r, ci, _num(v), pick[kind])
            elif kind == "int":
                ws.write_number(r, ci, int(_num(v)), f_int)
            else:
                ws.write_string(r, ci, "" if v is None else str(v), f_text)
        r += 1

    t = _totals(rows)
    for ci, (key, _h, _ph, _w1, _w2, kind) in enumerate(COLUMNS):
        if ci == 0:
            ws.write_string(r, ci, "TOTAL", f_tot_text)
        elif key in t and kind in ("money", "kwh"):
            ws.write_number(r, ci, t[key], pick_tot[kind])
        elif key in t and kind == "int":
            ws.write_number(r, ci, t[key], f_tot_int)
        else:
            ws.write_string(r, ci, "", f_tot_text)
    if rows:
        ws.autofilter(top, 0, r - 1, len(COLUMNS) - 1)

    # ── By charger ─────────────────────────────────────────────────────
    if breakdown:
        ws2 = wb.add_worksheet("By Charger")
        ws2.set_paper(9)
        ws2.fit_to_pages(1, 0)
        top2 = sheet_header(ws2, "By Charger", BREAKDOWN_COLUMNS[0][2])
        for ci, (_k, head, _ph, width, _w, _kind) in enumerate(BREAKDOWN_COLUMNS):
            ws2.set_column(ci, ci, width)
            ws2.write(top2, ci, head, f_head)
        ws2.set_row(top2, 28)
        ws2.freeze_panes(top2 + 1, 0)
        r2 = top2 + 1
        for row in breakdown:
            for ci, (key, _h, _ph, _w1, _w2, kind) in enumerate(BREAKDOWN_COLUMNS):
                v = row.get(key)
                if kind in ("money", "kwh"):
                    ws2.write_number(r2, ci, _num(v), pick[kind])
                elif kind == "int":
                    ws2.write_number(r2, ci, int(_num(v)), f_int)
                else:
                    ws2.write_string(r2, ci, "" if v is None else str(v), f_text)
            r2 += 1
        for ci, (key, _h, _ph, _w1, _w2, kind) in enumerate(BREAKDOWN_COLUMNS):
            if ci == 0:
                ws2.write_string(r2, ci, "TOTAL", f_tot_text)
            elif kind in ("money", "kwh", "int"):
                total = sum(_num(b.get(key)) for b in breakdown)
                if kind == "int":
                    ws2.write_number(r2, ci, int(total), f_tot_int)
                else:
                    ws2.write_number(r2, ci, round(total, 2), pick_tot[kind])
            else:
                ws2.write_string(r2, ci, "", f_tot_text)

    wb.close()
    return buf.getvalue()


# ════════════════════════════════════════════════════════════════════════
#  PDF
# ════════════════════════════════════════════════════════════════════════
class _Invoice:
    """PlagSini's invoice layout, with the session detail as an annex.

    The invoice page states what is owed and why: energy and idling as two
    charge lines, the figure in words, the bank details and a signature
    block. The line-by-line evidence follows on its own pages, because a
    settlement with four hundred sessions is not an invoice anyone can read
    if the sessions are the invoice.
    """

    def __init__(self, meta: dict, rows: list, breakdown: Optional[list]):
        from fpdf import FPDF

        tagline = TAGLINE
        company = COMPANY_NAME

        class _Doc(FPDF):
            """The footer is fpdf's own hook, run as each page is laid out.

            Writing it afterwards by assigning to `pdf.page` and drawing
            looked like it worked and in fact appended a blank page per
            footer: a four-page file for a seven-row invoice.
            """

            def footer(self):
                self.set_y(-12)
                self.set_font("helvetica", "I", 7)
                self.set_text_color(107, 114, 128)
                self.cell(0, 4, "%s  -  %s" % (company, tagline), align="L")
                self.set_y(-12)
                self.cell(0, 4, "Page %d of {nb}" % self.page_no(), align="R")

        self.meta = meta
        self.rows = rows
        self.breakdown = breakdown or []
        self.t = _totals(rows)
        self.pdf = _Doc(orientation="P", unit="mm", format="A4")
        self.pdf.alias_nb_pages()
        self.pdf.set_auto_page_break(auto=True, margin=16)
        self.pdf.set_title("%s invoice %s" % (COMPANY_NAME,
                                              meta.get("document_no", "")))

    # -- helpers ---------------------------------------------------------
    def _rgb(self, hexcolor):
        h = hexcolor.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    def _letterhead(self, pdf, width):
        y0 = pdf.get_y()
        if LOGO_PATH.exists():
            pdf.image(str(LOGO_PATH), x=12, y=y0, h=16)
        pdf.set_xy(34, y0)
        pdf.set_font("helvetica", "B", 15)
        pdf.set_text_color(*self._rgb(GREEN))
        pdf.cell(width - 34, 6, COMPANY_NAME, new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(34)
        pdf.set_font("helvetica", "I", 8.5)
        pdf.set_text_color(*self._rgb(MUTED))
        pdf.cell(width - 34, 4, TAGLINE, new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(34)
        pdf.set_font("helvetica", "", 7.5)
        pdf.multi_cell(width - 34, 3.4, COMPANY_ADDRESS + "\nTel: " + COMPANY_TEL)
        pdf.set_text_color(*self._rgb(INK))
        pdf.ln(2)
        pdf.set_draw_color(*self._rgb(GREEN))
        pdf.set_line_width(0.6)
        y = max(pdf.get_y(), y0 + 18)
        pdf.line(12, y, 12 + width, y)
        pdf.set_line_width(0.2)
        pdf.set_y(y + 4)

    def _kv_block(self, pdf, pairs, x, width, label_w=30):
        for k, v in pairs:
            pdf.set_x(x)
            pdf.set_font("helvetica", "", 8.5)
            pdf.set_text_color(*self._rgb(MUTED))
            pdf.cell(label_w, 5, k)
            pdf.set_font("helvetica", "B", 8.5)
            pdf.set_text_color(*self._rgb(INK))
            pdf.cell(width - label_w, 5, ": " + str(v), new_x="LMARGIN",
                     new_y="NEXT")

    # -- pages -----------------------------------------------------------
    def _invoice_page(self):
        pdf = self.pdf
        pdf.add_page()
        W = pdf.w - 24
        self._letterhead(pdf, W)

        pdf.set_font("helvetica", "B", 17)
        pdf.set_text_color(*self._rgb(INK))
        pdf.cell(W, 9, "INVOICE", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        top = pdf.get_y()
        # Bill-to on the left, document details on the right, as the format has
        # them. A settlement is billed to the party that sent us the charges.
        pdf.set_xy(12, top)
        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(*self._rgb(MUTED))
        pdf.cell(90, 5, "BILL TO", new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(12)
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(*self._rgb(INK))
        pdf.multi_cell(90, 5, self.meta.get("bill_to", "") or "-")
        left_end = pdf.get_y()

        pdf.set_y(top)
        self._kv_block(pdf, [
            ("No.", self.meta.get("document_no", "")),
            ("Date", self.meta.get("generated", "")),
            ("Terms", PAYMENT_TERMS),
            ("Billing Period", self.meta.get("period", "")),
            (self.meta.get("scope_label", "Scope"),
             self.meta.get("scope_value", "")),
        ], x=112, width=pdf.w - 12 - 112, label_w=30)
        pdf.set_y(max(left_end, pdf.get_y()) + 4)

        # Charge lines. Two of them: what was sold, and what the bay was held
        # for. The sessions behind each are the annex.
        heads = ["Item", "Description", "Qty", "UOM", "U/Price", "Total (RM)"]
        widths = [12, 88, 22, 18, 24, 22]
        self._table_head(pdf, heads, widths)

        rate = (self.t["energy_cost"] / self.t["energy_kwh"]) \
            if self.t["energy_kwh"] else 0.0
        lines = [
            ("1.", "EV charging - energy delivered", "%.2f" % self.t["energy_kwh"],
             "kWh", "%.4f" % rate, "%.2f" % self.t["energy_cost"]),
        ]
        if self.t["idle_cost"]:
            idle_rate = self.t["idle_cost"] / self.t["idle_minutes"] \
                if self.t["idle_minutes"] else 0.0
            lines.append(("2.", "Idling charges - bay occupied after charging",
                          "%d" % self.t["idle_minutes"], "min",
                          "%.4f" % idle_rate, "%.2f" % self.t["idle_cost"]))
        lines.append(("", "%s, %d charging session%s"
                      % (self.meta.get("period", ""), self.t["count"],
                         "" if self.t["count"] == 1 else "s"),
                      "", "", "", ""))

        pdf.set_font("helvetica", "", 9)
        for cells in lines:
            self._table_row(pdf, cells, widths,
                            aligns=["L", "L", "R", "C", "R", "R"])

        pdf.ln(1)
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(sum(widths[:-1]), 7, "Total", align="R")
        pdf.cell(widths[-1], 7, "%.2f" % self.t["total"], align="R",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "B", 8.5)
        pdf.set_text_color(*self._rgb(GREEN))
        pdf.multi_cell(W, 5, amount_in_words(self.t["total"]))
        pdf.set_text_color(*self._rgb(INK))
        pdf.ln(3)

        pdf.set_font("helvetica", "B", 8)
        pdf.cell(W, 5, "Notes :", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 7.5)
        pdf.multi_cell(W, 4,
                       "1. All cheques should be crossed and made payable to "
                       + COMPANY_NAME + ".\n"
                       "   " + BANK_NAME + ", " + BANK_ADDRESS + "\n"
                       "   Account No : " + BANK_ACCOUNT + "\n"
                       "2. Charges are per charging session recorded by the "
                       "charge point. The session list is attached.\n"
                       "3. Kindly email the remittance advice to us once paid.")
        pdf.ln(10)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(70, 5, "", border="T", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(70, 4, "Authorised Signature")

    def _table_head(self, pdf, heads, widths):
        pdf.set_font("helvetica", "B", 8)
        pdf.set_fill_color(*self._rgb(GREEN))
        pdf.set_text_color(255, 255, 255)
        for h, w in zip(heads, widths):
            pdf.cell(w, 7, h, border=0, align="C", fill=True)
        pdf.ln()
        pdf.set_text_color(*self._rgb(INK))

    def _table_row(self, pdf, cells, widths, aligns=None, fill=False):
        aligns = aligns or ["L"] * len(cells)
        pdf.set_draw_color(*self._rgb(RULE))
        if fill:
            pdf.set_fill_color(242, 249, 245)
        for text, w, a in zip(cells, widths, aligns):
            # Trim rather than wrap: a row that wraps breaks the grid, and a
            # location long enough to wrap is readable in the workbook.
            # The core PDF fonts are latin-1 only, so the ellipsis is two
            # dots rather than the character: an invoice that raises on a
            # long address is worse than one that is two pixels uglier.
            s = str(text)
            while s and pdf.get_string_width(s) > w - 2:
                s = s[:-1]
            if s != str(text) and len(s) > 2:
                s = s[:-2] + ".."
            pdf.cell(w, 5.2, s, border="B", align=a, fill=fill)
        pdf.ln()

    def _annex(self):
        if not self.rows:
            return
        pdf = self.pdf
        pdf.add_page(orientation="L")
        W = pdf.w - 24
        pdf.set_font("helvetica", "B", 11)
        pdf.set_text_color(*self._rgb(GREEN))
        pdf.cell(W, 7, "Charging sessions", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(*self._rgb(MUTED))
        pdf.cell(W, 5, "%s  |  %s: %s  |  %s"
                 % (self.meta.get("period", ""),
                    self.meta.get("scope_label", "Scope"),
                    self.meta.get("scope_value", ""),
                    self.meta.get("document_no", "")),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*self._rgb(INK))
        pdf.ln(1)

        widths = _pdf_widths(W)
        heads = [ph for (_k, _h, ph, _cw, _w, _kind) in COLUMNS]
        aligns = ["L" if k in ("text", "datetime") else "R"
                  for (_k, _h, _ph, _cw, _w, k) in COLUMNS]
        self._table_head(pdf, heads, widths)

        pdf.set_font("helvetica", "", 7.5)
        for i, row in enumerate(self.rows):
            if pdf.get_y() > pdf.h - 22:
                pdf.add_page(orientation="L")
                self._table_head(pdf, heads, widths)
                pdf.set_font("helvetica", "", 7.5)
            cells = []
            for (key, _h, _ph, _cw, _w, kind) in COLUMNS:
                v = row.get(key)
                if kind == "datetime":
                    cells.append(_dt(v))
                elif kind == "money":
                    cells.append("%.2f" % _num(v))
                elif kind == "kwh":
                    cells.append("%.2f" % _num(v))
                elif kind == "int":
                    cells.append("%d" % int(_num(v)))
                else:
                    cells.append("" if v is None else str(v))
            self._table_row(pdf, cells, widths, aligns, fill=(i % 2 == 1))

        t = self.t
        pdf.set_font("helvetica", "B", 8)
        cells = []
        for (key, _h, _ph, _cw, _w, kind) in COLUMNS:
            if key == "session_id":
                cells.append("TOTAL")
            elif key in t and kind == "money":
                cells.append("%.2f" % t[key])
            elif key in t and kind == "kwh":
                cells.append("%.2f" % t[key])
            elif key in t and kind == "int":
                cells.append("%d" % t[key])
            else:
                cells.append("")
        self._table_row(pdf, cells, widths, aligns, fill=True)

    def render(self) -> bytes:
        self._invoice_page()
        self._annex()
        return bytes(self.pdf.output())


def build_pdf(meta: dict, rows: list, breakdown: Optional[list] = None) -> bytes:
    return _Invoice(meta, rows, breakdown).render()
