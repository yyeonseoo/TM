import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.runs import router as runs_router
from backend.api.jobs import router as jobs_router


def _try_load_dotenv() -> None:
    """
    Load local env file if present.
    Keeps the project runnable without exporting env vars in the shell.
    """
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)
    except Exception:
        # If python-dotenv isn't installed, we just fall back to real environment variables.
        pass


def create_app() -> FastAPI:
    _try_load_dotenv()
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

