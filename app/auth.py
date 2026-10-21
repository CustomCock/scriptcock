"""Anmeldung per OIDC (Keycloak) und Rollen.

Rollen: ``nutzer`` (alle Mitglieder der erlaubten Gruppe) und ``admin``
(Mitglieder von ``OIDC_ADMIN_GRUPPE``). Mit ``AUTH_DISABLED=true`` ist jeder
Aufruf als ``DEV_BENUTZER`` angemeldet – nur für die lokale Entwicklung.
"""

from __future__ import annotations

from typing import Any

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from app.config import Einstellungen
from app.service import Benutzer

router = APIRouter()


class NichtAngemeldet(Exception):
    pass


class KeinZugriff(Exception):
    pass


def oauth_client(einst: Einstellungen) -> OAuth | None:
    if einst.auth_disabled:
        return None
    oauth = OAuth()
    oauth.register(
        name="keycloak",
        client_id=einst.oidc_client_id,
        client_secret=einst.oidc_client_secret,
        server_metadata_url=einst.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile email"},
    )
    return oauth


def _gruppen(claims: dict[str, Any], claim: str) -> set[str]:
    roh = claims.get(claim) or []
    if isinstance(roh, str):
        roh = [roh]
    # Keycloak liefert mit "Full group path" z. B. "/okm/it" – führenden Slash entfernen.
    return {str(g).lstrip("/") for g in roh}


def benutzer_aus_claims(claims: dict[str, Any], einst: Einstellungen) -> Benutzer:
    gruppen = _gruppen(claims, einst.oidc_gruppen_claim)
    erlaubt = einst.oidc_erlaubte_gruppe.lstrip("/")
    admin = einst.oidc_admin_gruppe.lstrip("/")
    if erlaubt and erlaubt not in gruppen and not (admin and admin in gruppen):
        raise KeinZugriff()
    name = str(claims.get("preferred_username") or claims.get("email") or claims.get("sub") or "unbekannt")
    return Benutzer(
        name=name,
        anzeige=str(claims.get("name") or name),
        ist_admin=bool(admin and admin in gruppen),
    )


def aktueller_benutzer(request: Request) -> Benutzer:
    einst: Einstellungen = request.app.state.einstellungen
    if einst.auth_disabled:
        return Benutzer(name=einst.dev_benutzer, anzeige=einst.dev_benutzer, ist_admin=einst.dev_admin)
    daten = request.session.get("benutzer")
    if not daten:
        raise NichtAngemeldet()
    return Benutzer(**daten)


@router.get("/login", name="login")
async def login(request: Request) -> Response:
    oauth: OAuth | None = request.app.state.oauth
    if oauth is None:
        return RedirectResponse(request.app.state.einstellungen.root_path + "/")
    ziel = str(request.url_for("auth_callback"))
    antwort: Response = await oauth.keycloak.authorize_redirect(request, ziel)
    return antwort


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request) -> Response:
    oauth: OAuth = request.app.state.oauth
    einst: Einstellungen = request.app.state.einstellungen
    try:
        token = await oauth.keycloak.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse(einst.root_path + "/login")
    claims: dict[str, Any] = dict(token.get("userinfo") or {})
    if einst.oidc_gruppen_claim not in claims:
        claims.update(await oauth.keycloak.userinfo(token=token))
    try:
        benutzer = benutzer_aus_claims(claims, einst)
    except KeinZugriff:
        request.session.clear()
        return Response(
            "Kein Zugriff: Dein Konto ist nicht für den Script-Baukasten freigeschaltet. "
            "Bitte wende dich an die IT.",
            status_code=403,
            media_type="text/plain; charset=utf-8",
        )
    request.session["benutzer"] = {
        "name": benutzer.name,
        "anzeige": benutzer.anzeige,
        "ist_admin": benutzer.ist_admin,
    }
    request.session["id_token"] = token.get("id_token", "")
    return RedirectResponse(einst.root_path + "/")


@router.get("/logout", name="logout")
async def logout(request: Request) -> Response:
    einst: Einstellungen = request.app.state.einstellungen
    id_token = request.session.get("id_token", "")
    request.session.clear()
    oauth: OAuth | None = request.app.state.oauth
    if oauth is None:
        return RedirectResponse(einst.root_path + "/")
    metadaten = await oauth.keycloak.load_server_metadata()
    ende = metadaten.get("end_session_endpoint")
    if not ende:
        return RedirectResponse(einst.root_path + "/")
    from urllib.parse import urlencode

    zurueck = str(request.url_for("startseite"))
    query = urlencode({"post_logout_redirect_uri": zurueck, "id_token_hint": id_token})
    return RedirectResponse(f"{ende}?{query}")
