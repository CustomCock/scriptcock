"""Zwischenrepräsentation (IR) eines Scripts – unabhängig vom Zielsystem.

Eine ``ScriptIR`` entsteht ausschließlich über ``app.validation`` und enthält
nur geprüfte, typisierte Werte. Generatoren arbeiten nur auf der IR.

Die Schritte bilden einen Baum über das Diskriminator-Feld ``art``:
``block`` (ein Baustein), ``wenn_fehler`` (Versuche … / Wenn das fehlschlägt …),
``wiederhole`` (N-mal), ``wenn`` (Bedingung auf einen Rückgabewert) sowie die Blätter
``abbrechen``, ``warten``, ``bestaetigung`` und ``kommentar``. Weitere Kontrollstrukturen kommen
als neue Knotentypen in die Union ``Knoten``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.block import ParamTyp

IR_VERSION = 3  # 2: wenn_fehler/wiederhole, 3: wenn/abbrechen/warten/bestaetigung/kommentar


class ParamValue(BaseModel):
    """Validierter, normalisierter Parameterwert (``None`` = nicht ausgefüllt)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    typ: ParamTyp
    wert: str | int | bool | None


class BlockSchritt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    art: Literal["block"] = "block"
    block_id: str
    block_version: int
    parameter: dict[str, ParamValue]


class WennFehler(BaseModel):
    """Führt ``versuche`` aus; schlägt darin ein Schritt fehl, folgen die Schritte in ``sonst``.

    Danach geht das Script normal weiter. Ein leeres ``sonst`` heißt „Fehler ignorieren“.
    """

    model_config = ConfigDict(extra="forbid")
    art: Literal["wenn_fehler"] = "wenn_fehler"
    versuche: list[Knoten]
    sonst: list[Knoten] = Field(default_factory=list)


class Wiederhole(BaseModel):
    """Führt ``rumpf`` ``anzahl``-mal hintereinander aus."""

    model_config = ConfigDict(extra="forbid")
    art: Literal["wiederhole"] = "wiederhole"
    anzahl: int
    rumpf: list[Knoten]


class Vergleich(StrEnum):
    GLEICH = "gleich"
    UNGLEICH = "ungleich"
    KLEINER = "kleiner"
    GROESSER = "groesser"
    KLEINER_GLEICH = "kleiner_gleich"
    GROESSER_GLEICH = "groesser_gleich"
    JA = "ja"
    NEIN = "nein"
    UNBEKANNT = "unbekannt"

    @property
    def mit_zahl(self) -> bool:
        return self in ZAHL_VERGLEICHE

    @property
    def text(self) -> str:
        return {
            "gleich": "=",
            "ungleich": "≠",
            "kleiner": "<",
            "groesser": ">",
            "kleiner_gleich": "≤",
            "groesser_gleich": "≥",
            "ja": "ist ja",
            "nein": "ist nein",
            "unbekannt": "ist unbekannt",
        }[self.value]


ZAHL_VERGLEICHE = frozenset(
    {
        Vergleich.GLEICH,
        Vergleich.UNGLEICH,
        Vergleich.KLEINER,
        Vergleich.GROESSER,
        Vergleich.KLEINER_GLEICH,
        Vergleich.GROESSER_GLEICH,
    }
)


class Wenn(BaseModel):
    """Prüft einen Rückgabewert (``wert`` = ``"<schritt>.<id>"``) und führt ``dann`` oder ``sonst`` aus.

    Ist der Wert unbekannt, sind alle Vergleiche falsch – außer ``unbekannt``.
    """

    model_config = ConfigDict(extra="forbid")
    art: Literal["wenn"] = "wenn"
    wert: str
    vergleich: Vergleich
    zahl: int | None = None
    dann: list[Knoten]
    sonst: list[Knoten] = Field(default_factory=list)


