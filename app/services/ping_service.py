"""Contrôle de disponibilité ICMP d'un hôte déjà autorisé.

La commande est une liste d'arguments, sans interpréteur de shell.
Seule l'adresse canonique validée est transmise à ping.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.core.config import Settings
from app.core.errors import PingExecutionError, TargetRejectedError
from app.services.target_validator import Resolver, ValidatedHost, prepare_host

Runner = Callable[[Sequence[str], float], subprocess.CompletedProcess[str]]

_LINUX_AVG_RE = re.compile(r"=\s*[\d.,]+/([\d.,]+)/")
_NAMED_AVG_RE = re.compile(
    r"(?:Average|Moyenne)\s*=\s*(\d+(?:[.,]\d+)?)\s*ms",
    re.IGNORECASE,
)
_SAMPLE_RE = re.compile(
    r"(?:time|temps)[=<]\s*(\d+(?:[.,]\d+)?)\s*ms",
    re.IGNORECASE,
)
_RECEIVED_PATTERNS = (
    re.compile(r"(\d+)\s+received", re.IGNORECASE),
    re.compile(r"(\d+)\s+reçus", re.IGNORECASE),
    re.compile(r"Received\s*=\s*(\d+)", re.IGNORECASE),
    re.compile(r"reçus\s*=\s*(\d+)", re.IGNORECASE),
)
_FORBIDDEN_MARKERS = (
    "operation not permitted",
    "permission denied",
    "accès refusé",
    "privilèges",
)


@dataclass(frozen=True)
class PingResult:
    """Résultat lisible d'un contrôle de disponibilité."""

    target: str
    resolved_ip: str
    reachable: bool
    packets_sent: int
    packets_received: int
    latency_ms: float | None
    detail: str


def run_availability_check(
    target: str,
    *,
    count: int,
    settings: Settings,
    runner: Runner | None = None,
    resolver: Resolver | None = None,
    system: str | None = None,
) -> PingResult:
    """Valide la cible, puis envoie au plus quelques paquets ICMP."""
    if runner is None:
        runner = default_runner
    _assert_count(count, settings.max_ping_count)
    host = prepare_host(
        target,
        settings.allowed_network_objects(),
        allow_public=settings.allow_public_targets,
        resolver=resolver,
    )
    command = build_ping_command(
        str(host.ip),
        count=count,
        timeout_seconds=settings.ping_timeout_seconds,
        system=system or sys.platform,
    )
    budget = float(settings.ping_timeout_seconds * count + 2)
    try:
        completed = runner(command, budget)
    except subprocess.TimeoutExpired as exc:
        raise PingExecutionError("Le contrôle de disponibilité a expiré.") from exc
    except FileNotFoundError as exc:
        raise PingExecutionError(
            "La commande ping est introuvable. Installez iputils-ping."
        ) from exc
    return interpret_ping(host, completed, packets_sent=count)


def build_ping_command(
    ip: str,
    *,
    count: int,
    timeout_seconds: int,
    system: str,
) -> list[str]:
    """Construit l'appel ping propre au système, sans option fournie par l'utilisateur."""
    if not isinstance(count, int) or isinstance(count, bool):
        raise PingExecutionError("Paramètre count invalide.")
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        raise PingExecutionError("Paramètre timeout invalide.")
    family = "-6" if ":" in ip else "-4"
    if system == "win32":
        return ["ping", family, "-n", str(count), "-w", str(timeout_seconds * 1000), ip]
    return ["ping", family, "-c", str(count), "-W", str(timeout_seconds), ip]


def interpret_ping(
    host: ValidatedHost,
    completed: subprocess.CompletedProcess[str],
    *,
    packets_sent: int,
) -> PingResult:
    """Traduit la sortie de ping en résultat de diagnostic."""
    output = f"{completed.stdout or ''}\n{completed.stderr or ''}"
    if _icmp_forbidden(output):
        raise PingExecutionError(
            "Le système refuse l'envoi ICMP. Sous Docker, ajoutez la capacité NET_RAW."
        )
    if completed.returncode not in (0, 1):
        raise PingExecutionError("La commande ping a échoué.")

    received = extract_received_count(output)
    reachable = completed.returncode == 0 and (received is None or received > 0)
    if received is None:
        received = packets_sent if reachable else 0
    if received == 0:
        reachable = False

    return PingResult(
        target=host.original,
        resolved_ip=str(host.ip),
        reachable=reachable,
        packets_sent=packets_sent,
        packets_received=received,
        latency_ms=extract_latency_ms(output) if reachable else None,
        detail="L'hôte répond à ICMP." if reachable else "L'hôte ne répond pas à ICMP.",
    )


def extract_latency_ms(output: str) -> float | None:
    """Retourne la latence moyenne en millisecondes lorsque la sortie la contient."""
    linux_avg = _LINUX_AVG_RE.search(output)
    if linux_avg:
        return _to_float(linux_avg.group(1))
    named_avg = _NAMED_AVG_RE.search(output)
    if named_avg:
        return _to_float(named_avg.group(1))
    samples = [_to_float(value) for value in _SAMPLE_RE.findall(output)]
    if not samples:
        return None
    return round(sum(samples) / len(samples), 3)


def extract_received_count(output: str) -> int | None:
    """Retourne le nombre de réponses ICMP, ou None si le format est inconnu."""
    for pattern in _RECEIVED_PATTERNS:
        match = pattern.search(output)
        if match:
            return int(match.group(1))
    return None


def default_runner(
    command: Sequence[str],
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Exécute ping sans shell."""
    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _assert_count(count: int, maximum: int) -> None:
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= maximum:
        raise TargetRejectedError("Nombre de paquets hors limite.")


def _icmp_forbidden(output: str) -> bool:
    lowered = output.lower()
    return any(marker in lowered for marker in _FORBIDDEN_MARKERS)


def _to_float(value: str) -> float:
    return float(value.replace(",", "."))
