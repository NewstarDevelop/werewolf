"""API router aggregation."""
from fastapi import APIRouter

from app.api.endpoints import admin, admin_broadcasts, auth, config, game, game_history, notifications, room, users, websocket, websocket_notifications

api_router = APIRouter(prefix="/api")
api_router.include_router(admin.router)
api_router.include_router(admin_broadcasts.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(config.router)
api_router.include_router(game.router)
api_router.include_router(room.router)
api_router.include_router(websocket.router)
api_router.include_router(websocket_notifications.router)
api_router.include_router(game_history.router)
api_router.include_router(notifications.router)
