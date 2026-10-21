"""Phase 4: Blockly-Modus – Seite, JSON-API mit Kontrollknoten, Wiederöffnen, CSP."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Einstellungen
from app.db import Datenbank
from app.main import create_app
from app.registry import Registry, lade_registry

API = {"X-Okm-Request": "1"}


@pytest.fixture
def reg() -> Registry:
    return lade_registry()


def client(reg: Registry, tmp_path: Path, name: str = "anna", db: Datenbank | None = None) -> TestClient:
    e = Einstellungen(AUTH_DISABLED=True, DEV_BENUTZER=name, DEV_ADMIN=False, APP_SECRET_KEY="x" * 32)
    return TestClient(create_app(e, reg, db or Datenbank(f"sqlite:///{tmp_path}/b.db")))


def daten(html: str) -> dict:
    roh = re.search(r'<script type="application/json" id="bl-daten">(.*?)</script>', html, re.S).group(1)
    return json.loads(roh)


ANFRAGE = {
    "ziel": "bash",
    "titel": "Blockly Test",
    "quelle": "blockly",
    "schritte": [
        {"art": "block", "block_id": "meldung", "parameter": {"text": "Start", "pause": "false"}},
        {
            "art": "wiederhole",
            "anzahl": "2",
            "rumpf": [
                {
                    "art": "wenn_fehler",
                    "versuche": [{"art": "block", "block_id": "ping", "parameter": {"ziel": "10.0.0.1"}}],
                    "sonst": [{"art": "block", "block_id": "meldung", "parameter": {"text": "Kein Ping"}}],
                }
            ],
        },
    ],
}


def test_seite_und_katalog(reg: Registry, tmp_path: Path) -> None:
    r = client(reg, tmp_path).get("/blockly?ziel=zsh")
    assert r.status_code == 200
    # Blockly ist vendored (keine CDNs) und braucht Inline-Styles nur auf dieser Seite
    assert "/static/vendor/blockly/blockly_compressed.js" in r.text and "cdn" not in r.text.lower()
    assert "style-src 'self' 'unsafe-inline'" in r.headers["content-security-policy"]
    assert "script-src 'self';" in r.headers["content-security-policy"]
    d = daten(r.text)
    assert d["ziel"] == "zsh" and d["vorbelegung"] is None
    ids = {b["id"] for b in d["katalog"]}
    assert ids == set(reg.bloecke)
    paket = next(b for b in d["katalog"] if b["id"] == "paket_installieren")
    assert "paketmanager" in paket["genutzt"]["bash"] and "paketmanager" not in paket["genutzt"]["powershell"]
    # Andere Seiten behalten die strenge CSP
    assert "unsafe-inline" not in client(reg, tmp_path).get("/").headers["content-security-policy"]


def test_vendor_dateien_vorhanden() -> None:
    basis = Path(__file__).parent.parent / "static" / "vendor" / "blockly"
    assert (basis / "blockly_compressed.js").stat().st_size > 100_000
    assert (basis / "msg" / "de.js").exists() and (basis / "media").is_dir()
    js = (Path(__file__).parent.parent / "static" / "js" / "blockly-modus.js").read_text()
    # Blockly erzeugt keinen Code – nur JSON für die API
    assert "Blockly.JavaScript" not in js and "javascriptGenerator" not in js and "/api/v1/vorschau" in js


def test_vorschau_api_mit_kontrollknoten(reg: Registry, tmp_path: Path) -> None:
    c = client(reg, tmp_path)
    assert c.post("/api/v1/vorschau", json=ANFRAGE).status_code == 403  # CSRF-Header fehlt
    r = c.post("/api/v1/vorschau", json=ANFRAGE, headers=API)
    assert r.status_code == 200, r.text
    text = r.json()["text"]
    assert "for ((okm_durchlauf_1 = 1; okm_durchlauf_1 <= 2; okm_durchlauf_1++)); do" in text
    assert "ping -c 4 '10.0.0.1'" in text and "Kein Ping" in text
    # Vorschau speichert nichts
    assert c.get("/bibliothek?meine=true").text.count("bib-eintrag") == 0


def test_vorschau_api_fehlerpositionen(reg: Registry, tmp_path: Path) -> None:
    anfrage = json.loads(json.dumps(ANFRAGE))
    anfrage["schritte"][1]["rumpf"][0]["versuche"][0]["parameter"]["ziel"] = "$(id)"
    anfrage["schritte"][1]["anzahl"] = "99"
    r = client(reg, tmp_path).post("/api/v1/vorschau", json=anfrage, headers=API)
    assert r.status_code == 422
    fehler = {(f["schritt"], f["feld"]) for f in r.json()["fehler"]}
    # Vorordnung: 0 meldung, 1 wiederhole, 2 wenn_fehler, 3 ping, 4 meldung
    assert (1, "anzahl") in fehler and (3, "ziel") in fehler


def test_rot_in_blockly(reg: Registry, tmp_path: Path) -> None:
    c = client(reg, tmp_path)
    anfrage = {
        **ANFRAGE,
        "schritte": [
            {
                "art": "wenn_fehler",
                "versuche": [
                    {"art": "block", "block_id": "prozess_beenden", "parameter": {"name": "notepad"}}
                ],
            }
        ],
    }
    assert (
        c.post("/api/v1/vorschau", json=anfrage, headers=API).status_code == 200
    )  # Vorschau ohne Bestätigung
    r = c.post("/api/v1/skripte", json=anfrage, headers=API)
    assert r.status_code == 422 and "Ich weiß" in r.text
    assert c.post("/api/v1/skripte", json={**anfrage, "rot_bestaetigt": True}, headers=API).status_code == 200


def test_erzeugen_ergebnis_und_wieder_oeffnen(reg: Registry, tmp_path: Path) -> None:
    db = Datenbank(f"sqlite:///{tmp_path}/b.db")
    c = client(reg, tmp_path, db=db)
    r = c.post("/api/v1/skripte", json=ANFRAGE, headers=API)
    assert r.status_code == 200
    sid = r.json()["id"]
    ergebnis = c.get(f"/skripte/{sid}/ergebnis").text
    assert "blockly-test.sh herunterladen" in ergebnis and "In Bibliothek speichern" in ergebnis
    # Nur der Ersteller sieht den Ergebnis-Bereich
    assert client(reg, tmp_path, "bernd", db).get(f"/skripte/{sid}/ergebnis").status_code == 404

    # Wieder öffnen: Blockly bekommt den Baum mit Werten als Text
    seite = c.get(f"/blockly?aus={sid}").text
    v = daten(seite)["vorbelegung"]
    assert v["titel"] == "Blockly Test"
    assert v["schritte"][1]["art"] == "wiederhole" and v["schritte"][1]["anzahl"] == 2
    innen = v["schritte"][1]["rumpf"][0]
    assert innen["versuche"][0] == {
        "art": "block",
        "block_id": "ping",
        "parameter": {"ziel": "10.0.0.1", "anzahl": "4", "abbrechen": "false"},
    }
    # Der Listen-Modus lehnt Scripte mit Ablauf-Bausteinen ab
    assert c.get(f"/baukasten?aus={sid}").status_code == 422
    # Bibliothek verlinkt den passenden Modus
    c.post(f"/skripte/{sid}/bibliothek", data={"titel": "Blockly Test"}, headers={"HX-Request": "true"})
    assert f"/blockly?aus={sid}" in c.get("/bibliothek").text
    assert "Blockly-Modus" in c.get(f"/skripte/{sid}").text


def test_wieder_oeffnen_meldet_entfernte_bloecke(reg: Registry, tmp_path: Path) -> None:
    c = client(reg, tmp_path)
    sid = c.post("/api/v1/skripte", json=ANFRAGE, headers=API).json()["id"]
    del reg.bloecke["ping"]
    v = daten(c.get(f"/blockly?aus={sid}").text)["vorbelegung"]
    assert any("„ping“ gibt es nicht mehr" in h for h in v["hinweise"])
    assert v["schritte"][1]["rumpf"][0]["versuche"] == []
