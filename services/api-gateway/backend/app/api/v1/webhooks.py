from fastapi import APIRouter

router = APIRouter()

@router.post("/replicate")
async def replicate_webhook(data: dict):
    return {"status": "received"}
