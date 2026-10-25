"""Schutzliste für Registry-Bausteine (``registry/schutz.yaml``).

Gesperrte Pfade sind nie schreib-/löschbar, rote Pfade machen den Schritt rot (JA-Abfrage),
zu flache Schlüssel dürfen nicht gelöscht werden. Die Liste steht bewusst nicht im Code.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

SCHUTZ_DATEI = Path(__file__).resolve().parent.parent / "registry" / "schutz.yaml"


@dataclass(frozen=True)
class Schutz:
    gesperrt: tuple[tuple[str, ...], ...]
    rot: tuple[tuple[str, ...], ...]
    rot_teile: frozenset[str]
    loeschen_min_ebenen: int

    def _teile(self, pfad: str) -> tuple[str, ...]:
        return tuple(t.lower() for t in pfad.split("\\"))

    def _unter(self, pfad: str, liste: tuple[tuple[str, ...], ...]) -> bool:
        teile = self._teile(pfad)
        return any(teile[: len(p)] == p for p in liste)

    def gesperrt_fuer(self, pfad: str) -> bool:
        return self._unter(pfad, self.gesperrt)

    def rot_fuer(self, pfad: str, ausser: frozenset[str] = frozenset()) -> bool:
        """``ausser``: Teile aus ``rot_teile``, die hier nicht zählen (Katalog-Richtlinien: „policies“)."""
        return self._unter(pfad, self.rot) or bool(set(self._teile(pfad)) & (self.rot_teile - ausser))

    def zu_flach_zum_loeschen(self, pfad: str) -> bool:
        return len(self._teile(pfad)) - 1 < self.loeschen_min_ebenen


@lru_cache(maxsize=4)
def lade_schutz(datei: Path = SCHUTZ_DATEI) -> Schutz:
    daten = yaml.safe_load(datei.read_text(encoding="utf-8")) or {}

    def pfade(schluessel: str) -> tuple[tuple[str, ...], ...]:
        return tuple(tuple(t.lower() for t in str(p).split("\\")) for p in daten.get(schluessel, []))

    return Schutz(
        gesperrt=pfade("gesperrt"),
        rot=pfade("rot"),
        rot_teile=frozenset(str(t).lower() for t in daten.get("rot_teile", [])),
        loeschen_min_ebenen=int(daten.get("loeschen_min_ebenen", 3)),
    )
