from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from api.health import router as health_router
from core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)
templates = Jinja2Templates(directory="templates")

app.include_router(health_router)

@app.get("/")
async def home(request: Request):
    # Sửa dòng này: Thêm rõ ràng name= và context=
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"title": "AI Publisher Dashboard"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)