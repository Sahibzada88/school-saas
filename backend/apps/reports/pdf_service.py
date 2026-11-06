"""PDF generation with ReportLab, fully in memory. Nothing is stored; every request builds its own document.

Text note: the built-in Helvetica font covers Latin text. Names in other scripts (e.g. Urdu) need a bundled TTF font."""
import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

MAX_PDF_ROWS = 500
_styles = getSampleStyleSheet()
TITLE = ParagraphStyle("t", parent=_styles["Title"], fontSize=16, spaceAfter=2)
SUB = ParagraphStyle("s", parent=_styles["Normal"], fontSize=10, textColor=colors.grey, alignment=1, spaceAfter=8)
BODY = ParagraphStyle("b", parent=_styles["Normal"], fontSize=10, leading=14)
CENTER = ParagraphStyle("c", parent=BODY, alignment=1, fontSize=12, leading=20)


def _text(value) -> str:
    return "" if value is None else str(value)


def _table(header, rows, widths=None, right_cols=(), font=9):
    data = [[_text(c) for c in header]] + [[_text(c) for c in row] for row in rows]
    table = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), font),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9ca3af")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    style += [("ALIGN", (c, 0), (c, -1), "RIGHT") for c in right_cols]
    table.setStyle(TableStyle(style))
    return table


def _kv(rows, widths=(45 * mm, 120 * mm)):
    table = Table([[_text(k), _text(v)] for k, v in rows], colWidths=widths)
    table.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 10), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2)]))
    return table


def build_pdf(*, school_name: str, title: str, subtitle: str = "", blocks: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=title)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 10 * mm, f"Generated {datetime.now():%Y-%m-%d %H:%M}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()

    story = [Paragraph(escape(school_name), TITLE), Paragraph(escape(title) + (f" &middot; {escape(subtitle)}" if subtitle else ""), SUB), Spacer(1, 4)]
    story.extend(blocks)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def _signatures(*labels):
    table = Table([[l for l in labels]], colWidths=[55 * mm] * len(labels))
    table.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black), ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    return [Spacer(1, 28), table]


CARD_W, CARD_H = 85.6 * mm, 54 * mm  # CR80 ID card


