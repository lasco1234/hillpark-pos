from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, Flowable, Image as RLImage,
)
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing


COMPANY = {
    'name': 'HILLPARK TECHNOLOGIES',
    'legal': 'Hillpark Technologies Ltd',
    'tagline': 'Laptops · Desktops · Accessories · Repairs',
    'phone': '0657 199 181  /  0758 537 328',
}

# Theme colors (same as before)
PRIMARY = colors.HexColor('#647688')
PRIMARY_DARK = colors.HexColor('#4a5a68')
LIGHT_BG = colors.HexColor('#F5F7FA')
GREEN_TOTAL = colors.HexColor('#C6EFCE')


def _signature_path():
    """Resolve signature image from static / staticfiles / media."""
    base = Path(settings.BASE_DIR)
    candidates = [
        # Project source static
        base / 'static' / 'invoices' / 'signature.png',
        base / 'static' / 'invoices' / 'signature.jpg',
        # Collected static (your path)
        base / 'staticfiles' / 'invoices' / 'signature.png',
        base / 'staticfiles' / 'invoices' / 'signature.jpg',
        # Media
        base / 'media' / 'invoices' / 'signature.png',
        base / 'media' / 'invoices' / 'signature.jpg',
    ]
    if getattr(settings, 'STATIC_ROOT', None):
        candidates.append(Path(settings.STATIC_ROOT) / 'invoices' / 'signature.png')
        candidates.append(Path(settings.STATIC_ROOT) / 'invoices' / 'signature.jpg')
    if getattr(settings, 'MEDIA_ROOT', None):
        candidates.append(Path(settings.MEDIA_ROOT) / 'invoices' / 'signature.png')

    for p in candidates:
        if p.exists():
            return str(p)
    return None


def money(v):
    try:
        return f"{Decimal(str(v)):,.0f}"
    except Exception:
        return "0"


class QRFlowable(Flowable):
    def __init__(self, data, size=26 * mm):
        Flowable.__init__(self)
        self.data = data
        self.size = size
        self.width = size
        self.height = size

    def draw(self):
        widget = qr.QrCodeWidget(self.data)
        bounds = widget.getBounds()
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1]
        d = Drawing(self.size, self.size, transform=[
            self.size / w, 0, 0, self.size / h, 0, 0
        ])
        d.add(widget)
        d.drawOn(self.canv, 0, 0)


