"""Pydantic-Schema für Rezepte (``recipes/*.yaml``).

Ein Rezept ist eine vorgefertigte Block-Kette mit eigenem, einfachem
Formular. Parameterwerte der Schritte sind entweder Konstanten oder
Verweise auf Formularfelder (``"$feld_id"``; ein wörtliches ``$`` wird als
``$$`` geschrieben).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.escaping import Ziel
from app.models.block import ID_MUSTER, ParameterDef


class RezeptSchritt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block: str = Field(pattern=ID_MUSTER)
    parameter: dict[str, Any] = Field(default_factory=dict)
    # Schritt nur für diese Ziele aufnehmen (leer = alle).
    nur_fuer: list[Ziel] = Field(default_factory=list)
    # Schritt nur, wenn Formularfelder diese Werte haben: {feld_id: wert | [werte]} (alle Bedingungen)
    nur_wenn: dict[str, Any] = Field(default_factory=dict)

    def aktiv_fuer(self, ziel: Ziel) -> bool:
        return not self.nur_fuer or ziel in self.nur_fuer

    def bedingung_erfuellt(self, werte: dict[str, Any]) -> bool:
        """``werte`` = geprüfte Formularwerte. Vergleich als Text (ja/nein als true/false)."""
        for feld, soll in self.nur_wenn.items():
            ist = werte.get(feld)
            erlaubt = soll if isinstance(soll, list) else [soll]
            if _als_text(ist) not in [_als_text(s) for s in erlaubt]:
                return False
        return True


def _als_text(wert: Any) -> str:
    return ("true" if wert else "false") if isinstance(wert, bool) else str(wert)


class RezeptDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_MUSTER)
    name: str
    kategorie: str
    beschreibung: str
    hilfe: str = ""
    schlagworte: list[str] = Field(default_factory=list)
    felder: list[ParameterDef] = Field(default_factory=list)
    schritte: list[RezeptSchritt]
    freigegeben: bool = True
    quelle: str = ""

    @model_validator(mode="after")
    def _konsistent(self) -> RezeptDef:
        if not self.schritte:
            raise ValueError("Ein Rezept braucht mindestens einen Schritt")
        ids = [f.id for f in self.felder]
        if len(ids) != len(set(ids)):
            raise ValueError("Formularfeld-IDs sind doppelt")
        return self

    def schritte_fuer(self, ziel: Ziel) -> list[RezeptSchritt]:
        return [s for s in self.schritte if s.aktiv_fuer(ziel)]


def feld_verweis(wert: Any) -> str | None:
    """Gibt die Feld-ID zurück, wenn ``wert`` ein Verweis ``$feld`` ist."""
    if isinstance(wert, str) and wert.startswith("$") and not wert.startswith("$$"):
        return wert[1:]
    return None


def konstante(wert: Any) -> Any:
    if isinstance(wert, str) and wert.startswith("$$"):
        return wert[1:]
    return wert
