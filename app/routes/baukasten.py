"""Freier Baukasten (Listen-Modus): Bausteine per Drag & Drop zu einem Script zusammenstellen."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from app import bibliothek
from app.auth import aktueller_benutzer
from app.baukasten import (
    BaukastenFormular,
    FormularFehler,
    lies_formular,
    neue_uid,
    rezept_als_yaml,
    rezept_aus_formular,
    rezept_speichern,
)
from app.bibliothek import Wiederherstellung, wiederherstellen
from app.escaping import Ziel
from app.generators.base import ZIEL_ANZEIGE
from app.models.block import BlockDef, Risiko
from app.registry import Registry
from app.routes.pages import HLJS_SPRACHE, _render, _sitzung
from app.service import Benutzer, erzeuge, generiere
from app.validation import FehlerSammlung, Feldfehler

router = APIRouter()

MAX_VORBELEGUNG = 300
ZIEL_KURZ = {Ziel.POWERSHELL: "PowerShell", Ziel.CMD: "CMD", Ziel.BASH: "Linux", Ziel.ZSH: "macOS"}


def _registry(request: Request) -> Registry:
    reg: Registry = request.app.state.registry
    return reg


async def _formular(request: Request) -> BaukastenFormular:
    daten = await request.form()
    try:
        return lies_formular(daten.multi_items())
    except FormularFehler as e:
        raise HTTPException(400, str(e)) from None


def _schritt_kontext(
    reg: Registry, block: BlockDef, ziel: Ziel, uid: str, werte: dict[str, str]
) -> dict[str, Any]:
    return {
        "uid": uid,
        "block": block,
        "ziel": ziel,
        "werte": werte,
        "genutzt": reg.benutzte_parameter(block, ziel),
        "verfuegbar": block.verfuegbar(ziel),
        "admin": block.braucht_admin(ziel),
        "hinweis": block.hinweise.get(ziel),
    }


def _schritte(reg: Registry, formular: BaukastenFormular) -> list[dict[str, Any]]:
    ergebnis = []
    for uid, block_id, werte in zip(formular.uids, formular.bloecke, formular.werte, strict=True):
        block = reg.bloecke.get(block_id)
        if block is not None:
            ergebnis.append(_schritt_kontext(reg, block, formular.ziel, uid, werte))
    return ergebnis


@router.get("/baukasten", name="baukasten", response_class=HTMLResponse)
async def baukasten(
    request: Request,
    ziel: str = "powershell",
    aus: int | None = None,
    benutzer: Benutzer = Depends(aktueller_benutzer),
    sitzung: Any = Depends(_sitzung),
) -> Response:
    reg = _registry(request)
    try:
        z = Ziel(ziel)
    except ValueError:
        z = Ziel.POWERSHELL
    vorbelegung: Wiederherstellung | None = None
    schritte: list[dict[str, Any]] = []
    if aus is not None:
        # „Erneut öffnen und anpassen“: aus der gespeicherten IR, nicht aus dem Script-Text
        try:
            vorbelegung = wiederherstellen(reg, bibliothek.hole(sitzung, aus, benutzer))
        except bibliothek.KeinZugriffAufScript:
            raise HTTPException(404, "Script nicht gefunden") from None
        except FehlerSammlung as e:
            raise HTTPException(422, e.fehler[0].meldung) from None
        z = vorbelegung.ziel
        schritte = [
            _schritt_kontext(reg, reg.bloecke[block_id], z, neue_uid(), werte)
            for block_id, werte in vorbelegung.schritte
        ]
    kategorien: dict[str, list[BlockDef]] = {}
    for b in sorted(reg.bloecke.values(), key=lambda b: (b.kategorie, b.name)):
        kategorien.setdefault(b.kategorie, []).append(b)
    return _render(
        request,
        "baukasten.html",
        benutzer,
        ziel=z,
        ziele=list(Ziel),
        ziel_kurz=ZIEL_KURZ,
        kategorien=kategorien,
        vorbelegung=vorbelegung,
        schritte=schritte,
    )


@router.get("/baukasten/schritt", response_class=HTMLResponse)
async def neuer_schritt(
    request: Request, block: str, ziel: str, benutzer: Benutzer = Depends(aktueller_benutzer)
) -> Response:
    reg = _registry(request)
    b = reg.bloecke.get(block)
    try:
        z = Ziel(ziel)
    except ValueError:
        raise HTTPException(400, "Ungültiges Zielsystem") from None
    if b is None:
        raise HTTPException(404, "Unbekannter Baustein")
    # Vorbelegte Werte (p.<parameter>=…), z. B. aus dem Software-Katalog. Sie landen nur als
    # Formularwerte im HTML und werden wie jede Eingabe erst beim Erzeugen geprüft.
    werte = {
        k[2:]: v[:MAX_VORBELEGUNG]
        for k, v in request.query_params.items()
        if k.startswith("p.") and b.param(k[2:]) is not None
    }
    return _render(request, "_bk_schritt.html", benutzer, **_schritt_kontext(reg, b, z, neue_uid(), werte))


@router.post("/baukasten/liste", response_class=HTMLResponse)
async def liste_neu(request: Request, benutzer: Benutzer = Depends(aktueller_benutzer)) -> Response:
    """Rendert die Schrittliste für ein anderes Zielsystem neu (Werte bleiben erhalten)."""
    formular = await _formular(request)
    return _render(request, "_bk_liste.html", benutzer, schritte=_schritte(_registry(request), formular))


def _fehler_zuordnen(formular: BaukastenFormular, fehler: list[Feldfehler]) -> dict[str, Any]:
    """Ordnet Fehler den Schritten (uid) und Feldern zu."""
    pro_feld: dict[str, str] = {}
    pro_schritt: dict[str, list[str]] = {}
    allgemein: list[str] = []
    for f in fehler:
        if f.schritt is not None and f.schritt < len(formular.uids):
            uid = formular.uids[f.schritt]
            if f.feld:
                pro_feld[f"{uid}-{f.feld}"] = f.meldung
            else:
                pro_schritt.setdefault(uid, []).append(f.meldung)
        elif f.feld != "rot_bestaetigt":
            allgemein.append(f.meldung)
    return {"pro_feld": pro_feld, "pro_schritt": pro_schritt, "allgemein": allgemein}


@router.post("/baukasten/vorschau", response_class=HTMLResponse)
async def vorschau(request: Request, benutzer: Benutzer = Depends(aktueller_benutzer)) -> Response:
    """Live-Vorschau – wird nicht gespeichert. Die rote Bestätigung ist hier noch nicht nötig."""
    reg = _registry(request)
    formular = await _formular(request)
    schritte = _schritte(reg, formular)
    hat_rot = any(s["block"].risiko is Risiko.ROT for s in schritte)
    nicht_verfuegbar = [s["block"].name for s in schritte if not s["verfuegbar"]]
    script = None
    fehler: list[Feldfehler] = []
    if formular.uids:
        try:
            _, script = generiere(reg, formular.als_request(rot_bestaetigt=True), benutzer)
        except FehlerSammlung as e:
            fehler = e.fehler
    return _render(
        request,
        "_bk_vorschau.html",
        benutzer,
        formular=formular,
        schritte=schritte,
        script=script,
        sprache=HLJS_SPRACHE[formular.ziel],
        nicht_verfuegbar=nicht_verfuegbar,
        ziel_anzeige_aktuell=ZIEL_ANZEIGE[formular.ziel],
        bestaetigung_noetig=hat_rot and not benutzer.ist_admin and not formular.dry_run,
        **_fehler_zuordnen(formular, fehler),
    )


@router.post("/baukasten/erzeugen", response_class=HTMLResponse)
async def baukasten_erzeugen(
    request: Request, benutzer: Benutzer = Depends(aktueller_benutzer), sitzung: Any = Depends(_sitzung)
) -> Response:
    reg = _registry(request)
    formular = await _formular(request)
    try:
        ergebnis = erzeuge(reg, formular.als_request(), benutzer, sitzung)
    except FehlerSammlung as e:
        return _render(request, "_fehler.html", benutzer, fehler=e.fehler, ohne_oob=True)
    return _render(
        request,
        "_vorschau.html",
        benutzer,
        ergebnis=ergebnis,
        ziel=formular.ziel,
        sprache=HLJS_SPRACHE[formular.ziel],
        braucht_admin=any(
            reg.bloecke[s.block_id].braucht_admin(formular.ziel) for s in ergebnis.ir.bloecke()
        ),
        ohne_code=True,
    )


@router.post("/baukasten/als-rezept", response_class=HTMLResponse)
async def als_rezept(
    request: Request, benutzer: Benutzer = Depends(aktueller_benutzer), sitzung: Any = Depends(_sitzung)
) -> Response:
    # Admins speichern direkt, Nutzer reichen einen Vorschlag zur Freigabe ein.
    reg = _registry(request)
    daten = await request.form()
    try:
        formular = lies_formular(daten.multi_items())
    except FormularFehler as e:
        raise HTTPException(400, str(e)) from None
    try:
        rezept = rezept_aus_formular(
            reg,
            formular,
            name=str(daten.get("rezept_name", "")),
            kategorie=str(daten.get("rezept_kategorie", "")),
            beschreibung=str(daten.get("rezept_beschreibung", "")),
            autor=benutzer.name,
        )
        rezept_speichern(reg, sitzung, rezept, autor=benutzer.name, freigegeben=benutzer.ist_admin)
    except FehlerSammlung as e:
        return _render(request, "_fehler.html", benutzer, fehler=e.fehler, ohne_oob=True)
    return _render(
        request,
        "_bk_rezept_gespeichert.html",
        benutzer,
        rezept=rezept,
        ziele=reg.rezept_ziele(rezept),
        ziel=formular.ziel,
        vorschlag=not benutzer.ist_admin,
    )


@router.get("/rezepte/{rid}/yaml")
async def rezept_yaml(
    request: Request, rid: str, benutzer: Benutzer = Depends(aktueller_benutzer)
) -> Response:
    rezept = _registry(request).rezepte.get(rid)
    if rezept is None:
        raise HTTPException(404, "Rezept nicht gefunden")
    return Response(
        rezept_als_yaml(rezept),
        media_type="application/x-yaml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{rezept.id}.yaml"'},
    )
