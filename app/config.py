"""Konfiguration über Umgebungsvariablen bzw. ``.env`` (siehe ``.env.example``)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Einstellungen(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    secret_key: str = Field(default="", alias="APP_SECRET_KEY")
    database_url: str = Field(default="sqlite:///./data/baukasten.db", alias="DATABASE_URL")
    root_path: str = Field(default="", alias="ROOT_PATH")
    cookie_secure: bool = Field(default=True, alias="SESSION_COOKIE_SECURE")

    auth_disabled: bool = Field(default=False, alias="AUTH_DISABLED")
    dev_benutzer: str = Field(default="entwickler", alias="DEV_BENUTZER")
    dev_admin: bool = Field(default=True, alias="DEV_ADMIN")

    oidc_issuer: str = Field(default="", alias="OIDC_ISSUER")
    oidc_client_id: str = Field(default="", alias="OIDC_CLIENT_ID")
    oidc_client_secret: str = Field(default="", alias="OIDC_CLIENT_SECRET")
    oidc_erlaubte_gruppe: str = Field(default="", alias="OIDC_ERLAUBTE_GRUPPE")
    oidc_admin_gruppe: str = Field(default="", alias="OIDC_ADMIN_GRUPPE")
    oidc_gruppen_claim: str = Field(default="groups", alias="OIDC_GRUPPEN_CLAIM")

    def pruefe(self) -> None:
        """Bricht den Start ab, wenn die Konfiguration unvollständig ist."""
        fehlend = []
        if not self.secret_key and not self.auth_disabled:
            fehlend.append("APP_SECRET_KEY")
        if not self.auth_disabled:
            for name, wert in (
                ("OIDC_ISSUER", self.oidc_issuer),
                ("OIDC_CLIENT_ID", self.oidc_client_id),
                ("OIDC_CLIENT_SECRET", self.oidc_client_secret),
            ):
                if not wert:
                    fehlend.append(name)
        if fehlend:
            raise RuntimeError(
                "Konfiguration unvollständig, fehlend: "
                + ", ".join(fehlend)
                + " (für die lokale Entwicklung: AUTH_DISABLED=true)"
            )


@lru_cache
def einstellungen() -> Einstellungen:
    return Einstellungen()
