"""FastAPI-Anwendung (Einstiegspunkt: ``uvicorn app.main:app``)."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import __version__
from app.auth import KeinZugriff, NichtAngemeldet, oauth_client
from app.auth import router as auth_router
from app.baukasten import lade_db_rezepte
from app.config import Einstellungen, einstellungen
from app.db import Datenbank
from app.registry import Registry, lade_registry
from app.routes import api, baukasten, bibliothek, blockly, pages, verwaltung

PROJEKT = Path(__file__).resolve().parent.parent
log = logging.getLogger("baukasten")

UNSICHERE_METHODEN = {"POST", "PUT", "PATCH", "DELETE"}

# Blockly setzt Inline-Styles (SVG) – nur auf der Blockly-Seite erlaubt. Scripte bleiben 'self'.
CSP_BLOCKLY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def create_app(
    einst: Einstellungen | None = None,
    registry: Registry | None = None,
    datenbank: Datenbank | None = None,
) -> FastAPI:
    einst = einst or einstellungen()
    einst.pruefe()
    if einst.auth_disabled:
        log.warning("AUTH_DISABLED=true – Anmeldung ist abgeschaltet! Nur für die Entwicklung.")

    app = FastAPI(title="okm Script-Baukasten", version=__version__, root_path=einst.root_path, docs_url=None)
    app.state.einstellungen = einst
    app.state.registry = registry or lade_registry()
    app.state.db = datenbank or Datenbank(einst.database_url)
    app.state.oauth = oauth_client(einst)
    with app.state.db.neue_sitzung() as sitzung:
        anzahl = lade_db_rezepte(app.state.registry, sitzung)
    if anzahl:
        log.info("%d eigene Rezepte aus der Datenbank geladen.", anzahl)

    templates = Jinja2Templates(directory=str(PROJEKT / "app" / "templates"))
    templates.env.globals.update(
        basis=einst.root_path,
        version=__version__,
        auth_disabled=einst.auth_disabled,
    )
    app.state.templates = templates

    @app.middleware("http")
    async def schutz(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # CSRF-Schutz: Ändernde Anfragen müssen von unserem JavaScript/htmx kommen.
        # Fremde Seiten können diese Header ohne CORS-Freigabe nicht setzen.
        if request.method in UNSICHERE_METHODEN and not request.url.path.startswith(
            einst.root_path + "/auth/"
        ):
            if request.headers.get("HX-Request") != "true" and request.headers.get("X-Okm-Request") != "1":
                return JSONResponse({"fehler": "Ungültige Anfrage (CSRF-Schutz)."}, status_code=403)
        antwort = await call_next(request)
        ist_blockly = request.url.path.rstrip("/") == einst.root_path + "/blockly"
        antwort.headers.setdefault("Content-Security-Policy", CSP_BLOCKLY if ist_blockly else CSP)
        antwort.headers.setdefault("X-Content-Type-Options", "nosniff")
        antwort.headers.setdefault("Referrer-Policy", "same-origin")
        return antwort

    app.add_middleware(
        SessionMiddleware,
        secret_key=einst.secret_key or secrets.token_urlsafe(32),
        session_cookie="okm_baukasten",
        same_site="lax",
        https_only=einst.cookie_secure and not einst.auth_disabled,
        max_age=8 * 3600,
    )

    @app.exception_handler(NichtAngemeldet)
    async def _nicht_angemeldet(request: Request, exc: NichtAngemeldet) -> Response:
        if request.url.path.startswith(einst.root_path + "/api/") or request.headers.get("HX-Request"):
            antwort = JSONResponse({"fehler": "Nicht angemeldet."}, status_code=401)
            antwort.headers["HX-Redirect"] = einst.root_path + "/login"
            return antwort
        return RedirectResponse(einst.root_path + "/login")

    @app.exception_handler(KeinZugriff)
    async def _kein_zugriff(request: Request, exc: KeinZugriff) -> Response:
        return JSONResponse({"fehler": "Kein Zugriff."}, status_code=403)

    app.mount("/static", StaticFiles(directory=str(PROJEKT / "static")), name="static")
    app.include_router(auth_router)
    app.include_router(pages.router)
    app.include_router(baukasten.router)
    app.include_router(bibliothek.router)
    app.include_router(verwaltung.router)
    app.include_router(blockly.router)
    app.include_router(api.router, prefix="/api/v1")

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


def __getattr__(name: str) -> FastAPI:
    # ``uvicorn app.main:app`` – App erst beim Zugriff bauen, damit Tests
    # ``create_app`` mit eigener Konfiguration aufrufen können.
    if name == "app":
        anwendung = create_app()
        globals()["app"] = anwendung
        return anwendung
    raise AttributeError(name)
