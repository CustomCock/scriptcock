"""Golden-File-Tests: Scripte aller Rezepte × Ziele als Snapshots.

Bei gewollten Änderungen neu erzeugen mit:  UPDATE_GOLDEN=1 pytest tests/test_golden.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.escaping import Ziel
from app.generators import GENERATOREN, generator_fuer
from app.registry import lade_registry
from app.service import rezept_felder, rezept_zu_request
from app.validation import validiere_request
from tests import syntax
from tests.conftest import FESTE_ZEIT

GOLDEN = Path(__file__).parent / "golden"
REG = lade_registry()
FAELLE = [(r.id, z) for r in sorted(REG.rezepte.values(), key=lambda r: r.id) for z in REG.rezept_ziele(r)]


def _endung(ziel: Ziel) -> str:
    # zsh bekommt im Golden-Ordner eine eigene Endung, damit bash/zsh nicht kollidieren
    return ".zsh.sh" if ziel is Ziel.ZSH else GENERATOREN[ziel].endung


def golden_inhalt(rezept_id: str, ziel: Ziel) -> bytes:
    rezept = REG.rezepte[rezept_id]
    formular = {
        f.id: f.beispiel if f.beispiel is not None else f.standard for f in rezept_felder(REG, rezept, ziel)
    }
    req = rezept_zu_request(REG, rezept, ziel, formular, rot_bestaetigt=True)
    ir = validiere_request(req, REG, autor="pytest", jetzt=FESTE_ZEIT)
    return generator_fuer(ziel, REG).erzeuge(ir).inhalt


@pytest.mark.parametrize(("rezept_id", "ziel"), FAELLE, ids=[f"{r}-{z.value}" for r, z in FAELLE])
def test_golden(rezept_id: str, ziel: Ziel) -> None:
    datei = GOLDEN / f"{rezept_id}{_endung(ziel)}"
    inhalt = golden_inhalt(rezept_id, ziel)
    if os.environ.get("UPDATE_GOLDEN") == "1" or not datei.exists():
        GOLDEN.mkdir(exist_ok=True)
        datei.write_bytes(inhalt)
    assert inhalt == datei.read_bytes(), (
        f"{datei.name} weicht ab. Wenn die Änderung gewollt ist: UPDATE_GOLDEN=1 pytest tests/test_golden.py"
    )


@pytest.mark.parametrize("ziel", list(Ziel), ids=[z.value for z in Ziel])
def test_golden_ablauf(ziel: Ziel) -> None:
    """Snapshot eines Scripts mit Kontrollknoten („Versuche“, „Wiederhole“)."""
    from tests.test_kontrolle import beispiel_baum, ir_aus

    datei = GOLDEN / f"_ablauf{_endung(ziel)}"
    inhalt = (
        generator_fuer(ziel, REG).erzeuge(ir_aus(REG, ziel, beispiel_baum(ziel), rot_bestaetigt=True)).inhalt
    )
    if os.environ.get("UPDATE_GOLDEN") == "1" or not datei.exists():
        datei.write_bytes(inhalt)
    assert inhalt == datei.read_bytes(), f"{datei.name} weicht ab (UPDATE_GOLDEN=1 zum Neuerzeugen)"


def test_keine_verwaisten_golden_dateien() -> None:
    erwartet = {f"{r}{_endung(z)}" for r, z in FAELLE} | {f"_ablauf{_endung(z)}" for z in Ziel}
    vorhanden = {p.name for p in GOLDEN.iterdir() if p.is_file()}
    assert vorhanden <= erwartet, f"Verwaiste Golden-Dateien: {sorted(vorhanden - erwartet)}"


def test_golden_syntax() -> None:
    dateien = sorted(GOLDEN.iterdir())
    bash = [d for d in dateien if d.name.endswith(".sh") and not d.name.endswith(".zsh.sh")]
    for d in bash:
        syntax.bash_n(d)
    syntax.shellcheck(bash)
    for d in dateien:
        if d.name.endswith(".zsh.sh"):
            syntax.zsh_n(d)
        if d.suffix == ".cmd":
            assert syntax.cmd_lint(d.read_bytes()) == [], d.name
    syntax.pwsh_pruefen([d for d in dateien if d.suffix == ".ps1"])
