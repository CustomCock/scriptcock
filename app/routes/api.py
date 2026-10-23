"""JSON-API (wird vom Listen-/Blockly-Modus genutzt). Gleiche Validierung wie die Seiten."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth import aktueller_benutzer
from app.escaping import Ziel
from app.models.request import ScriptRequest
from app.registry import Registry
from app.service import Benutzer, benutzte_parameter, erzeuge, generiere
from app.validation import FehlerSammlung

router = APIRouter()


def _sitzung(request: Request) -> Any:
    yield from request.app.state.db.sitzung()


@router.get("/bloecke")
async def bloecke(request: Request, benutzer: Benutzer = Depends(aktueller_benutzer)) -> dict[str, Any]:
    reg: Registry = request.app.state.registry
    return {
        "bloecke": [
            {
                "id": b.id,
                "version": b.version,
                "name": b.name,
                "kategorie": b.kategorie,
                "beschreibung": b.beschreibung,
                "hilfe": b.hilfe,
                "risiko": b.risiko.value,
                "ziele": [z.value for z in b.ziele],
                "admin": {z.value: b.braucht_admin(z) for z in b.ziele},
                "rechte": {z.value: b.recht(z).value for z in b.ziele},
                "hinweise": {z.value: t for z, t in b.hinweise.items()},
                "parameter_je_ziel": {z.value: sorted(benutzte_parameter(reg, b, z)) for z in b.ziele},
                "parameter": [p.model_dump(mode="json") for p in b.parameter],
            }
            for b in sorted(reg.bloecke.values(), key=lambda b: (b.kategorie, b.name))
        ],
        "ziele": [z.value for z in Ziel],
    }


def _fehler_json(e: FehlerSammlung) -> JSONResponse:
    return JSONResponse(
        {"fehler": [{"schritt": f.schritt, "feld": f.feld, "meldung": f.meldung} for f in e.fehler]},
        status_code=422,
    )


@router.post("/vorschau")
async def vorschau(
    request: Request, req: ScriptRequest, benutzer: Benutzer = Depends(aktueller_benutzer)
) -> JSONResponse:
    """Live-Vorschau (Blockly-Modus): wird nicht gespeichert, rote Bestätigung noch nicht nötig."""
    reg: Registry = request.app.state.registry
    try:
        _, script = generiere(reg, req.model_copy(update={"rot_bestaetigt": True}), benutzer)
    except FehlerSammlung as e:
        return _fehler_json(e)
    return JSONResponse(
        {"text": script.text.replace("\r\n", "\n"), "sha256": script.sha256, "dateiname": script.dateiname}
    )


@router.post("/skripte")
async def skript_erzeugen(
    request: Request,
    req: ScriptRequest,
    benutzer: Benutzer = Depends(aktueller_benutzer),
    sitzung: Any = Depends(_sitzung),
) -> JSONResponse:
    reg: Registry = request.app.state.registry
    try:
        ergebnis = erzeuge(reg, req, benutzer, sitzung)
    except FehlerSammlung as e:
        return _fehler_json(e)
    return JSONResponse(
        {
            "id": ergebnis.gespeichert.id,
            "sha256": ergebnis.script.sha256,
            "dateiname": ergebnis.script.dateiname,
            "text": ergebnis.script.text,
            "ir": ergebnis.ir.model_dump(mode="json"),
        }
    )
