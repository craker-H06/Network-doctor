"""Vérifie qu'une cible explicite appartient au périmètre autorisé.

Le diagnostic ne part jamais d'une découverte. L'administrateur nomme un hôte.
Une plage, une adresse spéciale ou une destination hors liste est refusée
avant tout appel système.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.core.errors import TargetRejectedError

_HOSTNAME_RE = re.compile(
    r"(?=.{1,253}$)"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)"
    r"(?:\.(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?))*$"
)
_DOTTED_QUAD_RE = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}")
_MIN_PREFIX = {4: 8, 6: 7}

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network
Resolver = Callable[[str], Sequence[IPAddress]]


@dataclass(frozen=True)
class ValidatedHost:
    """Hôte accepté, réduit à une adresse canonique."""

    original: str
    ip: IPAddress


def parse_allowed_networks(raw: str) -> tuple[IPNetwork, ...]:
    """Transforme la configuration en réseaux, ou lève ValueError si elle est dangereuse."""
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        raise ValueError("ALLOWED_NETWORKS est vide.")

    networks: list[IPNetwork] = []
    for part in parts:
        try:
            network = ipaddress.ip_network(part, strict=False)
        except ValueError as exc:
            raise ValueError(f"Réseau autorisé invalide : {part}") from exc
        _reject_oversized_or_special_network(network)
        networks.append(network)
    return tuple(networks)


def prepare_host(
    raw: str,
    networks: Sequence[IPNetwork],
    *,
    allow_public: bool,
    resolver: Resolver | None = None,
) -> ValidatedHost:
    """Accepte un seul hôte autorisé. N'appelle le résolveur que pour un nom valide."""
    if resolver is None:
        resolver = _resolve_hostname
    value = _normalize_target(raw)
    if "/" in value:
        raise TargetRejectedError("Indiquez un seul hôte, sans masque réseau.")

    ip = _parse_ip(value)
    if ip is not None:
        assert_ip_authorized(ip, networks, allow_public=allow_public)
        return ValidatedHost(original=value, ip=ip)

    if _DOTTED_QUAD_RE.fullmatch(value):
        raise TargetRejectedError("Adresse IPv4 invalide.")
    if not _HOSTNAME_RE.fullmatch(value):
        raise TargetRejectedError("Cible invalide : adresse IP ou nom d'hôte attendu.")

    addresses = list(resolver(value))
    if not addresses:
        raise TargetRejectedError("Le nom d'hôte ne peut pas être résolu.")
    selected = _first_authorized(addresses, networks, allow_public=allow_public)
    return ValidatedHost(original=value, ip=selected)


def assert_ip_authorized(
    ip: IPAddress,
    networks: Sequence[IPNetwork],
    *,
    allow_public: bool,
) -> None:
    """Refuse les adresses spéciales, publiques par défaut, et celles hors liste."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.scope_id is not None:
        raise TargetRejectedError("Les identifiants de zone IPv6 ne sont pas acceptés.")
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        raise TargetRejectedError("Les adresses IPv4-mappées ne sont pas acceptées.")
    if ip.is_unspecified or ip.is_multicast or ip.is_reserved or ip.is_link_local:
        raise TargetRejectedError("Cette adresse ne peut pas être diagnostiquée.")
    if ip.is_global and not allow_public:
        raise TargetRejectedError(
            "Les cibles publiques sont désactivées. "
            "Autorisez uniquement un hôte que vous administrez."
        )
    if not any(ip.version == network.version and ip in network for network in networks):
        raise TargetRejectedError("L'adresse n'appartient pas à un réseau autorisé.")


def _normalize_target(raw: str) -> str:
    if not isinstance(raw, str):
        raise TargetRejectedError("La cible doit être une chaîne de caractères.")
    value = raw.strip()
    if value.endswith("."):
        value = value[:-1]
    if not value:
        raise TargetRejectedError("La cible est obligatoire.")
    if len(value) > 253:
        raise TargetRejectedError("La cible dépasse 253 caractères.")
    return value


def _parse_ip(value: str) -> IPAddress | None:
    if "%" in value:
        raise TargetRejectedError("Les identifiants de zone IPv6 ne sont pas acceptés.")
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _first_authorized(
    addresses: Sequence[IPAddress],
    networks: Sequence[IPNetwork],
    *,
    allow_public: bool,
) -> IPAddress:
    last_error: TargetRejectedError | None = None
    for ip in addresses:
        try:
            assert_ip_authorized(ip, networks, allow_public=allow_public)
        except TargetRejectedError as exc:
            last_error = exc
            continue
        return ip
    raise last_error or TargetRejectedError("Aucune adresse autorisée pour ce nom.")


def _reject_oversized_or_special_network(network: IPNetwork) -> None:
    minimum = _MIN_PREFIX[network.version]
    if network.prefixlen < minimum:
        raise ValueError(
            f"Réseau autorisé trop large : {network}. Préfixe minimum /{minimum}."
        )
    if network.is_multicast:
        raise ValueError(f"Réseau multicast refusé : {network}.")


def _resolve_hostname(hostname: str) -> list[IPAddress]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise TargetRejectedError("Le nom d'hôte ne peut pas être résolu.") from exc

    addresses: list[IPAddress] = []
    seen: set[IPAddress] = set()
    for info in infos:
        raw_ip = str(info[4][0]).split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            continue
        if ip not in seen:
            seen.add(ip)
            addresses.append(ip)
    if not addresses:
        raise TargetRejectedError("Le nom d'hôte ne peut pas être résolu.")
    return addresses
