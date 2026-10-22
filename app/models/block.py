"""Pydantic-Schema für Block-Definitionen (``blocks/**/*.yaml``)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.escaping import Ziel

ID_MUSTER = r"^[a-z][a-z0-9_]*$"

# Namen, die der Generator selbst in Code-Templates bereitstellt.
EINGEBAUTE_VARIABLEN = frozenset({"whatif"})


class Risiko(StrEnum):
    GRUEN = "gruen"  # nur lesen
    GELB = "gelb"  # ändert etwas
    ROT = "rot"  # löscht / destruktiv

    @property
    def stufe(self) -> int:
        return {"gruen": 0, "gelb": 1, "rot": 2}[self.value]

    @property
    def anzeige(self) -> str:
        return {"gruen": "Grün (nur lesen)", "gelb": "Gelb (ändert etwas)", "rot": "Rot (destruktiv)"}[
            self.value
        ]


class ParamTyp(StrEnum):
    TEXT_KURZ = "text_kurz"
    TEXT = "text"
    ZAHL = "zahl"
    IPV4 = "ipv4"
    HOSTNAME = "hostname"
    IP_ODER_HOSTNAME = "ip_oder_hostname"
    PORT = "port"
    PFAD = "pfad"
    PFAD_WINDOWS = "pfad_windows"
    PFAD_UNIX = "pfad_unix"
    UNC_PFAD = "unc_pfad"
    LAUFWERKSBUCHSTABE = "laufwerksbuchstabe"
    DIENSTNAME = "dienstname"
    PROZESSNAME = "prozessname"
    PAKETNAME = "paketname"
    DRUCKERNAME = "druckername"
    BENUTZERNAME = "benutzername"
    URL = "url"
    SHA256 = "sha256"
    AUSWAHL = "auswahl"
    JA_NEIN = "ja_nein"


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wert: str = Field(pattern=r"^[A-Za-z0-9_.\-]+$")
    label: str


class ParameterDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_MUSTER)
    label: str
    typ: ParamTyp
    pflicht: bool = True
    beispiel: Any = None
    standard: Any = None
    hilfe: str = ""
    min: int | None = None
    max: int | None = None
    optionen: list[Option] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _nicht_eingebaut(cls, v: str) -> str:
        if v in EINGEBAUTE_VARIABLEN:
            raise ValueError(f"'{v}' ist ein reservierter Name und kann nicht als Parameter-ID dienen")
        return v

    @model_validator(mode="after")
    def _typ_passend(self) -> ParameterDef:
        if self.typ is ParamTyp.AUSWAHL and not self.optionen:
            raise ValueError("Typ 'auswahl' braucht eine Liste 'optionen'")
        if self.typ is not ParamTyp.AUSWAHL and self.optionen:
            raise ValueError("'optionen' ist nur beim Typ 'auswahl' erlaubt")
        if (self.min is not None or self.max is not None) and self.typ is not ParamTyp.ZAHL:
            raise ValueError("'min'/'max' sind nur beim Typ 'zahl' erlaubt")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("'min' ist größer als 'max'")
        return self


class BlockDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_MUSTER)
    version: int = Field(default=1, ge=1)
    name: str
    kategorie: str
    beschreibung: str
    hilfe: str = ""
    risiko: Risiko
    admin_noetig: bool | dict[Ziel, bool] = False
    # Interaktive Blöcke (Eingaben/Pausen) werden in CMD nicht umgeleitet,
    # damit der Benutzer die Ausgabe sofort sieht.
    interaktiv: bool = False
    # Fortschrittstext, z. B. "Dienst {{ dienst }} wird neu gestartet".
    # Wird mit den Rohwerten gerendert und danach als Ganzes escaped.
    fortschritt: str | None = None
    # Hilfe bei einem Fehler, wird unter „FEHLER …“ als „Tipp: …“ ausgegeben.
    tipp: str = ""
    parameter: list[ParameterDef] = Field(default_factory=list)
    ziele: dict[Ziel, str]
    pruefung: dict[Ziel, str] = Field(default_factory=dict)
    dry_run: dict[Ziel, str] = Field(default_factory=dict)
    hinweise: dict[Ziel, str] = Field(default_factory=dict)

    # Wird von der Registry gesetzt (relativer Pfad, für Fehlermeldungen).
    quelle: str = ""

    @model_validator(mode="after")
    def _konsistent(self) -> BlockDef:
        if not self.ziele:
            raise ValueError("'ziele' muss mindestens ein Zielsystem enthalten")
        ids = [p.id for p in self.parameter]
        doppelt = {i for i in ids if ids.count(i) > 1}
        if doppelt:
            raise ValueError(f"Parameter-ID(s) doppelt: {', '.join(sorted(doppelt))}")
        for feld in ("pruefung", "dry_run", "hinweise"):
            zusatz: dict[Ziel, str] = getattr(self, feld)
            fremd = set(zusatz) - set(self.ziele)
            if fremd:
                namen = ", ".join(sorted(z.value for z in fremd))
                raise ValueError(f"'{feld}' enthält Ziele ohne Eintrag in 'ziele': {namen}")
        if isinstance(self.admin_noetig, dict):
            fremd = set(self.admin_noetig) - set(self.ziele)
            if fremd:
                raise ValueError("'admin_noetig' enthält Ziele ohne Eintrag in 'ziele'")
        return self

    def verfuegbar(self, ziel: Ziel) -> bool:
        return ziel in self.ziele

    def braucht_admin(self, ziel: Ziel) -> bool:
        if isinstance(self.admin_noetig, dict):
            return self.admin_noetig.get(ziel, False)
        return self.admin_noetig

    def param(self, param_id: str) -> ParameterDef | None:
        return next((p for p in self.parameter if p.id == param_id), None)

    def abgeleitete_variablen(self) -> dict[str, str]:
        """Zusätzliche Template-Variablen, die aus Parametern berechnet werden.

        ``<id>_smb``: ein ``unc_pfad`` als ``smb://``-URL (für macOS).
        Rückgabe: Variablenname -> Parameter-ID.
        """
        return {f"{p.id}_smb": p.id for p in self.parameter if p.typ is ParamTyp.UNC_PFAD}
