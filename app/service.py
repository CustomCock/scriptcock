"""Anwendungslogik zwischen Web-Schicht und Kern (Validierung → IR → Generator → DB)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db import GespeichertesScript
from app.escaping import Ziel
from app.generators import GeneratedScript, GenerierungsFehler, generator_fuer
from app.ir import ScriptIR
from app.models.block import BlockDef, ParameterDef, Risiko
from app.models.recipe import RezeptDef, feld_verweis, konstante
from app.models.request import SchrittEingabe, ScriptRequest
from app.registry import Registry
from app.validation import (
    FehlerSammlung,
    Feldfehler,
    ValidierungsFehler,
    pruefe_wert_fuer_ziel,
    validiere_request,
    validiere_wert,
)


@dataclass
class Benutzer:
    name: str
    anzeige: str
    ist_admin: bool


@dataclass
class Ergebnis:
    ir: ScriptIR
    script: GeneratedScript
    gespeichert: GespeichertesScript


def benutzte_parameter(registry: Registry, block: BlockDef, ziel: Ziel) -> set[str]:
    return registry.benutzte_parameter(block, ziel)


def rezept_felder(registry: Registry, rezept: RezeptDef, ziel: Ziel) -> list[ParameterDef]:
    """Formularfelder, die für ``ziel`` eine Rolle spielen."""
    relevant: set[str] = set()
    for schritt in rezept.schritte_fuer(ziel):
        block = registry.bloecke[schritt.block]
        genutzt = benutzte_parameter(registry, block, ziel)
        for pid, wert in schritt.parameter.items():
            verweis = feld_verweis(wert)
            if verweis and pid in genutzt:
                relevant.add(verweis)
    return [f for f in rezept.felder if f.id in relevant]


@dataclass
class RechteHinweis:
    """Für Badge und Anleitung: welche Rechte das Script braucht und für welche Schritte."""

    art: str  # "Admin" (Windows) oder "sudo" (Linux/macOS)
    schritte: str  # "Schritt 2 (Dienst neu starten), Schritt 4 (…)"


def rechte_hinweis(registry: Registry, ir: ScriptIR, ziel: Ziel) -> RechteHinweis | None:
    schritte = [
        f"Schritt {i} ({b.name})"
        for i, s in enumerate(ir.bloecke(), 1)
        if (b := registry.bloecke.get(s.block_id)) is not None and b.braucht_admin(ziel)
    ]
    if not schritte:
        return None
    return RechteHinweis("Admin" if ziel in (Ziel.POWERSHELL, Ziel.CMD) else "sudo", ", ".join(schritte))


def rezept_bloecke(registry: Registry, rezept: RezeptDef, ziel: Ziel) -> list[BlockDef]:
    return [registry.bloecke[s.block] for s in rezept.schritte_fuer(ziel)]


def max_risiko(bloecke: list[BlockDef]) -> Risiko:
    return max((b.risiko for b in bloecke), key=lambda r: r.stufe, default=Risiko.GRUEN)


def pruefe_feld(feld: ParameterDef, roh: Any, ziel: Ziel) -> str | None:
    """Live-Validierung eines einzelnen Formularfelds. ``None`` = in Ordnung."""
    try:
        wert = validiere_wert(feld, roh)
        pruefe_wert_fuer_ziel(wert, ziel)
    except ValidierungsFehler as e:
        return str(e)
    return None


def rezept_zu_request(
    registry: Registry,
    rezept: RezeptDef,
    ziel: Ziel,
    formular: dict[str, Any],
    *,
    titel: str = "",
    dry_run: bool = False,
    rot_bestaetigt: bool = False,
) -> ScriptRequest:
    """Formularwerte eines Rezepts → ScriptRequest.

    Fehler werden pro *Formularfeld* gemeldet (``Feldfehler.feld`` = Feld-ID).
    """
    felder = rezept_felder(registry, rezept, ziel)
    werte: dict[str, Any] = {}
    fehler: list[Feldfehler] = []
    for feld in felder:
        try:
            wert = validiere_wert(feld, formular.get(feld.id))
            pruefe_wert_fuer_ziel(wert, ziel)
            werte[feld.id] = wert.wert
        except ValidierungsFehler as e:
            fehler.append(Feldfehler(None, feld.id, str(e)))
    if fehler:
        raise FehlerSammlung(fehler)

    schritte = []
    for schritt in rezept.schritte_fuer(ziel):
        parameter: dict[str, Any] = {}
        for pid, wert in schritt.parameter.items():
            verweis = feld_verweis(wert)
            if verweis is None:
                parameter[pid] = konstante(wert)
            elif verweis in werte:
                parameter[pid] = werte[verweis]
        schritte.append(SchrittEingabe(block_id=schritt.block, parameter=parameter))
    return ScriptRequest(
        ziel=ziel,
        titel=titel or rezept.name,
        beschreibung=rezept.beschreibung,
        dry_run=dry_run,
        rot_bestaetigt=rot_bestaetigt,
        quelle=f"rezept:{rezept.id}",
        schritte=schritte,
    )


def generiere(
    registry: Registry,
    req: ScriptRequest,
    benutzer: Benutzer,
    jetzt: datetime | None = None,
) -> tuple[ScriptIR, GeneratedScript]:
    """Validiert und erzeugt ein Script, ohne es zu speichern (z. B. für die Live-Vorschau)."""
    ir = validiere_request(
        req,
        registry,
        autor=benutzer.name,
        jetzt=(jetzt or datetime.now()).replace(microsecond=0),
        ist_admin=benutzer.ist_admin,
    )
    try:
        script = generator_fuer(req.ziel, registry).erzeuge(ir)
    except GenerierungsFehler as e:
        raise FehlerSammlung([Feldfehler(None, None, str(e))]) from None
    return ir, script


def erzeuge(
    registry: Registry,
    req: ScriptRequest,
    benutzer: Benutzer,
    sitzung: Session,
    jetzt: datetime | None = None,
) -> Ergebnis:
    """Validiert, erzeugt und speichert ein Script."""
    ir, script = generiere(registry, req, benutzer, jetzt)
    eintrag = GespeichertesScript(
        erstellt_am=ir.meta.erstellt_am,
        autor=benutzer.name,
        ziel=req.ziel.value,
        titel=ir.meta.titel,
        beschreibung=ir.meta.beschreibung,
        quelle=ir.meta.quelle,
        sha256=script.sha256,
        dateiname=script.dateiname,
        inhalt=script.inhalt,
        ir_json=ir.model_dump_json(),
    )
    sitzung.add(eintrag)
    sitzung.commit()
    return Ergebnis(ir=ir, script=script, gespeichert=eintrag)
