from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Werewolf Backend", version="0.1.0")

    @app.get("/health", tags=["system"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
