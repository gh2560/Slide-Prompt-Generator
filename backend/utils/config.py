"""
utils/config.py — Cấu hình ứng dụng, đọc từ .env
"""
from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Environment ────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"

    # ── Database ───────────────────────────────────────────────────────
    # SQLite cho đơn giản. Đổi sang Postgres khi cần:
    # SQLALCHEMY_DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"
    SQLALCHEMY_DATABASE_URL: str = "sqlite:///./prompt_builder.db"

    # ── Gemini LLM ─────────────────────────────────────────────────────
    gemini_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    min_slides_limit: int = 3
    max_slides_limit: int = 30

    # ── JWT ────────────────────────────────────────────────────────────
    # Default value đủ 32 ký tự để dev không crash. Production PHẢI override.
    JWT_SECRET_KEY: str = "dev_only_secret_key_change_in_production_2025"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 ngày

    # ── Google OAuth ───────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    # ── Frontend ───────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ── Backend base URL (dùng cho link trong email) ───────────────────
    BASE_URL: str = "http://localhost:8000"

    # ── Rate limiting (in-memory) ──────────────────────────────────────
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    MAX_GENERATE_ATTEMPTS: int = 5
    GENERATE_LOCKOUT_MINUTES: int = 10

    # ── Email verification ─────────────────────────────────────────────
    EMAIL_VERIFY_TTL_HOURS: int = 24

    # ── Resend verification email rate limit ───────────────────────────
    # Lớp chặn phụ phòng gọi API trực tiếp — frontend đã tự giới hạn bằng
    # cooldown 120s/lần nên ngưỡng này chỉ cần rộng hơn nhịp đó một chút.
    MAX_RESEND_ATTEMPTS: int = 5
    RESEND_LOCKOUT_MINUTES: int = 10

    # ── Verification-status polling rate limit (theo IP) ───────────────
    # Trang đăng ký poll endpoint này mỗi 3s (~20 req/phút/tab). Đặt ngưỡng
    # rộng hơn để không chặn user mở nhiều tab, nhưng vẫn chặn được spam
    # hoặc dò trạng thái verify của nhiều email.
    MAX_VERIFICATION_STATUS_ATTEMPTS: int = 60
    VERIFICATION_STATUS_LOCKOUT_MINUTES: int = 1

    # ── SMTP (để gửi email verify thật) ────────────────────────────────
    # Để trống = dev mode, chỉ in link ra console (không gửi email)
    # Điền vào để bật gửi email qua SMTP (vd: Gmail dùng App Password)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""        # email người gửi hiển thị
    SMTP_FROM_NAME: str = "Prompt Builder"

    # ── Resend API (thay thế SMTP, không bị chặn trên cloud) ──────────────
    RESEND_API_KEY: str = ""

    # ── OCR (Tesseract/Poppler) ─────────────────────────────────────────
    # Để trống = dùng binary trong PATH (mặc định trên Linux/Docker).
    # Set giá trị nếu Tesseract/Poppler không nằm trong PATH (vd: Windows).
    TESSERACT_CMD: str = ""   # vd: C:\Program Files\Tesseract-OCR\tesseract.exe
    POPPLER_PATH: str = ""    # vd: C:\poppler\Library\bin

    @model_validator(mode="after")
    def check_production_secrets(self) -> "Settings":
        if self.is_production and "dev_only" in self.JWT_SECRET_KEY:
            raise ValueError(
                "JWT_SECRET_KEY chưa được đổi cho production! "
                "Chạy lệnh sau để tạo key mạnh:\n"
                "  python -c \"import secrets; print(secrets.token_hex(32))\"\n"
                "Sau đó set JWT_SECRET_KEY=<key> trong file .env"
            )
        return self

    @property
    def smtp_enabled(self) -> bool:
        """True nếu đã config đủ SMTP credentials để gửi email thật."""
        return bool(self.SMTP_USER and self.SMTP_PASSWORD)

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    def get_allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Singleton settings, cached giữa các lần gọi."""
    return Settings()