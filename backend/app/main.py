"""FastAPI application entry point."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.api import api_router
from app.core.config import settings
from app.services.log_manager import init_game_logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Werewolf AI Game API",
    description="狼人杀 AI 游戏后端 API",
    version="1.0.0",
    debug=settings.DEBUG,
)

# T-SEC-005: CORS configuration from environment
# Use CORS_ORIGINS env var to specify allowed origins (comma-separated)
# If "*", credentials are automatically disabled per CORS spec
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.on_event("startup")
async def startup_event():
    """Log startup information and initialize services."""
    logger.info("Werewolf AI Game API starting up...")

    # P1-4 Fix: Validate critical configuration at startup
    config_warnings = []
    config_errors = []

    # Check JWT_SECRET_KEY (optional for development)
    if not settings.JWT_SECRET_KEY:
        config_warnings.append(
            "JWT_SECRET_KEY is not configured. "
            "Authentication will fail. Please set JWT_SECRET_KEY in .env"
        )

    # Check LLM configuration
    if not settings.OPENAI_API_KEY and not settings.LLM_USE_MOCK:
        config_warnings.append(
            "No LLM API key configured and mock mode disabled. "
            "AI features may not work properly."
        )

    # Check ADMIN_KEY (optional but recommended)
    if not settings.ADMIN_KEY:
        config_warnings.append(
            "ADMIN_KEY is not configured. "
            "Admin endpoints will only work via JWT admin token."
        )

    # Log warnings
    for warning in config_warnings:
        logger.warning(f"⚠️ Config Warning: {warning}")

    # Log errors and exit if critical
    for error in config_errors:
        logger.error(f"❌ Config Error: {error}")

    if config_errors:
        logger.error("Critical configuration missing. Please check your .env file.")
        logger.error("=" * 60)
        logger.error("FATAL: Cannot start server with missing critical configuration")
        logger.error("=" * 60)
        raise RuntimeError(
            "Critical configuration missing. "
            "Please set JWT_SECRET_KEY in .env file before starting the server."
        )

    logger.info(f"LLM Model: {settings.LLM_MODEL}")
    logger.info(f"LLM Mock Mode: {settings.LLM_USE_MOCK}")
    if settings.OPENAI_API_KEY:
        logger.info("OpenAI API Key: configured")
    else:
        logger.warning("OpenAI API Key: NOT configured - using mock mode")

    # Initialize database
    from app.init_db import init_database
    init_database()

    # WL-011 Fix: Reset orphaned rooms after restart
    # Since game state is stored in-memory, rooms in PLAYING state
    # after restart have lost their game objects and must be reset
    from app.core.database import SessionLocal
    from app.services.room_manager import room_manager

    db = SessionLocal()
    try:
        reset_count = room_manager.reset_orphaned_rooms(db)
        if reset_count > 0:
            logger.warning(
                f"WL-011: Reset {reset_count} orphaned room(s) from PLAYING to WAITING. "
                "Game state was lost due to server restart."
            )
    except Exception as e:
        logger.error(f"Failed to reset orphaned rooms: {e}")
    finally:
        db.close()

    # Initialize game logging
    init_game_logging()
    logger.info("Game logging initialized")


@app.get("/")
def root():
    """Root endpoint - health check."""
    return {
        "status": "ok",
        "message": "Werewolf AI Game API is running",
        "version": "1.0.0",
        "llm_mode": "mock" if settings.LLM_USE_MOCK or not settings.OPENAI_API_KEY else "real",
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
