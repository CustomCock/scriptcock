"""Teil F: Vorbereitung des Windows-CI-Jobs (tools/windows_test.py + tests/windows/lauf.ps1) unter Linux.

Ausgeführt werden die Scripte erst auf ``windows-latest`` (Job ``windows`` in ``.github/workflows/ci.yml``);
hier wird geprüft, dass alles erzeugt werden kann, das Manifest stimmt und die Dateien sauber parsen.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from app.escaping import Ziel
from app.syntaxpruefung import pruefe

PROJEKT = Path(__file__).resolve().parent.parent
LAUF = PROJEKT / "tests" / "windows" / "lauf.ps1"


@pytest.fixture(scope="module")
def erzeugt(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    ordner = tmp_path_factory.mktemp("okm-ci")
    subprocess.run([sys.executable, str(PROJEKT / "tools" / "windows_test.py"), str(ordner)], check=True)
    return ordner, json.loads((ordner / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_vollstaendig(erzeugt: tuple[Path, dict[str, Any]]) -> None:
    ordner, manifest = erzeugt
    laeufe = manifest["laeufe"]
    namen = {(lauf["name"], lauf["ziel"]) for lauf in laeufe}
    for name in ("typen", "nur_wenn_fehlt", "rueckgaengig", "loeschen", "import", "benutzer", "checkliste"):
        assert (name, "powershell") in namen and (name, "cmd") in namen, name
    for lauf in laeufe:
        assert (ordner / lauf["datei"]).is_file()
        assert lauf["exit"] in (0, 1, "ungleich0")
        for p in lauf["pruefungen"] + lauf.get("rueckgaengig", []):
            assert p["art"] in ("wert", "kein_wert", "kein_schluessel", "datei_enthaelt")
            if p["art"] == "wert":
                # Zahlen als Text (ConvertFrom-Json in PS 5.1 liest große Zahlen ungenau)
                assert not isinstance(p["daten"], int)
                assert p["pfad"].startswith(("HKLM\\SOFTWARE\\OkmTest\\", "HKCU\\Software\\OkmTest\\"))
    # Die Grenzfälle aus dem Auftrag sind dabei
    typen = next(lauf for lauf in laeufe if lauf["name"] == "typen" and lauf["ziel"] == "cmd")
    pruef = {p["name"]: p for p in typen["pruefungen"]}
    assert pruef["Gross"]["daten"] == "4294967295"
    assert pruef["Exp"]["daten"] == "%SystemRoot%\\okm"
    assert pruef["Multi"]["daten"] == ["eins", "zwei drei"]
    assert pruef[""]["daten"] == "Standard"
    assert pruef["Nachbar"]["daten"] == "bleibt"
    # Rückgängig: PowerShell prüft auch das Entfernen neuer Werte und Schlüssel
    ps = next(lauf for lauf in laeufe if lauf["name"] == "rueckgaengig" and lauf["ziel"] == "powershell")
    assert {p["art"] for p in ps["rueckgaengig"]} == {"wert", "kein_wert", "kein_schluessel"}


def test_reg_dateien_utf16(erzeugt: tuple[Path, dict[str, Any]]) -> None:
    ordner, _ = erzeugt
    roh = (ordner / "import-PS.reg").read_bytes()
    assert roh.startswith(b"\xff\xfe")
    assert "Windows Registry Editor Version 5.00" in roh.decode("utf-16")


@pytest.mark.parametrize("muster", ["*.ps1", "*.cmd"])
def test_erzeugte_scripte_syntax(erzeugt: tuple[Path, dict[str, Any]], muster: str) -> None:
    ordner, _ = erzeugt
    ziel = Ziel.POWERSHELL if muster == "*.ps1" else Ziel.CMD
    for datei in sorted(ordner.glob(muster)):
        ergebnis = pruefe(datei.read_bytes().decode("utf-8-sig"), ziel)
        assert not ergebnis.befunde, (datei.name, ergebnis.befunde[:3])


def test_lauf_ps1_parst_und_hat_bom() -> None:
    assert LAUF.read_bytes().startswith(b"\xef\xbb\xbf")  # Windows PowerShell 5.1 liest sonst ANSI
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("pwsh ist nicht installiert")
    befehl = (
        "$e = $null; $null = [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{LAUF}', [ref]$null, [ref]$e); $e.Count"
    )
    r = subprocess.run([pwsh, "-NoProfile", "-Command", befehl], capture_output=True, text=True, check=True)
    assert r.stdout.strip() == "0"


def test_ci_hat_windows_job() -> None:
    import yaml

    ci = yaml.safe_load((PROJEKT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    job = ci["jobs"]["windows"]
    assert job["runs-on"] == "windows-latest"
    schritte = " ".join(str(s.get("run", "")) for s in job["steps"])
    assert "tools/windows_test.py" in schritte and "tests\\windows\\lauf.ps1" in schritte
    assert any(s.get("shell") == "powershell" for s in job["steps"])  # Windows PowerShell 5.1, nicht pwsh
