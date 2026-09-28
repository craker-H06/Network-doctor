"""Le contrôle ICMP loopback confirme que la commande réelle fonctionne."""

from __future__ import annotations

import shutil

import pytest

from app.core.config import Settings
from app.services.ping_service import run_availability_check

pytestmark = pytest.mark.skipif(shutil.which("ping") is None, reason="ping est absent")


def test_loopback_answers_icmp() -> None:
    settings = Settings(
        allowed_networks="127.0.0.0/8",
        allow_public_targets=False,
        ping_timeout_seconds=2,
        max_ping_count=1,
    )

    result = run_availability_check("127.0.0.1", count=1, settings=settings)

    assert result.resolved_ip == "127.0.0.1"
    assert result.reachable is True
    assert result.packets_received >= 1
