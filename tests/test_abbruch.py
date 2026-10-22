"""Scripte beenden sich nie ohne Meldung: Fehler-Handler, Zusammenfassung, erwartete Exit-Codes, Pause."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.escaping import Ziel
from app.registry import Registry, lade_registry
from tests.conftest import erzeuge
from tests.test_ausfuehrung import SH_ZIELE, ausfuehren


def _attrappe(ordner: Path, name: str, code: int, ausgabe: str = "") -> None:
    """Ersetzt ein Programm im PATH (z. B. ping ohne Netz, systemctl ohne Dienst)."""
    ordner.mkdir(exist_ok=True)
    datei = ordner / name
    datei.write_text(f"#!/bin/sh\nprintf '%s\\n' '{ausgabe}'\nexit {code}\n", encoding="utf-8")
    datei.chmod(0o755)


def _test_registry(tmp_path: Path, code: dict[str, str]) -> Registry:
    bloecke = tmp_path / "blocks"
    bloecke.mkdir()
    ziele = "".join(f"  {z}: |\n    {c}\n" for z, c in code.items())
    (bloecke / "kaputt.yaml").write_text(
        f"id: kaputt\nname: Kaputt\nkategorie: Test\nbeschreibung: Test\nrisiko: gruen\nziele:\n{ziele}",
        encoding="utf-8",
    )
    (tmp_path / "recipes").mkdir()
    return lade_registry(bloecke, tmp_path / "recipes")


def _log(stdout: str) -> str:
    return stdout.split("--- LOG ---")[1] if "--- LOG ---" in stdout else ""


# --- Fehler werden immer gemeldet ---------------------------------------------------


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_nicht_gesetzte_variable_bricht_nicht_still_ab(tmp_path: Path, shell: str, ziel: Ziel) -> None:
    """set -u / NO_UNSET lösen kein ERR-Trap aus – früher war das Script einfach weg."""
    reg = _test_registry(tmp_path, {ziel.value: "printf '%s\\n' \"$OKM_GIBTSNICHT\""})
    r = ausfuehren(shell, erzeuge(reg, ziel, [("kaputt", {})]).inhalt, tmp_path)
    if ziel is Ziel.ZSH:
        # zsh endet bei NO_UNSET ohne EXIT-Trap – daher dort kein NO_UNSET: die Variable ist leer
        assert r.returncode == 0, r.stdout
        assert " Fertig: 1 von 1 Schritten erfolgreich." in r.stdout
        return
    assert r.returncode != 0
    assert "FEHLER" in r.stdout and "unerwartet beendet" in r.stdout
    assert " Abgebrochen bei Schritt 1 von 1." in r.stdout
    assert " Protokoll: " in r.stdout
    assert "Abgebrochen bei Schritt 1 von 1." in _log(r.stdout), "Zusammenfassung fehlt im Protokoll"


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_fehler_nennt_schritt_zeile_und_befehl(
    registry: Registry, tmp_path: Path, shell: str, ziel: Ziel
) -> None:
    s = erzeuge(
        registry,
        ziel,
        [
            ("meldung", {"text": "eins", "pause": False}),
            ("kopieren", {"art": "datei", "quelle": f"{tmp_path}/gibtsnicht", "ziel": f"{tmp_path}/a"}),
            ("meldung", {"text": "darf nicht erscheinen", "pause": False}),
        ],
    )
    r = ausfuehren(shell, s.inhalt, tmp_path)
    assert r.returncode != 0
    fehlerzeile = next(z for z in r.stdout.splitlines() if "FEHLER" in z)
    assert "Schritt 2/3 (Datei/Ordner kopieren)" in fehlerzeile and "Exit-Code 1" in fehlerzeile
    assert "Zeile " in r.stdout
    if ziel is Ziel.BASH:
        assert "Befehl: cp " in r.stdout
    assert " Abgebrochen bei Schritt 2 von 3." in r.stdout
    assert "darf nicht erscheinen" not in r.stdout.split("--- LOG ---")[0]
    assert "FEHLER" in _log(r.stdout) and "Abgebrochen bei Schritt 2 von 3." in _log(r.stdout)


def test_powershell_fehler_nennt_zeile(registry: Registry, tmp_path: Path) -> None:
    s = erzeuge(registry, Ziel.POWERSHELL, [("ping", {"ziel": "192.0.2.1", "anzahl": 1, "abbrechen": True})])
    r = ausfuehren("pwsh", s.inhalt, tmp_path, env={"TEMP": str(tmp_path)})
    assert r.returncode == 1
    assert "FEHLER" in r.stdout and "(Zeile " in r.stdout
    assert " Abgebrochen bei Schritt 1 von 1." in r.stdout
    assert "trap {" in s.text, "globales Fehler-Netz fehlt"


# --- Erwartete Exit-Codes: Prüfungen melden das Ergebnis statt abzubrechen ----------------


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_nicht_erreichbarer_ping_bricht_nicht_ab(
    registry: Registry, tmp_path: Path, shell: str, ziel: Ziel
) -> None:
    pfad = tmp_path / "bin"
    _attrappe(pfad, "ping", 1, "1 packets transmitted, 0 received, 100% packet loss")
    s = erzeuge(
        registry,
        ziel,
        [("ping", {"ziel": "192.0.2.1", "anzahl": 1}), ("meldung", {"text": "danach", "pause": False})],
    )
    r = ausfuehren(shell, s.inhalt, tmp_path, env={"PATH": f"{pfad}:{os.environ['PATH']}"})
    assert r.returncode == 0, r.stdout
    assert "nicht (vollständig) geantwortet" in r.stdout and "danach" in r.stdout
    assert " Fertig: 2 von 2 Schritten erfolgreich." in r.stdout


def test_dienst_status_unbekannter_dienst(registry: Registry, tmp_path: Path) -> None:
    pfad = tmp_path / "bin"
    _attrappe(pfad, "systemctl", 4, "Unit gibtsnicht.service could not be found.")
    s = erzeuge(
        registry,
        Ziel.BASH,
        [("dienst_status", {"dienst": "gibtsnicht"}), ("meldung", {"text": "danach", "pause": False})],
    )
    r = ausfuehren("bash", s.inhalt, tmp_path, env={"PATH": f"{pfad}:{os.environ['PATH']}"})
    assert r.returncode == 0, r.stdout
    assert "WARNUNG  Diesen Dienst gibt es nicht." in r.stdout and "danach" in r.stdout


def test_dienst_status_gestoppter_dienst(registry: Registry, tmp_path: Path) -> None:
    pfad = tmp_path / "bin"
    _attrappe(pfad, "systemctl", 3, "Active: inactive (dead)")
    s = erzeuge(registry, Ziel.BASH, [("dienst_status", {"dienst": "cups"})])
    r = ausfuehren("bash", s.inhalt, tmp_path, env={"PATH": f"{pfad}:{os.environ['PATH']}"})
    assert r.returncode == 0, r.stdout
    assert "WARNUNG  Der Dienst ist vorhanden, läuft aber nicht." in r.stdout


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_zertifikat_nicht_erreichbar_meldet_statt_abzubrechen(
    registry: Registry, tmp_path: Path, shell: str, ziel: Ziel
) -> None:
    if shutil.which("openssl") is None:
        pytest.skip("openssl fehlt")
    pfad = tmp_path / "bin"
    _attrappe(pfad, "openssl", 1, "connect: Connection refused")
    s = erzeuge(registry, ziel, [("zertifikat_website", {"host": "gibtsnicht.invalid", "port": 443})])
    r = ausfuehren(shell, s.inhalt, tmp_path, env={"PATH": f"{pfad}:{os.environ['PATH']}"})
    assert r.returncode == 0, r.stdout
    assert "WARNUNG  Keine TLS-Verbindung" in r.stdout


def test_vorlagen_mit_erwarteten_exitcodes() -> None:
    """Statische Prüfung für Ziele, die hier nicht laufen (Windows, macOS)."""
    reg = lade_registry()
    assert "-ErrorAction SilentlyContinue" in reg.bloecke["dienst_status"].ziele[Ziel.POWERSHELL]
    assert "cmd /c exit 0" in reg.bloecke["dienst_status"].ziele[Ziel.CMD]
    assert "Write-OkmWarnung" in reg.bloecke["zertifikat_website"].ziele[Ziel.POWERSHELL]
    assert "okm_warn" in reg.bloecke["dns_test"].ziele[Ziel.ZSH]


# --- Zusammenfassung und Fenster offen halten ------------------------------------------


def test_cmd_pause_und_nopause(registry: Registry) -> None:
    text = erzeuge(registry, Ziel.CMD, [("systeminfo", {})]).text
    assert 'if /i "%~1"=="/nopause" set "OKM_KEINE_PAUSE=1"' in text
    assert text.count("if not defined OKM_KEINE_PAUSE pause") >= 3  # Erfolg, Fehler, Abbruch


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_pause_nur_im_terminal(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    s = erzeuge(registry, ziel, [("meldung", {"text": "x", "pause": False})])
    datei = tmp_path / "s.sh"
    datei.write_bytes(s.inhalt)
    # Ohne Terminal (RMM, Pipe): keine Pause
    ohne = subprocess.run(
        [shell, str(datei)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60
    )
    assert "Drücke Enter" not in ohne.stdout
    # Mit Terminal: Pause, außer mit --nopause
    if shutil.which("script") is None:
        pytest.skip("script(1) fehlt")
    mit = subprocess.run(
        ["script", "-qec", f"{shell} {datei}", "/dev/null"],
        input="\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "Drücke Enter zum Schließen" in mit.stdout
    nopause = subprocess.run(
        ["script", "-qec", f"{shell} {datei} --nopause", "/dev/null"],
        input="\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "Drücke Enter" not in nopause.stdout
