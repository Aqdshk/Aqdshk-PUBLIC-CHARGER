"""Build one Word document from the handover markdown set.

Written rather than pandoc'd because pandoc and LibreOffice are not on this
machine. The parser only has to understand the constructs these nine files
actually use, which is why it is this short.

Mermaid does not render in Word, so the two diagrams are replaced: the
architecture one by its ASCII equivalent in a monospaced block, and the
OCPP sequence by a table, which reads better on paper than sequence art.
"""
import io
import os
import re
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

SRC = sys.argv[1]
OUT = sys.argv[2]
LOGO = sys.argv[3] if len(sys.argv) > 3 else None

GREEN = RGBColor(0x00, 0xA6, 0x51)
INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x60, 0x66, 0x70)
CODE_BG = "F3F4F6"
HEAD_BG = "00A651"

# Titles are stated, not derived from the filename: deriving them gave
# "2. Ocpp" and "5. Gotchas", which is not what a reader should see.
ORDER = [
    ("README.md", "Start here"),
    ("01-architecture.md", "1. Architecture"),
    ("02-ocpp.md", "2. How OCPP works"),
    ("03-operations.md", "3. Operations"),
    ("04-access.md", "4. Access"),
    ("05-gotchas.md", "5. What will bite you"),
    ("06-contacts.md", "6. Who to talk to, and what is outstanding"),
    ("07-local-setup.md", "7. Setting up on your laptop"),
    ("08-secrets-inventory.md", "8. Secrets inventory"),
]

ARCH_ASCII = """\
                         THE INTERNET
   +---------------+---------------------+------------------+
   |               |                     |                  |
 Driver      Charge points        Roaming partner
 phone or    DC3001, AION,        Voltality / Touch 'n Go
 walk-up     HICI, MT01...        (OCPI 2.2.1)
   |               |                     |
   +---------------+---------------------+
                   |
        +----------v-----------+
        |  nginx on the host   |   :80  :443
        |  TLS, routes by      |
        |  server_name         |
        +----------+-----------+
                   |
  +--------+-------+--------+-----------+-----------+
  |        |                |           |           |
+-v------------+ +-v---------+ +-v--------+ +-v-------+
| plagsini-api | | plagsini- | | customer-| | grafana |
|  :8000 HTTP  | |   web     | | service  | |  :3001  |
|  :9000 OCPP  | |  :3000    | |  :8001   | +----+----+
+------+-------+ +-----------+ +----------+      |
       |            AppEV        support bot     |
       |                                      +--v----+
       v                                      | loki  |<-- promtail
+---------------------------+                 | :3100 |
| charging-platform-mysql   |                 +-------+
|   MySQL 8   :3307         |
+---------------------------+

Some chargers connect straight to :9000 instead of through nginx."""

SEQ_ROWS = [
    ("Charger -> Us", "BootNotification", "vendor, model, firmware"),
    ("Us -> Charger", "Accepted", "plus the heartbeat interval"),
    ("Charger -> Us", "Heartbeat", "every interval, forever. This is what 'online' means"),
    ("Charger -> Us", "StatusNotification", "connector 1 is Available"),
    ("Driver/partner", "asks us to start", "from the app, the dashboard or OCPI"),
    ("Us -> Charger", "RemoteStartTransaction", "carrying an idTag"),
    ("Charger -> Us", "Accepted", "the instruction was taken. Nothing has charged yet"),
    ("Charger -> Us", "Authorize", "is this idTag valid? See the trap below"),
    ("Us -> Charger", "Accepted", ""),
    ("Charger -> Us", "StatusNotification", "Preparing, then Charging"),
    ("Charger -> Us", "StartTransaction", "meterStart. We assign the transaction id"),
    ("Charger -> Us", "MeterValues", "repeatedly: Wh, A, V, and SoC if the car reports it"),
    ("Us -> Charger", "RemoteStopTransaction", "by transaction id"),
    ("Charger -> Us", "StopTransaction", "meterStop and a reason"),
    ("Charger -> Us", "StatusNotification", "Finishing, then Available when the cable comes out"),
]

INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")


