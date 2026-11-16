import os
import sys
from pathlib import Path

# Đảm bảo đường dẫn thư mục backend luôn nằm trong sys.path
backend_root = os.path.dirname(os.path.abspath(__file__))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.auth import router as auth_router
from api.health import router as health_router
from api.projects import router as projects_router
from api.versions import router as versions_router
from core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

# Cấu hình CORS để Frontend tương tác mượt mà
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# Nhúng các Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(versions_router)

# Mount thư mục Frontend làm static files
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

# Endpoint tiện ích điều hướng nhanh tới form chỉnh sửa landing page
@app.get("/edit")
@app.get("/projects/{project_id}/edit")
async def edit_page(project_id: int = 1):
    return RedirectResponse(url=f"/frontend/pages/edit-project.html?project_id={project_id}")

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"title": "AI Publisher Dashboard"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
