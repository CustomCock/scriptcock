"""Lesbare Script-Ausgabe: Encoding, Zeilenenden, Export-Endpunkt, einheitliches Ausgabeformat."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import Datenbank
from app.escaping import Ziel
from app.export import exportiere
from app.main import create_app
from app.registry import Registry, lade_registry
from tests.conftest import erzeuge
from tests.test_ausfuehrung import SH_ZIELE, ausfuehren
from tests.test_web import einst

UMLAUTE = "Büro Größe Löschen"


@pytest.fixture
def client(registry: Registry, tmp_path: Path) -> TestClient:
    return TestClient(create_app(einst(), registry, Datenbank(f"sqlite:///{tmp_path}/t.db")))


# --- Export-Endpunkt: Encoding und Zeilenenden ---------------------------------------


@pytest.mark.parametrize(
    ("ziel", "bom", "crlf"),
    [
        (Ziel.POWERSHELL, True, True),
        (Ziel.CMD, False, True),
        (Ziel.BASH, False, False),
        (Ziel.ZSH, False, False),
    ],
)
@pytest.mark.parametrize("eingabe_ende", ["\n", "\r\n", "\r\n\n"])
def test_export_bytes(ziel: Ziel, bom: bool, crlf: bool, eingabe_ende: str) -> None:
    kopf = "@echo off" if ziel is Ziel.CMD else "# Kopf"
    text = "﻿" + eingabe_ende.join([kopf, f"echo {UMLAUTE}", ""])
    daten = exportiere(text, ziel)
    assert daten.startswith(b"\xef\xbb\xbf") is bom
    assert daten.count(b"\xef\xbb\xbf") == (1 if bom else 0), "BOM doppelt"
    rumpf = daten.removeprefix(b"\xef\xbb\xbf")
    if crlf:
        assert b"\n" not in rumpf.replace(b"\r\n", b""), "einzelnes LF in CRLF-Datei"
    else:
        assert b"\r" not in rumpf, "CR in bash/zsh-Script"
    assert UMLAUTE.encode() in rumpf
    if ziel is Ziel.CMD:
        assert rumpf.split(b"\r\n")[:2] == [b"@echo off", b"chcp 65001 >nul"]


def test_export_cmd_chcp_nur_einmal() -> None:
    daten = exportiere("@echo off\r\nchcp 65001 >nul\r\necho x\r\n", Ziel.CMD)
    assert daten.count(b"chcp 65001") == 1


def test_export_endpunkt(client: TestClient) -> None:
    r = client.post(
        "/api/script/export",
        json={"text": f"Write-Host '{UMLAUTE}'\n", "ziel": "powershell", "dateiname": "Büro Test"},
        headers={"X-Okm-Request": "1"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/octet-stream"
    assert 'filename="buero-test.ps1"' in r.headers["content-disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf") and r.content.endswith(b"\r\n")
    assert r.headers["x-script-sha256"]
    # CSRF-Schutz gilt auch hier
    assert client.post("/api/script/export", json={"text": "x", "ziel": "bash"}).status_code == 403
    # Ungültiges Ziel bzw. riesiger Text werden abgelehnt
    h = {"X-Okm-Request": "1"}
    assert (
        client.post("/api/script/export", json={"text": "x", "ziel": "amiga"}, headers=h).status_code == 422
    )
    gross = {"text": "x" * 2_000_001, "ziel": "bash"}
    assert client.post("/api/script/export", json=gross, headers=h).status_code == 422


@pytest.mark.parametrize("ziel", list(Ziel), ids=[z.value for z in Ziel])
def test_generator_nutzt_dieselben_regeln_wie_export(registry: Registry, ziel: Ziel) -> None:
    s = erzeuge(registry, ziel, [("meldung", {"text": UMLAUTE, "pause": False})])
    assert exportiere(s.text, ziel) == s.inhalt


@pytest.mark.parametrize("ziel", list(Ziel), ids=[z.value for z in Ziel])
def test_keine_ansi_farbcodes(registry: Registry, ziel: Ziel) -> None:
    for block in registry.bloecke.values():
        if block.verfuegbar(ziel):
            for vorlage in (block.ziele, block.pruefung, block.dry_run):
                assert "\x1b" not in vorlage.get(ziel, ""), block.id
    s = erzeuge(registry, ziel, [("meldung", {"text": UMLAUTE, "pause": False})])
    assert b"\x1b" not in s.inhalt


# --- Einheitliches Ausgabeformat -------------------------------------------------------


def _kopf_und_fuss(text: str) -> None:
    assert "==============================================" in text
    assert " okm Script-Baukasten · Büro-Check" in text
    assert " Erstellt: 15.01.2026 09:30 · von pytest" in text
    assert "[1/2] Hinweis für den Benutzer ..." in text
    assert "      OK" in text
    assert "----------------------------------------------" in text
    assert " Fertig: 2 von 2 Schritten erfolgreich." in text
    assert " Protokoll: " in text


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_ausgabeformat_sh(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    s = erzeuge(
        registry,
        ziel,
        [("meldung", {"text": UMLAUTE, "pause": False}), ("meldung", {"text": "zwei", "pause": False})],
        titel="Büro-Check",
    )
    r = ausfuehren(shell, s.inhalt, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    _kopf_und_fuss(r.stdout)
    assert UMLAUTE in r.stdout


def test_ausgabeformat_powershell(registry: Registry, tmp_path: Path) -> None:
    s = erzeuge(
        registry,
        Ziel.POWERSHELL,
        [("meldung", {"text": UMLAUTE, "pause": False}), ("meldung", {"text": "zwei", "pause": False})],
        titel="Büro-Check",
    )
    r = ausfuehren("pwsh", s.inhalt, tmp_path, env={"TEMP": str(tmp_path)})
    assert r.returncode == 0, r.stdout + r.stderr
    _kopf_und_fuss(r.stdout)


def test_ausgabeformat_cmd(registry: Registry) -> None:
    text = erzeuge(
        registry,
        Ziel.CMD,
        [("meldung", {"text": UMLAUTE, "pause": False}), ("meldung", {"text": "zwei", "pause": False})],
        titel="Büro-Check",
    ).text
    assert "echo(==============================================" in text
    assert "echo( okm Script-Baukasten · Büro-Check" in text
    assert "echo([1/2] Hinweis für den Benutzer ..." in text
    assert "echo(      OK" in text
    assert "echo( Fertig: %OKM_OK% von %OKM_GESAMT% Schritten erfolgreich." in text


# --- PowerShell: Ausgaben externer Programme ---------------------------------------------


def test_powershell_externe_ausgabe_in_utf8(tmp_path: Path) -> None:
    """Windows startet PowerShell mit OEM-Codepage (850); Programme wie winget schreiben UTF-8.

    Ohne ``[Console]::OutputEncoding = UTF8`` wird aus „Größe“ „Gr├Â├ƒe“.
    """
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("pwsh ist nicht installiert")
    bloecke = tmp_path / "blocks"
    bloecke.mkdir()
    (bloecke / "nativ.yaml").write_text(
        "id: nativ\nname: Nativ\nkategorie: Test\nbeschreibung: Test\nrisiko: gruen\n"
        "ziele:\n  powershell: |\n    /usr/bin/printf 'Größe Büro\\n'\n",
        encoding="utf-8",
    )
    rezepte = tmp_path / "recipes"
    rezepte.mkdir()
    reg = lade_registry(bloecke, rezepte)
    s = erzeuge(reg, Ziel.POWERSHELL, [("nativ", {})])
    datei = tmp_path / "s.ps1"
    datei.write_bytes(s.inhalt)
    befehl = f"[Console]::OutputEncoding = [System.Text.Encoding]::GetEncoding(850); & '{datei}' -NoPause"
    subprocess.run(
        [pwsh, "-NoProfile", "-Command", befehl],
        capture_output=True,
        env={"TEMP": str(tmp_path), "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        timeout=120,
    )
    log = next(tmp_path.glob("okm-script-*.log")).read_text(encoding="utf-8", errors="replace")
    assert "Größe Büro" in log, log
    assert "├" not in log


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_tipp_bei_fehler(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    s = erzeuge(
        registry,
        ziel,
        [("kopieren", {"art": "datei", "quelle": f"{tmp_path}/gibtsnicht", "ziel": f"{tmp_path}/z"})],
    )
    r = ausfuehren(shell, s.inhalt, tmp_path)
    assert r.returncode != 0
    assert "      FEHLER  Schritt 1/1 (Datei/Ordner kopieren)" in r.stdout
    assert "      Tipp: Gibt es die Quelle, und hast du Schreibrechte im Zielordner?" in r.stdout


def test_vorschau_kopieren_nutzt_export(client: TestClient) -> None:
    r = client.post(
        "/rezepte/diagnosepaket_support/erzeugen", data={"ziel": "powershell"}, headers={"HX-Request": "true"}
    )
    assert 'data-ziel="powershell"' in r.text and "UTF-8 mit BOM" in r.text
