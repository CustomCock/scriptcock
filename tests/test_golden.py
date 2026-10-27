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
    erwartet = {f"{r}{_endung(z)}" for r, z in FAELLE} | {
        f"{n}{_endung(z)}" for n in ("_ablauf", "_umlaute") for z in Ziel
    }
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


@pytest.mark.parametrize("ziel", list(Ziel), ids=[z.value for z in Ziel])
def test_golden_umlaute(ziel: Ziel) -> None:
    """Umlaute in Titel, Meldung und Pfad – müssen in jedem Ziel unverändert ankommen."""
    from tests.conftest import erzeuge

    pfad = "C:\\Büro\\Größe" if ziel in (Ziel.POWERSHELL, Ziel.CMD) else "/tmp/Büro/Größe"
    inhalt = erzeuge(
        REG,
        ziel,
        [
            ("meldung", {"text": "Büro: Größe prüfen, nichts löschen!", "pause": False}),
            ("ordner_anlegen", {"pfad": pfad}),
        ],
        titel="Büro – Größe und Löschen",
    ).inhalt
    for wort in ("Büro", "Größe", "Löschen"):
        assert wort.encode() in inhalt
    datei = GOLDEN / f"_umlaute{_endung(ziel)}"
    if os.environ.get("UPDATE_GOLDEN") == "1" or not datei.exists():
        datei.write_bytes(inhalt)
    assert inhalt == datei.read_bytes()


# --- Golden-Files je neuem Baustein (Registry, Richtlinien, Admin-Werkzeuge) -----------------------
# Ein Script mit genau diesem Baustein und seinen Beispielwerten aus dem YAML, je Zielsystem.

GOLDEN_BAUSTEINE = GOLDEN / "bausteine"
NEUE_BAUSTEINE = sorted(
    b.id for b in REG.bloecke.values() if b.kategorie == "Registry" or b.id == "explorer_neustarten"
)
BAUSTEIN_FAELLE = [(bid, z) for bid in NEUE_BAUSTEINE for z in REG.bloecke[bid].ziele]


def baustein_inhalt(block_id: str, ziel: Ziel) -> bytes:
    from tests.conftest import baue_ir, beispielwerte

    reg = REG
    reg.werkzeug_url = "https://baukasten.okm.test"  # Quelle „Intranet“ für admin_werkzeug_bereitstellen
    werte = beispielwerte(reg.bloecke[block_id], ziel)
    ir = baue_ir(reg, ziel, [(block_id, werte)], titel=f"Golden {block_id}")
    return generator_fuer(ziel, reg).erzeuge(ir).inhalt


@pytest.mark.parametrize(
    ("block_id", "ziel"), BAUSTEIN_FAELLE, ids=[f"{b}-{z.value}" for b, z in BAUSTEIN_FAELLE]
)
def test_golden_baustein(block_id: str, ziel: Ziel) -> None:
    datei = GOLDEN_BAUSTEINE / f"{block_id}{_endung(ziel)}"
    inhalt = baustein_inhalt(block_id, ziel)
    if os.environ.get("UPDATE_GOLDEN") == "1" or not datei.exists():
        GOLDEN_BAUSTEINE.mkdir(parents=True, exist_ok=True)
        datei.write_bytes(inhalt)
    assert inhalt == datei.read_bytes(), (
        f"bausteine/{datei.name} weicht ab. Wenn gewollt: UPDATE_GOLDEN=1 pytest tests/test_golden.py"
    )
