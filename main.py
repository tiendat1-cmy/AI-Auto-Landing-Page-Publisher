from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("base.html", {"request": request, "title": "Dashboard"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)