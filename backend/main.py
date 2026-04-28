import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.runs import router as runs_router
from backend.api.jobs import router as jobs_router


def create_app() -> FastAPI:
    app = FastAPI(title="News Consensus API", version="0.1.0")

    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(runs_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")

    return app


app = create_app()

