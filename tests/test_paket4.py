"""Backlog P1, Paket 4: Neustart, Verknüpfung, Wiederherstellung/Reparatur und Ausgabe-Bausteine.

bash/zsh werden ausgeführt – shutdown, pkill, xdg-open, open und osascript nur als protokollierende
Attrappen (es wird nie wirklich neu gestartet). Bausteine mit ``nie_root`` laufen als „nobody“.
Die reinen Windows-Bausteine (Wiederherstellungspunkt, chkdsk, KB) sind unter Linux nicht ausführbar:
Syntax über tests/test_generators.py, hier die sicherheitsrelevanten Teile im Script.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.escaping import Ziel
from app.registry import Registry
from tests.conftest import erzeuge
from tests.test_ausfuehrung import SH_ZIELE
from tests.test_paket1 import ROOT, aufzeichnen, lauf, protokoll
from tests.test_paket3 import als_benutzer, offen

__all__ = ["offen"]  # Fixture aus test_paket3


# --- Neustart / Herunterfahren ------------------------------------------------------------------


@ROOT
@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
@pytest.mark.parametrize(
    ("aktion", "sekunden", "erwartet"),
    [
        ("neustart", 0, "shutdown -r now"),
        ("neustart", 10, "shutdown -r +1"),
        ("herunterfahren", 120, "shutdown -h +2"),
        ("herunterfahren", 121, "shutdown -h +3"),
    ],
)
def test_neustart_herunterfahren(
    registry: Registry,
    tmp_path: Path,
    shell: str,
    ziel: Ziel,
    aktion: str,
    sekunden: int,
    erwartet: str,
) -> None:
    schritt = ("neustart_herunterfahren", {"aktion": aktion, "sekunden": sekunden})
    attrappen = {"shutdown": aufzeichnen(tmp_path, "shutdown")}
    r = lauf(registry, shell, ziel, tmp_path, [schritt], eingabe="JA\n", attrappen=attrappen)
    assert r.returncode == 0, r.stdout + r.stderr
    assert protokoll(tmp_path) == erwartet + "\n"
    # roter Baustein: ohne „JA“ wird nichts ausgelöst
    (tmp_path / "aufrufe.txt").unlink()
    r = lauf(registry, shell, ziel, tmp_path, [schritt], eingabe="nein\n", attrappen=attrappen)
    assert r.returncode == 2 and protokoll(tmp_path) == ""


@pytest.mark.parametrize(
    ("ziel", "teil"),
    [
        (Ziel.POWERSHELL, "shutdown.exe /s /t 30 /d p:4:1"),
        (Ziel.CMD, "shutdown /s /t 30 /d p:4:1"),
    ],
)
def test_neustart_windows(registry: Registry, ziel: Ziel, teil: str) -> None:
    text = erzeuge(
        registry, ziel, [("neustart_herunterfahren", {"aktion": "herunterfahren", "sekunden": 30})]
    ).text
    assert teil in text
    assert "Herunterfahren in 30 Sekunden" in text


@ROOT
@pytest.mark.parametrize(
    ("shell", "ziel", "befehl"), [("bash", Ziel.BASH, "shutdown"), ("zsh", Ziel.ZSH, "pkill")]
)
def test_neustart_abbrechen(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel, befehl: str) -> None:
    attrappen = {befehl: aufzeichnen(tmp_path, befehl)}
    r = lauf(registry, shell, ziel, tmp_path, [("neustart_abbrechen", {})], attrappen=attrappen)
    assert r.returncode == 0, r.stdout
    assert "Neustart abgebrochen" in r.stdout
    assert protokoll(tmp_path) == ("shutdown -c\n" if befehl == "shutdown" else "pkill -x shutdown\n")
    # nichts geplant: Befehl schlägt fehl → nur Hinweis, kein Fehler
    r = lauf(registry, shell, ziel, tmp_path, [("neustart_abbrechen", {})], attrappen={befehl: "exit 1"})
    assert r.returncode == 0, r.stdout
    assert "Es war kein Neustart geplant" in r.stdout


def test_neustart_abbrechen_cmd_reihenfolge(registry: Registry) -> None:
    text = erzeuge(registry, Ziel.CMD, [("neustart_abbrechen", {})]).text
    # erst Erfolg melden, dann 1116 („nichts geplant“) auf 0 setzen – sonst stünde beides da
    assert text.index("if not errorlevel 1 echo Geplanter") < text.index(
        "if errorlevel 1116 if not errorlevel 1117"
    )


# --- Verknüpfung --------------------------------------------------------------------------------


def desktop_exec(zeile: str) -> list[str]:
    """Exec-Wert einer .desktop-Datei nach der freedesktop-Spezifikation zerlegen."""
    wert = re.sub(r"\\(.)", lambda m: {"s": " ", "n": "\n", "t": "\t", "r": "\r"}.get(m[1], m[1]), zeile)
    teile: list[str] = []
    i = 0
    while i < len(wert):
        if wert[i] == " ":
            i += 1
            continue
        if wert[i] == '"':
            i += 1
            arg = ""
            while wert[i] != '"':
                if wert[i] == "\\":
                    assert wert[i + 1] in '"`$\\', f"unzulässiges Escape in {zeile!r}"
                    i += 1
                arg += wert[i]
                i += 1
            i += 1
        else:
            arg = ""
            while i < len(wert) and wert[i] != " ":
                arg += wert[i]
                i += 1
        teile.append(arg.replace("%%", "%"))
    return teile


def test_desktop_exec_parser() -> None:
    assert desktop_exec(r'xdg-open "/a b/\\\\x\\$y%%"') == ["xdg-open", "/a b/\\x$y%"]


SONDER = 'Ordner "x" $HOME `id` 100% \\a'


@pytest.mark.parametrize(
    ("ort", "unterordner"),
    [("desktop", "Desktop"), ("startmenue", ".local/share/applications"), ("autostart", ".config/autostart")],
)
def test_verknuepfung_linux(registry: Registry, offen: Path, ort: str, unterordner: str) -> None:
    ziel_ordner = offen / SONDER
    ziel_ordner.mkdir()
    programm = offen / "mein programm"
    programm.write_text("#!/bin/sh\n")
    programm.chmod(0o755)
    for ziel_pfad, exec_erwartet in [
        (ziel_ordner, ["xdg-open", str(ziel_ordner)]),
        (programm, [str(programm)]),
    ]:
        s = erzeuge(
            registry,
            Ziel.BASH,
            [
                (
                    "verknuepfung_erstellen",
                    {"ziel_pfad": str(ziel_pfad), "bezeichnung": "Firmen App", "ort": ort},
                )
            ],
        )
        r = als_benutzer("bash", s.inhalt, offen, {"xdg-user-dir": "exit 1", "gio": "exit 0"})
        assert r.returncode == 0, r.stdout + r.stderr
        datei = offen / unterordner / "Firmen App.desktop"
        felder = dict(z.split("=", 1) for z in datei.read_text(encoding="utf-8").splitlines()[1:])
        assert felder["Type"] == "Application" and felder["Name"] == "Firmen App"
        assert desktop_exec(felder["Exec"]) == exec_erwartet
        assert datei.stat().st_mode & 0o111
        assert not (offen / "PWNED").exists()
        (offen / "bin").rename(offen / f"bin-{ziel_pfad.name[:4]}")  # als_benutzer legt bin neu an


@pytest.mark.parametrize(("ort", "unterordner"), [("desktop", "Desktop"), ("startmenue", "Applications")])
def test_verknuepfung_macos_link(registry: Registry, offen: Path, ort: str, unterordner: str) -> None:
    ziel_ordner = offen / SONDER
    ziel_ordner.mkdir()
    s = erzeuge(
        registry,
        Ziel.ZSH,
        [("verknuepfung_erstellen", {"ziel_pfad": str(ziel_ordner), "bezeichnung": "Projekte", "ort": ort})],
    )
    r = als_benutzer("zsh", s.inhalt, offen, {})
    assert r.returncode == 0, r.stdout + r.stderr
    link = offen / unterordner / "Projekte"
    assert link.is_symlink() and link.resolve() == ziel_ordner.resolve()


def test_verknuepfung_macos_autostart(registry: Registry, offen: Path) -> None:
    s = erzeuge(
        registry,
        Ziel.ZSH,
        [
            (
                "verknuepfung_erstellen",
                {"ziel_pfad": "/Applications/Firma App.app", "bezeichnung": "Firma", "ort": "autostart"},
            )
        ],
    )
    aufrufe = offen / "osascript.txt"
    r = als_benutzer("zsh", s.inhalt, offen, {"osascript": f"printf '%s\\n' \"$@\" > '{aufrufe}'"})
    assert r.returncode == 0, r.stdout + r.stderr
    argumente = aufrufe.read_text().splitlines()
    # Pfad nur als Argument (argv), nie im AppleScript-Text
    assert argumente[-2:] == ["--", "/Applications/Firma App.app"]
    assert "Firma App" not in "".join(argumente[:-1])
    assert "WARNUNG" in r.stdout  # Ziel fehlt auf dem Testrechner


@pytest.mark.parametrize("ziel", [Ziel.POWERSHELL, Ziel.CMD])
def test_verknuepfung_windows(registry: Registry, ziel: Ziel) -> None:
    schritt = (
        "verknuepfung_erstellen",
        {"ziel_pfad": "C:\\Programme\\Firma\\app.exe", "bezeichnung": "Firma", "ort": "autostart"},
    )
    text = erzeuge(registry, ziel, [schritt]).text
    assert "GetFolderPath('Startup')" in text and "WScript.Shell" in text
    if ziel is Ziel.CMD:
        # Werte über Umgebungsvariablen, nicht im PowerShell-Befehlstext
        assert 'set OKM_ZIEL="C:\\Programme\\Firma\\app.exe"' in text
        assert "Firma\\app.exe" not in text.split("powershell -NoProfile", 1)[1].split("\n", 1)[0]


# --- Ordner / Datei öffnen ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("shell", "ziel", "oeffner"), [("bash", Ziel.BASH, "xdg-open"), ("zsh", Ziel.ZSH, "open")]
)
def test_oeffnen(registry: Registry, offen: Path, shell: str, ziel: Ziel, oeffner: str) -> None:
    ordner = offen / "Ergebnis 1"
    ordner.mkdir()
    datei = ordner / "bericht.html"
    datei.write_text("x")
    aufrufe = offen / "aufrufe.txt"
    attrappen = {oeffner: f"printf '%s|\\n' \"$@\" >> '{aufrufe}'"}
    schritte = [("ordner_oeffnen", {"ordner": str(ordner)}), ("datei_oeffnen", {"datei": str(datei)})]
    r = als_benutzer(shell, erzeuge(registry, ziel, schritte).inhalt, offen, attrappen)
    assert r.returncode == 0, r.stdout + r.stderr
    assert aufrufe.read_text().splitlines() == [f"{ordner}|", f"{datei}|"]
    # Datei statt Ordner (und umgekehrt) → Fehler, nichts geöffnet
    aufrufe.unlink()
    (offen / "bin").rename(offen / "bin-alt")
    schritte = [("ordner_oeffnen", {"ordner": str(datei)})]
    r = als_benutzer(shell, erzeuge(registry, ziel, schritte).inhalt, offen, attrappen)
    assert r.returncode != 0 and "Den Ordner gibt es nicht" in r.stdout
    assert not aufrufe.exists()


# --- Bericht als HTML ---------------------------------------------------------------------------


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_bericht_html(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    datei = tmp_path / "berichte" / "okm bericht.html"
    oeffner = "open" if ziel is Ziel.ZSH else "xdg-open"
    schritte = [
        # Textparameter lassen < & nicht zu – Pfade schon; der Fortschrittstext landet im Protokoll
        ("existiert_pruefen", {"pfad": f"{tmp_path}/<b>Tom & Jerry</b>"}),
        ("bericht_html", {"datei": str(datei), "titel": "Prüfung Empfang", "oeffnen": True}),
    ]
    r = lauf(registry, shell, ziel, tmp_path, schritte, attrappen={oeffner: aufzeichnen(tmp_path, oeffner)})
    assert r.returncode == 0, r.stdout + r.stderr
    html = datei.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "<title>Prüfung Empfang</title>" in html
    assert "&lt;b&gt;Tom &amp; Jerry&lt;/b&gt;?" in html
    assert "<b>" not in html
    assert re.search(r"<p>Rechner: .+ · Benutzer: .+ · Erstellt: \d\d\.\d\d\.\d{4} \d\d:\d\d</p>", html)
    assert protokoll(tmp_path) == f"{oeffner} {datei}\n"


def test_bericht_html_windows(registry: Registry) -> None:
    schritt = ("bericht_html", {"datei": "C:\\Berichte\\b.html", "titel": "Test"})
    ps = erzeuge(registry, Ziel.POWERSHELL, [schritt]).text
    assert "[System.Net.WebUtility]::HtmlEncode($okmProtokoll)" in ps
    assert "FileShare]::ReadWrite" in ps  # Transcript ist noch geöffnet
    cmd = erzeuge(registry, Ziel.CMD, [schritt]).text
    assert "Get-Content -LiteralPath $env:OKM_LOG" in cmd and "HtmlEncode($l)" in cmd


# --- Windows-Reparatur: Wiederherstellungspunkt, chkdsk, KB -------------------------------------------


def test_wiederherstellungspunkt(registry: Registry) -> None:
    schritt = ("wiederherstellungspunkt", {"beschreibung": "Vor Treiber-Update", "aktivieren": True})
    ps = erzeuge(registry, Ziel.POWERSHELL, [schritt]).text
    assert "Checkpoint-Computer -Description 'Vor Treiber-Update' -RestorePointType MODIFY_SETTINGS" in ps
    assert ps.index("Enable-ComputerRestore") < ps.index("Checkpoint-Computer")
    assert "$script:OkmS1_erstellt = $okmPunkte.Count -gt $okmVorher" in ps
    # Simulation legt nichts an
    sim = erzeuge(registry, Ziel.POWERSHELL, [schritt], dry_run=True).text
    assert "Checkpoint-Computer" not in sim and "Enable-ComputerRestore" not in sim
    cmd = erzeuge(registry, Ziel.CMD, [schritt]).text
    assert "Checkpoint-Computer -Description $env:OKM_BESCHREIBUNG.Trim([char]34)" in cmd


@pytest.mark.parametrize(
    ("ziel", "befehl"), [(Ziel.POWERSHELL, "fsutil.exe dirty set 'D:'"), (Ziel.CMD, 'fsutil dirty set "D:"')]
)
def test_chkdsk_planen(registry: Registry, ziel: Ziel, befehl: str) -> None:
    text = erzeuge(registry, ziel, [("chkdsk_planen", {"laufwerk": "d"})]).text
    assert befehl in text
    assert (
        "dirty set" not in erzeuge(registry, ziel, [("chkdsk_planen", {"laufwerk": "d"})], dry_run=True).text
    )


def test_kb_deinstallieren(registry: Registry) -> None:
    ps = erzeuge(registry, Ziel.POWERSHELL, [("kb_deinstallieren", {"kb": "kb5034441"})]).text
    assert "$okmKb = 'KB' + '5034441'" in ps
    assert "('/uninstall /kb:' + '5034441' + ' /quiet /norestart')" in ps
    assert "-eq 2359303" in ps  # „nicht installiert“ ist kein Fehler
    cmd = erzeuge(registry, Ziel.CMD, [("kb_deinstallieren", {"kb": "KB5034441"})]).text
    assert 'for %%k in ("5034441") do wusa /uninstall /kb:%%~k /quiet /norestart' in cmd
    assert "Update KB5034441 wird deinstalliert" in cmd
