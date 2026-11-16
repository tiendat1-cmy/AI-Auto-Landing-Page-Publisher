import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from api.health import router as health_router
from api.auth import router as auth_router
from api.versions import router as versions_router
from api.templates import router as templates_router
from core.config import settings
from fastapi.middleware.cors import CORSMiddleware
from api.projects import router as projects_router



app = FastAPI(title=settings.PROJECT_NAME)
templates = Jinja2Templates(directory="templates")

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Nhúng các Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(versions_router)
app.include_router(projects_router)
app.include_router(templates_router)

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