def _fit(text, limit):
    text = _text(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _draw_id_card(c, x, y, card: dict) -> None:
    """One ID card with its bottom-left corner at (x, y). card: school, name, number, class_label, session, photo (bytes|None)."""
    c.saveState()
    c.translate(x, y)
    c.setStrokeColor(colors.HexColor("#9ca3af"))
    c.setLineWidth(0.6)
    c.roundRect(0, 0, CARD_W, CARD_H, 3 * mm, stroke=1, fill=0)
    c.setFillColor(colors.HexColor("#1e3a8a"))
    c.roundRect(0, CARD_H - 11 * mm, CARD_W, 11 * mm, 3 * mm, stroke=0, fill=1)
    c.rect(0, CARD_H - 11 * mm, CARD_W, 5 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(CARD_W / 2, CARD_H - 6.5 * mm, _fit(card["school"], 38))
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(CARD_W / 2, CARD_H - 9.6 * mm, "STUDENT IDENTITY CARD")
    photo_x, photo_y, photo_w, photo_h = 4 * mm, 6 * mm, 24 * mm, 30 * mm
    c.setStrokeColor(colors.HexColor("#9ca3af"))
    c.rect(photo_x, photo_y, photo_w, photo_h, stroke=1, fill=0)
    if card.get("photo"):
        try:
            c.drawImage(ImageReader(io.BytesIO(card["photo"])), photo_x, photo_y, photo_w, photo_h, preserveAspectRatio=True, anchor="c", mask="auto")
        except Exception:  # a corrupt image must not break the whole sheet
            pass
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(32 * mm, 31 * mm, _fit(card["name"], 24))
    c.setFont("Helvetica", 7.5)
    for line_no, (label, value) in enumerate((("ID", card["number"]), ("Class", card["class_label"]), ("Session", card["session"]))):
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(32 * mm, (25 - line_no * 5) * mm, f"{label}:")
        c.setFont("Helvetica", 7.5)
        c.drawString(44 * mm, (25 - line_no * 5) * mm, _fit(value, 20))
    c.setFont("Helvetica-Oblique", 5.5)
    c.setFillColor(colors.grey)
    c.drawCentredString(CARD_W / 2, 2.2 * mm, "If found, please return to the school office.")
    c.restoreState()


class PDFService:
    @staticmethod
    def generate_result_pdf(card) -> bytes:
        b = card.breakdown or {}
        lines = [
            [l["subject"], l["total"], "Absent" if l["is_absent"] else l["obtained"], l.get("grade", ""), "Pass" if l["is_pass"] else "Fail"]
            for l in b.get("lines", [])
        ]
        blocks = [
            _kv([("Student", card.student.full_name), ("Student no.", card.student.student_number),
                 ("Class / Section", f"{card.enrollment.school_class.name} - {card.enrollment.section.name}"),
                 ("Roll no.", card.enrollment.roll_number or "-"), ("Session", card.exam.session.name)]),
            Spacer(1, 8),
            _table(["Subject", "Total", "Obtained", "Grade", "Result"], lines, widths=[70 * mm, 25 * mm, 30 * mm, 22 * mm, 25 * mm], right_cols=(1, 2)),
            Spacer(1, 8),
            _kv([("Total marks", f"{card.obtained_marks} / {card.total_marks}"), ("Percentage", f"{card.percentage}%"),
                 ("Grade / GPA", f"{card.grade} / {card.gpa}"), ("Position", f"{card.position_section or '-'} in section, {card.position_class or '-'} in class"),
                 ("Result", card.result_status)]),
        ]
        if card.teacher_remarks:
            blocks += [Spacer(1, 6), Paragraph("Teacher's remarks: " + escape(card.teacher_remarks), BODY)]
        if card.principal_remarks:
            blocks += [Spacer(1, 4), Paragraph("Principal's remarks: " + escape(card.principal_remarks), BODY)]
        blocks += _signatures("Class teacher", "Principal")
        return build_pdf(school_name=card.school.name, title="Report Card", subtitle=card.exam.name, blocks=blocks)

    @staticmethod
    def generate_transcript_pdf(student, school_name: str, cards) -> bytes:
        blocks = [_kv([("Student", student.full_name), ("Student no.", student.student_number)]), Spacer(1, 8)]
        rows = [[c.exam.session.name, c.exam.name, f"{c.obtained_marks}/{c.total_marks}", f"{c.percentage}%", c.grade, c.result_status] for c in cards]
        blocks.append(_table(["Session", "Exam", "Marks", "Percentage", "Grade", "Result"], rows, widths=[28 * mm, 55 * mm, 28 * mm, 25 * mm, 18 * mm, 20 * mm], right_cols=(2, 3)))
        blocks += _signatures("Examination controller", "Principal")
        return build_pdf(school_name=school_name, title="Academic Transcript", blocks=blocks)

    @staticmethod
    def generate_fee_receipt_pdf(payment) -> bytes:
        inv = payment.invoice
        rows = [("Receipt no.", payment.receipt_number), ("Date", payment.paid_on), ("Student", f"{inv.student.full_name} ({inv.student.student_number})"),
                ("Invoice", f"{inv.invoice_number} - {inv.period_label}"), ("Method", payment.method + (f" ({payment.reference})" if payment.reference else "")),
                ("Amount received", payment.amount), ("Invoice total", inv.total), ("Paid so far", inv.paid_total), ("Balance", inv.balance)]
        if payment.status == "REVERSED":
            rows.insert(0, ("STATUS", f"REVERSED - {payment.reversal_reason}"))
        blocks = [_kv(rows)] + _signatures("Received by", "Parent / guardian")
        return build_pdf(school_name=inv.school.name, title="Fee Receipt", subtitle=payment.receipt_number, blocks=blocks)

    @staticmethod
    def generate_invoice_pdf(invoice) -> bytes:
        blocks = [
            _kv([("Invoice", invoice.invoice_number), ("Student", f"{invoice.student.full_name} ({invoice.student.student_number})"),
                 ("Period", invoice.period_label), ("Issued / Due", f"{invoice.issue_date} / {invoice.due_date}"), ("Status", invoice.status)]),
            Spacer(1, 8),
            _table(["Description", "Amount"], [[i.description, i.amount] for i in invoice.items.all()], widths=[120 * mm, 40 * mm], right_cols=(1,)),
        ]
        extra = [[f"Discount: {d.reason}", f"-{d.amount}"] for d in invoice.discounts.all()] + [[f"Fine: {f.reason}", f.amount] for f in invoice.fines.all()]
        if extra:
            blocks += [Spacer(1, 4), _table(["Adjustment", "Amount"], extra, widths=[120 * mm, 40 * mm], right_cols=(1,))]
        blocks += [Spacer(1, 8), _kv([("Total", invoice.total), ("Paid", invoice.paid_total), ("Balance due", invoice.balance)])]
        pays = [[p.receipt_number, p.paid_on, p.method, p.amount, p.status] for p in invoice.payments.all()]
        if pays:
            blocks += [Spacer(1, 8), _table(["Receipt", "Date", "Method", "Amount", "Status"], pays, right_cols=(3,))]
        return build_pdf(school_name=invoice.school.name, title="Fee Invoice", subtitle=invoice.invoice_number, blocks=blocks)

    @staticmethod
    def generate_attendance_report_pdf(school_name: str, section_label: str, report: dict) -> bytes:
        rows = [[s["student_number"], s["student_name"], s["present"], s["absent"], s["late"], s["leave"], "-" if s["percentage"] is None else f"{s['percentage']}%"] for s in report["students"]]
        blocks = [_table(["No.", "Student", "Present", "Absent", "Late", "Leave", "%"], rows, widths=[24 * mm, 56 * mm, 20 * mm, 20 * mm, 16 * mm, 16 * mm, 18 * mm], right_cols=(2, 3, 4, 5, 6))]
        return build_pdf(school_name=school_name, title="Attendance Report", subtitle=f"{section_label} - {report['month']}", blocks=blocks)

    @staticmethod
    def generate_outstanding_fees_pdf(school_name: str, rows: list[dict], total) -> bytes:
        data = [[r["invoice_number"], r["student_name"], r["class_name"], r["due_date"], r["balance"], r["days_overdue"]] for r in rows]
        blocks = [_table(["Invoice", "Student", "Class", "Due", "Balance", "Days late"], data, widths=[28 * mm, 52 * mm, 28 * mm, 24 * mm, 24 * mm, 18 * mm], right_cols=(4, 5)),
                  Spacer(1, 8), _kv([("Total outstanding", total)])]
        return build_pdf(school_name=school_name, title="Outstanding Fees", blocks=blocks)

    @staticmethod
    def generate_student_list_pdf(school_name: str, rows: list[list]) -> bytes:
        blocks = [_table(["No.", "Name", "Gender", "Class", "Status", "Phone"], rows, widths=[26 * mm, 52 * mm, 18 * mm, 30 * mm, 24 * mm, 26 * mm])]
        return build_pdf(school_name=school_name, title="Student List", blocks=blocks)

    @staticmethod
    def generate_id_cards_pdf(cards: list[dict], *, sheet: bool) -> bytes:
        """sheet=False: one card per page at card size (for printing on a card printer). sheet=True: A4 sheet, 2 x 5 cards."""
        buffer = io.BytesIO()
        if not sheet:
            c = pdf_canvas.Canvas(buffer, pagesize=(CARD_W, CARD_H))
            for card in cards:
                _draw_id_card(c, 0, 0, card)
                c.showPage()
        else:
            c = pdf_canvas.Canvas(buffer, pagesize=A4)
            margin_x, margin_y, gap = 15 * mm, 12 * mm, 4 * mm
            for index, card in enumerate(cards):
                slot = index % 10
                if index and slot == 0:
                    c.showPage()
                col, row = slot % 2, slot // 2
                x = margin_x + col * (CARD_W + gap)
                y = A4[1] - margin_y - (row + 1) * CARD_H - row * gap
                _draw_id_card(c, x, y, card)
        c.save()
        return buffer.getvalue()

    @staticmethod
    def generate_certificate_pdf(student, school_name: str, class_label: str, session_name: str) -> bytes:
        text = (f"This is to certify that <b>{escape(student.full_name)}</b> (student no. {escape(student.student_number)}) "
                f"is a bonafide student of this school, enrolled in <b>{escape(class_label)}</b> for the academic session <b>{escape(session_name)}</b>.")
        blocks = [Spacer(1, 40), Paragraph(text, CENTER)] + _signatures("Date", "Principal")
        return build_pdf(school_name=school_name, title="Student Certificate", blocks=blocks)
