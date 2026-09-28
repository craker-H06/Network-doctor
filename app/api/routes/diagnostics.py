"""Routes de diagnostic. Chaque appel nomme sa cible."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.core.errors import PingExecutionError, TargetRejectedError
from app.schemas.diagnostic import PingRequest, PingResponse, ScopeResponse
from app.services.ping_service import run_availability_check

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/scope", response_model=ScopeResponse)
def read_scope(settings: Settings = Depends(get_settings)) -> ScopeResponse:
    """Expose le périmètre autorisé pour la console de laboratoire."""
    return ScopeResponse(
        allowed_networks=[str(network) for network in settings.allowed_network_objects()],
        allow_public_targets=settings.allow_public_targets,
        max_ping_count=settings.max_ping_count,
        ping_timeout_seconds=settings.ping_timeout_seconds,
    )


@router.post(
    "/ping",
    response_model=PingResponse,
    responses={
        400: {"description": "Cible refusée"},
        503: {"description": "ICMP indisponible sur le système"},
    },
)
def ping_target(
    body: PingRequest,
    settings: Settings = Depends(get_settings),
) -> PingResponse:
    """Vérifie la cible, puis contrôle sa disponibilité ICMP."""
    try:
        result = run_availability_check(body.target, count=body.count, settings=settings)
    except TargetRejectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PingExecutionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return PingResponse.model_validate(asdict(result))
