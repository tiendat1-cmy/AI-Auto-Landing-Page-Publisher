from fastapi import APIRouter

router = APIRouter()

@router.get("/api/health")
async def health_check():
    return {
        "status": "success",
        "message": "FastAPI Server & MySQL Engine đã sẵn sàng!",
        "project": "AI Auto-Landing Page Publisher"
    }