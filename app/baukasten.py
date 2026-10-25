"""Freier Baukasten (Listen-Modus): Formular lesen, Rezepte aus Schrittlisten bauen."""

from __future__ import annotations

import json
import logging
import re
import secrets
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import yaml
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import GespeichertesRezept
from app.escaping import Ziel
from app.models.block import ParameterDef, ParamTyp
from app.models.recipe import RezeptDef, RezeptSchritt
from app.models.request import SchrittEingabe, ScriptRequest
from app.registry import Registry, RegistryFehler
from app.validation import FehlerSammlung, Feldfehler, ValidierungsFehler, validiere_wert

log = logging.getLogger("baukasten")

UID_MUSTER = re.compile(r"^[a-f0-9]{8}$")
MAX_SCHRITTE = 100


def neue_uid() -> str:
    return secrets.token_hex(4)


@dataclass
class BaukastenFormular:
    """Inhalt des Baukasten-Formulars. Schritte in Reihenfolge der Liste."""

    ziel: Ziel
    titel: str = ""
    beschreibung: str = ""
    dry_run: bool = False
    rot_bestaetigt: bool = False
    uids: list[str] = field(default_factory=list)
    bloecke: list[str] = field(default_factory=list)
    werte: list[dict[str, str]] = field(default_factory=list)

    def als_request(self, *, rot_bestaetigt: bool | None = None) -> ScriptRequest:
        return ScriptRequest(
            ziel=self.ziel,
            titel=self.titel,
            beschreibung=self.beschreibung,
            dry_run=self.dry_run,
            rot_bestaetigt=self.rot_bestaetigt if rot_bestaetigt is None else rot_bestaetigt,
            quelle="baukasten",
            schritte=[
                SchrittEingabe(block_id=b, parameter={k: v for k, v in w.items() if v != ""})
                for b, w in zip(self.bloecke, self.werte, strict=True)
            ],
        )


class FormularFehler(ValueError):
    pass


def lies_formular(eintraege: Iterable[tuple[str, Any]]) -> BaukastenFormular:
    """Liest die Formulardaten (Reihenfolge wie im DOM).

    Schritte: ``schritt=<uid>:<block_id>``, Parameter: ``p.<uid>.<parameter_id>``.
    Bei mehrfach vorhandenen Namen (Checkbox + verstecktes ``false``) gewinnt der letzte Wert.
    """
    einfach: dict[str, str] = {}
    uids: list[str] = []
    bloecke: list[str] = []
    werte: dict[str, dict[str, str]] = {}
    for name, wert in eintraege:
        if not isinstance(wert, str):
            continue
        if name == "schritt":
            uid, _, block_id = wert.partition(":")
            if not UID_MUSTER.match(uid) or uid in werte:
                raise FormularFehler("Ungültige Schrittkennung.")
            uids.append(uid)
            bloecke.append(block_id[:64])
            werte[uid] = {}
        elif name.startswith("p."):
            _, uid, pid = [*name.split(".", 2), "", ""][:3]
            if uid in werte and pid:
                werte[uid][pid] = wert
        else:
            einfach[name] = wert
    if len(uids) > MAX_SCHRITTE:
        raise FormularFehler(f"Höchstens {MAX_SCHRITTE} Schritte pro Script.")
    try:
        ziel = Ziel(einfach.get("ziel", ""))
    except ValueError:
        raise FormularFehler("Bitte ein Zielsystem wählen.") from None
    return BaukastenFormular(
        ziel=ziel,
        titel=einfach.get("titel", "").strip()[:200],
        beschreibung=einfach.get("beschreibung", "").strip()[:2000],
        dry_run=einfach.get("dry_run") == "true",
        rot_bestaetigt=einfach.get("rot_bestaetigt") == "true",
        uids=uids,
        bloecke=bloecke,
        werte=[werte[u] for u in uids],
    )


# --- Rezept aus einer Schrittliste ------------------------------------------------

_REZEPT_NAME = ParameterDef(id="name", label="Name", typ=ParamTyp.TEXT_KURZ)
_REZEPT_KATEGORIE = ParameterDef(id="kategorie", label="Kategorie", typ=ParamTyp.TEXT_KURZ)
_REZEPT_BESCHREIBUNG = ParameterDef(id="beschreibung", label="Beschreibung", typ=ParamTyp.TEXT)


def _slug(text: str) -> str:
    text = text.lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(alt, neu)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")[:40] or "rezept"


