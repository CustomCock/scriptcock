"""Verwaltung (nur Admins): Rezept-Vorschläge freigeben, eigene Rezepte löschen."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError
from sqlalchemy import func, select

from app.auth import aktueller_benutzer
from app.baukasten import db_rezept, rezept_als_yaml, rezept_freigeben, rezept_loeschen
from app.db import GespeichertesRezept, GespeichertesScript
from app.registry import Registry
from app.routes.pages import _render, _sitzung
from app.service import Benutzer
from app.validation import FehlerSammlung

router = APIRouter()


def admin(benutzer: Benutzer = Depends(aktueller_benutzer)) -> Benutzer:
    if not benutzer.ist_admin:
        raise HTTPException(403, "Nur für Admins.")
    return benutzer


def _hole(sitzung: Any, rid: int) -> GespeichertesRezept:
    eintrag: GespeichertesRezept | None = sitzung.get(GespeichertesRezept, rid)
    if eintrag is None:
        raise HTTPException(404, "Rezept nicht gefunden")
    return eintrag


def _ansicht(reg: Registry, eintrag: GespeichertesRezept) -> dict[str, Any]:
    try:
        rezept = db_rezept(eintrag)
    except ValidationError:
        return {
            "e": eintrag,
            "rezept": None,
            "schritte": [],
            "ziele": [],
            "fehler": ["Rezept ist nicht lesbar."],
        }
    schritte = []
    for s in rezept.schritte:
        block = reg.bloecke.get(s.block)
        schritte.append(
            {"name": block.name if block else f"{s.block} (fehlt!)", "parameter": s.parameter, "block": block}
        )
    return {
        "e": eintrag,
        "rezept": rezept,
        "schritte": schritte,
        "ziele": reg.rezept_ziele(rezept),
        "fehler": [] if eintrag.freigegeben else reg.rezept_pruefen(rezept),
    }


@router.get("/verwaltung", name="verwaltung", response_class=HTMLResponse)
async def verwaltung(
    request: Request, benutzer: Benutzer = Depends(admin), sitzung: Any = Depends(_sitzung)
) -> Response:
    reg: Registry = request.app.state.registry
    eintraege = list(
        sitzung.scalars(select(GespeichertesRezept).order_by(GespeichertesRezept.erstellt_am.desc()))
    )
    statistik = {
        "scripte": sitzung.scalar(select(func.count()).select_from(GespeichertesScript)) or 0,
        "bibliothek": sitzung.scalar(
            select(func.count()).select_from(GespeichertesScript).where(GespeichertesScript.in_bibliothek)
        )
        or 0,
        "bloecke": len(reg.bloecke),
        "rezepte": len(reg.rezepte),
    }
    return _render(
        request,
        "verwaltung.html",
        benutzer,
        vorschlaege=[_ansicht(reg, e) for e in eintraege if not e.freigegeben],
        freigegeben=[_ansicht(reg, e) for e in eintraege if e.freigegeben],
        statistik=statistik,
    )


@router.post("/verwaltung/rezepte/{rid}/freigeben", response_class=HTMLResponse)
async def freigeben(
    request: Request, rid: int, benutzer: Benutzer = Depends(admin), sitzung: Any = Depends(_sitzung)
) -> Response:
    eintrag = _hole(sitzung, rid)
    try:
        rezept_freigeben(request.app.state.registry, sitzung, eintrag)
    except FehlerSammlung as e:
        return _render(request, "_fehler.html", benutzer, fehler=e.fehler, ohne_oob=True)
    return Response(status_code=204, headers={"HX-Refresh": "true"})


@router.post("/verwaltung/rezepte/{rid}/loeschen")
async def loeschen(
    request: Request, rid: int, benutzer: Benutzer = Depends(admin), sitzung: Any = Depends(_sitzung)
) -> Response:
    rezept_loeschen(request.app.state.registry, sitzung, _hole(sitzung, rid))
    return Response(status_code=204, headers={"HX-Refresh": "true"})


@router.get("/verwaltung/rezepte/{rid}/yaml")
async def yaml_export(
    rid: int, benutzer: Benutzer = Depends(admin), sitzung: Any = Depends(_sitzung)
) -> Response:
    eintrag = _hole(sitzung, rid)
    try:
        text = rezept_als_yaml(db_rezept(eintrag))
    except ValidationError:
        raise HTTPException(422, "Rezept ist nicht lesbar.") from None
    return Response(
        text,
        media_type="application/x-yaml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{eintrag.rezept_id}.yaml"'},
    )
