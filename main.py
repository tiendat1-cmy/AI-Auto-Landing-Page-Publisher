from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from api.health import router as health_router
from core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)
templates = Jinja2Templates(directory="templates")

# Include API router
app.include_router(health_router)

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "AI Publisher Dashboard"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)