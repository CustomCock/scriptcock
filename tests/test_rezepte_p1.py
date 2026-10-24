"""Backlog P1: Rezepte und ihre neuen Bausteine (pakete_installieren, netzwerkadapter_neustarten,
office_schnellreparatur).

Paketmanager, nmcli, ifconfig und winget nur als protokollierende Attrappen. Die Rezepte selbst werden
über tests/test_golden.py für jedes Ziel erzeugt und auf Syntax geprüft; hier Formular → Script.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.escaping import Ziel
from app.registry import Registry
from app.service import rezept_felder, rezept_zu_request
from app.validation import validiere_request
from tests.conftest import FESTE_ZEIT, erzeuge
from tests.test_ausfuehrung import ausfuehren
from tests.test_paket1 import ROOT, aufzeichnen, lauf, protokoll
from tests.test_paket2 import werte
from tests.test_paket3 import als_benutzer, offen
from tests.test_rueckgabe import ZEIGEN_ECHT, mit_bloecken
from tests.test_web import client

__all__ = ["client", "offen"]  # Fixtures aus test_web / test_paket3

NEUE_REZEPTE = [
    "standardsoftware_installieren",
    "neuer_arbeitsplatz",
    "drucker_printserver",
    "netzwerk_reparieren",
    "outlook_reparieren",
    "vor_aenderung_absichern",
]


@pytest.fixture(scope="module")
def reg() -> Registry:
    return mit_bloecken(ZEIGEN_ECHT)


# --- pakete_installieren ------------------------------------------------------------------------


@ROOT
def test_pakete_installieren_apt(reg: Registry, tmp_path: Path) -> None:
    attrappen = {"apt-get": aufzeichnen(tmp_path, "apt-get") + '\ncase "$*" in *kaputt*) exit 100 ;; esac'}
    schritt = {"block_id": "pakete_installieren", "parameter": {"pakete": "firefox-esr, vlc"}}
    anzahl, _, r = werte(
        reg, tmp_path / "a", "bash", Ziel.BASH, schritt, zahl="1.fehlgeschlagen", attrappen=attrappen
    )
    assert anzahl == "0", r.stdout
    assert protokoll(tmp_path) == "apt-get update\napt-get install -y firefox-esr\napt-get install -y vlc\n"
    # ein Paket schlägt fehl → die übrigen werden trotzdem installiert, am Ende Fehler
    (tmp_path / "aufrufe.txt").unlink()
    schritt = {"block_id": "pakete_installieren", "parameter": {"pakete": "kaputt vlc"}}
    _, _, r = werte(
        reg, tmp_path / "b", "bash", Ziel.BASH, schritt, zahl="1.fehlgeschlagen", attrappen=attrappen
    )
    assert r.returncode != 0 and "Nicht installiert: kaputt" in r.stdout
    assert "apt-get install -y vlc" in protokoll(tmp_path)


@ROOT
def test_pakete_installieren_falscher_paketmanager(reg: Registry, tmp_path: Path) -> None:
    schritt = {"block_id": "pakete_installieren", "parameter": {"pakete": "a, b", "paketmanager": "brew"}}
    _, _, r = werte(reg, tmp_path, "bash", Ziel.BASH, schritt, zahl="1.fehlgeschlagen")
    assert r.returncode != 0 and "unter Linux nicht verfügbar" in r.stdout


def test_pakete_installieren_brew(registry: Registry, offen: Path) -> None:
    aufrufe = offen / "brew.txt"
    brew = f"printf '%s\\n' \"$*\" >> '{aufrufe}'\ncase \"$*\" in *kaputt*) exit 1 ;; esac"
    s = erzeuge(
        registry,
        Ziel.ZSH,
        [
            (
                "pakete_installieren",
                {"pakete": "firefox, kaputt, visual-studio-code", "paketmanager": "brew_cask"},
            )
        ],
    )
    r = als_benutzer("zsh", s.inhalt, offen, {"brew": brew})
    assert r.returncode != 0 and "Nicht installiert: kaputt" in r.stdout
    assert aufrufe.read_text().splitlines() == [
        "install --cask firefox",
        "install --cask kaputt",
        "install --cask visual-studio-code",
    ]


@pytest.mark.parametrize("fehlschlag", [False, True])
def test_pakete_installieren_pwsh(registry: Registry, tmp_path: Path, fehlschlag: bool) -> None:
    """winget als Attrappe „winget.exe“ im PATH – PowerShell ruft sie wie unter Windows auf."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    aufrufe = tmp_path / "winget.txt"
    winget = bin_ / "winget.exe"
    winget.write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"$3\" >> '{aufrufe}'\n"
        + ('[ "$3" = "Kaputt.App" ] && exit 1\n' if fehlschlag else "")
        + "exit 0\n"
    )
    winget.chmod(0o755)
    s = erzeuge(registry, Ziel.POWERSHELL, [("pakete_installieren", {"pakete": "Kaputt.App, 7zip.7zip"})])
    r = ausfuehren(
        "pwsh", s.inhalt, tmp_path, env={"PATH": f"{bin_}:{os.environ['PATH']}", "TEMP": str(tmp_path)}
    )
    assert aufrufe.read_text().splitlines() == ["Kaputt.App", "7zip.7zip"]
    if fehlschlag:
        assert r.returncode != 0 and "Nicht installiert: Kaputt.App" in r.stdout
    else:
        assert r.returncode == 0, r.stdout + r.stderr
        assert "Alle Pakete installiert." in r.stdout


