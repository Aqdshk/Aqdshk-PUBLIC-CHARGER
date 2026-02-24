"""
Email service for automatic ticket responses.
Uses the same Gmail SMTP setup as ChargingPlatform.
"""

import logging
import os
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "PlagSini Support")


def _send_email_sync(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """Send email synchronously."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        logger.warning(f"📧 [DEV MODE] Would send email to {to_email}: {subject}")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_EMAIL}>"
        msg["To"] = to_email

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

        logger.info(f"📧 Email sent to {to_email}: {subject}")
        return True

    except Exception as e:
        logger.error(f"📧 Error sending email to {to_email}: {e}")
        return False


async def send_email(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """Send email asynchronously."""
    return await asyncio.to_thread(_send_email_sync, to_email, subject, html_body, text_body)


async def send_ticket_confirmation(
    to_email: str,
    user_name: str,
    ticket_number: str,
    category: str,
    subject: str,
    description: str,
    priority: str
) -> bool:
    """Send automatic ticket confirmation email."""
    
    priority_colors = {
        "critical": "#FF3333",
        "high": "#FF8800",
        "medium": "#FFD700",
        "low": "#00CC66",
    }
    priority_color = priority_colors.get(priority, "#FFD700")
    
    priority_labels = {
        "critical": "CRITICAL — Response within 30 minutes",
        "high": "HIGH — Response within 2 hours",
        "medium": "MEDIUM — Response within 12 hours",
        "low": "LOW — Response within 24 hours",
    }
    priority_label = priority_labels.get(priority, "Response within 24 hours")
    
    category_labels = {
        "login_account": "🔐 Login & Account",
        "charging": "⚡ Charging Issues",
        "wallet_payment": "💳 Wallet & Payment",
        "vehicle": "🚗 Vehicle Management",
        "rewards": "🎁 Rewards & Points",
        "app_issue": "📱 App Problems",
        "general": "❓ General",
    }
    category_label = category_labels.get(category, "❓ General")
    
    display_name = user_name if user_name else "Valued Customer"

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#0A0A1A;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0A0A1A;padding:40px 20px;">
<tr><td align="center">
<table width="520" cellpadding="0" cellspacing="0" style="background-color:#12192B;border-radius:16px;overflow:hidden;border:1px solid #1E2D42;">

<!-- Header -->
<tr><td style="background:linear-gradient(135deg,#00FF88 0%,#00AA55 100%);padding:24px;text-align:center;">
    <h1 style="color:#000;margin:0;font-size:22px;font-weight:800;letter-spacing:1px;">⚡ PlagSini Support</h1>
    <p style="color:rgba(0,0,0,0.5);margin:4px 0 0;font-size:11px;letter-spacing:2px;">TICKET CONFIRMATION</p>
</td></tr>

<!-- Body -->
<tr><td style="padding:30px;">
    <p style="color:#FFFFFF;font-size:16px;margin:0 0 20px;">Dear {display_name},</p>
    
    <p style="color:#BBBBBB;font-size:14px;line-height:1.6;margin:0 0 20px;">
        We've received your support request. Our team is on it and will get back to you as soon as possible.
    </p>

    <!-- Ticket Details Card -->
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#0A0F1A;border:1px solid #1E2D42;border-radius:12px;overflow:hidden;margin:0 0 20px;">
        <tr><td style="padding:16px;">
            <table width="100%" cellpadding="4" cellspacing="0">
                <tr>
                    <td style="color:#888;font-size:12px;text-transform:uppercase;letter-spacing:1px;width:120px;">Ticket ID</td>
                    <td style="color:#00FF88;font-size:14px;font-weight:bold;">{ticket_number}</td>
                </tr>
                <tr>
                    <td style="color:#888;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Category</td>
                    <td style="color:#FFFFFF;font-size:14px;">{category_label}</td>
                </tr>
                <tr>
                    <td style="color:#888;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Subject</td>
                    <td style="color:#FFFFFF;font-size:14px;">{subject}</td>
                </tr>
                <tr>
                    <td style="color:#888;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Priority</td>
                    <td style="font-size:13px;">
                        <span style="color:{priority_color};font-weight:bold;">{priority.upper()}</span>
                        <span style="color:#888;font-size:11px;"> — {priority_label.split('—')[1].strip() if '—' in priority_label else ''}</span>
                    </td>
                </tr>
            </table>
        </td></tr>
    </table>
    
    <!-- Description -->
    <div style="background:#0A0F1A;border:1px solid #1E2D42;border-radius:8px;padding:14px;margin:0 0 20px;">
        <p style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px;">Your Message</p>
        <p style="color:#CCCCCC;font-size:13px;line-height:1.5;margin:0;">{description[:500]}{'...' if len(description) > 500 else ''}</p>
    </div>

    <p style="color:#BBBBBB;font-size:13px;line-height:1.6;margin:0 0 10px;">
        📩 You can reply to this email to add more details to your ticket.<br>
        🔔 We'll notify you via email when there's an update.
    </p>
</td></tr>

<!-- Footer -->
<tr><td style="padding:16px 30px 24px;border-top:1px solid #1E2D42;text-align:center;">
    <p style="color:#555;font-size:11px;margin:0;">
        Thank you for using PlagSini EV Charging Platform.<br>
        <span style="color:#333;font-size:10px;">© 2026 PlagSini EV</span>
    </p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""

    text = f"""
PlagSini Support — Ticket Confirmation

Dear {display_name},

We've received your support request.

Ticket ID: {ticket_number}
Category: {category_label}
Subject: {subject}
Priority: {priority.upper()} — {priority_label}

Your Message:
{description[:500]}

Our team will respond based on the priority level.
Reply to this email to add more details.

Thank you for using PlagSini EV.
"""

    email_subject = f"[{ticket_number}] Support Request Received — {subject}"
    return await send_email(to_email, email_subject, html, text)


async def send_ticket_update(
    to_email: str,
    user_name: str,
    ticket_number: str,
    new_status: str,
    admin_message: str
) -> bool:
    """Send email when admin updates/responds to a ticket."""
    
    status_labels = {
        "in_progress": "🔄 In Progress",
        "waiting_user": "⏳ Waiting for Your Response",
        "resolved": "✅ Resolved",
        "closed": "🔒 Closed",
    }
    status_label = status_labels.get(new_status, new_status)
    display_name = user_name if user_name else "Valued Customer"

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#0A0A1A;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0A0A1A;padding:40px 20px;">
<tr><td align="center">
<table width="520" cellpadding="0" cellspacing="0" style="background-color:#12192B;border-radius:16px;overflow:hidden;border:1px solid #1E2D42;">

<tr><td style="background:linear-gradient(135deg,#00FF88 0%,#00AA55 100%);padding:24px;text-align:center;">
    <h1 style="color:#000;margin:0;font-size:22px;font-weight:800;">⚡ PlagSini Support</h1>
    <p style="color:rgba(0,0,0,0.5);margin:4px 0 0;font-size:11px;letter-spacing:2px;">TICKET UPDATE</p>
</td></tr>

<tr><td style="padding:30px;">
    <p style="color:#FFFFFF;font-size:16px;margin:0 0 16px;">Dear {display_name},</p>
    
    <p style="color:#BBBBBB;font-size:14px;line-height:1.6;margin:0 0 20px;">
        Your support ticket <strong style="color:#00FF88;">{ticket_number}</strong> has been updated.
    </p>
    
    <div style="background:#0A0F1A;border:1px solid #1E2D42;border-radius:8px;padding:14px;margin:0 0 16px;">
        <p style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 6px;">Status</p>
        <p style="color:#FFFFFF;font-size:15px;font-weight:bold;margin:0;">{status_label}</p>
    </div>
    
    <div style="background:#0A0F1A;border:1px solid #1E2D42;border-radius:8px;padding:14px;margin:0 0 20px;">
        <p style="color:#888;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin:0 0 6px;">Response from Support Team</p>
        <p style="color:#CCCCCC;font-size:13px;line-height:1.6;margin:0;">{admin_message}</p>
    </div>
    
    <p style="color:#BBBBBB;font-size:13px;margin:0;">
        📩 Reply to this email if you need further assistance.
    </p>
</td></tr>

<tr><td style="padding:16px 30px 24px;border-top:1px solid #1E2D42;text-align:center;">
    <p style="color:#555;font-size:11px;margin:0;">© 2026 PlagSini EV</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""

    email_subject = f"[{ticket_number}] Ticket Updated — {status_label}"
    return await send_email(to_email, email_subject, html)
