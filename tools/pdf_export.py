"""
PDF export (spec section 16).

Uses fpdf2 (pure Python, no system libraries like Cairo/Pango needed --
unlike weasyprint) so this works in restricted environments too. It's a
lightweight structural renderer of the report's own markdown -- headers,
bullets, and code blocks get distinct styling -- not a full CommonMark
renderer, which is the right scope for a generated research report.
"""
from __future__ import annotations
import re
from fpdf import FPDF


class ReportPDF(FPDF):
    def header(self):
        pass  # no running header -- the report's own title serves that role

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _safe(text: str) -> str:
    """fpdf2's core fonts only support latin-1. Normalize common Unicode
    punctuation to ASCII first (so em-dashes etc. render as '-' rather than
    '?'), then replace anything still outside latin-1 rather than crashing."""
    text = (
        text.replace("\u2014", "-").replace("\u2013", "-")
        .replace("\u2018", "'").replace("\u2019", "'")
        .replace("\u201c", '"').replace("\u201d", '"')
        .replace("\u2026", "...")
    )
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _add_evidence_visuals(pdf: ReportPDF, evidence: list[dict]) -> None:
    correlations = []
    trends = []
    for item in evidence:
        if item.get("kind") != "dataset_stat":
            continue
        payload = item.get("payload") or {}
        if isinstance(payload.get("r"), (int, float)) and payload.get("pair"):
            correlations.append((payload["pair"].replace("~", " / "), float(payload["r"])))
        change = payload.get("total_pct_change_first_to_last")
        if payload.get("trend_metric") and isinstance(change, (int, float)):
            trends.append((str(payload["trend_metric"]), float(change)))

    if not correlations and not trends:
        return

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(25, 35, 45)
    pdf.cell(0, 10, "Evidence Visualizations", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 100, 110)
    pdf.multi_cell(0, 5, "Charts summarize observed associations and trends; they do not establish causation.")

    def draw_rows(title: str, rows: list[tuple[str, float]], kind: str) -> None:
        if not rows:
            return
        if pdf.get_y() > pdf.h - 42:
            pdf.add_page()
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(35, 45, 55)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        chart_x = pdf.l_margin + 82
        chart_width = 64
        for label, value in rows:
            if pdf.get_y() > pdf.h - 25:
                pdf.add_page()
            y = pdf.get_y()
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(55, 65, 75)
            pdf.set_xy(pdf.l_margin, y)
            pdf.cell(78, 8, _safe(label[:42]))
            pdf.set_draw_color(215, 220, 225)
            if kind == "correlation":
                center = chart_x + chart_width / 2
                pdf.line(center, y + 4, center, y + 7)
                bar_width = min(abs(value), 1.0) * chart_width / 2
                bar_x = center if value >= 0 else center - bar_width
                value_label = f"r = {value:+.3f}"
            else:
                scale = max((abs(number) for _, number in rows), default=1) or 1
                bar_width = abs(value) / scale * chart_width
                bar_x = chart_x
                value_label = f"{value:+.1f}%"
            pdf.set_fill_color(*(49, 130, 99) if value >= 0 else (195, 91, 68))
            pdf.rect(bar_x, y + 2, max(bar_width, 0.5), 4, style="F")
            pdf.set_xy(chart_x + chart_width + 3, y)
            pdf.cell(0, 8, value_label)
            pdf.set_y(y + 9)

    correlations.sort(key=lambda item: abs(item[1]), reverse=True)
    trends.sort(key=lambda item: abs(item[1]), reverse=True)
    draw_rows("Strongest measured correlations", correlations[:8], "correlation")
    draw_rows("Measured time trends", trends[:8], "trend")


def markdown_to_pdf_bytes(markdown: str, evidence: list[dict] | None = None) -> bytes:
    pdf = ReportPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    in_code_block = False

    def reset_x(extra: int = 0) -> None:
        # multi_cell leaves the cursor at the right edge rather than the left
        # margin by default -- without this, x drifts right across calls
        # until a later call has ~0 width left and raises FPDFException.
        pdf.set_x(pdf.l_margin + extra)

    for raw_line in markdown.split("\n"):
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            pdf.set_font("Courier", "", 8)
            pdf.set_text_color(80, 80, 80)
            reset_x()
            pdf.multi_cell(0, 4, _safe(line) or " ")
            continue

        if not line.strip():
            pdf.ln(2)
            continue

        # Strip markdown emphasis markers; fpdf2's core fonts don't render markdown syntax.
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        clean = re.sub(r"`(.+?)`", r"\1", clean)
        clean = _safe(clean)

        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 20)
            pdf.set_text_color(20, 20, 20)
            pdf.ln(2)
            reset_x()
            pdf.multi_cell(0, 10, clean[2:])
            pdf.ln(2)
        elif line.startswith("## "):
            pdf.set_font("Helvetica", "B", 15)
            pdf.set_text_color(30, 30, 30)
            pdf.ln(4)
            reset_x()
            pdf.multi_cell(0, 8, clean[3:])
            pdf.set_draw_color(220, 220, 220)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 170, pdf.get_y())
            pdf.ln(3)
        elif line.startswith("### "):
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(40, 40, 40)
            pdf.ln(3)
            reset_x()
            pdf.multi_cell(0, 7, clean[4:])
        elif line.strip().startswith("- "):
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(50, 50, 50)
            indent = len(raw_line) - len(raw_line.lstrip())
            reset_x(indent)
            pdf.multi_cell(0, 6, f"- {clean.strip()[2:]}")
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(50, 50, 50)
            reset_x()
            pdf.multi_cell(0, 6, clean)

    _add_evidence_visuals(pdf, evidence or [])
    return bytes(pdf.output())
