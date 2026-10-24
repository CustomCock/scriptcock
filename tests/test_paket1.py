"""Backlog P1, Paket 1: Datei- und System-Bausteine – echte Ausführung in bash und zsh.

PowerShell/CMD: Syntax/Lint über tests/test_generators.py (Windows-Pfade lassen sich unter Linux nicht
ausführen). Systembefehle werden durch Attrappen ersetzt, die ihre Aufrufe protokollieren.
"""

from __future__ import annotations

import os
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

import pytest

from app.escaping import Ziel
from app.registry import Registry
from tests.conftest import erzeuge
from tests.test_ausfuehrung import SH_ZIELE, ausfuehren


def lauf(
    registry: Registry,
    shell: str,
    ziel: Ziel,
    tmp_path: Path,
    schritte: list[tuple[str, dict[str, Any]]],
    eingabe: str = "",
    attrappen: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
):
    pfad = tmp_path / "bin"
    pfad.mkdir(exist_ok=True)
    for name, inhalt in (attrappen or {}).items():
        datei = pfad / name
        datei.write_text("#!/bin/sh\n" + inhalt + "\n", encoding="utf-8")
        datei.chmod(0o755)
    s = erzeuge(registry, ziel, schritte)
    lauf_ordner = tmp_path / "lauf"
    lauf_ordner.mkdir(exist_ok=True)
    return ausfuehren(
        shell,
        s.inhalt,
        lauf_ordner,
        eingabe=eingabe,
        env={"PATH": f"{pfad}:{os.environ['PATH']}", **(env or {})},
    )


def protokoll(tmp_path: Path) -> str:
    datei = tmp_path / "aufrufe.txt"
    return datei.read_text(encoding="utf-8") if datei.exists() else ""


def aufzeichnen(tmp_path: Path, name: str, ausgabe: str = "") -> str:
    """Attrappe, die ihren Aufruf in aufrufe.txt schreibt."""
    return f"printf '%s %s\\n' {name} \"$*\" >> '{tmp_path}/aufrufe.txt'\nprintf '%s\\n' '{ausgabe}'"


