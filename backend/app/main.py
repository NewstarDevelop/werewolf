from fastapi import FastAPI

from app.ws.routes import router as ws_router


def create_app() -> FastAPI:
    app = FastAPI(title="Werewolf Backend", version="0.1.0")

    @app.get("/health", tags=["system"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(ws_router)

    return app


app = create_app()
