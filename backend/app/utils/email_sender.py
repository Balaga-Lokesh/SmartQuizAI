"""
app.utils.email_sender - patched for SmartQuiz AI

Improvements:
- Clear logging of success/failure.
- Raises exceptions for fatal SMTP errors (so background tasks log).
- If SMTP is not fully configured (SMTP_USER/SMTP_PASS missing), falls back to:
  - printing OTP to console
  - appending OTP to otp_logs.txt in project root for developer convenience
- Uses smtplib with STARTTLS for Gmail-like servers.
- Simple send_email_otp(email, otp, subject) function expected by auth.py
"""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

MAIL_FROM = os.environ.get("MAIL_FROM") or os.environ.get("SMTP_USER")
MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
MAIL_STARTTLS = os.environ.get("MAIL_STARTTLS", "true").lower() in ("1", "true", "yes")
MAIL_SSL_TLS = os.environ.get("MAIL_SSL_TLS", "false").lower() in ("1", "true", "yes")
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")

OTP_LOGFILE = Path(__file__).resolve().parents[2] / "otp_logs.txt"  # project root by default

def _write_dev_log(email: str, otp: str):
    try:
        OTP_LOGFILE.parent.mkdir(parents=True, exist_ok=True)
        with open(str(OTP_LOGFILE), "a", encoding="utf-8") as fh:
            fh.write(f"{__import__('datetime').datetime.utcnow().isoformat()}\t{email}\t{otp}\n")
    except Exception as e:
        print("Failed to write OTP to otp_logs.txt:", e)

def send_email_otp(email: str, otp: str, subject: Optional[str] = None) -> None:
    """
    Send an OTP to the specified email.
    In development (no SMTP credentials), prints OTP and writes to otp_logs.txt.
    Raises exceptions for SMTP failures to make debugging easier.
    """
    subject = subject or "Your SmartQuiz OTP"
    body = f"Your SmartQuiz verification code is: {otp}\nThis code will expire in a few minutes."

    # If SMTP credentials are missing, fallback to dev behavior
    if not SMTP_USER or not SMTP_PASS:
        print(f"[DEV] No SMTP credentials configured. OTP for {email}: {otp}")
        _write_dev_log(email, otp)
        return

    # Prepare message
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = MAIL_FROM or SMTP_USER
    msg["To"] = email
    msg.set_content(body)

    # Connect and send
    try:
        if MAIL_SSL_TLS:
            # SSL/TLS connection (SMTPS)
            with smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        else:
            with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
                server.ehlo()
                if MAIL_STARTTLS:
                    server.starttls()
                    server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        print(f"[INFO] OTP email sent to {email}")
    except smtplib.SMTPAuthenticationError as e:
        # Credentials problem - log and re-raise for visibility
        print(f"[ERROR] SMTP authentication failed for {SMTP_USER}: {e}")
        raise
    except smtplib.SMTPException as e:
        print(f"[ERROR] SMTP exception when sending OTP to {email}: {e}")
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error when sending OTP to {email}: {e}")
        raise
