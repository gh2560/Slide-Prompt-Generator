"""
api/auth_router.py — HTTP routes cho authentication
"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from core.dependencies import get_current_user
from core.oauth import oauth
from database.connection import get_db
from models.user import User
from schemas.auth import (
    MessageResponse,
    ResendVerificationRequest,
    UserLogin,
    UserRegister,
    UserResponse,
    VerificationStatusResponse,
)
from services.auth_service import AuthService
from utils.config import get_settings
from utils.rate_limiter import verification_status_tracker

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── EMAIL / PASSWORD ──────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Đăng ký bằng email/password. Trả về user info — chưa có token vì cần verify email."""
    service = AuthService(db)
    user = service.register_with_email(data)
    return user


@router.post("/login", response_model=UserResponse)
def login(data: UserLogin, response: Response, db: Session = Depends(get_db)):
    """
    Đăng nhập bằng email/password → set JWT vào httpOnly cookie (cùng cơ
    chế với Google OAuth) thay vì trả token trong response body, tránh lưu
    token ở localStorage (rủi ro bị đánh cắp qua XSS).
    """
    service = AuthService(db)
    user, access_token = service.login_with_email(data.email, data.password)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return user


@router.get("/verification-status", response_model=VerificationStatusResponse)
def verification_status(email: str, request: Request, db: Session = Depends(get_db)):
    """
    Polling: trang đăng ký gọi định kỳ để biết email đã được xác thực chưa.
    Hữu ích khi link verify được mở ở tab/thiết bị khác.

    Rate-limit theo IP (không theo email) — chặn spam hoặc dò trạng thái
    verify của nhiều email, mà không ảnh hưởng user đang poll bình thường.
    """
    client_ip = request.client.host if request.client else "unknown"
    if verification_status_tracker.is_locked(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều yêu cầu. Vui lòng thử lại sau ít phút.",
        )
    verification_status_tracker.record_attempt(client_ip)

    service = AuthService(db)
    return VerificationStatusResponse(verified=service.is_email_verified(email))


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(data: ResendVerificationRequest, db: Session = Depends(get_db)):
    """Gửi lại email xác thực — dùng khi user không nhận được hoặc đợi quá lâu."""
    service = AuthService(db)
    service.resend_verification_email(data.email)
    return MessageResponse(
        message="Nếu email của bạn chưa được xác thực, một email xác thực mới đã được gửi."
    )


@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """
    Xác thực email từ link trong email.
    Redirect về frontend (không trả JSON) để có UX tốt.
    """
    service = AuthService(db)
    try:
        service.verify_email(token)
        # Thành công → redirect về trang login với param báo thành công
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?verified=success",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except HTTPException as e:
        # Token hết hạn / sai → redirect kèm message lỗi
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?verified=error&msg={quote(e.detail)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


# ── GOOGLE OAUTH ──────────────────────────────────────────────────────
@router.get("/google")
async def google_login(request: Request):
    """
    Bước 1: Redirect user sang Google.
    prompt="select_account" — luôn hiện màn hình chọn account, tránh Google
    tự động tái sử dụng session đăng nhập sẵn có (silent SSO) và trả về
    sai account khi user muốn đăng nhập bằng account Google khác.
    """
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(
        request, redirect_uri, prompt="select_account"
    )


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """
    Bước 2: Google redirect về đây sau khi user đồng ý.
    LUÔN redirect về frontend (kể cả lỗi) để không kẹt user ở trang JSON.
    """
    # ── 1. Lấy token từ Google ──────────────────────────────────────
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote(f'OAuth thất bại: {e}')}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    google_user = token.get("userinfo")
    if not google_user:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote('Không lấy được thông tin từ Google')}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # ── 2. Xử lý login/register ─────────────────────────────────────
    service = AuthService(db)
    try:
        user, access_token, login_status = service.login_or_register_with_google(
            google_id=google_user["sub"],
            email=google_user["email"],
            verified_by_google=google_user.get("email_verified", False),
        )
    except HTTPException as e:
        # Vd: email đã đăng ký bằng password → redirect về login kèm message
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error={quote(e.detail)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # ── 3. Thành công → set cookie + redirect về callback page ──────
    response = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback?status={login_status}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


# ── USER INFO ─────────────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Lấy thông tin user hiện tại."""
    return current_user


@router.post("/logout", response_model=MessageResponse)
def logout(current_user: User = Depends(get_current_user)):
    """Đăng xuất — xóa cookie HttpOnly."""
    response = JSONResponse(content={"message": "Đăng xuất thành công"})
    response.delete_cookie("access_token")
    return response