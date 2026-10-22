"""Pydantic-Schema für den Software-Katalog (``katalog/software-katalog.yaml``).

Der Katalog ist reine Nachschlage-Hilfe: Paket-IDs für winget, Homebrew, apt und Flatpak.
Alle IDs müssen die Whitelist des Parametertyps ``paketname`` bestehen, damit jede ID
unverändert in den Baustein ``paket_installieren`` übernommen werden kann.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.block import ParameterDef, ParamTyp
from app.validation import ValidierungsFehler, validiere_wert

# Reihenfolge = Anzeige-Reihenfolge in der UI
PLATTFORM_FELDER = ("winget", "brew", "brew_cask", "apt", "flatpak")


def _pruefe(typ: ParamTyp, wert: str) -> str:
    param = ParameterDef(id="wert", label="wert", typ=typ, beispiel=wert)
    try:
        ergebnis = validiere_wert(param, wert).wert
    except ValidierungsFehler as e:
        raise ValueError(str(e)) from None
    return str(ergebnis)


class SoftwarePaket(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    kategorie: str = Field(min_length=1, max_length=60)
    beschreibung: str = Field(min_length=1, max_length=300)
    suchbegriffe: list[str] = Field(default_factory=list)
    winget: str = ""
    brew: str = ""
    brew_cask: str = ""
    apt: str = ""
    flatpak: str = ""
    # Für später vorgesehen
    hinweis: str = Field(default="", max_length=300)
    hersteller_url: str = ""
    intern: str = ""

    @field_validator(*PLATTFORM_FELDER)
    @classmethod
    def _paket_id(cls, wert: str) -> str:
        return _pruefe(ParamTyp.PAKETNAME, wert) if wert else ""

    @field_validator("hersteller_url")
    @classmethod
    def _url(cls, wert: str) -> str:
        return _pruefe(ParamTyp.URL, wert) if wert else ""

    @field_validator("intern")
    @classmethod
    def _intern(cls, wert: str) -> str:
        return _pruefe(ParamTyp.UNC_PFAD, wert) if wert else ""

    @model_validator(mode="after")
    def _mindestens_eine_quelle(self) -> SoftwarePaket:
        # hersteller_url/intern sind für Software ohne Paket-ID gedacht
        if not (self.ids() or self.hersteller_url or self.intern):
            raise ValueError(
                "mindestens eine Paket-ID (winget, brew, brew_cask, apt, flatpak) "
                "oder hersteller_url/intern angeben"
            )
        return self

    def ids(self) -> dict[str, str]:
        return {f: getattr(self, f) for f in PLATTFORM_FELDER if getattr(self, f)}


class SoftwareKatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1, le=1)
    geprueft_am: dt.date
    pakete: list[SoftwarePaket] = Field(min_length=1)

    @model_validator(mode="after")
    def _keine_doppelten_ids(self) -> SoftwareKatalog:
        fehler = []
        for feld in PLATTFORM_FELDER:
            gesehen: dict[str, str] = {}
            for p in self.pakete:
                pid = getattr(p, feld)
                if not pid:
                    continue
                # winget-IDs sind nicht case-sensitiv; für die anderen ist das ohnehin ein Fehler
                schluessel = pid.lower()
                if schluessel in gesehen:
                    fehler.append(f"{feld}-ID '{pid}' doppelt ('{gesehen[schluessel]}' und '{p.name}')")
                else:
                    gesehen[schluessel] = p.name
        if fehler:
            raise ValueError("; ".join(fehler))
        return self

    def kategorien(self) -> list[str]:
        """Kategorien in der Reihenfolge ihres ersten Auftretens in der Datei."""
        return list(dict.fromkeys(p.kategorie for p in self.pakete))

    def als_daten(self) -> list[dict[str, Any]]:
        """Kompakte Form für das im HTML eingebettete JSON (leere Felder entfallen)."""
        return [p.model_dump(exclude_defaults=True) for p in self.pakete]