# --- verschieben / umbenennen ------------------------------------------------------------------


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_verschieben(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    (tmp_path / "a.txt").write_text("neu")
    (tmp_path / "archiv").mkdir()
    (tmp_path / "archiv" / "a.txt").write_text("alt")
    schritt = ("verschieben", {"quelle": f"{tmp_path}/a.txt", "ziel": f"{tmp_path}/archiv"})
    r = lauf(registry, shell, ziel, tmp_path, [schritt])
    assert r.returncode != 0 and "Am Ziel gibt es bereits" in r.stdout
    assert (tmp_path / "a.txt").exists() and (tmp_path / "archiv" / "a.txt").read_text() == "alt"
    schritt[1]["ueberschreiben"] = True
    r = lauf(registry, shell, ziel, tmp_path, [schritt])
    assert r.returncode == 0, r.stdout
    assert not (tmp_path / "a.txt").exists() and (tmp_path / "archiv" / "a.txt").read_text() == "neu"
    # Ordner samt Inhalt
    (tmp_path / "ordner x").mkdir()
    (tmp_path / "ordner x" / "b").write_text("b")
    schritt = ("verschieben", {"quelle": f"{tmp_path}/ordner x", "ziel": f"{tmp_path}/archiv"})
    r = lauf(registry, shell, ziel, tmp_path, [schritt])
    assert r.returncode == 0, r.stdout
    assert (tmp_path / "archiv" / "ordner x" / "b").exists()


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_umbenennen(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    (tmp_path / "alt.txt").write_text("x")
    (tmp_path / "belegt.txt").write_text("y")
    schritt = ("umbenennen", {"pfad": f"{tmp_path}/alt.txt", "neuer_name": "belegt.txt"})
    r = lauf(registry, shell, ziel, tmp_path, [schritt])
    assert r.returncode != 0 and "gibt es dort schon" in r.stdout
    assert (tmp_path / "belegt.txt").read_text() == "y"
    schritt[1]["neuer_name"] = "Bericht 2026 (final).txt"
    r = lauf(registry, shell, ziel, tmp_path, [schritt])
    assert r.returncode == 0, r.stdout
    assert (tmp_path / "Bericht 2026 (final).txt").read_text() == "x"


def test_dateiname_schuetzt_vor_ordnerwechsel(registry: Registry) -> None:
    from app.validation import FehlerSammlung

    with pytest.raises(FehlerSammlung):
        erzeuge(registry, Ziel.BASH, [("umbenennen", {"pfad": "/tmp/a", "neuer_name": ".."})])


# --- löschen --------------------------------------------------------------------------------------


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_loeschen(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    ordner = tmp_path / "weg"
    (ordner / "unter").mkdir(parents=True)
    (ordner / "1.txt").write_text("1")
    (ordner / "unter" / "2.txt").write_text("2")
    r = lauf(registry, shell, ziel, tmp_path, [("loeschen", {"pfad": str(ordner)})], eingabe="JA\n")
    assert r.returncode == 0, r.stdout
    assert f"Wird gelöscht: Ordner {ordner} mit 2 Dateien" in r.stdout
    assert not ordner.exists()
    # ohne „JA“ passiert nichts
    datei = tmp_path / "datei.txt"
    datei.write_text("x")
    r = lauf(registry, shell, ziel, tmp_path, [("loeschen", {"pfad": str(datei)})], eingabe="nein\n")
    assert r.returncode == 2 and datei.exists()
    # nicht vorhanden
    r = lauf(
        registry, shell, ziel, tmp_path, [("loeschen", {"pfad": f"{tmp_path}/gibtsnicht"})], eingabe="JA\n"
    )
    assert r.returncode != 0 and "Das gibt es nicht" in r.stdout


# Tests mit Systempfaden: rm/find nur als Attrappen, die protokollieren – selbst wenn der Schutz
# im Baustein versagt, wird nichts gelöscht (die Tests laufen oft als root).
def sicher(tmp_path: Path) -> dict[str, str]:
    return {"rm": aufzeichnen(tmp_path, "rm"), "find": aufzeichnen(tmp_path, "find")}


def trifft(tmp_path: Path, pfad: str) -> bool:
    """Wurde rm/find mit genau diesem Pfad als Argument aufgerufen? (Aufräumen des Scripts zählt nicht.)"""
    return any(pfad in zeile.split()[1:] for zeile in protokoll(tmp_path).splitlines())


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
@pytest.mark.parametrize("geschuetzt", ["/", "/etc", "/usr", "HOME"])
def test_loeschen_geschuetzt(
    registry: Registry, tmp_path: Path, shell: str, ziel: Ziel, geschuetzt: str
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    pfad = str(home) if geschuetzt == "HOME" else geschuetzt
    r = lauf(
        registry,
        shell,
        ziel,
        tmp_path,
        [("loeschen", {"pfad": pfad})],
        eingabe="JA\n",
        attrappen=sicher(tmp_path),
        env={"HOME": str(home)},
    )
    assert r.returncode != 0
    assert "Dieser Ordner ist geschützt" in r.stdout
    assert not trifft(tmp_path, pfad)
    assert Path(pfad).exists()


def _alt(datei: Path, tage: int) -> None:
    datei.write_text(datei.name)
    zeit = time.time() - tage * 86400
    os.utime(datei, (zeit, zeit))


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_alte_dateien_loeschen(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    ordner = tmp_path / "logs"
    (ordner / "unter").mkdir(parents=True)
    _alt(ordner / "alt.log", 100)
    _alt(ordner / "unter" / "auch alt.log", 100)
    _alt(ordner / "neu.log", 1)
    _alt(ordner / "alt.txt", 100)
    schritt = ("alte_dateien_loeschen", {"pfad": str(ordner), "tage": 30, "muster": "*.log"})
    r = lauf(registry, shell, ziel, tmp_path, [schritt], eingabe="JA\n")
    assert r.returncode == 0, r.stdout
    assert "2 Dateien älter als 30 Tage gefunden." in r.stdout
    assert sorted(p.name for p in ordner.rglob("*") if p.is_file()) == ["alt.txt", "neu.log"]
    assert (ordner / "unter").is_dir()  # Ordner bleiben
    # ohne Muster: alles Alte
    schritt = ("alte_dateien_loeschen", {"pfad": str(ordner), "tage": 30})
    r = lauf(registry, shell, ziel, tmp_path, [schritt], eingabe="JA\n")
    assert r.returncode == 0, r.stdout
    assert sorted(p.name for p in ordner.rglob("*") if p.is_file()) == ["neu.log"]


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_alte_dateien_loeschen_geschuetzt(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    schritt = ("alte_dateien_loeschen", {"pfad": "/usr", "tage": 1})
    r = lauf(registry, shell, ziel, tmp_path, [schritt], eingabe="JA\n", attrappen=sicher(tmp_path))
    assert r.returncode != 0 and "Dieser Ordner ist geschützt" in r.stdout
    assert not trifft(tmp_path, "/usr")


# --- prüfen, entpacken, sichern ----------------------------------------------------------------------


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_existiert_pruefen(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    (tmp_path / "da.txt").write_text("x")
    r = lauf(registry, shell, ziel, tmp_path, [("existiert_pruefen", {"pfad": f"{tmp_path}/da.txt"})])
    assert r.returncode == 0 and "Vorhanden." in r.stdout
    r = lauf(registry, shell, ziel, tmp_path, [("existiert_pruefen", {"pfad": f"{tmp_path}/fehlt"})])
    assert r.returncode == 0 and "Nicht vorhanden." in r.stdout
    schritt = ("existiert_pruefen", {"pfad": f"{tmp_path}/fehlt", "abbrechen": True})
    r = lauf(registry, shell, ziel, tmp_path, [schritt])
    assert r.returncode != 0


def test_zip_entpacken_bash(registry: Registry, tmp_path: Path) -> None:
    if shutil.which("unzip") is None:
        pytest.skip("unzip fehlt")
    archiv = tmp_path / "paket.zip"
    with zipfile.ZipFile(archiv, "w") as z:
        z.writestr("treiber/setup.inf", "inf")
        z.writestr("liesmich.txt", "hallo")
    schritt = ("zip_entpacken", {"zip": str(archiv), "ziel": f"{tmp_path}/neu/ordner"})
    r = lauf(registry, "bash", Ziel.BASH, tmp_path, [schritt])
    assert r.returncode == 0, r.stdout
    assert (tmp_path / "neu" / "ordner" / "treiber" / "setup.inf").read_text() == "inf"


def test_zip_entpacken_zsh(registry: Registry, tmp_path: Path) -> None:
    schritt = ("zip_entpacken", {"zip": f"{tmp_path}/a.zip", "ziel": f"{tmp_path}/ziel"})
    r = lauf(
        registry, "zsh", Ziel.ZSH, tmp_path, [schritt], attrappen={"ditto": aufzeichnen(tmp_path, "ditto")}
    )
    assert r.returncode == 0, r.stdout
    assert protokoll(tmp_path) == f"ditto -x -k {tmp_path}/a.zip {tmp_path}/ziel\n"


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_datei_backup(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    (tmp_path / "hosts").write_text("127.0.0.1")
    (tmp_path / "app.conf").write_text("a=1")
    (tmp_path / "konfig").mkdir()
    (tmp_path / "konfig" / "x").write_text("x")
    (tmp_path / "sicherung").mkdir()
    schritte = [
        ("datei_backup", {"pfad": f"{tmp_path}/hosts"}),
        ("datei_backup", {"pfad": f"{tmp_path}/app.conf", "ziel": f"{tmp_path}/sicherung"}),
        ("datei_backup", {"pfad": f"{tmp_path}/konfig"}),
    ]
    r = lauf(registry, shell, ziel, tmp_path, schritte)
    assert r.returncode == 0, r.stdout
    stempel = r"\d{8}-\d{6}"
    neben = [p.name for p in tmp_path.iterdir()]
    assert any(re.fullmatch(rf"hosts_{stempel}", n) for n in neben), neben
    assert any(re.fullmatch(rf"app_{stempel}\.conf", p.name) for p in (tmp_path / "sicherung").iterdir())
    kopie = next(p for p in tmp_path.iterdir() if re.fullmatch(rf"konfig_{stempel}", p.name))
    assert (kopie / "x").read_text() == "x"
    assert "Sicherung: " in r.stdout


# --- System (Attrappen, als root – sonst würde sudo fragen) ----------------------------------------

ROOT = pytest.mark.skipif(os.geteuid() != 0, reason="braucht root (okm_sudo fragt sonst nach dem Passwort)")


@ROOT
def test_rechner_umbenennen_bash(registry: Registry, tmp_path: Path) -> None:
    attrappen = {"hostnamectl": aufzeichnen(tmp_path, "hostnamectl"), "hostname": "echo PC-EMPFANG-01"}
    schritt = ("rechner_umbenennen", {"neuer_name": "pc-empfang-01"})
    r = lauf(registry, "bash", Ziel.BASH, tmp_path, [schritt], attrappen=attrappen)
    assert r.returncode == 0, r.stdout
    assert protokoll(tmp_path) == "hostnamectl set-hostname PC-EMPFANG-01\n"
    assert "Neuer Hostname: PC-EMPFANG-01" in r.stdout


@ROOT
def test_rechner_umbenennen_zsh(registry: Registry, tmp_path: Path) -> None:
    attrappen = {"scutil": aufzeichnen(tmp_path, "scutil", "MAC-01")}
    schritt = ("rechner_umbenennen", {"neuer_name": "MAC-01"})
    r = lauf(registry, "zsh", Ziel.ZSH, tmp_path, [schritt], attrappen=attrappen)
    assert r.returncode == 0, r.stdout
    assert protokoll(tmp_path).splitlines() == [
        "scutil --set ComputerName MAC-01",
        "scutil --set LocalHostName MAC-01",
        "scutil --set HostName MAC-01",
        "scutil --get ComputerName",
    ]


@ROOT
def test_zeit_sync(registry: Registry, tmp_path: Path) -> None:
    attrappen = {"chronyc": aufzeichnen(tmp_path, "chronyc"), "timedatectl": "echo synchronisiert"}
    r = lauf(registry, "bash", Ziel.BASH, tmp_path, [("zeit_sync", {})], attrappen=attrappen)
    assert r.returncode == 0, r.stdout
    assert protokoll(tmp_path) == "chronyc makestep\n"

    zsh_ordner = tmp_path / "z"
    zsh_ordner.mkdir()
    attrappen = {"sntp": aufzeichnen(zsh_ordner, "sntp")}
    r = lauf(registry, "zsh", Ziel.ZSH, zsh_ordner, [("zeit_sync", {})], attrappen=attrappen)
    assert r.returncode == 0, r.stdout
    assert protokoll(zsh_ordner) == "sntp -sS time.apple.com\n"


@ROOT
@pytest.mark.parametrize(
    ("shell", "ziel", "befehl"),
    [
        ("bash", Ziel.BASH, "timedatectl set-timezone Europe/Berlin"),
        ("zsh", Ziel.ZSH, "systemsetup -settimezone Europe/Berlin"),
    ],
)
def test_zeitzone_setzen(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel, befehl: str) -> None:
    name = befehl.split()[0]
    schritt = ("zeitzone_setzen", {"zeitzone": "berlin"})
    r = lauf(registry, shell, ziel, tmp_path, [schritt], attrappen={name: aufzeichnen(tmp_path, name)})
    assert r.returncode == 0, r.stdout
    assert protokoll(tmp_path).splitlines()[0] == befehl
