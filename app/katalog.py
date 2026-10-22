"""Lädt und prüft den Software-Katalog beim Start (bricht bei Fehlern ab, wie die Registry)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from app.models.software import SoftwareKatalog

KATALOG_DATEI = Path(__file__).resolve().parent.parent / "katalog" / "software-katalog.yaml"


class KatalogFehler(Exception):
    def __init__(self, fehler: list[str]) -> None:
        self.fehler = fehler
        super().__init__("Software-Katalog ist fehlerhaft:\n" + "\n".join(f"  - {f}" for f in fehler))


def _ort(daten: object, loc: tuple[int | str, ...]) -> str:
    """``pakete.3.winget`` → ``pakete[3] (7-Zip): winget``."""
    if len(loc) >= 2 and loc[0] == "pakete" and isinstance(loc[1], int):
        name = ""
        if (
            isinstance(daten, dict)
            and isinstance(daten.get("pakete"), list)
            and loc[1] < len(daten["pakete"])
        ):
            eintrag = daten["pakete"][loc[1]]
            if isinstance(eintrag, dict):
                name = f" ({eintrag.get('name', '?')})"
        rest = ".".join(str(t) for t in loc[2:])
        return f"pakete[{loc[1]}]{name}" + (f": {rest}" if rest else "")
    return ".".join(str(t) for t in loc) or "(Datei)"


def lade_katalog(pfad: Path = KATALOG_DATEI) -> SoftwareKatalog:
    rel = f"{pfad.parent.name}/{pfad.name}"
    try:
        daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    except OSError as e:
        raise KatalogFehler([f"{rel}: kann nicht gelesen werden: {e}"]) from None
    except yaml.YAMLError as e:
        raise KatalogFehler([f"{rel}: YAML-Syntaxfehler: {e}"]) from None
    try:
        return SoftwareKatalog.model_validate(daten)
    except ValidationError as e:
        raise KatalogFehler(
            [
                f"{rel}: {_ort(daten, tuple(f['loc']))}: {f['msg'].removeprefix('Value error, ')}"
                for f in e.errors()
            ]
        ) from None
