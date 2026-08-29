import threading
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_email_notification(subject, message, recipient_list, html_message=None, from_email=None):
    """Send plain/HTML email synchronously (blocking). Returns count sent."""
    recipients = [e for e in recipient_list if e and "@" in e]
    if not recipients:
        logger.warning("No valid email recipients for: %s", subject)
        return 0

    from_email = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
    try:
        if html_message:
            email = EmailMultiAlternatives(
                subject=subject,
                body=strip_tags(message),
                from_email=from_email,
                to=recipients,
            )
            email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)
            return len(recipients)
        return send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception as e:
        logger.exception("Email send failed (%s): %s", subject, e)
        return 0


def send_email_async(subject, message, recipient_list, html_message=None, from_email=None):
    """
    Send email in a background daemon thread so the request returns immediately.
    Fire-and-forget: acceptable for a single-server POS.
    """
    def _send():
        send_email_notification(subject, message, recipient_list, html_message, from_email)

    threading.Thread(target=_send, daemon=True).start()