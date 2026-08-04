"""
email_notifier.py
─────────────────
Sends a beautiful HTML approval email to Dad whenever a client sends
a price-related negotiation message.

Returns (success: bool, error_message: str) so the caller can display
an in-app banner when email fails.
"""

import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from datetime             import datetime

from config import (
    SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
    DAD_EMAIL, APP_URL, HAS_EMAIL
)

logger = logging.getLogger(__name__)


def send_approval_email(
    quote: dict,
    client_message: str,
    ai_reply: str,
    suggested_price,
    trade_off: str,
    approval_id: int,
    secure_token: str
) -> tuple[bool, str]:
    """
    Send an HTML approval email to Dad.

    Returns:
        (True, "")          — email sent successfully
        (False, error_msg)  — something went wrong
    """
    # Log to console regardless of email config
    _log_to_console(quote, client_message, ai_reply, suggested_price,
                    trade_off, approval_id, secure_token)

    if not HAS_EMAIL:
        msg = "Email not configured — SMTP credentials missing in .env"
        logger.warning(msg)
        return False, msg

    approve_url = f"{APP_URL}/api/email-approve/{approval_id}?token={secure_token}"
    reject_url  = f"{APP_URL}/api/email-reject/{approval_id}?token={secure_token}"

    subject = (
        f"[PaintQuote Pro] Approval Needed — "
        f"{quote.get('client_name', 'Client')} Negotiation"
    )

    html_body = _build_html_email(
        quote=quote,
        client_message=client_message,
        ai_reply=ai_reply,
        suggested_price=suggested_price,
        trade_off=trade_off,
        approval_id=approval_id,
        approve_url=approve_url,
        reject_url=reject_url,
    )

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"PaintQuote Pro <{SMTP_USERNAME}>"
        msg["To"]      = DAD_EMAIL

        # Plain text fallback
        plain = (
            f"Approval Required — PaintQuote Pro\n\n"
            f"Client: {quote.get('client_name')}\n"
            f"Original Quote: ₹{quote.get('total_cost', 0):,.0f}\n\n"
            f"Client Message:\n{client_message}\n\n"
            f"AI Suggested Reply:\n{ai_reply}\n\n"
            f"APPROVE: {approve_url}\n"
            f"REJECT:  {reject_url}\n"
        )
        msg.attach(MIMEText(plain,     "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html",  "utf-8"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_USERNAME, DAD_EMAIL, msg.as_string())

        logger.info("Approval email sent to %s (AQ #%d)", DAD_EMAIL, approval_id)
        return True, ""

    except smtplib.SMTPAuthenticationError:
        err = "SMTP authentication failed — check SMTP_USERNAME and SMTP_PASSWORD in .env"
        logger.error(err)
        return False, err
    except Exception as exc:
        err = f"Failed to send approval email: {exc}"
        logger.error(err)
        return False, err


# ── HTML email builder ────────────────────────────────────────────────────────

def _build_html_email(
    quote, client_message, ai_reply, suggested_price,
    trade_off, approval_id, approve_url, reject_url
) -> str:
    client_name   = quote.get("client_name", "Client")
    original_price = quote.get("total_cost", 0)
    date_str      = datetime.now().strftime("%d %b %Y, %I:%M %p")

    suggested_block = ""
    if suggested_price:
        diff   = original_price - suggested_price
        pct    = (diff / original_price * 100) if original_price else 0
        suggested_block = f"""
        <tr>
          <td style="padding:6px 0;color:#6b7280;font-size:14px;">Suggested Counter-Offer</td>
          <td style="padding:6px 0;text-align:right;font-weight:700;color:#059669;font-size:14px;">
            ₹{suggested_price:,.0f}
            <span style="font-size:11px;font-weight:400;color:#9ca3af;">
              (-₹{diff:,.0f} / -{pct:.1f}%)
            </span>
          </td>
        </tr>"""

    trade_off_block = ""
    if trade_off:
        trade_off_block = f"""
        <div style="margin-top:12px;padding:10px 14px;
                    background:#fff7ed;border-left:3px solid #f97316;
                    border-radius:6px;font-size:13px;color:#9a3412;">
          <strong>↔ Trade-off:</strong> {trade_off}
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Approval Required — PaintQuote Pro</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:'Segoe UI',Arial,sans-serif;">

  <!-- Wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 16px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="max-width:600px;width:100%;background:#ffffff;
                    border-radius:12px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,0.10);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1e40af 0%,#3b82f6 100%);
                     padding:28px 32px;text-align:center;">
            <div style="font-size:28px;margin-bottom:8px;">🎨</div>
            <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;
                        letter-spacing:-0.3px;">PaintQuote Pro</h1>
            <p style="margin:6px 0 0;color:#bfdbfe;font-size:13px;">
              Professional Painting Quote System
            </p>
          </td>
        </tr>

        <!-- Alert Banner -->
        <tr>
          <td style="background:#fef3c7;padding:14px 32px;text-align:center;
                     border-bottom:1px solid #fde68a;">
            <span style="font-size:14px;font-weight:600;color:#92400e;">
              ⏳ Action Required — Client is negotiating on their quote
            </span>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:28px 32px;">

            <p style="margin:0 0 20px;color:#374151;font-size:15px;line-height:1.6;">
              Hi Dad, a client has sent a price-related message about their quote.
              Please review the AI-suggested reply below and either
              <strong style="color:#059669;">Approve</strong> it or
              <strong style="color:#dc2626;">Reject</strong> it.
            </p>

            <!-- Quote Details Card -->
            <div style="background:#f9fafb;border:1px solid #e5e7eb;
                        border-radius:8px;padding:16px 20px;margin-bottom:20px;">
              <p style="margin:0 0 12px;font-size:11px;font-weight:700;
                         color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;">
                Quote Details
              </p>
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding:6px 0;color:#6b7280;font-size:14px;">Client</td>
                  <td style="padding:6px 0;text-align:right;font-weight:600;
                              color:#111827;font-size:14px;">{client_name}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#6b7280;font-size:14px;">Original Quote</td>
                  <td style="padding:6px 0;text-align:right;font-weight:700;
                              color:#1e40af;font-size:16px;">₹{original_price:,.0f}</td>
                </tr>
                {suggested_block}
                <tr>
                  <td style="padding:6px 0;color:#6b7280;font-size:14px;">Date</td>
                  <td style="padding:6px 0;text-align:right;color:#111827;
                              font-size:14px;">{date_str}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#6b7280;font-size:14px;">Approval ID</td>
                  <td style="padding:6px 0;text-align:right;color:#6b7280;
                              font-size:12px;">AQ-{approval_id}</td>
                </tr>
              </table>
            </div>

            <!-- Client Message -->
            <div style="margin-bottom:20px;">
              <p style="margin:0 0 8px;font-size:11px;font-weight:700;
                         color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;">
                💬 Client's Message
              </p>
              <div style="background:#f0f4ff;border-left:4px solid #1e40af;
                          border-radius:6px;padding:14px 16px;
                          font-size:14px;color:#1e3a8a;line-height:1.6;">
                {client_message}
              </div>
            </div>

            <!-- AI Suggested Reply -->
            <div style="margin-bottom:20px;">
              <p style="margin:0 0 8px;font-size:11px;font-weight:700;
                         color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;">
                🤖 AI Suggested Reply
              </p>
              <div style="background:#fff7ed;border-left:4px solid #f97316;
                          border-radius:6px;padding:14px 16px;
                          font-size:14px;color:#7c2d12;line-height:1.6;">
                {ai_reply}
              </div>
              {trade_off_block}
            </div>

            <!-- Action Buttons -->
            <p style="margin:0 0 14px;font-size:13px;font-weight:600;
                       color:#374151;text-align:center;">
              What would you like to do?
            </p>

            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;">
              <tr>
                <td style="padding:0 6px 0 0;">
                  <a href="{approve_url}"
                     style="display:block;text-align:center;
                            background:#059669;color:#ffffff;
                            padding:16px 24px;border-radius:8px;
                            text-decoration:none;font-weight:700;
                            font-size:15px;letter-spacing:0.2px;">
                    ✅ Approve &amp; Send
                  </a>
                </td>
                <td style="padding:0 0 0 6px;">
                  <a href="{reject_url}"
                     style="display:block;text-align:center;
                            background:#dc2626;color:#ffffff;
                            padding:16px 24px;border-radius:8px;
                            text-decoration:none;font-weight:700;
                            font-size:15px;letter-spacing:0.2px;">
                    ❌ Reject &amp; Write My Own
                  </a>
                </td>
              </tr>
            </table>

            <!-- Text fallback links -->
            <p style="margin:16px 0 0;font-size:12px;color:#9ca3af;text-align:center;">
              If buttons don't work:
              <a href="{approve_url}" style="color:#059669;">Approve</a> |
              <a href="{reject_url}"  style="color:#dc2626;">Reject</a>
            </p>

          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f9fafb;padding:16px 32px;
                     border-top:1px solid #e5e7eb;text-align:center;">
            <p style="margin:0;font-size:12px;color:#9ca3af;">
              PaintQuote Pro — Built with ❤️ for Dad<br>
              <a href="{APP_URL}/approval-queue" style="color:#1e40af;text-decoration:none;">
                View full approval queue →
              </a>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _log_to_console(quote, client_message, ai_reply, suggested_price,
                    trade_off, approval_id, secure_token):
    """Always log to console as a fallback notification."""
    border = "=" * 62
    print(f"\n{border}")
    print(f"  📧  APPROVAL REQUIRED — PaintQuote Pro")
    print(border)
    print(f"  Quote:          #{quote.get('id')} — {quote.get('client_name')}")
    print(f"  Original Price: ₹{quote.get('total_cost', 0):,.0f}")
    print(f"\n  CLIENT MESSAGE:\n    {client_message}")
    print(f"\n  AI DRAFT REPLY:\n    {ai_reply}")
    if suggested_price:
        print(f"\n  SUGGESTED PRICE: ₹{suggested_price:,.0f}")
    if trade_off:
        print(f"  TRADE-OFF:       {trade_off}")
    print(f"\n  APPROVE: {APP_URL}/api/email-approve/{approval_id}?token={secure_token}")
    print(f"  REJECT:  {APP_URL}/api/email-reject/{approval_id}?token={secure_token}")
    print(border + "\n")
