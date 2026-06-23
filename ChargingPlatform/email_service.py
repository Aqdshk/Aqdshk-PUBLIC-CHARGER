"""
PlagSini EV — Email Service

Sends OTP codes (registration, password reset) via SMTP.
Also: ticket confirmation, updates, SLA reminders.

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
import secrets
import smtplib
import asyncio
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")           # SMTP login credential
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "PlagSini EV")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_EMAIL)  # Verified sender (FROM address)


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure numeric OTP code."""
    return ''.join([str(secrets.randbelow(10)) for _ in range(length)])


def _build_otp_email(to_email: str, otp_code: str) -> MIMEMultipart:
    """Build the OTP verification email with HTML template."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"PlagSini - Your Verification Code: {otp_code}"
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
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
            server.sendmail(SMTP_FROM_EMAIL, to_email, msg.as_string())

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
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
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


def _send_raw_html_email(to_email: str, subject: str, full_html: str) -> bool:
    """Send a complete HTML email without the shared ticket-style wrapper.
    Used for branded standalone templates (invoices, receipts) that need
    full control over layout and want to fit cleanly in one print page."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        logger.warning(f"📧 [DEV MODE] Raw email to {to_email}: {subject}")
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(full_html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        logger.info(f"📧 Raw HTML email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"📧 Error sending raw email to {to_email}: {e}")
        return False


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
    <p>Please log in to the <a href="{os.getenv('APP_BASE_URL', 'http://localhost:8000')}/staff-portal" style="color:#00FF88;">Staff Portal</a> to handle this ticket.</p>
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


# ============================================================
#  PAYMENT / CHARGING RECEIPT
# ============================================================

async def send_charging_receipt(
    to_email: str,
    transaction_ref: str,
    amount: float,
    charger_id: str,
    connector_id: int,
    paid_at_str: str,
    gateway: str = "TNG eWallet",
) -> bool:
    """Send a payment receipt + 'charger starting' confirmation to a quick-pay user."""
    body = f"""
    <h2 style="color:#00FF88;margin:0 0 15px;">⚡ Payment Received</h2>
    <p>Thank you! Your payment has been received and your charger is starting now.</p>
    <div style="background:#0A0A1A;border:1px solid #00FF88;border-radius:10px;padding:16px;margin:16px 0;">
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Receipt #:</strong> {transaction_ref}</p>
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Amount Paid:</strong> RM {amount:.2f}</p>
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Payment Method:</strong> {gateway}</p>
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Charger:</strong> {charger_id} (Connector {connector_id})</p>
      <p style="margin:4px 0;"><strong style="color:#00FF88;">Paid At:</strong> {paid_at_str}</p>
    </div>
    <p>Please plug in your cable if you haven't already. Charging will stop automatically once your prepaid balance is consumed.</p>
    <p style="color:#888;font-size:12px;margin-top:20px;">
      Need help? Reply to this email or contact PlagSini support.
    </p>
    """
    return await asyncio.to_thread(
        _send_generic_email,
        to_email,
        f"[Receipt {transaction_ref}] PlagSini Charging — RM {amount:.2f}",
        body,
    )


async def send_charging_invoice(
    to_email: str,
    transaction_ref: str,
    charger_id: str,
    connector_id: int,
    started_at_str: str,
    stopped_at_str: str,
    duration_str: str,
    energy_kwh: float,
    amount_paid: float,
    stop_reason: str = "Local",
    # Deposit/refund flow extras (terminal kiosk) — set when applicable
    hold_amount: Optional[float] = None,
    energy_cost: Optional[float] = None,
    idle_minutes: Optional[int] = None,
    idle_fee: Optional[float] = None,
    refund_amount: Optional[float] = None,
) -> bool:
    """Send post-charge invoice (session summary) to the user.

    Standalone branded HTML — uses _send_raw_html_email (NOT the generic
    ticket wrapper) so we control the full layout and the receipt fits
    cleanly in a single print page."""

    has_deposit_flow = hold_amount is not None and refund_amount is not None

    # Cost-breakdown rows
    if has_deposit_flow:
        idle_row = ""
        if idle_minutes and idle_minutes > 0 and idle_fee:
            idle_row = (
                '<tr><td style="padding:5px 0;color:#666;">Idle fee</td>'
                f'<td style="text-align:right;color:#E67E22;font-weight:600;">− RM {idle_fee:.2f} '
                f'<span style="color:#999;font-weight:400;font-size:11px;">({idle_minutes} min)</span></td></tr>'
            )
        cost_rows = f"""
            <tr><td style="padding:5px 0;color:#666;">Deposit captured</td><td style="text-align:right;color:#1a1a1a;font-weight:600;">RM {hold_amount:.2f}</td></tr>
            <tr><td style="padding:5px 0;color:#666;">Energy used</td><td style="text-align:right;color:#1a1a1a;font-weight:600;">− RM {(energy_cost or 0):.2f}</td></tr>
            {idle_row}
            <tr><td colspan="2" style="border-top:2px solid #00C266;padding-top:10px;"></td></tr>
            <tr><td style="padding:8px 0;color:#1a1a1a;font-size:15px;font-weight:700;">Refunded to TNG</td>
                <td style="text-align:right;color:#00A852;font-size:20px;font-weight:800;">RM {refund_amount:.2f}</td></tr>
        """
    else:
        cost_rows = (
            '<tr><td colspan="2" style="border-top:2px solid #00C266;padding-top:10px;"></td></tr>'
            f'<tr><td style="padding:8px 0;color:#1a1a1a;font-size:15px;font-weight:700;">Amount paid</td>'
            f'<td style="text-align:right;color:#00A852;font-size:20px;font-weight:800;">RM {amount_paid:.2f}</td></tr>'
        )

    # Pre-format energy + amount summary line for header
    summary_amt = refund_amount if has_deposit_flow else amount_paid

    # Compact session stats line for the hero stat block
    avg_kw = None
    try:
        # Derive average power if we can pull total seconds out of duration_str (HH:MM:SS)
        h, m, s = (int(x) for x in (duration_str or "00:00:00").split(":"))
        hours = (h + m/60 + s/3600) or 1
        avg_kw = round(energy_kwh / hours, 1)
    except Exception:
        avg_kw = None
    avg_kw_str = f"{avg_kw:.1f} kW" if avg_kw is not None else "—"
    co2_kg = round(energy_kwh * 0.585, 2)  # MY grid avg ≈ 0.585 kg CO2 / kWh

    full_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Receipt {transaction_ref}</title></head>
<body style="margin:0;padding:0;background:#EEF2F6;font-family:-apple-system,'Segoe UI',Arial,sans-serif;color:#0F172A;-webkit-text-size-adjust:100%;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#EEF2F6;padding:28px 16px;">
    <tr><td align="center">

      <table width="600" cellpadding="0" cellspacing="0" style="background:#FFFFFF;border-radius:18px;overflow:hidden;box-shadow:0 6px 24px rgba(15,23,42,0.06);max-width:600px;">

        <!-- Hero band: dark, big logo (no white box), tagline -->
        <tr><td style="background:linear-gradient(135deg,#0A2A18 0%,#00A852 100%);padding:32px 28px 28px;text-align:center;">
          <img src="https://charger.czeros.tech/static/logo.png" alt="PlagSini" width="110" style="display:block;margin:0 auto 14px;border:0;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic;">
          <div style="color:#FFFFFF;font-size:24px;font-weight:900;letter-spacing:-0.3px;line-height:1;">Plag<span style="color:#A8FFD3;">Sini</span></div>
          <div style="color:rgba(255,255,255,0.7);font-size:10px;font-weight:700;letter-spacing:3px;text-transform:uppercase;margin-top:8px;">Charge Your Journey</div>
        </td></tr>

        <!-- Receipt title -->
        <tr><td style="padding:26px 32px 0;text-align:center;">
          <div style="font-size:11px;color:#94A3B8;letter-spacing:2px;text-transform:uppercase;font-weight:700;">Charging Receipt</div>
          <div style="font-size:42px;color:#0F172A;font-weight:900;margin:10px 0 4px;letter-spacing:-1.5px;">{energy_kwh:.2f} <span style="font-size:20px;font-weight:600;color:#64748B;">kWh</span></div>
          <div style="font-size:11px;color:#64748B;font-family:'SF Mono',Consolas,monospace;">{transaction_ref}</div>
        </td></tr>

        <!-- Stat strip: 3 columns -->
        <tr><td style="padding:24px 32px 8px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#F8FAFC;border-radius:14px;border:1px solid #E2E8F0;">
            <tr>
              <td style="padding:18px 8px;text-align:center;border-right:1px solid #E2E8F0;">
                <div style="font-size:11px;color:#64748B;text-transform:uppercase;letter-spacing:1.2px;font-weight:700;margin-bottom:6px;">Duration</div>
                <div style="font-size:18px;color:#0F172A;font-weight:800;font-family:'SF Mono',Consolas,monospace;">{duration_str}</div>
              </td>
              <td style="padding:18px 8px;text-align:center;border-right:1px solid #E2E8F0;">
                <div style="font-size:11px;color:#64748B;text-transform:uppercase;letter-spacing:1.2px;font-weight:700;margin-bottom:6px;">Avg Power</div>
                <div style="font-size:18px;color:#0F172A;font-weight:800;">{avg_kw_str}</div>
              </td>
              <td style="padding:18px 8px;text-align:center;">
                <div style="font-size:11px;color:#64748B;text-transform:uppercase;letter-spacing:1.2px;font-weight:700;margin-bottom:6px;">CO₂ saved</div>
                <div style="font-size:18px;color:#00A852;font-weight:800;">{co2_kg} kg</div>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Session details -->
        <tr><td style="padding:18px 32px 0;">
          <div style="font-size:10px;color:#94A3B8;text-transform:uppercase;letter-spacing:1.5px;font-weight:800;margin-bottom:10px;">Session Details</div>
          <table width="100%" cellpadding="0" cellspacing="0" style="font-size:13px;color:#0F172A;">
            <tr>
              <td style="padding:7px 0;color:#64748B;width:42%;">📍 Charger</td>
              <td style="text-align:right;font-family:'SF Mono',Consolas,monospace;font-weight:600;color:#0F172A;">{charger_id}</td>
            </tr>
            <tr>
              <td style="padding:7px 0;color:#64748B;border-top:1px solid #F1F5F9;">🔌 Connector</td>
              <td style="text-align:right;font-weight:600;border-top:1px solid #F1F5F9;">{connector_id}</td>
            </tr>
            <tr>
              <td style="padding:7px 0;color:#64748B;border-top:1px solid #F1F5F9;">▶ Started</td>
              <td style="text-align:right;color:#0F172A;border-top:1px solid #F1F5F9;">{started_at_str}</td>
            </tr>
            <tr>
              <td style="padding:7px 0;color:#64748B;border-top:1px solid #F1F5F9;">■ Stopped</td>
              <td style="text-align:right;color:#0F172A;border-top:1px solid #F1F5F9;">{stopped_at_str}</td>
            </tr>
            <tr>
              <td style="padding:7px 0;color:#64748B;border-top:1px solid #F1F5F9;">↺ Stop reason</td>
              <td style="text-align:right;color:#94A3B8;font-size:12px;border-top:1px solid #F1F5F9;">{stop_reason or "—"}</td>
            </tr>
          </table>
        </td></tr>

        <!-- Payment breakdown -->
        <tr><td style="padding:22px 32px 8px;">
          <div style="font-size:10px;color:#94A3B8;text-transform:uppercase;letter-spacing:1.5px;font-weight:800;margin-bottom:10px;">Payment</div>
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#F8FAFC;border-radius:12px;padding:0;">
            <tr><td style="padding:14px 16px 4px;">
              <table width="100%" cellpadding="0" cellspacing="0" style="font-size:13px;">
                {cost_rows}
              </table>
            </td></tr>
          </table>
        </td></tr>

        <!-- Footer -->
        <tr><td style="padding:22px 32px 28px;text-align:center;">
          <div style="font-size:11px;color:#64748B;line-height:1.6;">
            This receipt is auto-generated and serves as your official invoice.<br>
            Questions? Reply to this email or visit <a href="https://charger.czeros.tech" style="color:#00A852;text-decoration:none;font-weight:600;">charger.czeros.tech</a>.
          </div>
          <div style="margin-top:14px;padding-top:14px;border-top:1px solid #E2E8F0;font-size:10px;color:#94A3B8;letter-spacing:0.5px;">
            © 2026 <b style="color:#64748B;">PlagSini EV</b> Charging Platform · <i style="color:#94A3B8;">Charge Your Journey</i>
          </div>
        </td></tr>

      </table>

    </td></tr>
  </table>
</body>
</html>"""

    return await asyncio.to_thread(
        _send_raw_html_email,
        to_email,
        f"[Receipt {transaction_ref}] PlagSini — {energy_kwh:.2f} kWh · RM {summary_amt:.2f}",
        full_html,
    )
