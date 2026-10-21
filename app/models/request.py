"""Eingabe aus der UI – gilt durchgehend als nicht vertrauenswürdig."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag

from app.escaping import Ziel


class SchrittEingabe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    art: Literal["block"] = "block"
    block_id: str = Field(max_length=64)
    parameter: dict[str, Any] = Field(default_factory=dict)


class WennFehlerEingabe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    art: Literal["wenn_fehler"]
    versuche: list[EingabeKnoten] = Field(max_length=100)
    sonst: list[EingabeKnoten] = Field(default_factory=list, max_length=100)


class WiederholeEingabe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    art: Literal["wiederhole"]
    anzahl: Any = None  # wird in validation.py mit deutscher Meldung geprüft
    rumpf: list[EingabeKnoten] = Field(max_length=100)


def _art(wert: Any) -> str:
    # Ältere Clients (Rezept-/Listen-Modus) schicken Blöcke ohne "art".
    if isinstance(wert, dict):
        return str(wert.get("art", "block"))
    return str(getattr(wert, "art", "block"))


EingabeKnoten = Annotated[
    Annotated[SchrittEingabe, Tag("block")]
    | Annotated[WennFehlerEingabe, Tag("wenn_fehler")]
    | Annotated[WiederholeEingabe, Tag("wiederhole")],
    Discriminator(_art),
]


class ScriptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ziel: Ziel
    titel: str = Field(default="", max_length=200)
    beschreibung: str = Field(default="", max_length=2000)
    dry_run: bool = False
    rot_bestaetigt: bool = False
    quelle: str = Field(default="frei", max_length=80)
    schritte: list[EingabeKnoten] = Field(max_length=100)


WennFehlerEingabe.model_rebuild()
WiederholeEingabe.model_rebuild()
ScriptRequest.model_rebuild()
