"""Vérification de cible : un hôte explicite, dans un réseau autorisé."""

from __future__ import annotations

import ipaddress

import pytest

from app.core.errors import TargetRejectedError
from app.services.target_validator import (
    assert_ip_authorized,
    parse_allowed_networks,
    prepare_host,
)

PRIVATE = parse_allowed_networks("10.0.0.0/8,192.168.0.0/16,127.0.0.0/8")


def _resolver(*addresses: str):
    parsed = [ipaddress.ip_address(address) for address in addresses]

    def resolve(_hostname: str):
        return parsed

    return resolve


def test_accepts_private_ipv4() -> None:
    host = prepare_host("10.1.1.1", PRIVATE, allow_public=False)

    assert host.original == "10.1.1.1"
    assert str(host.ip) == "10.1.1.1"


def test_accepts_loopback() -> None:
    host = prepare_host("127.0.0.1", PRIVATE, allow_public=False)

    assert str(host.ip) == "127.0.0.1"


def test_strips_a_trailing_dns_dot() -> None:
    host = prepare_host(
        "printer.lab.",
        PRIVATE,
        allow_public=False,
        resolver=_resolver("10.8.0.4"),
    )

    assert host.original == "printer.lab"
    assert str(host.ip) == "10.8.0.4"


@pytest.mark.parametrize(
    "target",
    ["", "   ", "10.1.1.0/28", "0.0.0.0/0", "10.1.1.1;id", "10.1.1.1 && ls"],
)
def test_rejects_missing_range_or_metacharacters(target: str) -> None:
    with pytest.raises(TargetRejectedError):
        prepare_host(target, PRIVATE, allow_public=False, resolver=_resolver("10.1.1.1"))


def test_rejects_invalid_dotted_quad_without_resolving() -> None:
    def explode(_hostname: str):
        raise AssertionError("le résolveur ne doit pas être appelé")

    with pytest.raises(TargetRejectedError, match="IPv4 invalide"):
        prepare_host("127.0.0.01", PRIVATE, allow_public=False, resolver=explode)


def test_rejects_public_address_by_default() -> None:
    with pytest.raises(TargetRejectedError, match="publiques"):
        prepare_host("8.8.8.8", PRIVATE, allow_public=False)


def test_rejects_public_address_not_listed_even_when_public_targets_are_enabled() -> None:
    with pytest.raises(TargetRejectedError, match="réseau autorisé"):
        prepare_host("8.8.8.8", PRIVATE, allow_public=True)


def test_accepts_listed_public_address_only_when_enabled() -> None:
    networks = parse_allowed_networks("8.8.8.8/32")

    with pytest.raises(TargetRejectedError, match="publiques"):
        prepare_host("8.8.8.8", networks, allow_public=False)

    host = prepare_host("8.8.8.8", networks, allow_public=True)
    assert str(host.ip) == "8.8.8.8"


@pytest.mark.parametrize(
    "target",
    ["0.0.0.0", "255.255.255.255", "224.0.0.1", "169.254.1.1", "::", "ff02::1"],
)
def test_rejects_special_purpose_addresses(target: str) -> None:
    with pytest.raises(TargetRejectedError, match="ne peut pas être diagnostiquée"):
        assert_ip_authorized(ipaddress.ip_address(target), PRIVATE, allow_public=True)


def test_rejects_ipv4_mapped_ipv6() -> None:
    with pytest.raises(TargetRejectedError, match="IPv4-mappées"):
        prepare_host("::ffff:10.1.1.1", PRIVATE, allow_public=False)


def test_rejects_ipv6_zone_index() -> None:
    with pytest.raises(TargetRejectedError, match="zone"):
        prepare_host("fe80::1%eth0", PRIVATE, allow_public=False)


def test_hostname_uses_the_first_authorized_address() -> None:
    host = prepare_host(
        "printer.lab",
        PRIVATE,
        allow_public=False,
        resolver=_resolver("8.8.8.8", "10.8.0.4"),
    )

    assert str(host.ip) == "10.8.0.4"


def test_hostname_without_authorized_address_is_rejected() -> None:
    with pytest.raises(TargetRejectedError):
        prepare_host(
            "example.com",
            PRIVATE,
            allow_public=False,
            resolver=_resolver("93.184.216.34"),
        )


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "0.0.0.0/0", "::/0", "1.0.0.0/7", "224.0.0.0/4", "pas-un-reseau"],
)
def test_rejects_dangerous_allowlist(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_allowed_networks(raw)


def test_accepts_a_lab_allowlist() -> None:
    networks = parse_allowed_networks("10.0.0.0/8, fc00::/7")

    assert len(networks) == 2
    assert ipaddress.ip_address("10.2.0.1") in networks[0]
