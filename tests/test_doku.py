"""Doku bleibt beim Code: jeder Parametertyp ist beschrieben, die Registry-Doku nennt alle Bausteine."""

from __future__ import annotations

from pathlib import Path

from app.models.block import REGISTRY_BEREICHE, ParamTyp
from app.registry import Registry

DOCS = Path(__file__).resolve().parent.parent / "docs"


def test_jeder_parametertyp_ist_dokumentiert() -> None:
    text = (DOCS / "neuen-block-anlegen.md").read_text(encoding="utf-8")
    fehlt = [t.value for t in ParamTyp if f"`{t.value}`" not in text]
    assert not fehlt, f"In docs/neuen-block-anlegen.md (Abschnitt 4) fehlen: {fehlt}"


def test_registry_doku_nennt_alle_bausteine_und_bereiche(registry: Registry) -> None:
    text = (DOCS / "registry.md").read_text(encoding="utf-8")
    namen = [b.name for b in registry.bloecke.values() if b.kategorie == "Registry" and b.dynamisch is None]
    assert namen
    assert not [n for n in namen if n not in text], "docs/registry.md: Baustein fehlt in der Tabelle"
    assert not [a for a in REGISTRY_BEREICHE.values() if a.split(" (")[0] not in text]
