from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from api.health import router as health_router
from api.auth import router as auth_router
from api.versions import router as versions_router
from core.config import settings
from fastapi.middleware.cors import CORSMiddleware
from api.projects import router as projects_router



app = FastAPI(title=settings.PROJECT_NAME)
templates = Jinja2Templates(directory="templates")


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