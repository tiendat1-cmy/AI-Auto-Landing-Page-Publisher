import logging
import os
import re
import sys
from pathlib import Path

# Đảm bảo thư mục backend luôn nằm trong sys.path dù chạy từ root hay backend
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.auth import router as auth_router
from api.deployments import router as deployments_router
from api.health import router as health_router
from api.projects import router as projects_router
from api.templates import router as templates_router
from api.versions import router as versions_router
from core.config import settings

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = FastAPI(title=settings.PROJECT_NAME)


# ── 1. Cấu hình CORS an toàn ─────────────────────────────────────────
def _get_allowed_origins() -> list[str]:
    raw_origins = os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5500,http://localhost:5500",
    )
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["X-GitHub-Error", "Retry-After"],
)


# ── 2. Hàm lọc sạch API Key / Token khỏi thông báo lỗi ───────────────
def _sanitize_error_text(text: str) -> str:
    if not text:
        return "Đã xảy ra lỗi không xác định."
    sanitized = text
    for secret_val in (
        getattr(settings, "GEMINI_API_KEY", None),
        getattr(settings, "GITHUB_TOKEN", None),
        getattr(settings, "JWT_SECRET", None),
        os.getenv("GEMINI_API_KEY"),
        os.getenv("GITHUB_TOKEN"),
    ):
        if secret_val and isinstance(secret_val, str) and len(secret_val) > 6:
            sanitized = sanitized.replace(secret_val, "***HIDDEN***")
    sanitized = re.sub(r"([?&]key=)[^&\s\"']+", r"\1***HIDDEN***", sanitized)
    sanitized = re.sub(r"(gh[pousr]_[A-Za-z0-9_]+|AIza[0-9A-Za-z\-_]+)", "***HIDDEN***", sanitized)
    return sanitized


# ── 3. Global Exception Handlers — Trả thông báo lỗi thân thiện ──────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        payload = exc.detail
        if isinstance(payload.get("error"), dict) and "message" in payload["error"]:
            payload["error"]["message"] = _sanitize_error_text(str(payload["error"]["message"]))
        return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)

    friendly_msg = _sanitize_error_text(str(exc.detail or "Yêu cầu không hợp lệ."))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "detail": friendly_msg,
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": friendly_msg,
                "details": [],
            },
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    field_errors = []
    for err in exc.errors():
        loc = " -> ".join(str(item) for item in err.get("loc", []) if item != "body")
        msg = err.get("msg", "Dữ liệu không hợp lệ")
        field_errors.append({"field": loc or "input", "message": msg})

    first_msg = (
        f"Dữ liệu đầu vào chưa hợp lệ ({field_errors[0]['field']}: {field_errors[0]['message']})."
        if field_errors
        else "Dữ liệu gửi lên không đúng định dạng yêu cầu."
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "detail": first_msg,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": first_msg,
                "details": field_errors,
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Lỗi hệ thống chưa được xử lý tại %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "detail": "Hệ thống đang gặp sự cố tạm thời. Vui lòng thử lại sau ít phút.",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Hệ thống đang gặp sự cố tạm thời. Vui lòng thử lại sau ít phút.",
                "details": [],
            },
        },
    )


# Nhúng các Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(versions_router)
app.include_router(templates_router)
app.include_router(deployments_router)
app.include_router(deployments_router, prefix="/api/v1")

# Projects router hỗ trợ cả 2 tiền tố: /projects/{id} và /api/v1/projects/{id}
app.include_router(projects_router)
app.include_router(projects_router, prefix="/api/v1")


STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)