"""Contrôle ICMP : construction de commande, lecture de sortie, refus avant exécution."""

from __future__ import annotations

import ipaddress
import subprocess

import pytest

from app.core.config import Settings
from app.core.errors import PingExecutionError, TargetRejectedError
from app.services.ping_service import (
    build_ping_command,
    default_runner,
    extract_latency_ms,
    extract_received_count,
    interpret_ping,
    run_availability_check,
)
from app.services.target_validator import ValidatedHost

LINUX_OK = """
PING 10.1.1.1 (10.1.1.1) 56(84) bytes of data.
64 bytes from 10.1.1.1: icmp_seq=1 ttl=64 time=0.42 ms

--- 10.1.1.1 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 0.420/0.420/0.420/0.000 ms
"""

LINUX_DOWN = """
1 packets transmitted, 0 received, 100% packet loss, time 0ms
"""

WINDOWS_FR_OK = """
Réponse de 10.1.1.1 : octets=32 temps=2 ms TTL=128
    Paquets : envoyés = 1, reçus = 1, perdus = 0 (perte 0%),
    Minimum = 2ms, Maximum = 2ms, Moyenne = 2ms
"""

LAB = Settings(
    allowed_networks="10.0.0.0/8,127.0.0.0/8",
    allow_public_targets=False,
    ping_timeout_seconds=2,
    max_ping_count=4,
)


def test_linux_command_is_a_fixed_argument_list() -> None:
    command = build_ping_command("10.1.1.1", count=2, timeout_seconds=2, system="linux")

    assert command == ["ping", "-4", "-c", "2", "-W", "2", "10.1.1.1"]


def test_windows_command_uses_milliseconds() -> None:
    command = build_ping_command("10.1.1.1", count=1, timeout_seconds=2, system="win32")

    assert command == ["ping", "-4", "-n", "1", "-w", "2000", "10.1.1.1"]


def test_ipv6_command_selects_the_matching_family() -> None:
    command = build_ping_command("fd00::10", count=1, timeout_seconds=1, system="linux")

    assert command[1] == "-6"
    assert command[-1] == "fd00::10"


def test_parser_reads_linux_success() -> None:
    assert extract_received_count(LINUX_OK) == 1
    assert extract_latency_ms(LINUX_OK) == 0.42


def test_parser_reads_french_windows_success() -> None:
    assert extract_received_count(WINDOWS_FR_OK) == 1
    assert extract_latency_ms(WINDOWS_FR_OK) == 2.0


def test_interpret_success_and_failure() -> None:
    host = ValidatedHost(original="10.1.1.1", ip=ipaddress.ip_address("10.1.1.1"))
    success = subprocess.CompletedProcess(["ping"], 0, stdout=LINUX_OK, stderr="")
    failure = subprocess.CompletedProcess(["ping"], 1, stdout=LINUX_DOWN, stderr="")

    reached = interpret_ping(host, success, packets_sent=1)
    missed = interpret_ping(host, failure, packets_sent=1)

    assert reached.reachable is True
    assert reached.latency_ms == 0.42
    assert missed.reachable is False
    assert missed.latency_ms is None
    assert missed.packets_received == 0


def test_permission_error_is_not_reported_as_host_down() -> None:
    host = ValidatedHost(original="10.1.1.1", ip=ipaddress.ip_address("10.1.1.1"))
    completed = subprocess.CompletedProcess(
        ["ping"],
        2,
        stdout="",
        stderr="ping: socket: Operation not permitted",
    )

    with pytest.raises(PingExecutionError, match="NET_RAW"):
        interpret_ping(host, completed, packets_sent=1)


def test_rejected_target_never_calls_ping() -> None:
    def explode(_command, _timeout):
        raise AssertionError("ping ne doit pas être exécuté")

    with pytest.raises(TargetRejectedError):
        run_availability_check("8.8.8.8", count=1, settings=LAB, runner=explode)


def test_hostname_is_replaced_by_the_authorized_ip() -> None:
    captured: dict[str, list[str]] = {}

    def resolver(_hostname: str):
        return [ipaddress.ip_address("8.8.8.8"), ipaddress.ip_address("10.8.0.4")]

    def runner(command, _timeout):
        captured["command"] = list(command)
        return subprocess.CompletedProcess(command, 0, stdout=LINUX_OK, stderr="")

    result = run_availability_check(
        "printer.lab",
        count=1,
        settings=LAB,
        runner=runner,
        resolver=resolver,
        system="linux",
    )

    assert captured["command"][-1] == "10.8.0.4"
    assert "printer.lab" not in captured["command"]
    assert result.resolved_ip == "10.8.0.4"
    assert result.reachable is True


def test_count_above_the_configured_maximum_is_rejected() -> None:
    with pytest.raises(TargetRejectedError, match="limite"):
        run_availability_check("10.1.1.1", count=5, settings=LAB, runner=lambda *_: None)


def test_default_runner_passes_a_list_without_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("app.services.ping_service.subprocess.run", fake_run)
    default_runner(["ping", "-4", "-c", "1", "-W", "1", "127.0.0.1"], 3)

    assert captured["command"] == ["ping", "-4", "-c", "1", "-W", "1", "127.0.0.1"]
    assert "shell" not in captured["kwargs"]