class Abbrechen(BaseModel):
    """Beendet das Script planmäßig mit Meldung und Exit-Code (0 = ohne Fehler)."""

    model_config = ConfigDict(extra="forbid")
    art: Literal["abbrechen"] = "abbrechen"
    meldung: str
    code: int


class Warten(BaseModel):
    model_config = ConfigDict(extra="forbid")
    art: Literal["warten"] = "warten"
    sekunden: int


class Bestaetigung(BaseModel):
    """Weiter nur, wenn der Benutzer JA eingibt – sonst Abbruch (wie bei roten Schritten)."""

    model_config = ConfigDict(extra="forbid")
    art: Literal["bestaetigung"] = "bestaetigung"
    meldung: str


class Kommentar(BaseModel):
    """Notiz, die nur als Kommentar im Script steht (keine Ausgabe, kein Schritt)."""

    model_config = ConfigDict(extra="forbid")
    art: Literal["kommentar"] = "kommentar"
    text: str


Knoten = Annotated[
    BlockSchritt | WennFehler | Wiederhole | Wenn | Abbrechen | Warten | Bestaetigung | Kommentar,
    Field(discriminator="art"),
]
KONTROLL_ARTEN = ("wenn_fehler", "wiederhole", "wenn", "abbrechen", "warten", "bestaetigung", "kommentar")


class ScriptMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    titel: str
    beschreibung: str = ""
    autor: str
    erstellt_am: datetime
    baukasten_version: str
    quelle: str = "frei"  # "rezept:<id>" oder "frei"


class Optionen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dry_run: bool = False
    rot_bestaetigt: bool = False


class ScriptIR(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ir_version: int = IR_VERSION
    meta: ScriptMeta
    optionen: Optionen = Field(default_factory=Optionen)
    schritte: list[Knoten]

    def bloecke(self) -> Iterator[BlockSchritt]:
        """Alle Block-Schritte in Textreihenfolge (auch verschachtelte, Schleifen einmal)."""
        yield from bloecke_in(self.schritte)

    def hat_kontrolle(self) -> bool:
        """Enthält Knoten außer Blöcken (nur im Blockly-Modus bearbeitbar)."""
        return _hat_kontrolle(self.schritte)

    def hat_verzweigung(self) -> bool:
        """Versuche/Wiederhole/Wenn: nicht jeder Schritt läuft genau einmal (keine feste Gesamtzahl)."""
        return _hat_verzweigung(self.schritte)


def bloecke_in(knoten: list[Knoten]) -> Iterator[BlockSchritt]:
    for k in knoten:
        if isinstance(k, BlockSchritt):
            yield k
        elif isinstance(k, WennFehler):
            yield from bloecke_in(k.versuche)
            yield from bloecke_in(k.sonst)
        elif isinstance(k, Wiederhole):
            yield from bloecke_in(k.rumpf)
        elif isinstance(k, Wenn):
            yield from bloecke_in(k.dann)
            yield from bloecke_in(k.sonst)


def alle_knoten(knoten: list[Knoten]) -> Iterator[Knoten]:
    """Alle Knoten in Vorordnung (auch verschachtelte)."""
    for k in knoten:
        yield k
        if isinstance(k, WennFehler):
            yield from alle_knoten(k.versuche)
            yield from alle_knoten(k.sonst)
        elif isinstance(k, Wiederhole):
            yield from alle_knoten(k.rumpf)
        elif isinstance(k, Wenn):
            yield from alle_knoten(k.dann)
            yield from alle_knoten(k.sonst)


def _hat_kontrolle(knoten: list[Knoten]) -> bool:
    return any(not isinstance(k, BlockSchritt) for k in knoten)


def _hat_verzweigung(knoten: list[Knoten]) -> bool:
    return any(isinstance(k, WennFehler | Wiederhole | Wenn) for k in knoten)


WennFehler.model_rebuild()
Wiederhole.model_rebuild()
Wenn.model_rebuild()
ScriptIR.model_rebuild()
