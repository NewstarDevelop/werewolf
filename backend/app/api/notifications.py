from fastapi import APIRouter

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
async def list_notifications():
    return {"items": [], "total": 0, "page": 1, "page_size": 20}


@router.post("/{notification_id}/read")
async def mark_read(notification_id: int):
    return {"message": "Not implemented"}