def rezept_aus_formular(
    registry: Registry,
    formular: BaukastenFormular,
    *,
    name: str,
    kategorie: str,
    beschreibung: str,
    autor: str,
) -> RezeptDef:
    """Baut aus der aktuellen Schrittliste ein Rezept.

    Ausgefüllte Parameter werden feste Werte; leere Pflichtparameter ohne Standard
    werden zu Feldern im Rezept-Formular.
    """
    fehler: list[Feldfehler] = []
    texte: dict[str, str] = {}
    for feld, roh, param in (
        ("rezept_name", name, _REZEPT_NAME),
        ("rezept_kategorie", kategorie, _REZEPT_KATEGORIE),
        ("rezept_beschreibung", beschreibung, _REZEPT_BESCHREIBUNG),
    ):
        try:
            texte[feld] = str(validiere_wert(param, roh).wert)
        except ValidierungsFehler as e:
            fehler.append(Feldfehler(None, feld, f"{param.label}: {e}"))
    if not formular.uids:
        fehler.append(Feldfehler(None, None, "Die Liste enthält noch keinen Schritt."))

    felder: list[ParameterDef] = []
    schritte: list[RezeptSchritt] = []
    mehrere = len(formular.uids) > 1
    for i, (block_id, werte) in enumerate(zip(formular.bloecke, formular.werte, strict=True)):
        block = registry.bloecke.get(block_id)
        if block is None:
            fehler.append(Feldfehler(i, None, f"Unbekannter Baustein „{block_id}“."))
            continue
        parameter: dict[str, Any] = {}
        # Richtlinie: die Optionen (e_…) der gewählten Richtlinie gehören dazu
        for p in [*block.parameter, *registry.element_parameter(block, werte.get("richtlinie"))]:
            roh = werte.get(p.id, "")
            if roh.strip() == "":
                if p.pflicht and p.standard is None:
                    fid = f"s{i + 1}_{p.id}"
                    label = f"{block.name}: {p.label}" if mehrere else p.label
                    felder.append(p.model_copy(update={"id": fid, "label": label}))
                    parameter[p.id] = "$" + fid
                continue
            try:
                wert = validiere_wert(p, roh).wert
            except ValidierungsFehler as e:
                fehler.append(Feldfehler(i, p.id, f"{p.label}: {e}"))
                continue
            if isinstance(wert, str) and wert.startswith("$"):
                wert = "$" + wert  # wörtliches $ (siehe models/recipe.py)
            parameter[p.id] = wert
        schritte.append(RezeptSchritt(block=block.id, parameter=parameter))
    if fehler:
        raise FehlerSammlung(fehler)
    try:
        return RezeptDef(
            id=f"eigen_{_slug(texte['rezept_name'])}_{secrets.token_hex(2)}",
            name=texte["rezept_name"],
            kategorie=texte["rezept_kategorie"],
            beschreibung=texte["rezept_beschreibung"],
            felder=felder,
            schritte=schritte,
            quelle=f"Datenbank (erstellt von {autor})",
        )
    except ValidationError as e:
        raise FehlerSammlung([Feldfehler(None, None, str(e))]) from None


def rezept_speichern(
    registry: Registry, sitzung: Session, rezept: RezeptDef, *, autor: str, freigegeben: bool
) -> GespeichertesRezept:
    """Prüft das Rezept gegen die Registry und speichert es.

    Freigegebene Rezepte (von Admins) sind sofort sichtbar; Vorschläge von Nutzern
    warten in der Verwaltung auf Freigabe.
    """
    fehler = registry.rezept_pruefen(rezept)
    if fehler:
        raise FehlerSammlung([Feldfehler(None, None, f) for f in fehler])
    if freigegeben:
        registry.rezept_hinzufuegen(rezept)
    eintrag = GespeichertesRezept(
        rezept_id=rezept.id,
        name=rezept.name,
        daten_json=rezept.model_dump_json(),
        autor=autor,
        erstellt_am=datetime.now().replace(microsecond=0),
        freigegeben=freigegeben,
    )
    sitzung.add(eintrag)
    sitzung.commit()
    return eintrag


def db_rezept(eintrag: GespeichertesRezept) -> RezeptDef:
    return RezeptDef.model_validate_json(eintrag.daten_json)


def rezept_freigeben(registry: Registry, sitzung: Session, eintrag: GespeichertesRezept) -> RezeptDef:
    """Gibt einen Vorschlag frei – mit erneuter Prüfung gegen die aktuellen Bausteine."""
    try:
        rezept = db_rezept(eintrag)
        registry.rezept_hinzufuegen(rezept)
    except ValidationError as e:
        raise FehlerSammlung([Feldfehler(None, None, f"Rezept ist nicht lesbar: {e}")]) from None
    except RegistryFehler as e:
        raise FehlerSammlung([Feldfehler(None, None, f) for f in e.fehler]) from None
    eintrag.freigegeben = True
    sitzung.commit()
    return rezept


def rezept_loeschen(registry: Registry, sitzung: Session, eintrag: GespeichertesRezept) -> None:
    registry.rezept_entfernen(eintrag.rezept_id)
    sitzung.delete(eintrag)
    sitzung.commit()


def lade_db_rezepte(registry: Registry, sitzung: Session) -> int:
    """Lädt freigegebene Rezepte aus der Datenbank. Ungültige werden übersprungen (mit Warnung)."""
    anzahl = 0
    for eintrag in sitzung.scalars(select(GespeichertesRezept).where(GespeichertesRezept.freigegeben)):
        try:
            rezept = RezeptDef.model_validate_json(eintrag.daten_json)
            if rezept.id not in registry.rezepte:
                registry.rezept_hinzufuegen(rezept)
                anzahl += 1
        except (ValidationError, RegistryFehler, json.JSONDecodeError) as e:
            log.warning("Rezept %s aus der Datenbank übersprungen: %s", eintrag.rezept_id, e)
    return anzahl


def rezept_als_yaml(rezept: RezeptDef) -> str:
    daten = rezept.model_dump(mode="json", exclude={"quelle"}, exclude_defaults=True)
    kopf = (
        "# Exportiert aus dem okm Script-Baukasten.\n"
        "# Zum dauerhaften Übernehmen unter recipes/ ablegen und per Pull-Request einreichen.\n"
    )
    return kopf + yaml.safe_dump(daten, allow_unicode=True, sort_keys=False)