def generate_invoice_pdf(invoice):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=12 * mm, bottomMargin=14 * mm
    )
    styles = getSampleStyleSheet()
    story = []

    company_name = ParagraphStyle(
        'CN', parent=styles['Normal'], fontSize=15, fontName='Helvetica-Bold',
        textColor=PRIMARY_DARK, spaceAfter=1
    )
    tagline = ParagraphStyle(
        'TG', parent=styles['Normal'], fontSize=8, textColor=PRIMARY
    )
    doc_title = ParagraphStyle(
        'DT', parent=styles['Normal'], fontSize=13, fontName='Helvetica-Bold',
        textColor=PRIMARY, alignment=TA_RIGHT
    )
    label = ParagraphStyle(
        'LB', parent=styles['Normal'], fontSize=8,
        textColor=PRIMARY, fontName='Helvetica-Bold'
    )
    body = ParagraphStyle('BD', parent=styles['Normal'], fontSize=9)
    small = ParagraphStyle('SM', parent=styles['Normal'], fontSize=8)
    right = ParagraphStyle('RT', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)
    center = ParagraphStyle(
        'CT', parent=styles['Normal'], fontSize=7.5,
        alignment=TA_CENTER, textColor=colors.HexColor('#555555')
    )

    is_delivery = invoice.doc_type == 'delivery'
    is_invoice = invoice.doc_type == 'invoice'

    # ── HEADER ─────────────────────────────────────────────────
    header_data = [
        [
            Paragraph(f"<b>{COMPANY['name']}</b>", company_name),
            Paragraph(f"<b>{invoice.doc_title.upper()}</b>", doc_title),
        ],
        [
            Paragraph(COMPANY['tagline'], tagline),
            Paragraph(f"<b>{invoice.number}</b>", right),
        ],
        [
            Paragraph(f"<b>Tel:</b> {COMPANY['phone']}", small),
            Paragraph(f"<b>Date:</b> {invoice.issue_date.strftime('%d %b %Y')}", right),
        ],
        [
            Paragraph(
                f"<i>{COMPANY['legal']}</i>",
                ParagraphStyle('LG', parent=small, textColor=PRIMARY, fontSize=7)
            ),
            Paragraph("", right),
        ],
    ]
    header = Table(header_data, colWidths=[112 * mm, 70 * mm])
    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    story.append(header)
    story.append(Spacer(1, 3))
    story.append(HRFlowable(width="100%", thickness=2.5, color=PRIMARY))
    story.append(Spacer(1, 2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=PRIMARY_DARK))
    story.append(Spacer(1, 10))

    # ── BILL TO / DELIVER TO ───────────────────────────────────
    bill_left = [
        Paragraph("DELIVER TO" if is_delivery else "BILL TO", label),
        Spacer(1, 3),
        Paragraph(f"<b>{invoice.customer_name}</b>", body),
    ]
    if invoice.customer_phone:
        bill_left.append(Paragraph(f"Phone: {invoice.customer_phone}", small))
    if invoice.customer_email:
        bill_left.append(Paragraph(f"Email: {invoice.customer_email}", small))
    if invoice.customer_address:
        bill_left.append(Paragraph(invoice.customer_address.replace('\n', '<br/>'), small))
    if invoice.customer_tin:
        bill_left.append(Paragraph(f"TIN: {invoice.customer_tin}", small))

    meta_lines = []
    if invoice.due_date and not is_delivery:
        meta_lines.append(
            Paragraph(f"<b>Due date:</b> {invoice.due_date.strftime('%d %b %Y')}", small)
        )
    if invoice.delivery_date:
        meta_lines.append(
            Paragraph(f"<b>Delivery date:</b> {invoice.delivery_date.strftime('%d %b %Y')}", small)
        )
    if invoice.reference:
        meta_lines.append(Paragraph(f"<b>Reference:</b> {invoice.reference}", small))
    meta_lines.append(Paragraph(f"<b>Status:</b> {invoice.get_status_display()}", small))
    if is_invoice and getattr(invoice, 'bank_account', None):
        meta_lines.append(Spacer(1, 4))
        meta_lines.append(Paragraph("<b>BANK ACCOUNT</b>", label))
        meta_lines.append(Paragraph(f"<b>{invoice.bank_account}</b>", body))

    bill_table = Table([[bill_left, meta_lines]], colWidths=[112 * mm, 70 * mm])
    bill_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('BOX', (1, 0), (1, 0), 0.5, colors.HexColor('#E0E0E0')),
        ('BACKGROUND', (1, 0), (1, 0), LIGHT_BG),
        ('LEFTPADDING', (1, 0), (1, 0), 8),
        ('RIGHTPADDING', (1, 0), (1, 0), 8),
        ('TOPPADDING', (1, 0), (1, 0), 6),
        ('BOTTOMPADDING', (1, 0), (1, 0), 6),
    ]))
    story.append(bill_table)
    story.append(Spacer(1, 12))

    # ── LINE ITEMS ─────────────────────────────────────────────
    if is_delivery:
        table_data = [['#', 'Description', 'Qty']]
        for i, item in enumerate(invoice.items.all(), 1):
            table_data.append([str(i), item.description, str(item.quantity)])
        total_qty = sum((it.quantity for it in invoice.items.all()), 0)
        table_data.append(['', 'TOTAL QUANTITY', str(total_qty)])
        col_widths = [12 * mm, 145 * mm, 25 * mm]
        extra_align = [('ALIGN', (2, 1), (2, -1), 'CENTER')]
    else:
        table_data = [['#', 'Description', 'Qty', 'Unit Price', 'Amount']]
        for i, item in enumerate(invoice.items.all(), 1):
            table_data.append([
                str(i), item.description, str(item.quantity),
                money(item.unit_price), money(item.line_total),
            ])
        col_widths = [12 * mm, 90 * mm, 20 * mm, 30 * mm, 30 * mm]
        extra_align = [('ALIGN', (2, 1), (-1, -1), 'RIGHT')]

    t = Table(table_data, colWidths=col_widths)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -2 if is_delivery else -1), 0.4, colors.HexColor('#CFD8DC')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2 if is_delivery else -1),
         [colors.white, LIGHT_BG]),
    ] + extra_align
    if is_delivery:
        style_cmds += [
            ('BACKGROUND', (0, -1), (-1, -1), GREEN_TOTAL),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 1, PRIMARY),
        ]
    t.setStyle(TableStyle(style_cmds))
    story.append(t)
    story.append(Spacer(1, 10))

    # ── TOTALS (not delivery) ──────────────────────────────────
    if not is_delivery:
        totals = [['Subtotal', f"{money(invoice.subtotal)} TZS"]]
        if invoice.tax_percent and invoice.tax_percent > 0:
            totals.append([f"Tax ({invoice.tax_percent}%)", f"{money(invoice.tax_amount)} TZS"])
        if invoice.discount and invoice.discount > 0:
            totals.append(['Discount', f"-{money(invoice.discount)} TZS"])
        totals.append(['TOTAL', f"{money(invoice.total)} TZS"])
        if is_invoice and invoice.amount_paid:
            totals.append(['Amount paid', f"{money(invoice.amount_paid)} TZS"])
            totals.append(['Balance due', f"{money(invoice.balance_due)} TZS"])

        tot_table = Table(totals, colWidths=[42 * mm, 42 * mm])
        tot_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 11),
            ('BACKGROUND', (0, -1), (-1, -1), PRIMARY),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        wrap = Table([[None, tot_table]], colWidths=[98 * mm, 84 * mm])
        wrap.setStyle(TableStyle([('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        story.append(wrap)

        if is_invoice and getattr(invoice, 'bank_account', None):
            story.append(Spacer(1, 8))
            bank_box = Table([
                [Paragraph(
                    f"<b>Please pay to account:</b>  {invoice.bank_account}",
                    ParagraphStyle('BK', parent=body, fontSize=9)
                )]
            ], colWidths=[182 * mm])
            bank_box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF8E1')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#FFC107')),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ]))
            story.append(bank_box)

    # ── NOTES ──────────────────────────────────────────────────
    if invoice.notes:
        story.append(Spacer(1, 10))
        story.append(Paragraph("NOTES", label))
        story.append(Paragraph(invoice.notes.replace('\n', '<br/>'), small))

    if not is_delivery and invoice.terms:
        story.append(Spacer(1, 6))
        story.append(Paragraph("TERMS & CONDITIONS", label))
        story.append(Paragraph(invoice.terms.replace('\n', '<br/>'), small))

    # ── SIGNATURE BLOCK ────────────────────────────────────────
    # Layout: "For Hillpark Computers" → handwritten sign image → line → "Authorized Signature"
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor('#B0BEC5')))
    story.append(Spacer(1, 10))

    signed_by = ""
    if invoice.created_by:
        signed_by = str(invoice.created_by.get_full_name() or invoice.created_by)
    issued_str = invoice.created_at.strftime('%d %b %Y %H:%M')

    sig_path = _signature_path()
    sig_image = None
    if sig_path:
        # Width ~45mm, height proportional
        sig_image = RLImage(sig_path, width=45 * mm, height=28 * mm, kind='proportional')

    if is_delivery:
        left_parts = [Paragraph("<b>For Hillpark Computers</b>", body), Spacer(1, 4)]
        if sig_image:
            left_parts.append(sig_image)
            left_parts.append(Spacer(1, 2))
        else:
            left_parts.append(Spacer(1, 18))
        left_parts += [
            Paragraph("____________________________", small),
            Paragraph("Authorized Signature (System)", small),
            Paragraph(f"Issued by: {signed_by or 'System'}", small),
            Paragraph(f"Doc: {invoice.number}", small),
            Paragraph(f"Generated: {issued_str}", small),
        ]
        right_parts = [
            Paragraph("<b>Goods received by</b>", body),
            Spacer(1, 8),
            Paragraph("Name: _______________________________", small),
            Spacer(1, 6),
            Paragraph("Sign: _______________________________", small),
            Spacer(1, 6),
            Paragraph("Date: _______________________________", small),
            Spacer(1, 6),
            Paragraph("ID / Phone: _________________________", small),
        ]
        sig = Table([[left_parts, right_parts]], colWidths=[95 * mm, 87 * mm])
    else:
        left_parts = [
            Paragraph("<b>For Hillpark Technologies</b>", body),
            Paragraph(f"<i>{COMPANY['legal']}</i>", small),
            Spacer(1, 4),
        ]
        if sig_image:
            left_parts.append(sig_image)
            left_parts.append(Spacer(1, 2))
        else:
            left_parts.append(Spacer(1, 18))
        left_parts += [
            Paragraph("____________________________", small),
            Paragraph("Authorized Signature (System)", small),
            Paragraph(f"Issued by: <b>{signed_by or 'System'}</b>", small),
            Paragraph(f"Document: <b>{invoice.number}</b>", small),
            Paragraph(f"Generated: {issued_str}", small),
            Spacer(1, 3),
            Paragraph(
                "Valid without physical stamp or wet-ink signature.",
                ParagraphStyle('VX', parent=small, textColor=PRIMARY, fontSize=7)
            ),
        ]
        qr_block = [
            QRFlowable("hillpark technologies ltd", size=26 * mm),
            Spacer(1, 3),
            Paragraph("Scan to verify", ParagraphStyle(
                'QR', parent=center, fontSize=7, textColor=PRIMARY
            )),
            Paragraph("Hillpark Technologies Ltd", ParagraphStyle(
                'QR2', parent=center, fontSize=6.5, textColor=PRIMARY_DARK
            )),
        ]
        sig = Table([[left_parts, qr_block]], colWidths=[130 * mm, 52 * mm])

    sig.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
    ]))
    story.append(sig)

    # ── FOOTER ─────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CFD8DC')))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"{COMPANY['name']}  ·  {COMPANY['legal']}  ·  {COMPANY['phone']}  ·  "
        f"Electronically generated document — authentic without physical seal.",
        center
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer