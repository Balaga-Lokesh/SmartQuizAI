# test_smtp_debug.py  (replace your test_smtp.py with this temporarily)
from dotenv import load_dotenv
load_dotenv()   # force-load .env in current working directory

import os, smtplib
from email.message import EmailMessage

def masked(v):
    if not v:
        return "<MISSING>"
    if "@" in v:
        return v.split("@")[0][:3] + "..." + "@" + v.split("@")[1]
    return v[:3] + "..."

MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
MAIL_FROM = os.environ.get("MAIL_FROM")
MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
MAIL_STARTTLS = os.environ.get("MAIL_STARTTLS", "True").lower() in ("1", "true", "yes")
MAIL_SSL_TLS = os.environ.get("MAIL_SSL_TLS", "False").lower() in ("1", "true", "yes")

print("=== env seen by Python ===")
print("MAIL_USERNAME (masked):", masked(MAIL_USERNAME))
print("MAIL_FROM           :", masked(MAIL_FROM))
print("MAIL_SERVER         :", MAIL_SERVER)
print("MAIL_PORT           :", MAIL_PORT)
print("MAIL_STARTTLS       :", MAIL_STARTTLS)
print("MAIL_SSL_TLS        :", MAIL_SSL_TLS)
print("==========================")

if not (MAIL_USERNAME and MAIL_PASSWORD and MAIL_FROM):
    print("SMTP test: FAILED — missing one of MAIL_USERNAME / MAIL_PASSWORD / MAIL_FROM")
    raise SystemExit(1)

msg = EmailMessage()
msg["From"] = MAIL_FROM
msg["To"] = MAIL_FROM
msg["Subject"] = "SMTP debug test"
msg.set_content("If you see this, SMTP config is OK.")

try:
    if MAIL_SSL_TLS:
        import ssl
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT, context=context, timeout=20) as smtp:
            smtp.login(MAIL_USERNAME, MAIL_PASSWORD)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=20) as smtp:
            if MAIL_STARTTLS:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
            smtp.login(MAIL_USERNAME, MAIL_PASSWORD)
            smtp.send_message(msg)
    print("SMTP test: SUCCESS — message sent to", MAIL_FROM)
except Exception as e:
    print("SMTP test: FAILED —", repr(e))