def test_pakete_installieren_cmd(registry: Registry) -> None:
    text = erzeuge(
        registry, Ziel.CMD, [("pakete_installieren", {"pakete": "Mozilla.Firefox, 7zip.7zip"})]
    ).text
    assert 'for %%p in ("Mozilla.Firefox" "7zip.7zip") do (' in text
    # Fehler über „||“ (auch negative winget-Codes) und eine Datei – nicht über %VAR% im Block
    assert "|| (set /a OKM_FEHLT+=1" in text
    assert "set /a OKM_S1_FEHLGESCHLAGEN=OKM_FEHLT" in text


# --- netzwerkadapter_neustarten -----------------------------------------------------------------


@ROOT
@pytest.mark.parametrize(
    ("adapter", "erwartet"),
    [
        ("", ["nmcli networking off", "nmcli networking on", "nmcli device status"]),
        ("enp3s0", ["nmcli device disconnect enp3s0", "nmcli device connect enp3s0", "nmcli device status"]),
    ],
)
def test_netzwerkadapter_linux(registry: Registry, tmp_path: Path, adapter: str, erwartet: list[str]) -> None:
    attrappen = {"nmcli": aufzeichnen(tmp_path, "nmcli"), "sleep": ":"}
    parameter = {"adapter": adapter} if adapter else {}
    r = lauf(
        registry,
        "bash",
        Ziel.BASH,
        tmp_path,
        [("netzwerkadapter_neustarten", parameter)],
        attrappen=attrappen,
    )
    assert r.returncode == 0, r.stdout
    assert protokoll(tmp_path).splitlines() == erwartet


@ROOT
def test_netzwerkadapter_macos(registry: Registry, tmp_path: Path) -> None:
    attrappen = {
        "ifconfig": aufzeichnen(tmp_path, "ifconfig"),
        "ipconfig": "echo 192.168.1.20",
        "sleep": ":",
    }
    r = lauf(registry, "zsh", Ziel.ZSH, tmp_path, [("netzwerkadapter_neustarten", {})], attrappen=attrappen)
    assert r.returncode == 0, r.stdout
    assert protokoll(tmp_path).splitlines() == ["ifconfig en0 down", "ifconfig en0 up"]
    assert "192.168.1.20" in r.stdout


def test_netzwerkadapter_windows(registry: Registry) -> None:
    ps = erzeuge(registry, Ziel.POWERSHELL, [("netzwerkadapter_neustarten", {"adapter": "Ethernet 2"})]).text
    assert "Get-NetAdapter -Name 'Ethernet 2' -ErrorAction Stop" in ps
    ps = erzeuge(registry, Ziel.POWERSHELL, [("netzwerkadapter_neustarten", {})]).text
    assert "Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' }" in ps


# --- office_schnellreparatur --------------------------------------------------------------------


def test_office_schnellreparatur(registry: Registry) -> None:
    ps = erzeuge(registry, Ziel.POWERSHELL, [("office_schnellreparatur", {})]).text
    assert "RepairType=QuickRepair" in ps and "DisplayLevel=False" in ps
    # ohne Haken: laufende Office-Programme → Abbruch statt Datenverlust
    assert "throw ('Bitte zuerst schließen: '" in ps and "Stop-Process" not in ps
    ps = erzeuge(registry, Ziel.POWERSHELL, [("office_schnellreparatur", {"apps_schliessen": True})]).text
    assert "$okmApps | Stop-Process -Force" in ps
    sim = erzeuge(
        registry, Ziel.POWERSHELL, [("office_schnellreparatur", {"apps_schliessen": True})], dry_run=True
    ).text
    assert "Start-Process -FilePath $okmC2r" not in sim and "Stop-Process" not in sim


# --- Rezepte ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("rezept_id", NEUE_REZEPTE)
def test_rezept_mit_beispielwerten(registry: Registry, rezept_id: str) -> None:
    rezept = registry.rezepte[rezept_id]
    ziele = registry.rezept_ziele(rezept)
    assert Ziel.POWERSHELL in ziele
    for ziel in ziele:
        formular = {
            f.id: f.beispiel if f.beispiel is not None else f.standard
            for f in rezept_felder(registry, rezept, ziel)
        }
        req = rezept_zu_request(registry, rezept, ziel, formular, rot_bestaetigt=True)
        ir = validiere_request(req, registry, autor="pytest", jetzt=FESTE_ZEIT)
        assert ir.schritte


def test_rezept_ziele(registry: Registry) -> None:
    nur_windows = {"drucker_printserver", "outlook_reparieren", "vor_aenderung_absichern"}
    for rezept_id in NEUE_REZEPTE:
        ziele = set(registry.rezept_ziele(registry.rezepte[rezept_id]))
        if rezept_id in nur_windows:
            assert ziele == {Ziel.POWERSHELL, Ziel.CMD}, rezept_id
        else:
            assert ziele == set(Ziel), rezept_id


def test_rezept_standardsoftware_formular(client) -> None:
    html = client.get("/rezepte/standardsoftware_installieren?ziel=powershell").text
    assert 'name="f.pakete"' in html and 'data-listen-typ="paketname"' in html
    assert "Ausgewählte übernehmen" in html
    antwort = client.post(
        "/rezepte/standardsoftware_installieren/erzeugen",
        data={"ziel": "powershell", "f.pakete": "Mozilla.Firefox, 7zip.7zip", "f.paketmanager": "standard"},
        headers={"HX-Request": "true"},
    )
    assert antwort.status_code == 200, antwort.text
    assert "@(&#39;Mozilla.Firefox&#39;, &#39;7zip.7zip&#39;)" in antwort.text
    # keine freie Eingabe: Option-Injection und Shell-Zeichen werden abgelehnt
    antwort = client.post(
        "/rezepte/standardsoftware_installieren/erzeugen",
        data={"ziel": "powershell", "f.pakete": "Mozilla.Firefox, --force", "f.paketmanager": "standard"},
        headers={"HX-Request": "true"},
    )
    assert "Eintrag 2" in antwort.text
