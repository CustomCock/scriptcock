"""Blockly-Modus: Bausteine grafisch zusammenstecken.

Blockly erzeugt **kein** Script, sondern nur die Schrittliste (IR-Eingabe) als JSON.
Die geht an ``/api/v1/vorschau`` bzw. ``/api/v1/skripte`` – mit derselben Validierung
und denselben Generatoren wie alle anderen Modi.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from app import bibliothek
from app.auth import aktueller_benutzer
from app.escaping import Ziel
from app.generators.base import ZIEL_ANZEIGE, GeneratedScript
from app.ir import ScriptIR
from app.registry import Registry
from app.routes.pages import HLJS_SPRACHE, _render, _sitzung
from app.service import Benutzer, Ergebnis, rechte_hinweis
from app.validation import MAX_TIEFE, MAX_WIEDERHOLUNGEN, FehlerSammlung

router = APIRouter()


def katalog(reg: Registry) -> list[dict[str, Any]]:
    """Bausteine für die Blockly-Toolbox (Kategorie = ``kategorie`` aus dem YAML)."""
    return [
        {
            "id": b.id,
            "name": b.name,
            "kategorie": b.kategorie,
            "beschreibung": b.beschreibung,
            "hilfe": b.hilfe,
            "risiko": b.risiko.value,
            "ziele": [z.value for z in b.ziele],
            "admin": {z.value: b.braucht_admin(z) for z in b.ziele},
            "genutzt": {z.value: sorted(reg.benutzte_parameter(b, z)) for z in b.ziele},
            "parameter": [p.model_dump(mode="json") for p in b.parameter],
        }
        for b in sorted(reg.bloecke.values(), key=lambda b: (b.kategorie, b.name))
    ]


@router.get("/blockly", name="blockly", response_class=HTMLResponse)
async def blockly_seite(
    request: Request,
    ziel: str = "powershell",
    aus: int | None = None,
    benutzer: Benutzer = Depends(aktueller_benutzer),
    sitzung: Any = Depends(_sitzung),
) -> Response:
    reg: Registry = request.app.state.registry
    try:
        z = Ziel(ziel)
    except ValueError:
        z = Ziel.POWERSHELL
    vorbelegung: dict[str, Any] | None = None
    editor: dict[str, object] | None = None
    if aus is not None:
        try:
            eintrag = bibliothek.hole(sitzung, aus, benutzer)
            ir, schritte, hinweise = bibliothek.baum_wiederherstellen(reg, eintrag)
            editor = bibliothek.editor_vorbelegung(eintrag)
        except bibliothek.KeinZugriffAufScript:
            raise HTTPException(404, "Script nicht gefunden") from None
        except FehlerSammlung as e:
            raise HTTPException(422, e.fehler[0].meldung) from None
        z = Ziel(eintrag.ziel)
        vorbelegung = {
            "titel": ir.meta.titel,
            "beschreibung": ir.meta.beschreibung,
            "dry_run": ir.optionen.dry_run,
            "schritte": schritte,
            "hinweise": hinweise,
        }
    daten = {
        "basis": request.app.state.einstellungen.root_path,
        "ziel": z.value,
        "ist_admin": benutzer.ist_admin,
        "ziele": {zz.value: ZIEL_ANZEIGE[zz] for zz in Ziel},
        "sprachen": {zz.value: HLJS_SPRACHE[zz] for zz in Ziel},
        "katalog": katalog(reg),
        "max_wiederholungen": MAX_WIEDERHOLUNGEN,
        "max_tiefe": MAX_TIEFE,
        "vorbelegung": vorbelegung,
    }
    return _render(
        request,
        "blockly.html",
        benutzer,
        daten=daten,
        ziel=z,
        ziele=list(Ziel),
        vorbelegung=vorbelegung,
        editor_vorbelegung=editor,
    )


@router.get("/skripte/{sid}/ergebnis", response_class=HTMLResponse)
async def ergebnis(
    request: Request,
    sid: int,
    benutzer: Benutzer = Depends(aktueller_benutzer),
    sitzung: Any = Depends(_sitzung),
) -> Response:
    """Download-/Bibliotheksbereich nach dem Erzeugen (für Blockly-Modus nachgeladen)."""
    try:
        eintrag = bibliothek.hole(sitzung, sid, benutzer, aendern=True)
    except bibliothek.KeinZugriffAufScript:
        raise HTTPException(404, "Script nicht gefunden") from None
    reg: Registry = request.app.state.registry
    ir = ScriptIR.model_validate_json(eintrag.ir_json)
    ziel = Ziel(eintrag.ziel)

    script = GeneratedScript(
        ziel=ziel,
        text=eintrag.inhalt.decode("utf-8-sig"),
        inhalt=eintrag.inhalt,
        sha256=eintrag.sha256,
        dateiname=eintrag.dateiname,
    )
    return _render(
        request,
        "_vorschau.html",
        benutzer,
        ergebnis=Ergebnis(ir=ir, script=script, gespeichert=eintrag),
        ziel=ziel,
        sprache=HLJS_SPRACHE[ziel],
        rechte=rechte_hinweis(reg, ir, ziel),
        ohne_code=True,
    )
