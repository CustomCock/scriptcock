"""Erzeugte Scripte wirklich ausführen (bash, zsh; PowerShell soweit unter Linux möglich).

Nur harmlose Blöcke, alles in ``tmp_path``. Prüft Logging, Fortschritt,
Zusammenfassung, Fehlerabbruch, Simulation, rote Bestätigung – und dass
Injection-Payloads als wörtliche Dateinamen ankommen.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.escaping import Ziel
from app.registry import Registry
from tests.conftest import erzeuge


def _shell(name: str) -> str:
    pfad = shutil.which(name)
    if pfad is None:
        pytest.skip(f"{name} ist nicht installiert")
    return pfad


def ausfuehren(
    shell: str, inhalt: bytes, tmp_path: Path, eingabe: str = "", env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    datei = tmp_path / ("script.ps1" if shell == "pwsh" else "script.sh")
    datei.write_bytes(inhalt)
    args = (
        [_shell(shell), "-NoProfile", "-File", str(datei)] if shell == "pwsh" else [_shell(shell), str(datei)]
    )
    r = subprocess.run(
        args,
        input=eingabe,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=120,
        env={**os.environ, **(env or {})},
    )
    log = re.search(r"Protokoll: (\S+)", r.stdout)
    if log and Path(log.group(1)).exists() and str(log.group(1)).startswith(("/tmp/", str(tmp_path))):
        r.stdout += "\n--- LOG ---\n" + Path(log.group(1)).read_text(encoding="utf-8", errors="replace")
        Path(log.group(1)).unlink()
    return r


SH_ZIELE = [("bash", Ziel.BASH), ("zsh", Ziel.ZSH)]


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_erfolgreicher_ablauf_und_log(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    kanarie = tmp_path / "PWNED"
    boese = f"{tmp_path}/neu $(touch {kanarie}) `touch {kanarie}` ' \" ; & | *"
    quelle = tmp_path / "quelle.txt"
    quelle.write_text("hallo", encoding="utf-8")
    s = erzeuge(
        registry,
        ziel,
        [
            ("ordner_anlegen", {"pfad": boese}),
            ("kopieren", {"art": "datei", "quelle": str(quelle), "ziel": boese}),
            ("meldung", {"text": "Hallo (Test)!", "pause": False}),
            ("prozess_suchen", {"name": "okmgibtsnicht"}),
        ],
    )
    r = ausfuehren(shell, s.inhalt, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[1/4]" in r.stdout and "[4/4]" in r.stdout
    assert "Fertig: 4 von 4 Schritten erfolgreich." in r.stdout
    assert "Hallo (Test)!" in r.stdout
    assert "Kein passender Prozess gefunden." in r.stdout
    assert (Path(boese) / "quelle.txt").read_text(encoding="utf-8") == "hallo"
    assert not kanarie.exists(), "Injection wurde ausgeführt!"
    assert "--- LOG ---" in r.stdout and r.stdout.split("--- LOG ---")[1].count("[4/4]") == 1


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_fehler_bricht_ab(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    s = erzeuge(
        registry,
        ziel,
        [
            ("ordner_anlegen", {"pfad": f"{tmp_path}/a"}),
            ("kopieren", {"art": "datei", "quelle": f"{tmp_path}/gibtsnicht", "ziel": f"{tmp_path}/a"}),
            ("ordner_anlegen", {"pfad": f"{tmp_path}/b"}),
        ],
    )
    r = ausfuehren(shell, s.inhalt, tmp_path)
    assert r.returncode != 0
    assert "FEHLER  Schritt 2/3 (Datei/Ordner kopieren): Befehl endete mit Exit-Code" in r.stdout
    assert "Abgebrochen bei Schritt 2 von 3." in r.stdout
    assert "Erfolgreich bis dahin: 1 von 3 Schritten." in r.stdout
    assert not (tmp_path / "b").exists(), "Script ist nach dem Fehler weitergelaufen"


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_simulation_aendert_nichts(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    ziel_ordner = tmp_path / "nicht anlegen"
    s = erzeuge(registry, ziel, [("ordner_anlegen", {"pfad": str(ziel_ordner)})], dry_run=True)
    r = ausfuehren(shell, s.inhalt, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not ziel_ordner.exists()
    assert f"[SIMULATION] würde ausführen: mkdir -p -- '{ziel_ordner}'" in r.stdout


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
@pytest.mark.parametrize(("eingabe", "erwartet_code"), [("nein\n", 2), ("ja\n", 2), ("", 2), ("JA\n", 0)])
def test_rote_bestaetigung(
    registry: Registry, tmp_path: Path, shell: str, ziel: Ziel, eingabe: str, erwartet_code: int
) -> None:
    s = erzeuge(
        registry,
        ziel,
        [("prozess_beenden", {"name": "okmgibtsnicht"}), ("ordner_anlegen", {"pfad": f"{tmp_path}/danach"})],
    )
    r = ausfuehren(shell, s.inhalt, tmp_path, eingabe=eingabe)
    assert r.returncode == erwartet_code, r.stdout + r.stderr
    if erwartet_code == 2:
        assert "Abgebrochen" in r.stdout
        assert not (tmp_path / "danach").exists()
    else:
        assert "Kein passender Prozess gefunden" in r.stdout
        assert (tmp_path / "danach").exists()


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_admin_pruefung_ohne_root(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    if os.geteuid() == 0:
        pytest.skip("Test läuft als root – sudo wäre nicht nötig (siehe tests/test_rechte.py)")
    s = erzeuge(registry, ziel, [("dienst_neustarten", {"dienst": "cups"})])
    r = ausfuehren(shell, s.inhalt, tmp_path)
    # Ohne Terminal kann sudo kein Passwort abfragen → verständlicher Abbruch statt stillem Ende
    assert r.returncode == 1
    assert "Administratorrechte (sudo)" in r.stdout
    assert " Abgebrochen: fehlende Rechte." in r.stdout


# --- PowerShell (pwsh unter Linux; nur plattformneutrale Blöcke) ---------------


def test_powershell_ablauf(registry: Registry, tmp_path: Path) -> None:
    s = erzeuge(
        registry,
        Ziel.POWERSHELL,
        [
            ("meldung", {"text": "Hallo 'Welt' (Test)!", "pause": False}),
            ("prozess_suchen", {"name": "okmgibtsnicht"}),
        ],
    )
    r = ausfuehren("pwsh", s.inhalt, tmp_path, env={"TEMP": str(tmp_path)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[1/2]" in r.stdout and "Hallo 'Welt' (Test)!" in r.stdout
    assert "Fertig: 2 von 2 Schritten erfolgreich." in r.stdout
    assert "--- LOG ---" in r.stdout, "Transcript fehlt"
    assert "Hallo 'Welt' (Test)!" in r.stdout.split("--- LOG ---")[1]


def test_powershell_fehler_bricht_ab(registry: Registry, tmp_path: Path) -> None:
    # ping.exe gibt es unter Linux nicht → Schritt 2 schlägt fehl
    s = erzeuge(
        registry,
        Ziel.POWERSHELL,
        [
            ("meldung", {"text": "eins", "pause": False}),
            ("ping", {"ziel": "192.0.2.1", "anzahl": 1, "abbrechen": True}),
            ("meldung", {"text": "darf nicht erscheinen", "pause": False}),
        ],
    )
    r = ausfuehren("pwsh", s.inhalt, tmp_path, env={"TEMP": str(tmp_path)})
    assert r.returncode == 1
    assert "FEHLER  " in r.stdout
    assert "Abgebrochen bei Schritt 2 von 3." in r.stdout
    assert "darf nicht erscheinen" not in r.stdout.split("--- LOG ---")[0]
