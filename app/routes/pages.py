"""HTML-Seiten (Jinja2 + htmx): Rezept-Modus."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select

from app.auth import aktueller_benutzer
from app.db import GespeichertesRezept, GespeichertesScript
from app.escaping import Ziel
from app.generators.base import ZIEL_ANZEIGE
from app.models.block import ParamTyp, Risiko
from app.models.recipe import RezeptDef
from app.registry import Registry
from app.service import (
    Benutzer,
    erzeuge,
    max_risiko,
    pruefe_feld,
    rechte_hinweis,
    rezept_bloecke,
    rezept_felder,
    rezept_zu_request,
)
from app.validation import FehlerSammlung

router = APIRouter()

ZIEL_KACHELN = [
    (Ziel.POWERSHELL, "Windows PowerShell", "Empfohlen für Windows 10/11", "ps"),
    (Ziel.CMD, "Windows CMD", "Klassische Eingabeaufforderung", "cmd"),
    (Ziel.BASH, "Linux", "Bash – Debian, Ubuntu, Fedora …", "linux"),
    (Ziel.ZSH, "macOS", "zsh – Terminal auf dem Mac", "mac"),
]
FELD_PREFIX = "f."
HLJS_SPRACHE = {Ziel.POWERSHELL: "powershell", Ziel.CMD: "dos", Ziel.BASH: "bash", Ziel.ZSH: "bash"}


def _render(request: Request, vorlage: str, benutzer: Benutzer | None = None, **kontext: Any) -> HTMLResponse:
    templates = request.app.state.templates
    antwort: HTMLResponse = templates.TemplateResponse(
        request,
        vorlage,
        {
            "benutzer": benutzer,
            "ziel_anzeige": ZIEL_ANZEIGE,
            "ParamTyp": ParamTyp,
            "Risiko": Risiko,
            **kontext,
        },
    )
    return antwort


def _registry(request: Request) -> Registry:
    reg: Registry = request.app.state.registry
    return reg


def _ziel(wert: str | None) -> Ziel | None:
    try:
        return Ziel(wert) if wert else None
    except ValueError:
        return None


def _rezept(request: Request, rid: str) -> RezeptDef:
    rezept = _registry(request).rezepte.get(rid)
    if rezept is None or not rezept.freigegeben:
        raise HTTPException(404, "Rezept nicht gefunden")
    return rezept


def _sitzung(request: Request) -> Any:
    yield from request.app.state.db.sitzung()


@router.get("/", name="startseite", response_class=HTMLResponse)
async def startseite(
    request: Request, benutzer: Benutzer = Depends(aktueller_benutzer), sitzung: Any = Depends(_sitzung)
) -> Response:
    """Einstieg: die drei Modi, zuletzt erstellte Scripte, Bibliothek (und offene Vorschläge für Admins)."""
    zuletzt = list(
        sitzung.scalars(
            select(GespeichertesScript)
            .where(GespeichertesScript.autor == benutzer.name)
            .order_by(GespeichertesScript.erstellt_am.desc(), GespeichertesScript.id.desc())
            .limit(6)
        )
    )
    bibliothek_anzahl = sitzung.scalar(
        select(func.count()).select_from(GespeichertesScript).where(GespeichertesScript.in_bibliothek)
    )
    vorschlaege = 0
    if benutzer.ist_admin:
        vorschlaege = sitzung.scalar(
            select(func.count())
            .select_from(GespeichertesRezept)
            .where(GespeichertesRezept.freigegeben.is_(False))
        )
    return _render(
        request,
        "index.html",
        benutzer,
        zuletzt=zuletzt,
        bibliothek_anzahl=bibliothek_anzahl or 0,
        vorschlaege=vorschlaege or 0,
        anzahl_rezepte=sum(1 for r in _registry(request).rezepte.values() if r.freigegeben),
    )


def _rezepte_fuer(reg: Registry, ziel: Ziel, q: str, kategorie: str) -> list[RezeptDef]:
    suchwoerter = q.lower().split()
    treffer = []
    for r in sorted(reg.rezepte.values(), key=lambda r: (r.kategorie, r.name)):
        if not r.freigegeben or ziel not in reg.rezept_ziele(r):
            continue
        if kategorie and r.kategorie != kategorie:
            continue
        text = " ".join([r.name, r.beschreibung, r.kategorie, *r.schlagworte]).lower()
        if all(w in text for w in suchwoerter):
            treffer.append(r)
    return treffer


@router.get("/rezepte", name="rezepte", response_class=HTMLResponse)
async def rezepte(
    request: Request,
    ziel: str | None = None,
    q: str = "",
    kategorie: str = "",
    benutzer: Benutzer = Depends(aktueller_benutzer),
) -> Response:
    z = _ziel(ziel)
    if z is None:
        # Schritt 1 des Rezept-Ablaufs: Betriebssystem wählen
        return _render(request, "betriebssystem.html", benutzer, kacheln=ZIEL_KACHELN)
    reg = _registry(request)
    liste = _rezepte_fuer(reg, z, q[:100], kategorie[:100])
    if request.headers.get("HX-Request") and request.headers.get("HX-Target") == "rezeptliste":
        return _render(request, "_rezeptliste.html", benutzer, rezepte=liste, ziel=z, reg=reg)
    kategorien = sorted({r.kategorie for r in reg.rezepte.values() if z in reg.rezept_ziele(r)})
    return _render(
        request,
        "rezepte.html",
        benutzer,
        rezepte=liste,
        ziel=z,
        q=q,
        kategorie=kategorie,
        kategorien=kategorien,
        reg=reg,
    )


@router.get("/rezepte/{rid}", name="rezept", response_class=HTMLResponse)
async def rezept_formular(
    request: Request, rid: str, ziel: str | None = None, benutzer: Benutzer = Depends(aktueller_benutzer)
) -> Response:
    rezept = _rezept(request, rid)
    reg = _registry(request)
    z = _ziel(ziel)
    if z is None or z not in reg.rezept_ziele(rezept):
        return RedirectResponse(request.app.state.einstellungen.root_path + "/rezepte")
    bloecke = rezept_bloecke(reg, rezept, z)
    return _render(
        request,
        "rezept.html",
        benutzer,
        rezept=rezept,
        ziel=z,
        felder=rezept_felder(reg, rezept, z),
        bloecke=bloecke,
        risiko=max_risiko(bloecke),
        admin=any(b.braucht_admin(z) for b in bloecke),
        hinweise=[(b.name, b.hinweise[z]) for b in bloecke if z in b.hinweise],
    )


@router.post("/rezepte/{rid}/feld/{fid}", response_class=HTMLResponse)
async def feld_pruefen(
    request: Request, rid: str, fid: str, ziel: str, benutzer: Benutzer = Depends(aktueller_benutzer)
) -> Response:
    rezept = _rezept(request, rid)
    z = _ziel(ziel)
    feld = next((f for f in rezept.felder if f.id == fid), None)
    if feld is None or z is None:
        raise HTTPException(404)
    formular = await request.form()
    fehler = pruefe_feld(feld, formular.get(FELD_PREFIX + fid), z)
    return _render(request, "_feldstatus.html", benutzer, fehler=fehler)


@router.post("/rezepte/{rid}/erzeugen", response_class=HTMLResponse)
async def rezept_erzeugen(
    request: Request,
    rid: str,
    benutzer: Benutzer = Depends(aktueller_benutzer),
    sitzung: Any = Depends(_sitzung),
) -> Response:
    rezept = _rezept(request, rid)
    reg = _registry(request)
    formular = await request.form()
    z = _ziel(str(formular.get("ziel", "")))
    if z is None or z not in reg.rezept_ziele(rezept):
        raise HTTPException(400, "Ungültiges Zielsystem")
    werte = {k: v for k, v in formular.items() if isinstance(v, str)}
    # Rezeptfelder tragen das Präfix "f.", damit sie nie mit "ziel", "titel" usw. kollidieren.
    felder = {k.removeprefix(FELD_PREFIX): v for k, v in werte.items() if k.startswith(FELD_PREFIX)}
    try:
        req = rezept_zu_request(
            reg,
            rezept,
            z,
            felder,
            titel=werte.get("titel", "").strip()[:120],
            dry_run=werte.get("dry_run") == "true",
            rot_bestaetigt=werte.get("rot_bestaetigt") == "true",
        )
        ergebnis = erzeuge(reg, req, benutzer, sitzung)
    except FehlerSammlung as e:
        return _render(request, "_fehler.html", benutzer, fehler=e.fehler)
    return _render(
        request,
        "_vorschau.html",
        benutzer,
        ergebnis=ergebnis,
        ziel=z,
        sprache=HLJS_SPRACHE[z],
        rechte=rechte_hinweis(reg, ergebnis.ir, z),
    )


@router.get("/skripte/{sid}/download", name="download")
async def download(
    request: Request,
    sid: int,
    benutzer: Benutzer = Depends(aktueller_benutzer),
    sitzung: Any = Depends(_sitzung),
) -> Response:
    eintrag = sitzung.scalar(select(GespeichertesScript).where(GespeichertesScript.id == sid))
    if eintrag is None or (
        eintrag.autor != benutzer.name and not eintrag.in_bibliothek and not benutzer.ist_admin
    ):
        raise HTTPException(404, "Script nicht gefunden")
    return Response(
        content=eintrag.inhalt,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{eintrag.dateiname}"',
            "X-Script-SHA256": eintrag.sha256,
        },
    )
