"""
services/email_service.py — Gửi email qua Resend API.

Cách dùng:
- Nếu chưa config RESEND_API_KEY → chỉ in link ra console
- Đã config → gửi email thật qua Resend HTTP API

Để bật Resend:
1. Đăng ký tại https://resend.com (free tier: 3000 email/tháng)
2. Lấy API key
3. Set trong .env / Railway Variables:
   RESEND_API_KEY=re_xxxxxxxxxxxx
   SMTP_FROM_EMAIL=onboarding@resend.dev  (hoặc domain đã verify)
"""
import logging

from utils.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def send_email(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """
    Gửi email qua Resend API.
    Return True nếu gửi thành công, False nếu fail hoặc chưa config.
    """
    if not settings.RESEND_API_KEY:
        logger.info(f"[DEV - Resend disabled] Would send to {to_email}: {subject}")
        return False

    try:
        import resend
        resend.api_key = settings.RESEND_API_KEY

        from_email = settings.SMTP_FROM_EMAIL or "onboarding@resend.dev"
        from_name = settings.SMTP_FROM_NAME

        params = {
            "from": f"{from_name} <{from_email}>",
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        }
        if text_body:
            params["text"] = text_body

        resend.Emails.send(params)
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
