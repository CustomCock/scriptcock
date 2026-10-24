"""Backlog P1, Paket 3: Software-, Drucker- und Log-Bausteine.

bash/zsh werden ausgeführt (Paketmanager, dpkg-query, journalctl, log als protokollierende Attrappen;
Homebrew-Bausteine laufen als „nobody“, weil Homebrew root verweigert). Die reinen Windows-Bausteine
(MSI/EXE/Treiber/Druckserver) sind unter Linux nicht ausführbar – hier wird geprüft, dass die
sicherheitsrelevanten Teile im Script stehen (feste Schalter, Exit-Code-Behandlung).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.escaping import Ziel
from app.generators import generator_fuer
from app.registry import Registry
from app.validation import FehlerSammlung
from tests.conftest import erzeuge
from tests.test_ausfuehrung import SH_ZIELE, ausfuehren
from tests.test_paket1 import aufzeichnen, lauf, protokoll
from tests.test_rueckgabe import ZEIGEN_ECHT, ir_aus, mit_bloecken

ROOT = pytest.mark.skipif(os.geteuid() != 0, reason="braucht root (okm_sudo fragt sonst nach dem Passwort)")


# --- Paketmanager (bash, als root) ---------------------------------------------------------------


@ROOT
@pytest.mark.parametrize(
    ("block", "parameter", "erwartet"),
    [
        ("paket_entfernen", {"paket": "firefox-esr"}, ["apt-get remove -y firefox-esr"]),
        ("paket_entfernen", {"paket": "htop", "paketmanager": "dnf"}, ["dnf remove -y htop"]),
        (
            "paket_entfernen",
            {"paket": "org.videolan.VLC", "paketmanager": "flatpak"},
            ["flatpak uninstall -y --noninteractive org.videolan.VLC"],
        ),
        ("pakete_aktualisieren", {}, ["apt-get update", "apt-get upgrade -y"]),
        (
            "pakete_aktualisieren",
            {"paket": "firefox-esr"},
            ["apt-get update", "apt-get install --only-upgrade -y firefox-esr"],
        ),
        ("pakete_aktualisieren", {"paketmanager": "flatpak"}, ["flatpak update -y --noninteractive"]),
        ("pakete_aktualisieren", {"paket": "htop", "paketmanager": "dnf"}, ["dnf upgrade -y htop"]),
    ],
)
def test_paketmanager_bash(
    registry: Registry, tmp_path: Path, block: str, parameter: dict[str, Any], erwartet: list[str]
) -> None:
    attrappen = {name: aufzeichnen(tmp_path, name) for name in ("apt-get", "dnf", "flatpak")}
    r = lauf(registry, "bash", Ziel.BASH, tmp_path, [(block, parameter)], attrappen=attrappen)
    assert r.returncode == 0, r.stdout
    assert protokoll(tmp_path).splitlines() == erwartet


def test_paketmanager_falsch_fuer_ziel(registry: Registry, tmp_path: Path) -> None:
    r = lauf(
        registry, "bash", Ziel.BASH, tmp_path, [("paket_entfernen", {"paket": "vlc", "paketmanager": "brew"})]
    )
    assert r.returncode != 0 and "unter Linux nicht verfügbar" in r.stdout


# --- Homebrew (zsh, als normaler Benutzer) -----------------------------------------------------


@pytest.fixture
def offen() -> Iterator[Path]:
    """Verzeichnis, das auch „nobody“ lesen und beschreiben kann."""
    pfad = Path(tempfile.mkdtemp(prefix="okm-paket3-", dir="/tmp"))
    pfad.chmod(0o777)
    yield pfad
    shutil.rmtree(pfad, ignore_errors=True)


def als_benutzer(
    shell: str, inhalt: bytes, ordner: Path, attrappen: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    if shutil.which(shell) is None:
        pytest.skip(f"{shell} fehlt")
    pfad = ordner / "bin"
    pfad.mkdir()
    pfad.chmod(0o755)
    for name, text in attrappen.items():
        (pfad / name).write_text("#!/bin/sh\n" + text + "\n", encoding="utf-8")
        (pfad / name).chmod(0o755)
    datei = ordner / "s.sh"
    datei.write_bytes(inhalt)
    datei.chmod(0o755)
    befehl = [shell, str(datei)]
    if os.geteuid() == 0:
        if shutil.which("setpriv") is None:
            pytest.skip("braucht setpriv, um als normaler Benutzer zu starten")
        befehl = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", *befehl]
    return subprocess.run(
        befehl,
        capture_output=True,
        text=True,
        cwd=ordner,
        timeout=60,
        stdin=subprocess.DEVNULL,
        env={"PATH": f"{pfad}:/usr/bin:/bin", "TMPDIR": str(ordner), "HOME": str(ordner)},
    )


@pytest.mark.parametrize(
    ("block", "parameter", "erwartet"),
    [
        ("paket_entfernen", {"paket": "vlc", "paketmanager": "brew_cask"}, ["brew uninstall --cask vlc"]),
        ("paket_entfernen", {"paket": "wget"}, ["brew uninstall wget"]),
        ("pakete_aktualisieren", {}, ["brew update", "brew upgrade"]),
        (
            "pakete_aktualisieren",
            {"paket": "vlc", "paketmanager": "brew_cask"},
            ["brew update", "brew upgrade --cask vlc"],
        ),
    ],
)
def test_homebrew_zsh(
    registry: Registry, offen: Path, block: str, parameter: dict[str, Any], erwartet: list[str]
) -> None:
    s = erzeuge(registry, Ziel.ZSH, [(block, parameter)])
    r = als_benutzer("zsh", s.inhalt, offen, {"brew": aufzeichnen(offen, "brew")})
    assert r.returncode == 0, r.stdout + r.stderr
    assert protokoll(offen).splitlines() == erwartet


# --- software_version -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def reg() -> Registry:
    return mit_bloecken(ZEIGEN_ECHT)


def ok_wert(
    reg: Registry,
    tmp_path: Path,
    shell: str,
    ziel: Ziel,
    schritt: dict[str, Any],
    rueckgabe: str,
    attrappen: dict[str, str],
) -> tuple[str, Any]:
    pfad = tmp_path / "bin"
    pfad.mkdir(parents=True, exist_ok=True)
    for name, text in attrappen.items():
        (pfad / name).write_text("#!/bin/sh\n" + text + "\n", encoding="utf-8")
        (pfad / name).chmod(0o755)
    zeigen = {"block_id": "test_wert", "parameter": {"ok": f"1.{rueckgabe}"}}
    s = generator_fuer(ziel, reg).erzeuge(ir_aus(reg, ziel, [schritt, zeigen]))
    r = ausfuehren(shell, s.inhalt, tmp_path, env={"PATH": f"{pfad}:{os.environ['PATH']}"})
    m = re.search(r"OKM-OK=(\S*)", r.stdout)
    return (m.group(1) if m else "?"), r


DPKG = "case \"$*\" in *firefox-esr*) printf '%s' '1:115.3.0esr-1~deb12u1' ;; *) exit 1 ;; esac"


@pytest.mark.parametrize(
    ("name", "mindestens", "rueckgabe", "erwartet"),
    [
        ("firefox-esr", "115.0", "aktuell", "1"),
        ("firefox-esr", "115.3", "aktuell", "1"),
        ("firefox-esr", "115.10", "aktuell", "0"),  # 115.10 > 115.3 (Versionsvergleich, nicht Text)
        ("firefox-esr", "116", "aktuell", "0"),
        ("firefox-esr", "1", "installiert", "1"),
        ("gibtsnicht", "1", "installiert", "0"),
        ("gibtsnicht", "1", "aktuell", "0"),
    ],
)
def test_software_version_bash(
    reg: Registry, tmp_path: Path, name: str, mindestens: str, rueckgabe: str, erwartet: str
) -> None:
    schritt = {"block_id": "software_version", "parameter": {"name": name, "mindestens": mindestens}}
    wert, r = ok_wert(reg, tmp_path, "bash", Ziel.BASH, schritt, rueckgabe, {"dpkg-query": DPKG})
    assert r.returncode == 0, r.stdout
    assert wert == erwartet, r.stdout


def test_software_version_zsh_nicht_installiert(reg: Registry, tmp_path: Path) -> None:
    schritt = {"block_id": "software_version", "parameter": {"name": "Gibt Es Nicht", "mindestens": "1"}}
    wert, r = ok_wert(reg, tmp_path, "zsh", Ziel.ZSH, schritt, "installiert", {})
    assert wert == "0" and "Nicht installiert" in r.stdout


# --- Logs ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_logdatei_ende(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    log = tmp_path / "app log.txt"
    log.write_text("".join(f"Zeile {i} {'ERROR' if i % 10 == 0 else 'ok'}\n" for i in range(1, 101)))
    r = lauf(registry, shell, ziel, tmp_path, [("logdatei_ende", {"pfad": str(log), "zeilen": 3})])
    assert r.returncode == 0, r.stdout
    assert re.findall(r"^Zeile \d+", r.stdout.split("--- LOG ---")[0], re.M) == [
        "Zeile 98",
        "Zeile 99",
        "Zeile 100",
    ]
    r = lauf(
        registry,
        shell,
        ziel,
        tmp_path,
        [("logdatei_ende", {"pfad": str(log), "zeilen": 2, "suche": "error"})],
    )
    assert re.findall(r"^Zeile \d+", r.stdout.split("--- LOG ---")[0], re.M) == ["Zeile 90", "Zeile 100"]
    # kein Treffer ist kein Fehler
    r = lauf(registry, shell, ziel, tmp_path, [("logdatei_ende", {"pfad": str(log), "suche": "gibtsnicht"})])
    assert r.returncode == 0, r.stdout
    r = lauf(registry, shell, ziel, tmp_path, [("logdatei_ende", {"pfad": f"{tmp_path}/fehlt.log"})])
    assert r.returncode != 0 and "gibt es nicht" in r.stdout


@ROOT
def test_eventlog_export_bash(registry: Registry, tmp_path: Path) -> None:
    journal = aufzeichnen(tmp_path, "journalctl") + "\nprintf '%s\\n' 'Eintrag 1' 'Eintrag 2'"
    schritt = ("eventlog_export", {"tage": 3, "ordner": str(tmp_path)})
    r = lauf(registry, "bash", Ziel.BASH, tmp_path, [schritt], attrappen={"journalctl": journal})
    assert r.returncode == 0, r.stdout
    assert protokoll(tmp_path).splitlines()[0] == "journalctl --no-pager --since=-3d -o short-iso"
    datei = next(tmp_path.glob("journal-*.txt"))
    assert "Eintrag 2" in datei.read_text()
    assert re.search(r"Exportiert: .*journal-\d{8}-\d{6}\.txt \(\d+ Zeilen\)", r.stdout)


def test_eventlog_export_zsh(registry: Registry, tmp_path: Path) -> None:
    log = aufzeichnen(tmp_path, "log") + "\nprintf '%s\\n' 'a' 'b' 'c'"
    schritt = ("eventlog_export", {"tage": 2, "ordner": str(tmp_path)})
    r = lauf(registry, "zsh", Ziel.ZSH, tmp_path, [schritt], attrappen={"log": log})
    assert r.returncode == 0, r.stdout
    assert protokoll(tmp_path).splitlines()[0] == "log show --last 2d --style compact"
    datei = next(tmp_path.glob("unified-log-*.txt"))
    assert datei.read_text().split() == ["a", "b", "c"]
    assert re.search(r"Exportiert: .*unified-log-\d{8}-\d{6}\.txt \(\d+ Zeilen\)", r.stdout)


# --- Windows-Bausteine: feste Schalter, Exit-Codes ---------------------------------------------------


def test_msi_installieren(registry: Registry) -> None:
    schritt = (
        "msi_installieren",
        {"datei": "\\\\fs01\\Software\\Mein Tool.msi", "eigenschaften": "ALLUSERS=1, INSTALLDIR=C:\\Tools"},
    )
    ps = erzeuge(registry, Ziel.POWERSHELL, [schritt]).text
    assert "$okmArgumente = '/i \"' + '\\\\fs01\\Software\\Mein Tool.msi' + '\" /qn /norestart /l*v" in ps
    assert "(@('ALLUSERS=1', 'INSTALLDIR=C:\\Tools') -join ' ')" in ps
    assert "-eq 3010" in ps and "throw ('msiexec endete mit Exit-Code '" in ps
    cmd = erzeuge(registry, Ziel.CMD, [schritt]).text
    assert (
        'msiexec /i "\\\\fs01\\Software\\Mein Tool.msi" /qn /norestart /l*v "%TEMP%\\okm-msi.log" "ALLUSERS=1" "INSTALLDIR=C:\\Tools"'
        in cmd
    )
    assert "if errorlevel 3010 if not errorlevel 3011 (" in cmd


@pytest.mark.parametrize("roh", ["A=1 /qb", 'A="x"', "allusers=1", "TRANSFORMS=a b.mst"])
def test_msi_eigenschaften_keine_freien_argumente(registry: Registry, roh: str) -> None:
    with pytest.raises(FehlerSammlung):
        erzeuge(
            registry, Ziel.POWERSHELL, [("msi_installieren", {"datei": "C:\\a.msi", "eigenschaften": roh})]
        )


@pytest.mark.parametrize(
    ("profil", "schalter"),
    [
        ("inno", "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-"),
        ("nsis", "/S"),
        ("installshield", '/s /v"/qn /norestart"'),
        ("burn", "/quiet /norestart"),
    ],
)
def test_exe_installieren_profile(registry: Registry, profil: str, schalter: str) -> None:
    schritt = ("exe_installieren", {"datei": "\\\\fs01\\Software\\setup.exe", "profil": profil})
    ps = erzeuge(registry, Ziel.POWERSHELL, [schritt]).text
    assert f"$okmSchalter = '{schalter}'" in ps
    cmd = erzeuge(registry, Ziel.CMD, [schritt]).text
    assert f'start "" /wait "\\\\fs01\\Software\\setup.exe" {schalter}' in cmd


def test_treiber_und_druckserver(registry: Registry) -> None:
    ps = erzeuge(
        registry,
        Ziel.POWERSHELL,
        [
            (
                "treiber_installieren",
                {"inf": "\\\\fs01\\Treiber\\hp.inf", "druckertreiber": "HP Universal Printing PCL 6"},
            )
        ],
    ).text
    assert "pnputil.exe /add-driver '\\\\fs01\\Treiber\\hp.inf' /install" in ps
    assert "-eq 259" in ps and "Add-PrinterDriver -Name 'HP Universal Printing PCL 6'" in ps
    ps = erzeuge(registry, Ziel.POWERSHELL, [("treiber_entfernen", {"name": "Alter Treiber"})]).text
    assert "Der Treiber wird noch genutzt von" in ps  # erst prüfen, dann entfernen
    assert ps.index("noch genutzt") < ps.index("Remove-PrinterDriver")
    ps = erzeuge(
        registry,
        Ziel.POWERSHELL,
        [("drucker_server_verbinden", {"freigabe": "\\\\ps01\\Empfang", "standard": True})],
    ).text
    assert "Add-Printer -ConnectionName '\\\\ps01\\Empfang'" in ps and "SetDefaultPrinter" in ps
    cmd = erzeuge(registry, Ziel.CMD, [("drucker_server_verbinden", {"freigabe": "\\\\ps01\\Empfang"})]).text
    assert 'rundll32 printui.dll,PrintUIEntry /in /n "\\\\ps01\\Empfang"' in cmd


# --- zsh: „log“ ist ein eingebautes Kommando ---------------------------------------------------


def test_registry_lehnt_zsh_builtin_log_ab() -> None:
    """In zsh zeigt das Builtin „log“ angemeldete Benutzer – „log show …“ scheitert („too many
    arguments“). Templates müssen „command log …“ schreiben."""
    from app.registry import RegistryFehler
    from tests.test_rueckgabe import mit_bloecken as mit

    block = {
        "id": "test_log",
        "name": "Test",
        "kategorie": "Test",
        "beschreibung": "x",
        "risiko": "gruen",
        "ziele": {"zsh": "log show --last 1h"},
    }
    with pytest.raises(RegistryFehler, match="command log"):
        mit(block)
    mit({**block, "id": "test_log2", "ziele": {"zsh": "command log show --last 1h\nprintf 'log ok'"}})


def test_echte_zsh_bloecke_nutzen_command_log(registry: Registry, tmp_path: Path) -> None:
    for block_id in ("systemlog_fehler", "diagnosepaket", "eventlog_export"):
        text = registry.bloecke[block_id].ziele[Ziel.ZSH]
        assert "command log show" in text, block_id
