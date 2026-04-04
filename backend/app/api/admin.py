from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users():
    return {"items": [], "total": 0, "page": 1, "page_size": 20}
