"""Generatoren: jeder Block × jedes verfügbare Ziel, Script-Aufbau und Syntax-Checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.escaping import Ziel
from app.generators import GENERATOREN, GeneratedScript
from app.generators.base import SIMULATION_PREFIX, dateiname, unc_zu_smb_url
from app.models.block import Risiko
from app.registry import Registry
from tests import syntax
from tests.conftest import beispielwerte, erzeuge


def alle_kombinationen(registry: Registry) -> list[tuple[str, Ziel]]:
    return [(b.id, z) for b in registry.bloecke.values() for z in b.ziele]


@pytest.fixture(scope="module")
def einzel_scripte(
    registry: Registry, tmp_path_factory: pytest.TempPathFactory
) -> dict[tuple[str, Ziel], Path]:
    """Jeder Block einzeln, normal und als Simulation, für jedes Ziel als Datei."""
    ordner = tmp_path_factory.mktemp("einzeln")
    dateien: dict[tuple[str, Ziel], Path] = {}
    for block_id, ziel in alle_kombinationen(registry):
        block = registry.bloecke[block_id]
        for dry in (False, True):
            s = erzeuge(registry, ziel, [(block_id, beispielwerte(block, ziel))], dry_run=dry)
            endung = ".ps1" if ziel is Ziel.POWERSHELL else s.dateiname[s.dateiname.rfind(".") :]
            pfad = ordner / f"{block_id}-{ziel.value}{'-dry' if dry else ''}{endung}"
            pfad.write_bytes(s.inhalt)
            dateien[(block_id + ("-dry" if dry else ""), ziel)] = pfad
    return dateien


def test_jeder_block_jedes_ziel(registry: Registry, einzel_scripte) -> None:
    for block_id, ziel in alle_kombinationen(registry):
        assert (block_id, ziel) in einzel_scripte
        assert (block_id + "-dry", ziel) in einzel_scripte


def _nach_ziel(einzel_scripte, ziel: Ziel) -> list[Path]:
    return [p for (_, z), p in einzel_scripte.items() if z is ziel]


def test_syntax_bash(einzel_scripte) -> None:
    dateien = _nach_ziel(einzel_scripte, Ziel.BASH)
    for d in dateien:
        syntax.bash_n(d)
    syntax.shellcheck(dateien)


def test_syntax_zsh(einzel_scripte) -> None:
    for d in _nach_ziel(einzel_scripte, Ziel.ZSH):
        syntax.zsh_n(d)


def test_syntax_powershell(einzel_scripte) -> None:
    syntax.pwsh_pruefen(_nach_ziel(einzel_scripte, Ziel.POWERSHELL))


def test_lint_cmd(einzel_scripte) -> None:
    for d in _nach_ziel(einzel_scripte, Ziel.CMD):
        assert syntax.cmd_lint(d.read_bytes()) == [], d.name


# --- Dateiformat ------------------------------------------------------------


@pytest.mark.parametrize(
    ("ziel", "bom", "crlf", "anfang"),
    [
        (Ziel.POWERSHELL, True, True, "#Requires -Version 5.1"),
        (Ziel.CMD, False, True, "@echo off\r\nchcp 65001 >nul"),
        (Ziel.BASH, False, False, "#!/usr/bin/env bash"),
        (Ziel.ZSH, False, False, "#!/bin/zsh"),
    ],
)
def test_dateiformat(registry: Registry, ziel: Ziel, bom: bool, crlf: bool, anfang: str) -> None:
    s = erzeuge(registry, ziel, [("systeminfo", {})], titel="Prüfung äöü")
    assert s.inhalt.startswith(b"\xef\xbb\xbf") is bom
    text = s.inhalt.decode("utf-8-sig")
    assert text.startswith(anfang)
    if crlf:
        assert "\n" not in text.replace("\r\n", "")
    else:
        assert "\r" not in text
    assert s.dateiname == "pruefung-aeoeue" + GENERATOREN[ziel].endung
    import hashlib

    assert s.sha256 == hashlib.sha256(s.inhalt).hexdigest()


@pytest.mark.parametrize("ziel", list(Ziel))
def test_kopfkommentar_und_ablauf(registry: Registry, ziel: Ziel) -> None:
    s = erzeuge(
        registry,
        ziel,
        [("systeminfo", {}), ("ping", {"ziel": "10.0.0.1"}), ("ip_konfiguration", {})],
        titel="Mein Script",
    )
    t = s.text
    for erwartet in [
        "Titel:             Mein Script",
        "Erstellt von:      pytest",
        "Erstellt am:       15.01.2026 09:30:00",
        "Baukasten-Version:",
        "Zielsystem:",
        "1. Systeminfo anzeigen [Risiko: gruen]",
        "Generiert mit dem okm Script-Baukasten",
        "[1/3]",
        "[2/3] Ping auf 10.0.0.1 ^(4x^)" if ziel is Ziel.CMD else "[2/3] Ping auf 10.0.0.1 (4x)",
        "[3/3]",
        "okm-script-",
        "Fertig: ",
        "Protokoll",
    ]:
        assert erwartet in t, (ziel, erwartet)


def test_fehlerbehandlung(registry: Registry) -> None:
    ps = erzeuge(registry, Ziel.POWERSHELL, [("systeminfo", {})]).text
    assert "$ErrorActionPreference = 'Stop'" in ps and "try {" in ps and "} catch {" in ps
    assert "Start-Transcript" in ps
    assert 'if not "%OKM_RC%"=="0" goto :okm_fehler' in erzeuge(registry, Ziel.CMD, [("systeminfo", {})]).text
    assert "set -Eeuo pipefail" in erzeuge(registry, Ziel.BASH, [("systeminfo", {})]).text
    assert "setopt ERR_EXIT PIPE_FAIL" in erzeuge(registry, Ziel.ZSH, [("systeminfo", {})]).text


@pytest.mark.parametrize(
    ("ziel", "pruefung"),
    [
        (Ziel.POWERSHELL, "WindowsBuiltInRole]::Administrator"),
        (Ziel.CMD, "net session"),
        (Ziel.BASH, "id -u"),
        (Ziel.ZSH, "id -u"),
    ],
)
def test_admin_pruefung(registry: Registry, ziel: Ziel, pruefung: str) -> None:
    mit = erzeuge(registry, ziel, [("dienst_neustarten", {"dienst": "Spooler"})]).text
    ohne = erzeuge(registry, ziel, [("ping", {"ziel": "10.0.0.1"})]).text
    assert pruefung in mit
    assert pruefung not in ohne
    # Prüfung steht vor dem ersten Schritt
    assert mit.index(pruefung) < mit.index("[1/1]")


@pytest.mark.parametrize("ziel", list(Ziel))
def test_rote_bestaetigung(registry: Registry, ziel: Ziel) -> None:
    rot = erzeuge(registry, ziel, [("prozess_beenden", {"name": "notepad"})]).text
    assert "JA" in rot and "destruktiv" in rot
    gruen = erzeuge(registry, ziel, [("prozess_suchen", {"name": "notepad"})]).text
    assert "destruktiv" not in gruen
    # In der Simulation wird nicht nachgefragt
    sim = erzeuge(registry, ziel, [("prozess_beenden", {"name": "notepad"})], dry_run=True).text
    assert "destruktiv" not in sim


@pytest.mark.parametrize("ziel", [Ziel.CMD, Ziel.BASH, Ziel.ZSH])
def test_dry_run_echo(registry: Registry, ziel: Ziel) -> None:
    s = erzeuge(registry, ziel, [("prozess_beenden", {"name": "notepad"})], dry_run=True).text
    assert SIMULATION_PREFIX in s
    assert "NUR SIMULATION" in s
    befehl = {"cmd": "taskkill", "bash": "pkill", "zsh": "pkill"}[ziel.value]
    # Jede Zeile mit dem ändernden Befehl ist eine Ausgabe, kein Aufruf
    for zeile in s.splitlines():
        if befehl in zeile and not zeile.lstrip().startswith(("#", "rem")):
            assert zeile.startswith(("printf '%s\\n' '[SIMULATION]", "echo([SIMULATION]")), zeile


def test_dry_run_powershell_whatif(registry: Registry) -> None:
    s = erzeuge(registry, Ziel.POWERSHELL, [("ordner_anlegen", {"pfad": "C:\\temp\\x"})], dry_run=True).text
    assert "-Force -WhatIf" in s
    normal = erzeuge(registry, Ziel.POWERSHELL, [("ordner_anlegen", {"pfad": "C:\\temp\\x"})]).text
    assert "-WhatIf" not in normal
    # Ohne WhatIf-Unterstützung: Ausgabe statt Ausführung
    s = erzeuge(registry, Ziel.POWERSHELL, [("dns_cache_leeren", {})], dry_run=True).text
    assert "Write-Host '[SIMULATION] würde ausführen: Clear-DnsClientCache'" in s


def test_dry_run_gruene_bloecke_laufen_normal(registry: Registry) -> None:
    s = erzeuge(registry, Ziel.BASH, [("systeminfo", {})], dry_run=True).text
    assert "free -h" in s and SIMULATION_PREFIX not in s


def test_nicht_verfuegbarer_block(registry: Registry) -> None:
    from app.generators import GenerierungsFehler, generator_fuer
    from tests.conftest import baue_ir

    ir = baue_ir(registry, Ziel.POWERSHELL, [("setupdiag", {})])
    with pytest.raises(GenerierungsFehler, match="nicht verfügbar"):
        generator_fuer(Ziel.BASH, registry).erzeuge(ir)


def test_unc_smb_url() -> None:
    assert unc_zu_smb_url("\\\\fileserver\\Abteilung IT\\ä") == "smb://fileserver/Abteilung%20IT/%C3%A4"


def test_dateiname() -> None:
    assert dateiname("Drucker einrichten!", ".ps1") == "drucker-einrichten.ps1"
    assert dateiname("", ".sh") == "script.sh"
    assert dateiname("../../etc/passwd", ".sh") == "etc-passwd.sh"


def test_titel_kann_kommentar_nicht_verlassen(registry: Registry) -> None:
    from app.validation import FehlerSammlung

    # ">" (PowerShell-Blockkommentar-Ende "#>") ist im Titel verboten …
    with pytest.raises(FehlerSammlung):
        erzeuge(registry, Ziel.POWERSHELL, [("systeminfo", {})], titel="Ende #> Write-Host x")
    # … und der Kopf nutzt ohnehin nur Zeilenkommentare.
    s = erzeuge(registry, Ziel.POWERSHELL, [("systeminfo", {})], titel="Ende # x")
    zeile = next(z for z in s.text.split("\r\n") if "Titel:" in z)
    assert zeile.startswith("# ")


def test_injection_in_parametern_bleibt_literal(registry: Registry) -> None:
    payload = "/tmp/x'; touch /tmp/PWNED; echo '$(id)`id`"
    s: GeneratedScript = erzeuge(registry, Ziel.BASH, [("ordner_anlegen", {"pfad": payload})])
    assert "mkdir -p -- '/tmp/x'\\''; touch /tmp/PWNED; echo '\\''$(id)`id`'" in s.text


@pytest.mark.parametrize("risiko", list(Risiko))
def test_bibliothek_hat_alle_risikostufen(registry: Registry, risiko: Risiko) -> None:
    assert any(b.risiko is risiko for b in registry.bloecke.values())


def test_cmd_erkennt_negative_exitcodes(registry: Registry) -> None:
    # winget meldet Fehler als negative HRESULTs – "if errorlevel 1" allein reicht nicht.
    erfasst = erzeuge(registry, Ziel.CMD, [("paket_installieren", {"paket": "Mozilla.Firefox"})]).text
    # Der Code wird als Text gesichert und mit "0" verglichen – das erfasst auch negative Werte.
    assert 'set "OKM_RC=%ERRORLEVEL%"' in erfasst and 'if not "%OKM_RC%"=="0" goto :okm_fehler' in erfasst
    interaktiv = erzeuge(registry, Ziel.CMD, [("meldung", {"text": "Hallo"})]).text
    assert 'if not "%OKM_RC%"=="0" goto :okm_fehler' in interaktiv
