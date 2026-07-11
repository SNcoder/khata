"""
Invite / password-reset emails — Gmail SMTP (App Password) ke through.

.env me set karo:
  SMTP_USER=you@gmail.com
  SMTP_PASSWORD=16-char App Password (Google Account > Security > App Passwords —
                 normal Gmail password kaam nahi karega, 2FA on hona zaroori hai)
  SMTP_FROM=you@gmail.com          (optional, SMTP_USER se default)
  APP_BASE_URL=http://localhost:5000  (production me apna domain daalo)

SMTP configure nahi hai to email bhejne ki jagah link console par print ho jaati
hai — local dev me bina Gmail setup ke bhi invite flow test ho sakta hai.
"""

import os
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM") or SMTP_USER
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000")


def invite_link(token):
    return f"{APP_BASE_URL.rstrip('/')}/?invite={token}"


def send_mail(to_email, subject, body_text):
    """True return karta hai agar bhej diya. SMTP configure nahi hai to
    console par print karke False return karta hai (dev fallback)."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[mailer] SMTP configure nahi hai — email manually bhejo:\n"
              f"  To: {to_email}\n  Subject: {subject}\n\n{body_text}\n")
        return False
    msg = MIMEText(body_text)
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [to_email], msg.as_string())
    return True


def send_invite_email(to_email, full_name, token, is_reset=False):
    """Invite ya password-reset email bhejta hai.
    Returns (sent: bool, link: str) — link hamesha return hota hai taaki
    email fail hone par bhi admin ko manually share karne ka fallback mile."""
    link = invite_link(token)
    name = full_name or to_email
    if is_reset:
        subject = "Site Khata — Password Reset"
        body = (
            f"Hi {name},\n\n"
            f"Aapke Site Khata account ka password reset karne ke liye admin ne request ki hai.\n"
            f"Naya password set karne ke liye is link par jao (48 ghante ke liye valid):\n{link}\n\n"
            f"Agar aapne ye request nahi ki, to is email ko ignore karo — password same rahega.\n"
        )
    else:
        subject = "Site Khata — Aapka Account Banaya Gaya Hai"
        body = (
            f"Hi {name},\n\n"
            f"Aapko Site Khata par ek account banaya gaya hai (login email: {to_email}).\n"
            f"Apna password set karke login karne ke liye is link par jao (48 ghante ke liye valid):\n{link}\n\n"
            f"Ye link kisi ke saath share mat karo.\n"
        )
    try:
        sent = send_mail(to_email, subject, body)
    except Exception as e:  # SMTP/network fail — user phir bhi ban jaaye, admin ko link mil jaaye
        print(f"[mailer] Email bhejne me error: {e}")
        sent = False
    return sent, link