def shade(cell, hexcolor):
    el = OxmlElement("w:shd")
    el.set(qn("w:val"), "clear")
    el.set(qn("w:fill"), hexcolor)
    cell._tc.get_or_add_tcPr().append(el)


def add_runs(par, text):
    """Bold, inline code and links. Links are flattened to their text plus
    the target in brackets: a Word reader cannot hover a markdown link."""
    for piece in INLINE.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            r = par.add_run(piece[2:-2])
            r.bold = True
        elif piece.startswith("`") and piece.endswith("`"):
            r = par.add_run(piece[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(0xB0, 0x30, 0x60)
        elif re.fullmatch(r"\[[^\]]+\]\([^)]+\)", piece):
            # startswith("[") also matched the "[  ]" checkbox prefix, which
            # is not a link and has no groups to read.
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", piece)
            label, target = m.group(1), m.group(2)
            r = par.add_run(label)
            r.underline = True
            r.font.color.rgb = RGBColor(0x1A, 0x57, 0xA0)
            if target.startswith("http"):
                s = par.add_run("  " + target)
                s.font.size = Pt(8)
                s.font.color.rgb = MUTED
        else:
            par.add_run(piece.replace("\\|", "|"))


def code_block(doc, lines):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    cell = t.rows[0].cells[0]
    shade(cell, CODE_BG)
    cell.text = ""
    for i, line in enumerate(lines):
        p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        r = p.add_run(line if line.strip() else " ")
        r.font.name = "Consolas"
        r.font.size = Pt(8.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def table_block(doc, rows):
    header, body = rows[0], rows[1:]
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        shade(c, HEAD_BG)
        c.text = ""
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.space_before = Pt(2)
        r = p.add_run(re.sub(r"\*\*", "", h))
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    for row in body:
        cells = t.add_row().cells
        for i, val in enumerate(row[:len(header)]):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.space_before = Pt(2)
            add_runs(p, val)
            for r in p.runs:
                if not r.font.size:
                    r.font.size = Pt(9)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def split_row(line):
    line = line.strip().strip("|")
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)]


def render(doc, md, seq_used):
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # fenced block
        if line.startswith("```"):
            lang = line[3:].strip()
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            if lang == "mermaid":
                if "flowchart" in "\n".join(buf):
                    code_block(doc, ARCH_ASCII.split("\n"))
                else:
                    table_block(doc, [["Direction", "Message", "What it means"]]
                                + [list(r) for r in SEQ_ROWS])
                    seq_used.append(True)
            else:
                code_block(doc, buf)
            i = j + 1
            continue

        # table
        if line.strip().startswith("|") and i + 1 < len(lines) and \
                re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            rows = [split_row(line)]
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(split_row(lines[j]))
                j += 1
            table_block(doc, rows)
            i = j
            continue

        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped.lstrip("#").strip()
            doc.add_heading(text, level=min(level, 4))
            i += 1
            continue

        if stripped in ("---", "***", "___"):
            p = doc.add_paragraph()
            pb = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "6")
            bottom.set(qn("w:color"), "D1D5DB")
            pb.append(bottom)
            p._p.get_or_add_pPr().append(pb)
            i += 1
            continue

        if stripped.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25)
            pb = OxmlElement("w:pBdr")
            left = OxmlElement("w:left")
            left.set(qn("w:val"), "single")
            left.set(qn("w:sz"), "18")
            left.set(qn("w:space"), "8")
            left.set(qn("w:color"), "00A651")
            pb.append(left)
            p._p.get_or_add_pPr().append(pb)
            add_runs(p, " ".join(x for x in buf if x))
            continue

        m = re.match(r"^(\s*)[-*] \[([ x])\] (.*)$", line)
        if m:
            p = doc.add_paragraph(style="List Bullet")
            add_runs(p, ("[done] " if m.group(2) == "x" else "[  ] ") + m.group(3))
            i += 1
            continue

        m = re.match(r"^(\s*)[-*] (.*)$", line)
        if m:
            p = doc.add_paragraph(style="List Bullet")
            if len(m.group(1)) >= 2:
                p.paragraph_format.left_indent = Inches(0.75)
            add_runs(p, m.group(2))
            i += 1
            continue

        m = re.match(r"^(\s*)(\d+)\. (.*)$", line)
        if m:
            p = doc.add_paragraph(style="List Number")
            add_runs(p, m.group(3))
            i += 1
            continue

        # paragraph: join the wrapped lines that follow
        buf = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and \
                not re.match(r"^\s*([-*#>|]|\d+\.|```)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        p = doc.add_paragraph()
        add_runs(p, " ".join(buf))


def page_number_footer(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("PlagSini EV handover   |   page ")
    r.font.size = Pt(8)
    r.font.color.rgb = MUTED
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    p._p.append(fld)


def main():
    doc = Document()

    st = doc.styles
    st["Normal"].font.name = "Calibri"
    st["Normal"].font.size = Pt(10.5)
    st["Normal"].paragraph_format.space_after = Pt(6)
    st["Normal"].paragraph_format.line_spacing = 1.12

    for name, size, colour in (("Heading 1", 20, GREEN), ("Heading 2", 14, INK),
                               ("Heading 3", 11.5, INK), ("Heading 4", 10.5, MUTED)):
        s = st[name]
        s.font.name = "Calibri"
        s.font.size = Pt(size)
        s.font.bold = True
        s.font.color.rgb = colour
        s.paragraph_format.space_before = Pt(14 if size > 13 else 10)
        s.paragraph_format.space_after = Pt(5)
        s.paragraph_format.keep_with_next = True

    for s in doc.sections:
        s.top_margin = s.bottom_margin = Inches(0.8)
        s.left_margin = s.right_margin = Inches(0.9)

    # ── title page ───────────────────────────────────────────────────
    if LOGO and os.path.exists(LOGO):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(LOGO, width=Inches(1.5))

    for text, size, bold, colour, space in (
        ("PlagSini EV", 30, True, GREEN, 2),
        ("Charge Your Journey", 12, False, MUTED, 22),
        ("Platform Handover", 24, True, INK, 4),
        ("Everything needed to run the charging platform", 12, False, MUTED, 30),
    ):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(space)
        r = p.add_run(text)
        r.font.size = Pt(size)
        r.bold = bold
        r.font.color.rgb = colour

    meta = doc.add_table(rows=0, cols=2)
    meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    for k, v in (("Prepared for", "Aina"),
                 ("Prepared by", "Aqid Ishak"),
                 ("Date", "26 November 2026"),
                 ("System", "charger.czeros.tech"),
                 ("Source", "ChargingPlatform/docs/handover")):
        cells = meta.add_row().cells
        a = cells[0].paragraphs[0]
        a.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        ra = a.add_run(k + "   ")
        ra.font.size = Pt(9.5)
        ra.font.color.rgb = MUTED
        rb = cells[1].paragraphs[0].add_run(v)
        rb.font.size = Pt(9.5)
        rb.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(36)
    r = p.add_run("This document contains no passwords, keys or tokens. "
                  "Section 8 says where each one lives.")
    r.font.size = Pt(9)
    r.italic = True
    r.font.color.rgb = MUTED

    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ── contents ─────────────────────────────────────────────────────
    doc.add_heading("Contents", level=1)
    p = doc.add_paragraph()
    r = p.add_run()
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-2" \\h \\z \\u'
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    hint = OxmlElement("w:t")
    hint.text = "Right-click here and choose Update Field to build the contents."
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for el in (fld, instr, sep, hint, end):
        r._r.append(el)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ── the nine documents ───────────────────────────────────────────
    seq_used = []
    for n, (fname, override) in enumerate(ORDER):
        md = io.open(os.path.join(SRC, fname), encoding="utf-8").read()
        md = re.sub(r"^# .*$", "", md, count=1, flags=re.M)
        # The web version's link table is navigation, useless on paper.
        if fname == "README.md":
            md = re.sub(r"\n\| \|\n\|---\|---\|\n(\|.*\n)+", "\n", md)
        doc.add_heading(override, level=1)
        render(doc, md, seq_used)
        if n < len(ORDER) - 1:
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    page_number_footer(doc.sections[0])
    doc.save(OUT)
    print("wrote", OUT)
    print("sequence table rendered:", len(seq_used))


main()
