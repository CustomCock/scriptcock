"""Bibliothek: gespeicherte Scripte suchen, beschriften, bewerten und erneut öffnen."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.db import Bewertung, GespeichertesScript
from app.escaping import UnsicherError, Ziel, pruefe_zeichen
from app.ir import ScriptIR
from app.registry import Registry
from app.service import Benutzer
from app.validation import FehlerSammlung, Feldfehler, ValidierungsFehler

SEITENGROESSE = 50
_TAG = re.compile(r"^[\w\-.]{1,30}$")


class KeinZugriffAufScript(Exception):
    pass


def tags_lesen(roh: str) -> list[str]:
    """``"Drucker, netzwerk  test"`` → ``["drucker", "netzwerk", "test"]`` (geprüft, ohne Doppelte)."""
    tags: list[str] = []
    for teil in re.split(r"[,\s]+", roh.strip().lower()):
        if not teil:
            continue
        if not _TAG.match(teil):
            raise ValidierungsFehler(
                f"Ungültiger Tag „{teil}“. Erlaubt sind Buchstaben, Ziffern, - _ . (höchstens 30 Zeichen)."
            )
        if teil not in tags:
            tags.append(teil)
    if len(tags) > 10:
        raise ValidierungsFehler("Höchstens 10 Tags.")
    return tags


def tags_als_text(tags: list[str]) -> str:
    # Mit Kommas umschlossen, damit die Suche nach ",tag," exakt trifft.
    return "," + ",".join(tags) + "," if tags else ""


def tags_aus_text(text: str) -> list[str]:
    return [t for t in text.split(",") if t]


def darf_lesen(eintrag: GespeichertesScript, benutzer: Benutzer) -> bool:
    return eintrag.in_bibliothek or eintrag.autor == benutzer.name or benutzer.ist_admin


def darf_aendern(eintrag: GespeichertesScript, benutzer: Benutzer) -> bool:
    return eintrag.autor == benutzer.name or benutzer.ist_admin


def hole(sitzung: Session, sid: int, benutzer: Benutzer, *, aendern: bool = False) -> GespeichertesScript:
    eintrag = sitzung.get(GespeichertesScript, sid)
    if eintrag is None or not darf_lesen(eintrag, benutzer):
        raise KeinZugriffAufScript()
    if aendern and not darf_aendern(eintrag, benutzer):
        raise KeinZugriffAufScript()
    return eintrag


def in_bibliothek_speichern(
    sitzung: Session,
    eintrag: GespeichertesScript,
    *,
    titel: str,
    beschreibung: str,
    tags: str,
) -> GespeichertesScript:
    # Titel/Beschreibung sind reine Metadaten (nur HTML-escaped angezeigt, nie in Scripten),
    # daher genügt hier: keine Steuerzeichen, Länge begrenzt.
    fehler: list[Feldfehler] = []
    werte: dict[str, str] = {}
    for name, roh, max_laenge, pflicht in (
        ("titel", titel, 120, True),
        ("beschreibung", beschreibung, 500, False),
    ):
        text = roh.strip()
        try:
            pruefe_zeichen(text)
            if pflicht and not text:
                raise ValidierungsFehler("Dieses Feld muss ausgefüllt werden.")
            if len(text) > max_laenge:
                raise ValidierungsFehler(f"Höchstens {max_laenge} Zeichen.")
        except (ValidierungsFehler, UnsicherError) as e:
            fehler.append(Feldfehler(None, name, f"{name.capitalize()}: {e}"))
        werte[name] = text
    try:
        tag_liste = tags_lesen(tags)
    except ValidierungsFehler as e:
        fehler.append(Feldfehler(None, "tags", f"Tags: {e}"))
        tag_liste = []
    if fehler:
        raise FehlerSammlung(fehler)
    eintrag.titel = werte["titel"]
    eintrag.beschreibung = werte["beschreibung"]
    eintrag.tags = tags_als_text(tag_liste)
    eintrag.in_bibliothek = True
    sitzung.commit()
    return eintrag


def aus_bibliothek_entfernen(sitzung: Session, eintrag: GespeichertesScript) -> None:
    eintrag.in_bibliothek = False
    sitzung.commit()


@dataclass
class Suchergebnis:
    eintraege: list[GespeichertesScript]
    gesamt: int
    meine_stimmen: set[int] = field(default_factory=set)
    alle_tags: list[str] = field(default_factory=list)


def suche(
    sitzung: Session,
    benutzer: Benutzer,
    *,
    q: str = "",
    ziel: Ziel | None = None,
    tag: str = "",
    nur_meine: bool = False,
    seite: int = 0,
) -> Suchergebnis:
    """Bibliothek durchsuchen. ``nur_meine`` zeigt alle eigenen Scripte (auch nicht veröffentlichte)."""
    abfrage = select(GespeichertesScript)
    if nur_meine:
        abfrage = abfrage.where(GespeichertesScript.autor == benutzer.name)
    else:
        abfrage = abfrage.where(GespeichertesScript.in_bibliothek)
    for wort in q.split()[:10]:
        abfrage = abfrage.where(
            or_(
                GespeichertesScript.titel.contains(wort, autoescape=True),
                GespeichertesScript.beschreibung.contains(wort, autoescape=True),
                GespeichertesScript.tags.contains(wort.lower(), autoescape=True),
            )
        )
    if ziel is not None:
        abfrage = abfrage.where(GespeichertesScript.ziel == ziel.value)
    if tag:
        abfrage = abfrage.where(GespeichertesScript.tags.contains(f",{tag.lower()},", autoescape=True))
    gesamt = sitzung.scalar(select(func.count()).select_from(abfrage.subquery())) or 0
    eintraege = list(
        sitzung.scalars(
            abfrage.order_by(GespeichertesScript.funktioniert.desc(), GespeichertesScript.erstellt_am.desc())
            .offset(max(seite, 0) * SEITENGROESSE)
            .limit(SEITENGROESSE)
        )
    )
    ids = [e.id for e in eintraege]
    stimmen = set(
        sitzung.scalars(
            select(Bewertung.skript_id).where(
                Bewertung.benutzer == benutzer.name, Bewertung.skript_id.in_(ids)
            )
        )
    )
    alle_tags = sorted(
        {
            t
            for text in sitzung.scalars(
                select(GespeichertesScript.tags).where(GespeichertesScript.in_bibliothek)
            )
            for t in tags_aus_text(text)
        }
    )
    return Suchergebnis(eintraege=eintraege, gesamt=gesamt, meine_stimmen=stimmen, alle_tags=alle_tags)


def hat_bewertet(sitzung: Session, eintrag: GespeichertesScript, benutzer: Benutzer) -> bool:
    return (
        sitzung.scalar(
            select(Bewertung.id).where(Bewertung.skript_id == eintrag.id, Bewertung.benutzer == benutzer.name)
        )
        is not None
    )


def funktioniert_umschalten(sitzung: Session, eintrag: GespeichertesScript, benutzer: Benutzer) -> bool:
    """Setzt bzw. entfernt die eigene „Hat funktioniert“-Stimme. Rückgabe: Stimme jetzt gesetzt?"""
    if hat_bewertet(sitzung, eintrag, benutzer):
        sitzung.execute(
            delete(Bewertung).where(Bewertung.skript_id == eintrag.id, Bewertung.benutzer == benutzer.name)
        )
        gesetzt = False
    else:
        sitzung.add(Bewertung(skript_id=eintrag.id, benutzer=benutzer.name, erstellt_am=datetime.now()))
        gesetzt = True
    sitzung.flush()
    eintrag.funktioniert = sitzung.scalar(select(func.count()).where(Bewertung.skript_id == eintrag.id)) or 0
    sitzung.commit()
    return gesetzt


# --- Erneut öffnen ---------------------------------------------------------------------


@dataclass
class Wiederherstellung:
    """Inhalt eines gespeicherten Scripts für den Baukasten (aus der IR, nicht aus dem Text)."""

    ziel: Ziel
    titel: str
    beschreibung: str
    dry_run: bool
    schritte: list[tuple[str, dict[str, str]]]  # (block_id, Werte als Text)
    hinweise: list[str]


def _als_text(wert: str | int | bool | None) -> str | None:
    if wert is None:
        return None
    if isinstance(wert, bool):
        return "true" if wert else "false"
    return str(wert)


def wiederherstellen(registry: Registry, eintrag: GespeichertesScript) -> Wiederherstellung:
    """Lädt die gespeicherte IR und vergleicht sie mit den aktuellen Bausteinen."""
    try:
        ir = ScriptIR.model_validate_json(eintrag.ir_json)
    except ValidationError:
        raise FehlerSammlung(
            [Feldfehler(None, None, "Dieses Script wurde mit einer nicht mehr lesbaren Version gespeichert.")]
        ) from None
    hinweise: list[str] = []
    schritte: list[tuple[str, dict[str, str]]] = []
    for nr, s in enumerate(ir.bloecke(), start=1):
        block = registry.bloecke.get(s.block_id)
        if block is None:
            hinweise.append(
                f"Schritt {nr}: Den Baustein „{s.block_id}“ gibt es nicht mehr – er wurde weggelassen."
            )
            continue
        if block.version != s.block_version:
            hinweise.append(
                f"Schritt {nr}: „{block.name}“ wurde seit dem Speichern geändert "
                f"(Version {s.block_version} → {block.version}). Bitte Werte und Vorschau prüfen."
            )
        werte: dict[str, str] = {}
        for pid, pv in s.parameter.items():
            if block.param(pid) is None:
                hinweise.append(f"Schritt {nr}: Den Parameter „{pid}“ gibt es bei „{block.name}“ nicht mehr.")
                continue
            text = _als_text(pv.wert)
            if text is not None:
                werte[pid] = text
        schritte.append((block.id, werte))
    return Wiederherstellung(
        ziel=Ziel(eintrag.ziel),
        titel=ir.meta.titel,
        beschreibung=ir.meta.beschreibung,
        dry_run=ir.optionen.dry_run,
        schritte=schritte,
        hinweise=hinweise,
    )


def blockversionen(registry: Registry, eintrag: GespeichertesScript) -> list[dict[str, object]]:
    """Für die Detailansicht: gespeicherte vs. aktuelle Blockversion je Schritt."""
    try:
        ir = ScriptIR.model_validate_json(eintrag.ir_json)
    except ValidationError:
        return []
    ergebnis: list[dict[str, object]] = []
    for s in ir.bloecke():
        block = registry.bloecke.get(s.block_id)
        ergebnis.append(
            {
                "name": block.name if block else s.block_id,
                "gespeichert": s.block_version,
                "aktuell": block.version if block else None,
                "risiko": block.risiko.value if block else None,
            }
        )
    return ergebnis
