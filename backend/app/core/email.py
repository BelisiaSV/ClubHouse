import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("clubhouse.email")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@clubhouse.local")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


def send_email(to: str, subject: str, body: str) -> None:
    """Sends via SMTP when SMTP_HOST is configured. Otherwise logs the message so
    the flow is still testable/usable in dev without real mail credentials."""
    if not SMTP_HOST:
        logger.info("SMTP not configured; logging email instead of sending.\nTo: %s\nSubject: %s\n\n%s", to, subject, body)
        return

    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        if SMTP_USER and SMTP_PASSWORD:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(message)


def send_password_reset_email(to: str, raw_token: str) -> None:
    reset_link = f"{FRONTEND_URL}/reset-password?token={raw_token}"
    send_email(
        to=to,
        subject="ClubHouse — wachtwoord resetten",
        body=(
            "Je hebt een wachtwoordreset aangevraagd voor je ClubHouse-account.\n\n"
            f"Klik op onderstaande link om een nieuw wachtwoord in te stellen (verloopt over "
            f"30 minuten):\n{reset_link}\n\n"
            "Heb je dit niet aangevraagd? Dan kan je deze e-mail negeren."
        ),
    )
