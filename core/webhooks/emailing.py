from django.conf import settings
from django.core.mail import EmailMessage


def send_simple_email(*, subject: str, body: str, to_email: str):
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@localhost"
    msg = EmailMessage(subject=subject, body=body, from_email=from_email, to=[to_email])
    msg.send(fail_silently=False)
