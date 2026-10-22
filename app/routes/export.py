"""Export-Endpunkt: Script-Text → Datei mit den Encoding-Regeln des Zielsystems (siehe app/export.py)."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.auth import aktueller_benutzer
from app.escaping import Ziel
from app.export import exportiere
from app.generators import GENERATOREN
from app.generators.base import dateiname
from app.service import Benutzer

router = APIRouter()

MAX_TEXT = 2_000_000  # Zeichen – deutlich mehr als jedes erzeugte Script


class ExportAnfrage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=MAX_TEXT)
    ziel: Ziel
    dateiname: str = Field(default="script", max_length=120)


@router.post("/api/script/export")
async def export(anfrage: ExportAnfrage, benutzer: Benutzer = Depends(aktueller_benutzer)) -> Response:
    """Liefert die Bytes als ``application/octet-stream``, damit der Browser nichts umwandelt."""
    inhalt = exportiere(anfrage.text, anfrage.ziel)
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
