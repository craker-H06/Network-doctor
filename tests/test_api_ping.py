"""API du contrôle de disponibilité."""

from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from app.services import ping_service

LINUX_OK = """
1 packets transmitted, 1 received, 0% packet loss
rtt min/avg/max/mdev = 1.200/1.200/1.200/0.000 ms
"""


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    def fake_runner(command, _timeout):
        return subprocess.CompletedProcess(list(command), 0, stdout=LINUX_OK, stderr="")

    monkeypatch.setattr(ping_service, "default_runner", fake_runner)
    app.dependency_overrides[get_settings] = lambda: Settings(
        allowed_networks="10.0.0.0/8,127.0.0.0/8",
        allow_public_targets=False,
        ping_timeout_seconds=2,
        max_ping_count=4,
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_console_page(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Console de laboratoire" in response.text
    assert "/static/lab.js" in response.text


def test_console_stylesheet(client: TestClient) -> None:
    response = client.get("/static/lab.css")

    assert response.status_code == 200
    assert "color-scheme: dark" in response.text


def test_scope_lists_authorized_networks(client: TestClient) -> None:
    response = client.get("/api/v1/diagnostics/scope")

    assert response.status_code == 200
    body = response.json()
    assert "10.0.0.0/8" in body["allowed_networks"]
    assert body["allow_public_targets"] is False
    assert body["max_ping_count"] == 4


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ping_authorized_host(client: TestClient) -> None:
    response = client.post("/api/v1/diagnostics/ping", json={"target": "10.1.1.1"})

    assert response.status_code == 200
    body = response.json()
    assert body["resolved_ip"] == "10.1.1.1"
    assert body["reachable"] is True
    assert body["latency_ms"] == 1.2
    assert body["packets_sent"] == 1


def test_ping_rejects_a_public_target(client: TestClient) -> None:
    response = client.post("/api/v1/diagnostics/ping", json={"target": "8.8.8.8"})

    assert response.status_code == 400
    assert "publiques" in response.json()["detail"]


def test_ping_rejects_extra_fields(client: TestClient) -> None:
    response = client.post(
        "/api/v1/diagnostics/ping",
        json={"target": "10.1.1.1", "options": "-f"},
    )

    assert response.status_code == 422


def test_ping_requires_a_target(client: TestClient) -> None:
    response = client.post("/api/v1/diagnostics/ping", json={})

    assert response.status_code == 422
