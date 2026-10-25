"""Registry in der Oberfläche: Seite ``/registry`` und JSON-API für das Registry-Panel.

Der Richtlinien-Katalog ist zu groß zum Einbetten – Suche, Kategoriebaum und Details kommen per API
(FTS5 im Backend). Häufige Einstellungen und .reg-Import liefern fertige Schritte
(``block_id`` + ``parameter``), die das Panel in Baukasten, Blockly oder Rezept übernimmt; geprüft
wird wie immer erst beim Erzeugen (und für die .reg-Vorschau schon hier, Schritt für Schritt).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from app import regdatei
from app.auth import aktueller_benutzer
from app.escaping import Ziel
from app.models.block import ParameterDef, ParamTyp, Risiko
from app.models.request import ScriptRequest
from app.registry import Registry
from app.richtlinien import haeufig, haeufig_schritte, parameter_fuer
from app.routes.pages import _render
from app.service import Benutzer
from app.validation import (
    FehlerSammlung,
    ValidierungsFehler,
    registry_pfad_fuer_bereich,
    registry_ps_form,
    validiere_request,
    validiere_wert,
)

router = APIRouter()

HAEUFIG_ANZEIGE = ("id", "titel", "beschreibung", "gruppe", "bereich", "wirkung", "risiko")
KLASSE_TEXT = {"machine": "Computer", "user": "Benutzer", "both": "Computer und Benutzer"}
_PFAD = ParameterDef(id="pfad", label="Schlüssel", typ=ParamTyp.REGISTRY_PFAD)


def _registry(request: Request) -> Registry:
    reg: Registry = request.app.state.registry
    return reg


def parameter_daten(p: ParameterDef) -> dict[str, Any]:
    """ParameterDef → JSON für die Formulare im Panel und in Blockly (gleiches Format wie der Katalog)."""
    return p.model_dump(mode="json")


def richtlinie_daten(reg: Registry, rid: str) -> dict[str, Any] | None:
    """Details einer Richtlinie fürs Panel: Texte, Registry-Orte, Formularfelder der Elemente."""
    r = reg.richtlinien.richtlinie(rid)
    if r is None:
        return None
    paket = reg.richtlinien.paket(r["paket"]) or {}
    wurzeln = {"machine": ["HKLM"], "user": ["HKCU"], "both": ["HKLM", "HKCU"]}[r["klasse"]]
    orte: list[dict[str, str]] = []
    gesehen: set[tuple[str, str]] = set()
    kandidaten = [(r["schluessel"], r["wertname"])]
    for zustand in ("aktiviert", "deaktiviert"):
        kandidaten += [(i["schluessel"], i["wertname"]) for i in r[zustand]["liste"]]
    kandidaten += [(e["schluessel"], e.get("wertname", "")) for e in r["elemente"]]
    for schluessel, wertname in kandidaten:
        schon = (schluessel.lower(), wertname.lower()) in gesehen
        if schon or not (wertname or schluessel != r["schluessel"]):
            continue
        gesehen.add((schluessel.lower(), wertname.lower()))
        for w in wurzeln:
            orte.append({"schluessel": f"{w}\\{schluessel}", "wertname": wertname})
    if not orte:
        orte = [{"schluessel": f"{w}\\{r['schluessel']}", "wertname": ""} for w in wurzeln]
    return {
        "id": r["id"],
        "paket": r["paket"],
        "paket_name": paket.get("name", r["paket"]),
        "paket_version": paket.get("version", ""),
        "titel": r["titel"],
        "erklaerung": r["erklaerung"],
        "sprache": r["sprache"],
        "unterstuetzt": r["unterstuetzt"],
        "klasse": r["klasse"],
        "klasse_text": KLASSE_TEXT[r["klasse"]],
        "kategorie_pfad": r["kategorie_pfad"],
        "datei": r["datei"],
        "orte": orte,
        "parameter": [parameter_daten(p) for p, _ in parameter_fuer(r)],
    }


# --- Seite ---------------------------------------------------------------------------------------


@router.get("/registry", name="registry", response_class=HTMLResponse)
async def registry_seite(request: Request, benutzer: Benutzer = Depends(aktueller_benutzer)) -> Response:
    return _render(request, "registry.html", benutzer)


# --- Richtlinien -----------------------------------------------------------------------------------


@router.get("/api/registry/pakete")
async def pakete(request: Request, benutzer: Benutzer = Depends(aktueller_benutzer)) -> dict[str, Any]:
    return {"pakete": _registry(request).richtlinien.pakete()}


@router.get("/api/registry/kategorien")
async def kategorien(
    request: Request,
    eltern: str = "",
    paket: str = "",
    benutzer: Benutzer = Depends(aktueller_benutzer),
) -> dict[str, Any]:
    liste = _registry(request).richtlinien.kategorien(eltern[:300] or None, paket[:40] or None)
    return {
        "kategorien": [
            {"id": k["id"], "name": k["name"], "anzahl": k["anzahl"], "hat_kinder": bool(k["hat_kinder"])}
            for k in liste
        ]
    }


@router.get("/api/registry/suche")
async def suche(
    request: Request,
    q: str = "",
    paket: str = "",
    klasse: str = "",
    kategorie: str = "",
    seite: int = 1,
    benutzer: Benutzer = Depends(aktueller_benutzer),
) -> dict[str, Any]:
    erg = _registry(request).richtlinien.suche(
        q[:200], paket[:40] or None, klasse or None, kategorie[:300] or None, seite=seite, pro_seite=25
    )
    for t in erg["treffer"]:
        t["klasse_text"] = KLASSE_TEXT.get(t["klasse"], t["klasse"])
    erg["pro_seite"] = 25
    return erg


@router.get("/api/registry/richtlinie")
async def richtlinie(
    request: Request, id: str, benutzer: Benutzer = Depends(aktueller_benutzer)
) -> dict[str, Any]:
    daten = richtlinie_daten(_registry(request), id[:300])
    if daten is None:
        raise HTTPException(404, "Diese Richtlinie gibt es im Katalog nicht.")
    return daten


# --- Häufige Einstellungen -------------------------------------------------------------------------


@router.get("/api/registry/haeufig")
async def haeufige(request: Request, benutzer: Benutzer = Depends(aktueller_benutzer)) -> dict[str, Any]:
    reg = _registry(request)
    eintraege = []
    richtlinien: dict[str, Any] = {}
    for e in haeufig():
        schritte = haeufig_schritte(e)
        for s in schritte:
            rid = s["parameter"].get("richtlinie")
            if rid and rid not in richtlinien:
                richtlinien[rid] = richtlinie_daten(reg, rid)
        eintraege.append(
            {
                **{k: e.get(k) for k in HAEUFIG_ANZEIGE},
                "quelle": e.get("quelle"),
                "hinweis": e.get("hinweis"),
                "anpassen": e.get("anpassen", []),
                "schritte": schritte,
            }
        )
    return {"eintraege": eintraege, "richtlinien": richtlinien}


# --- Eigener Eintrag: Pfad-Vorschau und .reg-Import -------------------------------------------------


@router.get("/api/registry/pfad")
async def pfad_vorschau(
    pfad: str = "", bereich: str = "computer", benutzer: Benutzer = Depends(aktueller_benutzer)
) -> dict[str, Any]:
    """Live-Vorschau: der Pfad in beiden Schreibweisen (reg.exe / PowerShell) oder die Fehlermeldung."""
    try:
        normal = validiere_wert(_PFAD, pfad[:600]).wert
        assert isinstance(normal, str)
        form = registry_pfad_fuer_bereich(normal, bereich, nur_lesen=False)
    except (ValidierungsFehler, AssertionError) as e:
        return {"ok": False, "fehler": str(e)}
    if bereich == "computer":
        ps = registry_ps_form(form).replace("Registry::HKEY_LOCAL_MACHINE", "HKLM:")
        return {"ok": True, "reg": form, "ps": ps}
    benutzer_text = {
        "angemeldeter_benutzer": "des angemeldeten Benutzers",
        "alle_benutzer": "jedes Benutzerprofils",
        "standardprofil": "des Standardprofils (neue Benutzer)",
    }.get(bereich, "")
    return {
        "ok": True,
        "reg": f"HKU\\<SID>\\{form}",
        "ps": f"Registry::HKEY_USERS\\<SID>\\{form}",
        "hinweis": f"HKCU {benutzer_text} – das Script ermittelt das richtige Profil, nie das Admin-Konto.",
    }


class RegImport(BaseModel):
    text: str = Field(max_length=regdatei.MAX_TEXT)


def _schritt_text(s: dict[str, Any]) -> str:
    p = s["parameter"]
    ort = str(p["pfad"]) + (f" → {p['wertname'] or '(Standard)'}" if "wertname" in p else "")
    if s["block_id"] == "registry_wert_setzen":
        daten = p["daten"]
        anzeige = " | ".join(daten) if isinstance(daten, list) else str(daten)
        return f"{ort} = {p['typ']} {anzeige[:120]}"
    return ort


@router.post("/api/registry/reg")
async def reg_import(
    request: Request, eingabe: RegImport, benutzer: Benutzer = Depends(aktueller_benutzer)
) -> dict[str, Any]:
    """.reg-Text → geprüfte Schritte (jeder einzeln validiert, Fehler mit Zeilennummer)."""
    reg = _registry(request)
    erg = regdatei.parsen(eingabe.text)
    schritte = []
    for e in erg.eintraege:
        s = regdatei.schritt(e)
        block = reg.bloecke[s["block_id"]]
        eintrag: dict[str, Any] = {
            **s,
            "zeile": e.zeile,
            "name": block.name,
            "text": _schritt_text(s),
            "risiko": block.risiko.value,
            "fehler": [],
        }
        try:
            anfrage = ScriptRequest.model_validate(
                {"ziel": Ziel.POWERSHELL.value, "titel": "reg", "rot_bestaetigt": True, "schritte": [s]}
            )
            ir = validiere_request(anfrage, reg, autor=benutzer.name, jetzt=datetime.now())
            risiko = getattr(ir.schritte[0], "risiko", None)
            if risiko is Risiko.ROT:
                eintrag["risiko"] = Risiko.ROT.value
        except FehlerSammlung as f:
            eintrag["fehler"] = [x.meldung for x in f.fehler]
        schritte.append(eintrag)
    return {"schritte": schritte, "fehler": erg.fehler, "hinweise": erg.hinweise}
