from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Einstellungen
from app.db import Datenbank
from app.main import create_app

HX = {"HX-Request": "true"}


def einst(**kw) -> Einstellungen:
    basis = {"AUTH_DISABLED": True, "DEV_BENUTZER": "tester", "DEV_ADMIN": False, "APP_SECRET_KEY": "x" * 32}
    return Einstellungen(**{**basis, **kw})


@pytest.fixture
def client(registry, tmp_path: Path) -> TestClient:
    return TestClient(create_app(einst(), registry, Datenbank(f"sqlite:///{tmp_path}/t.db")))


def test_startseite_mit_warnbanner(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "AUTH_DISABLED=true" in r.text
    for text in ["Windows PowerShell", "Windows CMD", "Linux", "macOS"]:
        assert text in r.text
    assert "Content-Security-Policy" in r.headers


def test_rezeptliste_und_suche(client: TestClient) -> None:
    r = client.get("/rezepte?ziel=cmd")
    assert "Windows Update reparieren" in r.text
    assert "Drucker einrichten" not in r.text  # für CMD nicht verfügbar
    r = client.get("/rezepte?ziel=bash&q=drucker", headers={**HX, "HX-Target": "rezeptliste"})
    assert "Drucker einrichten" in r.text and "<html" not in r.text
    assert "Windows Update" not in client.get("/rezepte?ziel=bash").text
    assert client.get("/rezepte?ziel=amiga", follow_redirects=False).status_code == 307


def test_formular_zeigt_nur_relevante_felder(client: TestClient) -> None:
    r = client.get("/rezepte/software_installieren?ziel=powershell")
    assert 'name="paket"' in r.text and 'name="paketmanager"' not in r.text
    r = client.get("/rezepte/software_installieren?ziel=bash")
    assert 'name="paketmanager"' in r.text
    r = client.get("/rezepte/netzlaufwerk_verbinden?ziel=zsh")
    assert 'name="laufwerk"' not in r.text


def test_live_validierung(client: TestClient) -> None:
    url = "/rezepte/drucker_einrichten/feld/drucker_ip?ziel=bash"
    assert "keine gültige IP-Adresse" in client.post(url, data={"drucker_ip": "1.2.3.400"}, headers=HX).text
    assert "in Ordnung" in client.post(url, data={"drucker_ip": "10.0.0.5"}, headers=HX).text


def test_csrf_schutz(client: TestClient) -> None:
    r = client.post("/rezepte/drucker_einrichten/erzeugen", data={"ziel": "bash"})
    assert r.status_code == 403


def test_erzeugen_vorschau_und_download(client: TestClient) -> None:
    daten = {"ziel": "bash", "druckername": "Empfang", "drucker_ip": "10.0.0.5", "dry_run": "false"}
    r = client.post("/rezepte/drucker_einrichten/erzeugen", data=daten, headers=HX)
    assert r.status_code == 200
    assert "SHA-256" in r.text and "chmod +x" in r.text
    assert "lpadmin -p &#39;Empfang&#39;" in r.text  # HTML-escaped in der Vorschau
    sha = r.text.split("SHA-256: <code>")[1].split("<")[0]
    d = client.get("/skripte/1/download")
    assert d.status_code == 200
    assert d.headers["x-script-sha256"] == sha
    assert 'filename="drucker-einrichten.sh"' in d.headers["content-disposition"]
    import hashlib

    assert hashlib.sha256(d.content).hexdigest() == sha


def test_validierungsfehler_im_formular(client: TestClient) -> None:
    daten = {"ziel": "bash", "druckername": "Mit Leerzeichen", "drucker_ip": "x;y"}
    r = client.post("/rezepte/drucker_einrichten/erzeugen", data=daten, headers=HX)
    assert "Bitte noch korrigieren" in r.text
    assert 'id="status-druckername" hx-swap-oob' in r.text


def test_rote_rezepte_brauchen_checkbox(client: TestClient) -> None:
    seite = client.get("/rezepte/speicherplatz_freigeben?ziel=bash").text
    assert "Ich weiß, was dieses Script tut" in seite
    daten = {"ziel": "bash", "tage": "7", "rot_bestaetigt": "false"}
    r = client.post("/rezepte/speicherplatz_freigeben/erzeugen", data=daten, headers=HX)
    assert "Ich weiß, was dieses Script tut" in r.text and "Bitte noch korrigieren" in r.text
    daten["rot_bestaetigt"] = "true"
    r = client.post("/rezepte/speicherplatz_freigeben/erzeugen", data=daten, headers=HX)
    assert "SHA-256" in r.text


def test_admin_ohne_zusatzbestaetigung(registry, tmp_path: Path) -> None:
    c = TestClient(create_app(einst(DEV_ADMIN=True), registry, Datenbank(f"sqlite:///{tmp_path}/a.db")))
    assert "Ich weiß, was dieses Script tut" not in c.get("/rezepte/speicherplatz_freigeben?ziel=bash").text
    r = c.post("/rezepte/speicherplatz_freigeben/erzeugen", data={"ziel": "bash", "tage": "7"}, headers=HX)
    assert "SHA-256" in r.text


def test_download_nur_fuer_ersteller(registry, tmp_path: Path) -> None:
    db = Datenbank(f"sqlite:///{tmp_path}/d.db")
    a = TestClient(create_app(einst(DEV_BENUTZER="anna"), registry, db))
    b = TestClient(create_app(einst(DEV_BENUTZER="bernd"), registry, db))
    a.post("/rezepte/diagnosepaket_support/erzeugen", data={"ziel": "zsh"}, headers=HX)
    assert a.get("/skripte/1/download").status_code == 200
    assert b.get("/skripte/1/download").status_code == 404


def test_api(client: TestClient) -> None:
    bloecke = client.get("/api/v1/bloecke").json()["bloecke"]
    assert any(b["id"] == "ping" for b in bloecke)
    nutzlast = {
        "ziel": "powershell",
        "titel": "API-Test",
        "schritte": [{"block_id": "ping", "parameter": {"ziel": "10.0.0.1"}}],
    }
    assert client.post("/api/v1/skripte", json=nutzlast).status_code == 403  # ohne CSRF-Header
    r = client.post("/api/v1/skripte", json=nutzlast, headers={"X-Okm-Request": "1"})
    assert r.status_code == 200 and r.json()["dateiname"] == "api-test.ps1"
    nutzlast["schritte"][0]["parameter"]["ziel"] = "$(id)"
    r = client.post("/api/v1/skripte", json=nutzlast, headers={"X-Okm-Request": "1"})
    assert r.status_code == 422 and r.json()["fehler"][0]["feld"] == "ziel"


def test_ohne_auth_disabled_wird_umgeleitet(registry, tmp_path: Path) -> None:
    e = einst(
        AUTH_DISABLED=False,
        OIDC_ISSUER="https://keycloak.example/realms/okm",
        OIDC_CLIENT_ID="baukasten",
        OIDC_CLIENT_SECRET="geheim",
    )
    c = TestClient(create_app(e, registry, Datenbank(f"sqlite:///{tmp_path}/o.db")))
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"].endswith("/login")
    r = c.get("/api/v1/bloecke")
    assert r.status_code == 401
    assert "AUTH_DISABLED" not in c.get("/healthz").text


def test_unvollstaendige_konfiguration_bricht_ab(registry) -> None:
    with pytest.raises(RuntimeError, match="OIDC_ISSUER"):
        create_app(einst(AUTH_DISABLED=False), registry)
