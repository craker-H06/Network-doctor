"""Point d'entrée HTTP de Network Doctor."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes.diagnostics import router as diagnostics_router
from app.core.config import get_settings

PACKAGE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    """Construit l'application. La configuration invalide empêche le démarrage."""
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="Diagnostic réseau défensif pour un laboratoire ou un réseau autorisé.",
    )

    @application.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "network-doctor"}

    @application.get("/", include_in_schema=False)
    def console() -> FileResponse:
        return FileResponse(PACKAGE_DIR / "templates" / "index.html")

    application.mount(
        "/static",
        StaticFiles(directory=PACKAGE_DIR / "static"),
        name="static",
    )
    application.include_router(diagnostics_router, prefix="/api/v1")
    return application


app = create_app()
