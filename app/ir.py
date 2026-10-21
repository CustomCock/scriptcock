"""Zwischenrepräsentation (IR) eines Scripts – unabhängig vom Zielsystem.

Eine ``ScriptIR`` entsteht ausschließlich über ``app.validation`` und enthält
nur geprüfte, typisierte Werte. Generatoren arbeiten nur auf der IR.

Die Schritte bilden einen Baum über das Diskriminator-Feld ``art``. In
Phase 1 gibt es nur ``BlockSchritt``; Kontrollstrukturen (Phase 4, z. B.
``wenn_fehler``, ``wiederhole``) werden als weitere Knotentypen in die Union
``Knoten`` aufgenommen – ohne Umbau der bestehenden Typen.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.block import ParamTyp

IR_VERSION = 1


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


# Phase 4 erweitert diese Union, z. B.:
#   Knoten = Annotated[BlockSchritt | WennFehler | Wiederhole, Field(discriminator="art")]
Knoten = Annotated[BlockSchritt, Field(discriminator="art")]


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
        """Alle Block-Schritte in Ausführungsreihenfolge (auch verschachtelte)."""
        yield from _bloecke(self.schritte)


def _bloecke(knoten: list[BlockSchritt]) -> Iterator[BlockSchritt]:
    for k in knoten:
        if isinstance(k, BlockSchritt):
            yield k
