"""HTML-Seiten (Jinja2 + htmx): Rezept-Modus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select

from app.auth import aktueller_benutzer
from app.db import GespeichertesRezept, GespeichertesScript
from app.escaping import Ziel
from app.generators.base import ZIEL_ANZEIGE
from app.models.block import ZAHLENTYPEN, ParamTyp, Risiko
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
from app.validation import LISTEN_MIT_LEERZEICHEN, FehlerSammlung

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
            "ZAHLENTYPEN": ZAHLENTYPEN,
            "LISTEN_MIT_LEERZEICHEN": LISTEN_MIT_LEERZEICHEN,
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


RISIKO_TEXT = {Risiko.GRUEN: "nur lesen", Risiko.GELB: "ändert etwas", Risiko.ROT: "kritisch"}
ZIEL_KURZNAME = {Ziel.POWERSHELL: "Windows", Ziel.CMD: "Windows", Ziel.BASH: "Linux", Ziel.ZSH: "macOS"}


@dataclass
class RezeptKarte:
    rezept: RezeptDef
    verfuegbar: bool
    systeme: list[tuple[str, bool]]  # ("Windows", verfügbar?) …
    risiko: Risiko
    risiko_text: str
    schritte: int
    rechte: str  # "braucht Admin" / "braucht sudo" / ""
    suche: str  # Name, Beschreibung, Kategorie, Schlagworte (clientseitige Suche)


def _karte(reg: Registry, r: RezeptDef, ziel: Ziel) -> RezeptKarte:
    ziele = reg.rezept_ziele(r)
    verfuegbar = ziel in ziele
    # Für nicht verfügbare Rezepte Schritte/Risiko/Rechte am ersten verfügbaren Ziel zeigen
    bezug = ziel if verfuegbar else ziele[0]
    bloecke = rezept_bloecke(reg, r, bezug)
    risiko = max_risiko(bloecke)
    rechte = ""
    if any(b.braucht_admin(bezug) for b in bloecke):
        rechte = "braucht Admin" if bezug in (Ziel.POWERSHELL, Ziel.CMD) else "braucht sudo"
    systeme = [
        ("Windows", Ziel.POWERSHELL in ziele or Ziel.CMD in ziele),
        ("macOS", Ziel.ZSH in ziele),
        ("Linux", Ziel.BASH in ziele),
    ]
    return RezeptKarte(
        rezept=r,
        verfuegbar=verfuegbar,
        systeme=systeme,
        risiko=risiko,
        risiko_text=RISIKO_TEXT[risiko],
        schritte=len(bloecke),
        rechte=rechte,
        suche=" ".join([r.name, r.beschreibung, r.kategorie, *r.schlagworte]),
    )


def _rezepte_fuer(reg: Registry, ziel: Ziel, q: str, kategorie: str) -> list[RezeptDef]:
    """Server-Filter (ohne JavaScript bzw. für ?q=…); mit JavaScript filtert die Seite live."""
    suchwoerter = q.lower().split()
    treffer = []
    for r in sorted(reg.rezepte.values(), key=lambda r: (r.kategorie, r.name)):
        if not r.freigegeben or not reg.rezept_ziele(r):
            continue
        if kategorie and r.kategorie != kategorie:
            continue
        text = " ".join([r.name, r.beschreibung, r.kategorie, *r.schlagworte]).lower()
        if all(w in text for w in suchwoerter):
            treffer.append(r)
    return treffer


def _zuletzt(sitzung: Any, benutzer: Benutzer, reg: Registry, ziel: Ziel) -> list[RezeptKarte]:
    """Die letzten (bis zu vier) Rezepte, aus denen dieser Benutzer Scripte erzeugt hat."""
    ids: list[str] = []
    for quelle in sitzung.scalars(
        select(GespeichertesScript.quelle)
        .where(GespeichertesScript.autor == benutzer.name, GespeichertesScript.quelle.like("rezept:%"))
        .order_by(GespeichertesScript.erstellt_am.desc(), GespeichertesScript.id.desc())
        .limit(50)
    ):
        rid = quelle.removeprefix("rezept:")
        r = reg.rezepte.get(rid)
        if r is not None and r.freigegeben and rid not in ids and ziel in reg.rezept_ziele(r):
            ids.append(rid)
        if len(ids) == 4:
            break
    return [_karte(reg, reg.rezepte[rid], ziel) for rid in ids]


@router.get("/rezepte", name="rezepte", response_class=HTMLResponse)
async def rezepte(
    request: Request,
    ziel: str | None = None,
    q: str = "",
    kategorie: str = "",
    benutzer: Benutzer = Depends(aktueller_benutzer),
    sitzung: Any = Depends(_sitzung),
) -> Response:
    z = _ziel(ziel)
    if z is None:
        # Schritt 1 des Rezept-Ablaufs: Betriebssystem wählen
        return _render(request, "betriebssystem.html", benutzer, kacheln=ZIEL_KACHELN)
    reg = _registry(request)
    karten = [_karte(reg, r, z) for r in _rezepte_fuer(reg, z, q[:100], kategorie[:100])]
    gruppen: dict[str, list[RezeptKarte]] = {}
    for k in karten:
        if k.verfuegbar:
            gruppen.setdefault(k.rezept.kategorie, []).append(k)
    return _render(
        request,
        "rezepte.html",
        benutzer,
        ziel=z,
        ziel_kurz=ZIEL_KURZNAME[z],
        q=q,
        kategorie=kategorie,
        kategorien=sorted(
            {r.kategorie for r in reg.rezepte.values() if r.freigegeben and reg.rezept_ziele(r)}
        ),
        gruppen=gruppen,
        nicht_verfuegbar=[k for k in karten if not k.verfuegbar],
        zuletzt=[] if q or kategorie else _zuletzt(sitzung, benutzer, reg, z),
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
