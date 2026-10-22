"""Software-Katalog als eigene Seite (Daten und Suche liegen komplett im Browser)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response

from app.auth import aktueller_benutzer
from app.routes.pages import _render
from app.service import Benutzer

router = APIRouter()


@router.get("/software", name="software", response_class=HTMLResponse)
async def software(request: Request, benutzer: Benutzer = Depends(aktueller_benutzer)) -> Response:
    return _render(request, "software.html", benutzer)
