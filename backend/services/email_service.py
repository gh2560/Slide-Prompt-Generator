"""
services/email_service.py — Gửi email qua SMTP.

Cách dùng:
- Nếu chưa config SMTP (settings.smtp_enabled == False) → chỉ in link ra console
- Đã config → gửi email thật qua smtplib

Để bật SMTP qua Gmail:
1. Bật 2FA cho Google account
2. Tạo App Password tại https://myaccount.google.com/apppasswords
3. Set trong .env:
   SMTP_USER=your.email@gmail.com
   SMTP_PASSWORD=<app-password-16-ký-tự>
   SMTP_FROM_EMAIL=your.email@gmail.com
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def send_email(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """
    Gửi email qua SMTP.
    Return True nếu gửi thành công, False nếu fail hoặc chưa config.

    Trong dev mode (chưa config SMTP) → chỉ log ra console, return False.
    """
    if not settings.smtp_enabled:
        logger.info(f"[DEV - SMTP disabled] Would send to {to_email}: {subject}")
        return False

    from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    from_name = settings.SMTP_FROM_NAME

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_verification_email(to_email: str, verify_url: str) -> bool:
    """Gửi email xác thực với link verify."""
    subject = "Xác thực email - Prompt Builder"

    html_body = f"""
    <html>
      <body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2>Chào mừng đến với Prompt Builder!</h2>
        <p>Cảm ơn bạn đã đăng ký. Vui lòng click vào link dưới đây để xác thực email:</p>
        <p style="margin: 30px 0;">
          <a href="{verify_url}"
             style="background: #667eea; color: white; padding: 12px 24px;
                    text-decoration: none; border-radius: 6px; display: inline-block;">
            Xác thực email
          </a>
        </p>
        <p style="color: #666; font-size: 13px;">
          Hoặc copy link sau vào trình duyệt:<br/>
          <span style="word-break: break-all;">{verify_url}</span>
        </p>
        <p style="color: #999; font-size: 12px; margin-top: 40px;">
          Link có hiệu lực trong {settings.EMAIL_VERIFY_TTL_HOURS} giờ.
          Nếu bạn không đăng ký, vui lòng bỏ qua email này.
        </p>
      </body>
    </html>
    """

    text_body = (
        f"Chào mừng đến với Prompt Builder!\n\n"
        f"Vui lòng truy cập link sau để xác thực email:\n{verify_url}\n\n"
        f"Link có hiệu lực trong {settings.EMAIL_VERIFY_TTL_HOURS} giờ."
    )

    return send_email(to_email, subject, html_body, text_body)