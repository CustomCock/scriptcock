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


class FuerJedenEingabe(BaseModel):
    """Werte als Liste oder Text (getrennt mit , oder ;). Im Rumpf steht der aktuelle Wert als
    Parameterwert ``{"schleifenwert": true}``."""

    model_config = ConfigDict(extra="forbid")
    art: Literal["fuer_jeden"]
    werte: Any = None
    rumpf: list[EingabeKnoten] = Field(max_length=100)


class WennEingabe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    art: Literal["wenn"]
    wert: Any = None  # alles Weitere prüft validation.py mit deutschen Meldungen
    vergleich: Any = None
    zahl: Any = None
    dann: list[EingabeKnoten] = Field(default_factory=list, max_length=100)
    sonst: list[EingabeKnoten] = Field(default_factory=list, max_length=100)


class AbbrechenEingabe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    art: Literal["abbrechen"]
    meldung: Any = None
    code: Any = None


class WartenEingabe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    art: Literal["warten"]
    sekunden: Any = None


class BestaetigungEingabe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    art: Literal["bestaetigung"]
    meldung: Any = None


class KommentarEingabe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    art: Literal["kommentar"]
    text: Any = None


def _art(wert: Any) -> str:
    # Ältere Clients (Rezept-/Listen-Modus) schicken Blöcke ohne "art".
    if isinstance(wert, dict):
        return str(wert.get("art", "block"))
    return str(getattr(wert, "art", "block"))


EingabeKnoten = Annotated[
    Annotated[SchrittEingabe, Tag("block")]
    | Annotated[WennFehlerEingabe, Tag("wenn_fehler")]
    | Annotated[WiederholeEingabe, Tag("wiederhole")]
    | Annotated[FuerJedenEingabe, Tag("fuer_jeden")]
    | Annotated[WennEingabe, Tag("wenn")]
    | Annotated[AbbrechenEingabe, Tag("abbrechen")]
    | Annotated[WartenEingabe, Tag("warten")]
    | Annotated[BestaetigungEingabe, Tag("bestaetigung")]
    | Annotated[KommentarEingabe, Tag("kommentar")],
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
FuerJedenEingabe.model_rebuild()
WennEingabe.model_rebuild()
ScriptRequest.model_rebuild()
