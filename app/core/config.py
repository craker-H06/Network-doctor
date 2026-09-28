"""Configuration lue depuis l'environnement. Aucun secret n'est codé en dur."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.target_validator import parse_allowed_networks


class Settings(BaseSettings):
    """Paramètres du service. Les bornes limitent l'usage accidentel d'ICMP."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Network Doctor"
    allowed_networks: str = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8"
    allow_public_targets: bool = False
    ping_timeout_seconds: int = Field(default=2, ge=1, le=5)
    max_ping_count: int = Field(default=4, ge=1, le=4)

    @field_validator("allowed_networks")
    @classmethod
    def validate_allowed_networks(cls, value: str) -> str:
        parse_allowed_networks(value)
        return value

    def allowed_network_objects(self):
        """Réseaux déjà validés, prêts pour le contrôle de cible."""
        return parse_allowed_networks(self.allowed_networks)


@lru_cache
def get_settings() -> Settings:
    """Retourne la configuration mise en cache pour le processus."""
    return Settings()
