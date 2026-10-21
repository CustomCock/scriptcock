"""Eingabe aus der UI – gilt durchgehend als nicht vertrauenswürdig."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.escaping import Ziel


class SchrittEingabe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_id: str = Field(max_length=64)
    parameter: dict[str, Any] = Field(default_factory=dict)


class ScriptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ziel: Ziel
    titel: str = Field(default="", max_length=200)
    beschreibung: str = Field(default="", max_length=2000)
    dry_run: bool = False
    rot_bestaetigt: bool = False
    quelle: str = Field(default="frei", max_length=80)
    schritte: list[SchrittEingabe] = Field(max_length=100)
