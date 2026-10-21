from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from app.escaping import Ziel
from app.generators import GeneratedScript, generator_fuer
from app.ir import ScriptIR
from app.models.block import BlockDef, ParamTyp
from app.models.request import SchrittEingabe, ScriptRequest
from app.registry import Registry, lade_registry
from app.validation import validiere_request

FESTE_ZEIT = datetime(2026, 1, 15, 9, 30, 0)


@pytest.fixture(scope="session")
def registry() -> Registry:
    return lade_registry()


def beispielwerte(block: BlockDef, ziel: Ziel) -> dict[str, Any]:
    """Beispielwerte eines Blocks, Pfade passend zum Zielsystem."""
    werte: dict[str, Any] = {}
    windows = ziel in (Ziel.POWERSHELL, Ziel.CMD)
    for p in block.parameter:
        wert = p.beispiel if p.beispiel is not None else p.standard
        if wert is None:
            continue
        if p.typ is ParamTyp.PFAD and not windows and isinstance(wert, str) and ":" in wert:
            wert = "/tmp/okm-test/" + wert.split("\\")[-1]
        werte[p.id] = wert
    return werte


def baue_ir(
    registry: Registry,
    ziel: Ziel,
    schritte: list[tuple[str, dict[str, Any]]],
    *,
    titel: str = "Test",
    dry_run: bool = False,
    rot_bestaetigt: bool = True,
) -> ScriptIR:
    req = ScriptRequest(
        ziel=ziel,
        titel=titel,
        dry_run=dry_run,
        rot_bestaetigt=rot_bestaetigt,
        schritte=[SchrittEingabe(block_id=b, parameter=p) for b, p in schritte],
    )
    return validiere_request(req, registry, autor="pytest", jetzt=FESTE_ZEIT)


def erzeuge(
    registry: Registry, ziel: Ziel, schritte: list[tuple[str, dict[str, Any]]], **kw: Any
) -> GeneratedScript:
    return generator_fuer(ziel, registry).erzeuge(baue_ir(registry, ziel, schritte, **kw))
