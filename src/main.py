from fastapi import FastAPI
from src.api.v1.system import router as system_router


def create_app() -> FastAPI:
    app = FastAPI(title="Autoderm API", version="1.1.0")
    app.include_router(system_router, prefix="/api/v1/system", tags=["system"])
    return app


app = create_app()
