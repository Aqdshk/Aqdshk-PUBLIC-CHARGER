"""
Email service for sending OTP codes via Gmail SMTP.

Configuration via environment variables:
    SMTP_HOST       - SMTP server host (default: smtp.gmail.com)
    SMTP_PORT       - SMTP server port (default: 587)
    SMTP_EMAIL      - Sender email address
    SMTP_PASSWORD   - Sender email password or Gmail App Password
    SMTP_FROM_NAME  - Display name (default: PlagSini EV)

If SMTP_EMAIL is not set, OTPs are logged to console (dev mode).
"""

import logging
import os
import random
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "PlagSini EV")


def generate_otp(length: int = 6) -> str:
    """Generate a random numeric OTP code."""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])


def _build_otp_email(to_email: str, otp_code: str) -> MIMEMultipart:
    """Build the OTP verification email with HTML template."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"PlagSini - Your Verification Code: {otp_code}"
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_EMAIL}>"
    msg["To"] = to_email

    # Plain text fallback
    text = f"""
PlagSini EV Charging Platform

Your verification code is: {otp_code}

This code will expire in 5 minutes.
Do not share this code with anyone.

If you did not request this code, please ignore this email.
"""

    # HTML email
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#0A0A1A; font-family: Arial, Helvetica, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0A0A1A; padding:40px 20px;">
        <tr>
            <td align="center">
                <table width="480" cellpadding="0" cellspacing="0" style="background-color:#12192B; border-radius:16px; overflow:hidden; border:1px solid #1E2D42;">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #00FF88 0%, #00AA55 100%); padding:30px; text-align:center;">
                            <h1 style="color:#000; margin:0; font-size:24px; font-weight:800; letter-spacing:1px;">⚡ PlagSini</h1>
                            <p style="color:rgba(0,0,0,0.6); margin:5px 0 0; font-size:12px; letter-spacing:2px;">EV CHARGING PLATFORM</p>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding:40px 30px; text-align:center;">
                            <h2 style="color:#FFFFFF; margin:0 0 10px; font-size:20px;">Email Verification</h2>
                            <p style="color:#888888; font-size:14px; line-height:1.6; margin:0 0 30px;">
                                Enter the following code to verify your email address and complete your registration.
                            </p>

                            <!-- OTP Code Box -->
                            <div style="background:#0A0A1A; border:2px solid #00FF88; border-radius:12px; padding:20px; margin:0 auto; max-width:280px;">
                                <p style="color:#888; font-size:11px; text-transform:uppercase; letter-spacing:2px; margin:0 0 10px;">Verification Code</p>
                                <p style="color:#00FF88; font-size:36px; font-weight:800; letter-spacing:8px; margin:0;">{otp_code}</p>
                            </div>

                            <p style="color:#666666; font-size:12px; margin:25px 0 0;">
                                ⏱️ This code expires in <strong style="color:#FF8800;">5 minutes</strong>
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding:20px 30px 30px; border-top:1px solid #1E2D42; text-align:center;">
                            <p style="color:#555555; font-size:11px; line-height:1.6; margin:0;">
                                If you didn't request this code, you can safely ignore this email.<br>
                                Do not share this code with anyone.
                            </p>
                            <p style="color:#333333; font-size:10px; margin:15px 0 0;">
                                © 2026 PlagSini EV Charging Platform
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def _send_email_sync(to_email: str, otp_code: str) -> bool:
    """Send OTP email synchronously (runs in thread pool)."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        logger.warning(
            f"📧 [DEV MODE] SMTP not configured. OTP for {to_email}: {otp_code}"
        )
        return True  # Return True in dev mode so flow continues

    try:
        msg = _build_otp_email(to_email, otp_code)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

        logger.info(f"📧 OTP email sent to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("📧 SMTP Authentication failed. Check SMTP_EMAIL and SMTP_PASSWORD.")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"📧 SMTP error sending to {to_email}: {e}")
        return False
    except Exception as e:
        logger.error(f"📧 Unexpected error sending email to {to_email}: {e}", exc_info=True)
        return False


async def send_otp_email(to_email: str, otp_code: str) -> bool:
    """Send OTP email asynchronously."""
    return await asyncio.to_thread(_send_email_sync, to_email, otp_code)


# ============================================================
#  TICKET EMAIL HELPERS
# ============================================================

def _build_ticket_email(to_email: str, subject: str, body_html: str) -> MIMEMultipart:
    """Build a generic HTML email for ticket notifications."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_EMAIL}>"
    msg["To"] = to_email

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background-color:#0A0A1A;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0A0A1A;padding:40px 20px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="background-color:#12192B;border-radius:16px;overflow:hidden;border:1px solid #1E2D42;">
        <tr><td style="background:linear-gradient(135deg,#00FF88 0%,#00AA55 100%);padding:24px;text-align:center;">
          <h1 style="color:#000;margin:0;font-size:22px;font-weight:800;">⚡ PlagSini Support</h1>
        </td></tr>
        <tr><td style="padding:30px;color:#ddd;font-size:14px;line-height:1.7;">
          {body_html}
        </td></tr>
        <tr><td style="padding:16px 30px 24px;border-top:1px solid #1E2D42;text-align:center;">
          <p style="color:#555;font-size:10px;">© 2026 PlagSini EV Charging Platform</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    msg.attach(MIMEText(html, "html"))
    return msg


def _send_generic_email(to_email: str, subject: str, body_html: str) -> bool:
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        logger.warning(f"📧 [DEV MODE] Email to {to_email}: {subject}")
        return True
    try:
        email_msg = _build_ticket_email(to_email, subject, body_html)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, email_msg.as_string())
        logger.info(f"📧 Ticket email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"📧 Error sending ticket email to {to_email}: {e}")
        return False


async def send_ticket_confirmation(to_email: str, ticket_number: str, subject: str, category: str) -> bool:
    body = f"""
    <h2 style="color:#00FF88;margin:0 0 15px;">Ticket Created Successfully</h2>
    <p>Thank you for contacting PlagSini Support. Your ticket has been received.</p>
    <div style="background:#0A0A1A;border:1px solid #00FF88;border-radius:10px;padding:16px;margin:16px 0;">
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Ticket #:</strong> {ticket_number}</p>
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Subject:</strong> {subject}</p>
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Category:</strong> {category}</p>
    </div>
    <p>Our support team will review your issue and respond as soon as possible. You will receive email updates when there's progress on your ticket.</p>
    """
    return await asyncio.to_thread(_send_generic_email, to_email, f"[{ticket_number}] Ticket Received – {subject}", body)


async def send_ticket_reminder(to_email: str, staff_name: str, ticket_number: str, subject: str, priority: str, due_at_str: str, is_overdue: bool) -> bool:
    """Send SLA reminder/overdue alert email to assigned staff."""
    if is_overdue:
        status_label = "OVERDUE"
        status_color = "#FF4444"
        status_icon = "🚨"
        msg_text = "This ticket has <strong>exceeded its SLA deadline</strong> and requires immediate attention."
    else:
        status_label = "APPROACHING DEADLINE"
        status_color = "#FFA500"
        status_icon = "⚠️"
        msg_text = "This ticket is <strong>approaching its SLA deadline</strong>. Please take action soon."

    body = f"""
    <h2 style="color:{status_color};margin:0 0 15px;">{status_icon} Ticket {status_label}</h2>
    <p>Hi <strong>{staff_name}</strong>,</p>
    <p>{msg_text}</p>
    <div style="background:#0A0A1A;border:1px solid {status_color};border-radius:10px;padding:16px;margin:16px 0;">
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Ticket #:</strong> {ticket_number}</p>
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Subject:</strong> {subject}</p>
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Priority:</strong> <span style="color:{status_color};font-weight:bold;">{priority.upper()}</span></p>
      <p style="margin:4px 0;"><strong style="color:#00FF88;">SLA Deadline:</strong> {due_at_str}</p>
    </div>
    <p>Please log in to the <a href="http://localhost:8000/staff-portal" style="color:#00FF88;">Staff Portal</a> to handle this ticket.</p>
    """
    email_subject = f"[{status_icon} {status_label}] {ticket_number} - {subject}"
    return await asyncio.to_thread(_send_generic_email, to_email, email_subject, body)


async def send_ticket_update(to_email: str, ticket_number: str, subject: str, new_status: str) -> bool:
    status_labels = {
        "in_progress": "🔧 In Progress",
        "resolved": "✅ Resolved",
        "closed": "🔒 Closed",
        "admin_reply": "💬 New Reply from Support",
    }
    label = status_labels.get(new_status, new_status.replace("_", " ").title())
    body = f"""
    <h2 style="color:#00FF88;margin:0 0 15px;">Ticket Update</h2>
    <p>There's an update on your support ticket.</p>
    <div style="background:#0A0A1A;border:1px solid #00FF88;border-radius:10px;padding:16px;margin:16px 0;">
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Ticket #:</strong> {ticket_number}</p>
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Subject:</strong> {subject}</p>
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Status:</strong> {label}</p>
    </div>
    <p>{"A support agent has replied to your ticket. Please check your conversation for details." if new_status == "admin_reply" else "Our team is working to resolve your issue as quickly as possible."}</p>
    """
    return await asyncio.to_thread(_send_generic_email, to_email, f"[{ticket_number}] {label} – {subject}", body)
