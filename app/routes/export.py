"""Editor-Endpunkte: Export (Script-Text → Datei nach den Regeln in app/export.py) und Syntax-Prüfung."""

from __future__ import annotations

import hashlib
import threading
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.auth import aktueller_benutzer
from app.escaping import Ziel
from app.export import exportiere
from app.generators import GENERATOREN
from app.generators.base import dateiname
from app.service import Benutzer
from app.syntaxpruefung import pruefe

router = APIRouter()

MAX_TEXT = 2_000_000  # Zeichen – deutlich mehr als jedes erzeugte Script
MAX_PRUEFTEXT = 500_000
# Prüfwerkzeuge starten Prozesse – höchstens so viele Prüfungen gleichzeitig.
_PRUEF_PLAETZE = threading.BoundedSemaphore(4)


class ExportAnfrage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=MAX_TEXT)
    ziel: Ziel
    dateiname: str = Field(default="script", max_length=120)
    manuell_bearbeitet: bool = False


class PruefAnfrage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=MAX_PRUEFTEXT)
    ziel: Ziel


@router.post("/api/script/export")
async def export(anfrage: ExportAnfrage, benutzer: Benutzer = Depends(aktueller_benutzer)) -> Response:
    """Liefert die Bytes als ``application/octet-stream``, damit der Browser nichts umwandelt."""
    inhalt = exportiere(anfrage.text, anfrage.ziel, manuell_bearbeitet=anfrage.manuell_bearbeitet)
    name = dateiname(
        anfrage.dateiname.removesuffix(GENERATOREN[anfrage.ziel].endung), GENERATOREN[anfrage.ziel].endung
    )
    return Response(
        content=inhalt,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-Script-SHA256": hashlib.sha256(inhalt).hexdigest(),
            "Cache-Control": "no-store",
        },
    )


@router.post("/api/script/pruefen")
def pruefen(anfrage: PruefAnfrage, benutzer: Benutzer = Depends(aktueller_benutzer)) -> dict[str, Any]:
    """„Syntax prüfen“ im Editor: dieselben Checks wie die Tests, nur parsen – nie ausführen."""
    if not _PRUEF_PLAETZE.acquire(blocking=False):
        raise HTTPException(429, "Gerade laufen zu viele Prüfungen – bitte gleich noch einmal versuchen.")
    try:
        erg = pruefe(anfrage.text, anfrage.ziel)
    finally:
        _PRUEF_PLAETZE.release()
    return {
        "ok": erg.ok,
        "befunde": [asdict(b) for b in erg.befunde],
        "geprueft": erg.geprueft,
        "hinweise": erg.hinweise,
    }
