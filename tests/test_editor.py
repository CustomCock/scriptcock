"""Fehlerbehebung Runde 1, Punkt 9: bearbeitbarer Editor – Export-Markierung, Syntax-Prüfung,
Speichern/Erneut öffnen des bearbeiteten Textes."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import syntaxpruefung
from app.config import Einstellungen
from app.db import Datenbank, GespeichertesScript
from app.escaping import Ziel
from app.export import MANUELL_ZEILE, exportiere
from app.main import create_app
from app.registry import Registry
from tests.conftest import erzeuge
from tests.test_bibliothek import erzeuge_rezept, post

API = {"X-Okm-Request": "1"}


@pytest.fixture
def db(tmp_path: Path) -> Datenbank:
    return Datenbank(f"sqlite:///{tmp_path}/editor.db")


@pytest.fixture
def client(registry: Registry, db: Datenbank) -> TestClient:
    einst = Einstellungen(AUTH_DISABLED=True, DEV_BENUTZER="anna", APP_SECRET_KEY="x" * 32)
    return TestClient(create_app(einst, registry, db))


# --- Export-Markierung „Manuell bearbeitet“ ------------------------------------------------


@pytest.mark.parametrize("ziel", list(Ziel))
def test_manuell_markierung_im_kopf(registry: Registry, ziel: Ziel) -> None:
    text = erzeuge(registry, ziel, [("ping", {"ziel": "server01"})]).text
    zeilen = exportiere(text, ziel, manuell_bearbeitet=True).decode("utf-8-sig").splitlines()
    rechte = next(i for i, z in enumerate(zeilen) if "Benötigte Rechte:" in z)
    praefix = "rem " if ziel is Ziel.CMD else "# "
    assert zeilen[rechte + 1] == praefix + MANUELL_ZEILE
    assert MANUELL_ZEILE == "Manuell bearbeitet: ja (nicht vom Baukasten geprüft)"
    # idempotent: zweimal exportieren ergibt dieselben Bytes
    einmal = exportiere(text, ziel, manuell_bearbeitet=True)
    assert exportiere(einmal.decode("utf-8-sig"), ziel, manuell_bearbeitet=True) == einmal
    # ohne Flag unverändert
    assert exportiere(text, ziel) == exportiere(text, ziel, manuell_bearbeitet=False)
    assert MANUELL_ZEILE not in exportiere(text, ziel).decode("utf-8-sig")


@pytest.mark.parametrize(
    ("ziel", "text", "erwartet"),
    [
        (
            Ziel.BASH,
            "#!/usr/bin/env bash\necho hi\n",
            ["#!/usr/bin/env bash", "# " + MANUELL_ZEILE, "echo hi"],
        ),
        (
            Ziel.CMD,
            "@echo off\necho hi\n",
            ["@echo off", "chcp 65001 >nul", "rem " + MANUELL_ZEILE, "echo hi"],
        ),
        (Ziel.POWERSHELL, "Write-Host 'x'\n", ["# " + MANUELL_ZEILE, "Write-Host 'x'"]),
    ],
)
def test_manuell_markierung_ohne_kopf(ziel: Ziel, text: str, erwartet: list[str]) -> None:
    """Hat jemand den Kopf gelöscht, kommt die Zeile direkt nach Shebang/@echo off/chcp."""
    assert exportiere(text, ziel, manuell_bearbeitet=True).decode("utf-8-sig").splitlines() == erwartet


def test_export_endpunkt_mit_markierung(client: TestClient) -> None:
    r = client.post(
        "/api/script/export",
        json={"text": "#!/bin/zsh\necho ok\n", "ziel": "zsh", "manuell_bearbeitet": True},
        headers=API,
    )
    assert r.status_code == 200
    assert r.content == b"#!/bin/zsh\n# " + MANUELL_ZEILE.encode() + b"\necho ok\n"
    assert r.headers["X-Script-SHA256"] == hashlib.sha256(r.content).hexdigest()


# --- Syntax prüfen -------------------------------------------------------------------------


def _pruefen(client: TestClient, text: str, ziel: str) -> dict:
    r = client.post("/api/script/pruefen", json={"text": text, "ziel": ziel}, headers=API)
    assert r.status_code == 200, r.text
    return r.json()


def test_pruefen_braucht_csrf_header(client: TestClient) -> None:
    r = client.post("/api/script/pruefen", json={"text": "echo", "ziel": "bash"})
    assert r.status_code == 403


def test_pruefen_cmd_regeln_mit_zeile(client: TestClient) -> None:
    text = "@echo off\nsetlocal EnableExtensions DisableDelayedExpansion\necho hi\nsetlocal EnableDelayedExpansion\n"
    erg = _pruefen(client, text, "cmd")
    assert not erg["ok"]
    # chcp wird beim Export ergänzt → Zeile 5 in der Datei, im Editor Zeile 4
    assert [(b["zeile"], b["werkzeug"]) for b in erg["befunde"]] == [(4, "CMD-Regeln")]
    assert "EnableDelayedExpansion" in erg["befunde"][0]["meldung"]
    assert any("keinen echten Parser" in h for h in erg["hinweise"])


def test_pruefen_bash_findet_fehler_mit_zeile(client: TestClient) -> None:
    if not syntaxpruefung.shutil.which("bash"):
        pytest.skip("bash fehlt")
    erg = _pruefen(client, "#!/usr/bin/env bash\necho a\nif true; then\necho b\n", "bash")
    assert not erg["ok"]
    assert "bash -n" in erg["geprueft"]
    assert any(b["werkzeug"] == "bash -n" and b["zeile"] == 5 for b in erg["befunde"]), erg


def test_pruefen_generiertes_script_ist_ok(client: TestClient, registry: Registry) -> None:
    for ziel in (Ziel.BASH, Ziel.ZSH):
        werkzeuge = ["bash", "shellcheck"] if ziel is Ziel.BASH else ["zsh"]
        if not all(syntaxpruefung.shutil.which(w) for w in werkzeuge):
            pytest.skip("Prüfwerkzeuge fehlen")
        erg = _pruefen(client, erzeuge(registry, ziel, [("ping", {"ziel": "server01"})]).text, ziel.value)
        assert erg["ok"], erg
        assert erg["befunde"] == []


def test_pruefen_meldet_fehlendes_werkzeug_ehrlich(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(syntaxpruefung.shutil, "which", lambda name: None)
    erg = _pruefen(client, "Write-Host 'x'\n", "powershell")
    assert erg["ok"] is False  # nichts geprüft ist nicht „in Ordnung“
    assert erg["geprueft"] == []
    assert any("nicht installiert" in h for h in erg["hinweise"])


def test_pruefen_fuehrt_nichts_aus(client: TestClient, tmp_path: Path) -> None:
    if not syntaxpruefung.shutil.which("bash"):
        pytest.skip("bash fehlt")
    marke = tmp_path / "ausgefuehrt"
    _pruefen(client, f"#!/usr/bin/env bash\ntouch '{marke}'\n", "bash")
    assert not marke.exists()


def test_pruefen_textlaenge_begrenzt(client: TestClient) -> None:
    r = client.post("/api/script/pruefen", json={"text": "x" * 600_000, "ziel": "bash"}, headers=API)
    assert r.status_code == 422


# --- Bibliothek: bearbeiteten Text speichern und wieder öffnen -----------------------------


BEARBEITET = "# eigene Ergänzung\n"


def _bearbeitet_speichern(client: TestClient, ziel: str = "bash") -> tuple[int, str]:
    sid = erzeuge_rezept(
        client, "drucker_einrichten", ziel, {"druckername": "Empfang", "drucker_ip": "10.0.0.5"}
    )
    original = client.get(f"/skripte/{sid}/download").content.decode("utf-8-sig").replace("\r\n", "\n")
    text = original + BEARBEITET
    r = post(client, f"/skripte/{sid}/bibliothek", [("titel", "Bearbeitet"), ("editor_text", text)])
    assert r.status_code == 200, r.text
    return sid, text


def test_bibliothek_speichert_editor_text(client: TestClient, db: Datenbank) -> None:
    sid, text = _bearbeitet_speichern(client)
    with db.neue_sitzung() as s:
        e = s.get(GespeichertesScript, sid)
        assert e is not None
        assert e.manuell_bearbeitet is True
        assert e.editor_text == text
        assert e.inhalt == exportiere(text, Ziel.BASH, manuell_bearbeitet=True)
        assert e.sha256 == hashlib.sha256(e.inhalt).hexdigest()
        assert e.ir_json  # IR bleibt erhalten
    download = client.get(f"/skripte/{sid}/download").content.decode()
    assert MANUELL_ZEILE in download and BEARBEITET in download
    seite = client.get(f"/skripte/{sid}").text
    assert "Manuell bearbeitet" in seite


def test_bibliothek_ohne_aenderung_bleibt_generiert(client: TestClient, db: Datenbank) -> None:
    sid = erzeuge_rezept(
        client, "drucker_einrichten", "bash", {"druckername": "Empfang", "drucker_ip": "10.0.0.5"}
    )
    vorher = client.get(f"/skripte/{sid}/download").content
    post(client, f"/skripte/{sid}/bibliothek", [("titel", "Normal"), ("editor_text", "")])
    with db.neue_sitzung() as s:
        e = s.get(GespeichertesScript, sid)
        assert e is not None and e.manuell_bearbeitet is False and e.editor_text is None
        assert e.inhalt == vorher


def test_bibliothek_editor_text_steuerzeichen_abgelehnt(client: TestClient) -> None:
    sid = erzeuge_rezept(
        client, "drucker_einrichten", "bash", {"druckername": "Empfang", "drucker_ip": "10.0.0.5"}
    )
    r = post(client, f"/skripte/{sid}/bibliothek", [("titel", "X"), ("editor_text", "echo \x1b[31m\n")])
    assert "Steuerzeichen" in r.text or "nicht erlaubt" in r.text


@pytest.mark.parametrize("modus", ["baukasten", "blockly"])
def test_erneut_oeffnen_stellt_editor_text_her(client: TestClient, modus: str) -> None:
    sid, text = _bearbeitet_speichern(client)
    seite = client.get(f"/{modus}?aus={sid}").text
    m = re.search(r'<script type="application/json" id="editor-vorbelegung">(.*?)</script>', seite, re.S)
    assert m, "Editor-Vorbelegung fehlt"
    daten = json.loads(m.group(1))
    assert daten == {"text": text, "manuell": True}


def test_migration_ergaenzt_spalten(tmp_path: Path) -> None:
    pfad = tmp_path / "alt.db"
    Datenbank(f"sqlite:///{pfad}")
    with sqlite3.connect(pfad) as con:  # Zustand vor Punkt 9 nachstellen
        con.execute("ALTER TABLE skripte DROP COLUMN editor_text")
        con.execute("ALTER TABLE skripte DROP COLUMN manuell_bearbeitet")
    Datenbank(f"sqlite:///{pfad}")
    with sqlite3.connect(pfad) as con:
        spalten = {z[1] for z in con.execute("PRAGMA table_info(skripte)")}
    assert {"editor_text", "manuell_bearbeitet"} <= spalten
