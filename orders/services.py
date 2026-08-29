from decimal import Decimal
from io import BytesIO
from urllib.parse import quote

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable


def money(v):
    try:
        return f"{Decimal(str(v)):,.0f}"
    except Exception:
        return str(v)


def build_order_text(order):
    """Plain text body for WhatsApp / email."""
    lines = [
        f"PURCHASE ORDER: {order.order_number}",
        f"Store: {order.store.name}",
        f"Date: {order.created_at.strftime('%d %b %Y %H:%M')}",
        f"Supplier: {order.supplier_name}",
        "",
        "ITEMS:",
        "-" * 40,
    ]
    for i, item in enumerate(order.items.all(), 1):
        tag = " [NEW]" if item.is_new_product else ""
        lines.append(
            f"{i}. {item.product_name}{tag}  x{item.quantity}  "
            f"@ {money(item.unit_price)} = {money(item.line_total)}"
        )
        if item.description:
            lines.append(f"   ({item.description})")
    lines += [
        "-" * 40,
        f"TOTAL: {money(order.total_amount)} TZS",
    ]
    if order.notes:
        lines += ["", f"Notes: {order.notes}"]
    lines += ["", "Please confirm availability and delivery time.", "Thank you."]
    return "\n".join(lines)


def whatsapp_url(order):
    """wa.me link with pre-filled message."""
    phone = (order.supplier_phone or "").strip().replace(" ", "").replace("+", "")
    if phone.startswith("0"):
        # Tanzania local → assume 255
        phone = "255" + phone[1:]
    text = build_order_text(order)
    return f"https://wa.me/{phone}?text={quote(text)}"


def send_order_email(order):
    """Send order by email. Returns (ok: bool, message: str)."""
    if not order.supplier_email:
        return False, "Supplier email is missing."

    subject = f"Purchase Order {order.order_number} — {order.store.name}"
    body = build_order_text(order)

    # Attach PDF
    pdf_buf = generate_order_pdf(order)

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        to=[order.supplier_email],
    )
    email.attach(f"{order.order_number}.pdf", pdf_buf.getvalue(), 'application/pdf')

    try:
        email.send(fail_silently=False)
        order.status = 'sent'
        order.sent_at = timezone.now()
        order.save(update_fields=['status', 'sent_at'])
        return True, f"Email sent to {order.supplier_email}"
    except Exception as e:
        return False, f"Email failed: {e}"


def generate_order_pdf(order):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle('T', parent=styles['Heading1'], fontSize=16, spaceAfter=4)
    sub = ParagraphStyle('S', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    normal = styles['Normal']
    story = []

    story.append(Paragraph("PURCHASE ORDER", title))
    story.append(Paragraph(f"{order.order_number}", styles['Heading2']))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#647688')))
    story.append(Spacer(1, 8))

    info = [
        f"<b>Store:</b> {order.store.name}",
        f"<b>Date:</b> {order.created_at.strftime('%d %b %Y %H:%M')}",
        f"<b>Status:</b> {order.get_status_display()}",
        f"<b>Supplier:</b> {order.supplier_name}",
        f"<b>Email:</b> {order.supplier_email or '—'}",
        f"<b>Phone:</b> {order.supplier_phone or '—'}",
    ]
    for line in info:
        story.append(Paragraph(line, normal))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Order Items</b>", styles['Heading3']))
    story.append(Spacer(1, 4))

    table_data = [['#', 'Item', 'Qty', 'Unit Price', 'Total']]
    for i, item in enumerate(order.items.all(), 1):
        name = item.product_name
        if item.is_new_product:
            name += " (NEW)"
        if item.description:
            name += f"\n{item.description}"
        table_data.append([
            str(i),
            name,
            str(item.quantity),
            money(item.unit_price),
            money(item.line_total),
        ])
    table_data.append(['', 'TOTAL', '', '', money(order.total_amount)])

    t = Table(table_data, colWidths=[12*mm, 90*mm, 20*mm, 35*mm, 35*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#647688')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#C6EFCE')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    if order.notes:
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Notes</b>", styles['Heading3']))
        story.append(Paragraph(order.notes.replace('\n', '<br/>'), normal))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "Please confirm availability, pricing and expected delivery date.",
        sub
    ))
    story.append(Paragraph("Thank you.", sub))

    doc.build(story)
    buffer.seek(0)
    return buffer