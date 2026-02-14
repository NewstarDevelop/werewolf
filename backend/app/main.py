"""FastAPI application entry point."""
import asyncio
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.api import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.services.log_manager import init_game_logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    # ── Startup ──
    background_tasks: list[asyncio.Task] = []
    await _startup(background_tasks)
    yield
    # ── Shutdown ──
    await _shutdown(background_tasks)


app = FastAPI(
    title="Werewolf AI Game API",
    description="狼人杀 AI 游戏后端 API",
    version="1.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# T-SEC-005: CORS configuration from environment
# Use CORS_ORIGINS env var to specify allowed origins (comma-separated)
# If "*", credentials are automatically disabled per CORS spec
# MINOR FIX: Explicitly specify allowed methods and headers to minimize attack surface
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
)

# Include API routes
app.include_router(api_router)


# ── Global Exception Handlers ──

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Convert AppException subclasses to structured JSON responses."""
    return JSONResponse(
        status_code=exc.http_status,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler to prevent stack trace leaking in production."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred." if not settings.DEBUG else str(exc),
            "details": {},
        },
    )


async def _startup(background_tasks: list[asyncio.Task]):
    """Log startup information and initialize services."""
    logger.info("Werewolf AI Game API starting up...")

    # A4-FIX: 生产环境安全配置 fail-fast
    # 调用 settings 的安全配置校验，获取 warnings 和 errors
    security_warnings, security_errors = settings._validate_security_config()

    # P1-4 Fix: Validate critical configuration at startup
    config_warnings = []
    config_errors = []

    # A4-FIX: 将安全配置错误添加到 config_errors
    config_warnings.extend(security_warnings)
    config_errors.extend(security_errors)

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

    # Check AI Analysis configuration (separate from game AI)
    analysis_provider = settings.get_analysis_provider()
    if not analysis_provider:
        config_warnings.append(
            "AI analysis is not configured. Analysis will use fallback mode (basic statistics only). "
            "To enable AI analysis: "
            "1) Set OPENAI_API_KEY in .env, OR "
            "2) Configure another provider (e.g., DEEPSEEK_API_KEY) and set ANALYSIS_PROVIDER=deepseek"
        )

    # Log warnings
    for warning in config_warnings:
        logger.warning(f"⚠️ Config Warning: {warning}")

    # Log errors and exit if critical
    for error in config_errors:
        logger.error(f"❌ Config Error: {error}")

    if config_errors:
        logger.error("=" * 60)
        logger.error("FATAL: Security configuration errors detected")
        logger.error("=" * 60)
        for i, error in enumerate(config_errors, 1):
            logger.error(f"  {i}. {error}")
        logger.error("=" * 60)
        logger.error("Please fix the above errors in your .env file before starting.")
        logger.error("In development, set DEBUG=true to bypass strict validation.")
        logger.error("=" * 60)
        raise RuntimeError(
            f"Critical security configuration errors ({len(config_errors)} issues). "
            "Check logs for details."
        )

    logger.info(f"LLM Model: {settings.LLM_MODEL}")
    logger.info(f"LLM Mock Mode: {settings.LLM_USE_MOCK}")
    if settings.OPENAI_API_KEY:
        logger.info("OpenAI API Key: configured")
    else:
        logger.warning("OpenAI API Key: NOT configured - using mock mode")

    # NOTE: Database initialization and migrations are now handled in entrypoint.sh
    # before server startup. This ensures:
    # 1. Base tables are created (init_database)
    # 2. Schema migrations are applied (alembic upgrade head)
    # 3. Health checks don't fail during migration

    # Recover game state from persistence snapshots (crash recovery)
    from app.models.game import game_store
    try:
        recovered = game_store.recover_from_snapshots()
        if recovered:
            logger.info(f"Recovered {recovered} game(s) from persistence snapshots")
    except Exception as e:
        logger.warning(f"Game snapshot recovery failed (non-fatal): {e}")

    # WL-011 Fix: Reset orphaned rooms after restart
    # Only reset rooms whose games were NOT recovered from snapshots
    from app.core.database_async import AsyncSessionLocal
    from app.services.room_manager import room_manager

    async with AsyncSessionLocal() as db:
        try:
            reset_count = await room_manager.reset_orphaned_rooms(db)
            if reset_count > 0:
                logger.warning(
                    f"WL-011: Reset {reset_count} orphaned room(s) from PLAYING to WAITING. "
                    "Game state was lost due to server restart."
                )
        except Exception as e:
            logger.error(f"Failed to reset orphaned rooms: {e}")

    # Initialize game logging
    init_game_logging()
    logger.info("Game logging initialized")

    # Start cross-instance game broadcaster (Redis Pub/Sub)
    from app.storage.game_broadcaster import GameUpdateBroadcaster
    from app.services.websocket_manager import websocket_manager
    import app.storage.game_broadcaster as gb_module
    broadcaster = GameUpdateBroadcaster(websocket_manager)
    await broadcaster.start()
    gb_module.game_broadcaster = broadcaster

    # FIX: Start background task for periodic rate limiter cleanup
    task1 = asyncio.create_task(_periodic_rate_limiter_cleanup())
    background_tasks.append(task1)
    logger.info("Rate limiter cleanup task started")

    # FIX: Start background task for periodic game store cleanup
    task2 = asyncio.create_task(_periodic_game_store_cleanup())
    background_tasks.append(task2)
    logger.info("Game store cleanup task started")

    # Start background task for periodic DB token/state cleanup
    task3 = asyncio.create_task(_periodic_db_token_cleanup())
    background_tasks.append(task3)
    logger.info("DB token cleanup task started")


async def _periodic_rate_limiter_cleanup():
    """Background task to periodically clean up expired rate limit records.

    Runs every hour to prevent memory leaks from accumulated login attempt records.
    """
    from app.services.login_rate_limiter import admin_login_limiter, user_login_limiter

    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour

            # Clean up both limiters
            admin_cleaned = admin_login_limiter.cleanup_expired()
            user_cleaned = user_login_limiter.cleanup_expired()

            if admin_cleaned > 0 or user_cleaned > 0:
                logger.info(
                    f"Rate limiter cleanup: admin={admin_cleaned}, user={user_cleaned} records removed"
                )
        except Exception as e:
            logger.error(f"Error in rate limiter cleanup task: {e}")
            # Continue running even if cleanup fails
            await asyncio.sleep(60)  # Wait 1 minute before retry


async def _periodic_game_store_cleanup():
    """Background task to periodically clean up expired games.

    Runs every 30 minutes to prevent memory leaks from abandoned games.
    This complements the on-demand cleanup in create_game().
    """
    from app.models.game import game_store

    while True:
        try:
            await asyncio.sleep(1800)  # Run every 30 minutes

            # Clean up expired games
            cleaned = game_store._cleanup_old_games()

            if cleaned > 0:
                logger.info(
                    f"Game store cleanup: {cleaned} expired game(s) removed. "
                    f"Active games: {game_store.game_count}"
                )
            else:
                logger.debug(f"Game store cleanup: no expired games. Active: {game_store.game_count}")

        except Exception as e:
            logger.error(f"Error in game store cleanup task: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retry


async def _periodic_db_token_cleanup():
    """Background task to clean up expired OAuthState and RefreshToken records.

    Runs every 6 hours to prevent unbounded table growth from accumulated
    expired OAuth states and revoked/expired refresh tokens.
    """
    from app.core.database_async import AsyncSessionLocal
    from app.models.user import OAuthState, RefreshToken
    from sqlalchemy import delete

    while True:
        try:
            await asyncio.sleep(21600)  # Run every 6 hours

            now = datetime.now(timezone.utc)
            async with AsyncSessionLocal() as db:
                # Clean up expired OAuth states (> 10 min old, should be used or expired)
                oauth_result = await db.execute(
                    delete(OAuthState).where(OAuthState.expires_at < now)
                )
                oauth_cleaned = oauth_result.rowcount or 0

                # Clean up expired or revoked refresh tokens
                refresh_result = await db.execute(
                    delete(RefreshToken).where(RefreshToken.expires_at < now)
                )
                refresh_cleaned = refresh_result.rowcount or 0

                await db.commit()

            if oauth_cleaned > 0 or refresh_cleaned > 0:
                logger.info(
                    f"DB token cleanup: oauth_states={oauth_cleaned}, "
                    f"refresh_tokens={refresh_cleaned} expired records removed"
                )
        except Exception as e:
            logger.error(f"Error in DB token cleanup task: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retry


async def _shutdown(background_tasks: list[asyncio.Task]):
    """
    A7-FIX: Clean up resources on shutdown.

    Ensures LLM clients and other async resources are properly closed
    to prevent resource leaks (unclosed httpx connection pools).
    """
    logger.info("Werewolf AI Game API shutting down...")

    # MINOR FIX: Cancel and wait for background tasks
    if background_tasks:
        logger.info(f"Cancelling {len(background_tasks)} background task(s)...")
        for task in background_tasks:
            task.cancel()

        # Wait for all tasks to complete cancellation
        await asyncio.gather(*background_tasks, return_exceptions=True)
        logger.info("Background tasks cancelled")

    # Close game engine (which closes LLM clients)
    from app.services.game_engine import game_engine
    try:
        await game_engine.close()
        logger.info("Game engine closed successfully")
    except Exception as e:
        logger.warning(f"Error closing game engine: {e}")

    # Close async database connections
    from app.core.database_async import close_async_db
    try:
        await close_async_db()
    except Exception as e:
        logger.warning(f"Error closing async database: {e}")

    # Stop game broadcaster
    from app.storage.game_broadcaster import game_broadcaster
    if game_broadcaster:
        try:
            await game_broadcaster.stop()
            logger.info("Game broadcaster stopped")
        except Exception as e:
            logger.warning(f"Error stopping game broadcaster: {e}")

    # Close Redis connections if any
    from app.services.notification_emitter import _publisher, _publisher_initialized
    if _publisher_initialized and _publisher:
        try:
            await _publisher.close()
            logger.info("Redis publisher closed successfully")
        except Exception as e:
            logger.warning(f"Error closing Redis publisher: {e}")

    logger.info("Shutdown complete")


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
