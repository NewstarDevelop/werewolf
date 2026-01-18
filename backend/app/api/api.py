"""API router aggregation."""
from fastapi import APIRouter

from app.api.endpoints import game, room, auth, users, websocket, game_history, config

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(config.router)
api_router.include_router(game.router)
api_router.include_router(room.router)
api_router.include_router(websocket.router)
api_router.include_router(game_history.router)
