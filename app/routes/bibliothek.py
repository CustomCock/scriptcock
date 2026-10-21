"""Bibliothek: gespeicherte Scripte durchsuchen, ansehen, bewerten, erneut öffnen."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from app import bibliothek
from app.auth import aktueller_benutzer
from app.db import GespeichertesScript
from app.escaping import Ziel
from app.registry import Registry
from app.routes.pages import HLJS_SPRACHE, _render, _sitzung
from app.service import Benutzer
from app.validation import FehlerSammlung

router = APIRouter()


def _hole(sitzung: Any, sid: int, benutzer: Benutzer, *, aendern: bool = False) -> GespeichertesScript:
    try:
        return bibliothek.hole(sitzung, sid, benutzer, aendern=aendern)
    except bibliothek.KeinZugriffAufScript:
        raise HTTPException(404, "Script nicht gefunden") from None


@router.get("/bibliothek", name="bibliothek", response_class=HTMLResponse)
async def bibliothek_seite(
    request: Request,
    q: str = "",
    ziel: str = "",
    tag: str = "",
    meine: bool = False,
    seite: int = 0,
    benutzer: Benutzer = Depends(aktueller_benutzer),
    sitzung: Any = Depends(_sitzung),
) -> Response:
    try:
        z = Ziel(ziel) if ziel else None
    except ValueError:
        z = None
    ergebnis = bibliothek.suche(
        sitzung, benutzer, q=q[:200], ziel=z, tag=tag[:30], nur_meine=meine, seite=max(0, min(seite, 1000))
    )
    kontext = {
        "ergebnis": ergebnis,
        "q": q,
        "ziel": z,
        "tag": tag,
        "meine": meine,
        "seite": seite,
        "seitengroesse": bibliothek.SEITENGROESSE,
        "tags_aus_text": bibliothek.tags_aus_text,
        "ziele": list(Ziel),
    }
    if request.headers.get("HX-Request") and request.headers.get("HX-Target") == "bibliotheksliste":
        return _render(request, "_bib_liste.html", benutzer, **kontext)
    return _render(request, "bibliothek.html", benutzer, **kontext)


@router.get("/skripte/{sid}", name="skript", response_class=HTMLResponse)
async def skript_detail(
    request: Request,
    sid: int,
    benutzer: Benutzer = Depends(aktueller_benutzer),
    sitzung: Any = Depends(_sitzung),
) -> Response:
    eintrag = _hole(sitzung, sid, benutzer)
    reg: Registry = request.app.state.registry
    ziel = Ziel(eintrag.ziel)
    quelle = "Blockly-Modus" if eintrag.quelle == "blockly" else "Freier Baukasten"
    if eintrag.quelle.startswith("rezept:"):
        rezept = reg.rezepte.get(eintrag.quelle.removeprefix("rezept:"))
        quelle = f"Rezept „{rezept.name if rezept else eintrag.quelle.removeprefix('rezept:')}“"
    return _render(
        request,
        "skript.html",
        benutzer,
        e=eintrag,
        ziel=ziel,
        sprache=HLJS_SPRACHE[ziel],
        quelle=quelle,
        text=eintrag.inhalt.decode("utf-8-sig").replace("\r\n", "\n"),
        versionen=bibliothek.blockversionen(reg, eintrag),
        tags=bibliothek.tags_aus_text(eintrag.tags),
        darf_aendern=bibliothek.darf_aendern(eintrag, benutzer),
        hat_bewertet=bibliothek.hat_bewertet(sitzung, eintrag, benutzer),
    )


@router.post("/skripte/{sid}/bibliothek", response_class=HTMLResponse)
async def in_bibliothek(
    request: Request,
    sid: int,
    benutzer: Benutzer = Depends(aktueller_benutzer),
    sitzung: Any = Depends(_sitzung),
) -> Response:
    eintrag = _hole(sitzung, sid, benutzer, aendern=True)
    form = await request.form()
    try:
        bibliothek.in_bibliothek_speichern(
            sitzung,
            eintrag,
            titel=str(form.get("titel", "")),
            beschreibung=str(form.get("beschreibung", "")),
            tags=str(form.get("tags", "")),
        )
    except FehlerSammlung as e:
        return _render(request, "_fehler.html", benutzer, fehler=e.fehler, ohne_oob=True)
    return _render(request, "_bib_gespeichert.html", benutzer, e=eintrag)


@router.post("/skripte/{sid}/entfernen")
async def aus_bibliothek(
    request: Request,
    sid: int,
    benutzer: Benutzer = Depends(aktueller_benutzer),
    sitzung: Any = Depends(_sitzung),
) -> Response:
    eintrag = _hole(sitzung, sid, benutzer, aendern=True)
    bibliothek.aus_bibliothek_entfernen(sitzung, eintrag)
    return Response(
        status_code=204, headers={"HX-Redirect": request.app.state.einstellungen.root_path + "/bibliothek"}
    )


@router.post("/skripte/{sid}/funktioniert", response_class=HTMLResponse)
async def funktioniert(
    request: Request,
    sid: int,
    benutzer: Benutzer = Depends(aktueller_benutzer),
    sitzung: Any = Depends(_sitzung),
) -> Response:
    eintrag = _hole(sitzung, sid, benutzer)
    gesetzt = bibliothek.funktioniert_umschalten(sitzung, eintrag, benutzer)
    return _render(request, "_funktioniert.html", benutzer, e=eintrag, hat_bewertet=gesetzt)
