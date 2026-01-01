"""API router aggregation."""
from fastapi import APIRouter

from app.api.endpoints import game, room, auth, users

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(game.router)
api_router.include_router(room.router)
