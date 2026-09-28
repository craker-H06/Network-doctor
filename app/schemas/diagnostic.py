"""Contrats du contrôle de disponibilité."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PingRequest(BaseModel):
    """Demande explicite de contrôle d'un seul hôte."""

    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=1, max_length=253)
    count: int = Field(default=1, ge=1, le=4)


class PingResponse(BaseModel):
    """Compte rendu d'un contrôle ICMP."""

    target: str
    resolved_ip: str
    reachable: bool
    packets_sent: int
    packets_received: int
    latency_ms: float | None
    detail: str


class ScopeResponse(BaseModel):
    """Périmètre affiché par la console, sans donnée sensible."""

    allowed_networks: list[str]
    allow_public_targets: bool
    max_ping_count: int
    ping_timeout_seconds: int
