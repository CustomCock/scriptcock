"""Zwischenrepräsentation (IR) eines Scripts – unabhängig vom Zielsystem.

Eine ``ScriptIR`` entsteht ausschließlich über ``app.validation`` und enthält
nur geprüfte, typisierte Werte. Generatoren arbeiten nur auf der IR.

Die Schritte bilden einen Baum über das Diskriminator-Feld ``art``:
``block`` (ein Baustein), ``wenn_fehler`` (Versuche … / Wenn das fehlschlägt …) und
``wiederhole`` (N-mal). Weitere Kontrollstrukturen kommen als neue Knotentypen in die
Union ``Knoten``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.block import ParamTyp

IR_VERSION = 2  # 2: Kontrollknoten wenn_fehler/wiederhole (v1-IRs bleiben lesbar)


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


Knoten = Annotated[BlockSchritt | WennFehler | Wiederhole, Field(discriminator="art")]
KONTROLL_ARTEN = ("wenn_fehler", "wiederhole")


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
        return _hat_kontrolle(self.schritte)


def bloecke_in(knoten: list[Knoten]) -> Iterator[BlockSchritt]:
    for k in knoten:
        if isinstance(k, BlockSchritt):
            yield k
        elif isinstance(k, WennFehler):
            yield from bloecke_in(k.versuche)
            yield from bloecke_in(k.sonst)
        elif isinstance(k, Wiederhole):
            yield from bloecke_in(k.rumpf)


def _hat_kontrolle(knoten: list[Knoten]) -> bool:
    return any(not isinstance(k, BlockSchritt) for k in knoten)


WennFehler.model_rebuild()
Wiederhole.model_rebuild()
ScriptIR.model_rebuild()
