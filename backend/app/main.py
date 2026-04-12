import logging

from fastapi import FastAPI

from app.ws.routes import router as ws_router


def configure_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if root_logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"),
    )
    root_logger.addHandler(handler)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Werewolf Backend", version="0.1.0")

    @app.get("/health", tags=["system"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(ws_router)

    return app


app = create_app()
