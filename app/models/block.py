"""Pydantic-Schema für Block-Definitionen (``blocks/**/*.yaml``)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.escaping import Ziel

ID_MUSTER = r"^[a-z][a-z0-9_]*$"

# Namen, die der Generator selbst in Code-Templates bereitstellt.
EINGEBAUTE_VARIABLEN = frozenset({"whatif", "sudo"})
# Platzhalter für Rückgabewerte: {{ rueckgabe_<id> }} = Variablenname, den der Generator vergibt.
RUECKGABE_PRAEFIX = "rueckgabe_"

WINDOWS = frozenset({Ziel.POWERSHELL, Ziel.CMD})
UNIX = frozenset({Ziel.BASH, Ziel.ZSH})


class Recht(StrEnum):
    """Benötigte Rechte eines Blocks pro Ziel (``rechte:`` im YAML)."""

    BENUTZER = "benutzer"  # Standard
    ADMIN = "admin"  # Windows: Administrator (UAC)
    ROOT = "root"  # Linux/macOS: Befehle mit {{ sudo }}
    NIE_ROOT = "nie_root"  # Linux/macOS: darf NICHT als root laufen (z. B. Homebrew)


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
    VARIABLE = "variable"  # Rückgabewert eines vorherigen Schritts, Wert "<schritt>.<rueckgabe_id>"


class RueckgabeTyp(StrEnum):
    """Bewusst nur Zahl und ja/nein: Der Generator normalisiert die Werte nach jedem Schritt,
    damit Folgeschritte sie gefahrlos verwenden können (kein Freitext aus Systemausgaben)."""

    ZAHL = "zahl"
    JA_NEIN = "ja_nein"

    @property
    def anzeige(self) -> str:
        return {"zahl": "Zahl", "ja_nein": "ja/nein"}[self.value]


class RueckgabeDef(BaseModel):
    """Ein Wert, den ein Block nach seinem Lauf liefert (``rueckgabe:`` im YAML)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_MUSTER, max_length=40)
    typ: RueckgabeTyp
    beschreibung: str = Field(min_length=1)
    # Leer = alle Ziele des Blocks. Sonst nur diese (z. B. Ping-Laufzeit nicht unter CMD).
    ziele: list[Ziel] = Field(default_factory=list)


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
    # Nur bei typ: variable – welcher Rückgabetyp erwartet wird
    variable_typ: RueckgabeTyp | None = None

    @field_validator("id")
    @classmethod
    def _nicht_eingebaut(cls, v: str) -> str:
        if v in EINGEBAUTE_VARIABLEN or v.startswith(RUECKGABE_PRAEFIX):
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
        if (self.typ is ParamTyp.VARIABLE) != (self.variable_typ is not None):
            raise ValueError("'variable_typ' (zahl oder ja_nein) gehört genau zum Typ 'variable'")
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
    rechte: dict[Ziel, Recht] = Field(default_factory=dict)
    # Interaktive Blöcke (Eingaben/Pausen) werden in CMD nicht umgeleitet,
    # damit der Benutzer die Ausgabe sofort sieht.
    interaktiv: bool = False
    # Fortschrittstext, z. B. "Dienst {{ dienst }} wird neu gestartet".
    # Wird mit den Rohwerten gerendert und danach als Ganzes escaped.
    fortschritt: str | None = None
    # Hilfe bei einem Fehler, wird unter „FEHLER …“ als „Tipp: …“ ausgegeben.
    tipp: str = ""
    parameter: list[ParameterDef] = Field(default_factory=list)
    rueckgabe: list[RueckgabeDef] = Field(default_factory=list)
    ziele: dict[Ziel, str]
    pruefung: dict[Ziel, str] = Field(default_factory=dict)
    dry_run: dict[Ziel, str] = Field(default_factory=dict)
    hinweise: dict[Ziel, str] = Field(default_factory=dict)

    # Wird von der Registry gesetzt (relativer Pfad, für Fehlermeldungen).
    quelle: str = ""

    @model_validator(mode="before")
    @classmethod
    def _altes_schema(cls, daten: Any) -> Any:
        if isinstance(daten, dict) and "admin_noetig" in daten:
            raise ValueError(
                "'admin_noetig' gibt es nicht mehr – bitte 'rechte' pro Ziel angeben, z. B. "
                "rechte: {powershell: admin, cmd: admin, bash: root, zsh: root} "
                "(siehe docs/neuen-block-anlegen.md)"
            )
        return daten

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
        rids = [r.id for r in self.rueckgabe]
        doppelt = {i for i in rids if rids.count(i) > 1}
        if doppelt:
            raise ValueError(f"Rückgabe-ID(s) doppelt: {', '.join(sorted(doppelt))}")
        for r in self.rueckgabe:
            fremd = set(r.ziele) - set(self.ziele)
            if fremd:
                namen = ", ".join(sorted(z.value for z in fremd))
                raise ValueError(f"rueckgabe.{r.id}.ziele enthält Ziele ohne Eintrag in 'ziele': {namen}")
        fremd = set(self.rechte) - set(self.ziele)
        if fremd:
            namen = ", ".join(sorted(z.value for z in fremd))
            raise ValueError(f"'rechte' enthält Ziele ohne Eintrag in 'ziele': {namen}")
        for ziel, recht in self.rechte.items():
            if recht is Recht.ADMIN and ziel not in WINDOWS:
                raise ValueError(f"rechte.{ziel.value}: 'admin' gibt es nur für powershell/cmd – hier 'root'")
            if recht in (Recht.ROOT, Recht.NIE_ROOT) and ziel not in UNIX:
                raise ValueError(
                    f"rechte.{ziel.value}: '{recht.value}' gibt es nur für bash/zsh – hier 'admin'"
                )
        return self

    def verfuegbar(self, ziel: Ziel) -> bool:
        return ziel in self.ziele

    def recht(self, ziel: Ziel) -> Recht:
        return self.rechte.get(ziel, Recht.BENUTZER)

    def braucht_admin(self, ziel: Ziel) -> bool:
        """Erhöhte Rechte nötig (Windows: Administrator, Linux/macOS: sudo)."""
        return self.recht(ziel) in (Recht.ADMIN, Recht.ROOT)

    def rueckgaben(self, ziel: Ziel) -> list[RueckgabeDef]:
        """Rückgabewerte, die der Block unter ``ziel`` liefert."""
        if not self.verfuegbar(ziel):
            return []
        return [r for r in self.rueckgabe if not r.ziele or ziel in r.ziele]

    def rueckgabe_def(self, rid: str) -> RueckgabeDef | None:
        return next((r for r in self.rueckgabe if r.id == rid), None)

    def param(self, param_id: str) -> ParameterDef | None:
        return next((p for p in self.parameter if p.id == param_id), None)

    def abgeleitete_variablen(self) -> dict[str, str]:
        """Zusätzliche Template-Variablen, die aus Parametern berechnet werden.

        ``<id>_smb``: ein ``unc_pfad`` als ``smb://``-URL (für macOS).
        Rückgabe: Variablenname -> Parameter-ID.
        """
        return {f"{p.id}_smb": p.id for p in self.parameter if p.typ is ParamTyp.UNC_PFAD}
