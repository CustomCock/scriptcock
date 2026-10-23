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
    # Einstieg in die drei Modi + Bibliothek
    for text in ['href="/rezepte"', 'href="/baukasten"', 'href="/blockly"', 'href="/bibliothek"']:
        assert text in r.text
    assert "Content-Security-Policy" in r.headers
    assert 'class="aktiv" aria-current="page"' not in r.text.split("Hauptnavigation")[1].split("</nav>")[0]


def test_betriebssystem_wahl(client: TestClient) -> None:
    r = client.get("/rezepte")
    for text in ["Windows PowerShell", "Windows CMD", "Linux", "macOS"]:
        assert text in r.text
    assert 'href="/rezepte" class="aktiv"' in r.text
    # Unbekanntes Ziel → wieder die Auswahl
    assert "Für welches System?" in client.get("/rezepte?ziel=amiga").text


def test_startseite_zeigt_letzte_scripte(client: TestClient) -> None:
    client.post("/rezepte/diagnosepaket_support/erzeugen", data={"ziel": "zsh"}, headers=HX)
    seite = client.get("/").text
    assert "Diagnosepaket für den Support erstellen" in seite and 'href="/skripte/1"' in seite


def test_rezeptliste_und_suche(client: TestClient) -> None:
    r = client.get("/rezepte?ziel=cmd")
    oben, unten = r.text.split('id="nicht-verfuegbar"')
    assert "Windows Update reparieren" in oben
    assert "Drucker einrichten" in unten and "Drucker einrichten" not in oben  # für CMD nicht verfügbar
    # Suche ohne JavaScript (Server-Filter)
    r = client.get("/rezepte?ziel=bash&q=drucker")
    assert "Drucker einrichten" in r.text and "Windows Update" not in r.text


def test_formular_zeigt_nur_relevante_felder(client: TestClient) -> None:
    r = client.get("/rezepte/software_installieren?ziel=powershell")
    assert 'name="f.paket"' in r.text and 'name="f.paketmanager"' not in r.text
    r = client.get("/rezepte/software_installieren?ziel=bash")
    assert 'name="f.paketmanager"' in r.text
    r = client.get("/rezepte/netzlaufwerk_verbinden?ziel=zsh")
    assert 'name="f.laufwerk"' not in r.text


def test_live_validierung(client: TestClient) -> None:
    url = "/rezepte/drucker_einrichten/feld/drucker_ip?ziel=bash"
    assert "keine gültige IP-Adresse" in client.post(url, data={"f.drucker_ip": "1.2.3.400"}, headers=HX).text
    assert "in Ordnung" in client.post(url, data={"f.drucker_ip": "10.0.0.5"}, headers=HX).text


def test_csrf_schutz(client: TestClient) -> None:
    r = client.post("/rezepte/drucker_einrichten/erzeugen", data={"ziel": "bash"})
    assert r.status_code == 403


def test_erzeugen_vorschau_und_download(client: TestClient) -> None:
    daten = {"ziel": "bash", "f.druckername": "Empfang", "f.drucker_ip": "10.0.0.5", "dry_run": "false"}
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
    daten = {"ziel": "bash", "f.druckername": "Mit Leerzeichen", "f.drucker_ip": "x;y"}
    r = client.post("/rezepte/drucker_einrichten/erzeugen", data=daten, headers=HX)
    assert "Bitte noch korrigieren" in r.text
    assert 'id="status-druckername" hx-swap-oob' in r.text


def test_rote_rezepte_brauchen_checkbox(client: TestClient) -> None:
    seite = client.get("/rezepte/speicherplatz_freigeben?ziel=bash").text
    assert "Ich weiß, was dieses Script tut" in seite
    daten = {"ziel": "bash", "f.tage": "7", "rot_bestaetigt": "false"}
    r = client.post("/rezepte/speicherplatz_freigeben/erzeugen", data=daten, headers=HX)
    assert "Ich weiß, was dieses Script tut" in r.text and "Bitte noch korrigieren" in r.text
    daten["rot_bestaetigt"] = "true"
    r = client.post("/rezepte/speicherplatz_freigeben/erzeugen", data=daten, headers=HX)
    assert "SHA-256" in r.text


def test_admin_ohne_zusatzbestaetigung(registry, tmp_path: Path) -> None:
    c = TestClient(create_app(einst(DEV_ADMIN=True), registry, Datenbank(f"sqlite:///{tmp_path}/a.db")))
    assert "Ich weiß, was dieses Script tut" not in c.get("/rezepte/speicherplatz_freigeben?ziel=bash").text
    r = c.post("/rezepte/speicherplatz_freigeben/erzeugen", data={"ziel": "bash", "f.tage": "7"}, headers=HX)
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


def test_rezeptfeld_namens_ziel_kollidiert_nicht(client: TestClient) -> None:
    # Regression: Das Rezept hat ein Feld "ziel" – genau wie das Zielsystem.
    daten = {"ziel": "zsh", "f.ziel": "server01.okm.local", "f.port": "8443"}
    r = client.post("/rezepte/netzwerkproblem_diagnostizieren/erzeugen", data=daten, headers=HX)
    assert r.status_code == 200 and "SHA-256" in r.text
    assert "server01.okm.local" in r.text and "8443" in r.text


# --- Rezept-Übersicht (Punkt 8) -------------------------------------------------------------


def test_rezeptuebersicht_karten(client: TestClient) -> None:
    import re

    seite = client.get("/rezepte?ziel=zsh").text
    # Gruppiert nach Kategorie mit Zwischenüberschriften
    assert '<h2 class="rezept-gruppe-titel"' in seite and ">Drucker</h2>" in seite
    karte = seite[seite.index('data-rezept="drucker_einrichten"') :].split("</li>")[0]
    assert 'class="kategorie-icon"' in karte  # Icon der Kategorie
    assert "Drucker einrichten" in karte and "rezept-beschreibung" in karte
    # Zielsysteme als Badges, nicht verfügbare ausgegraut
    assert 'class="ziel-badge">Windows' in karte and 'class="ziel-badge">macOS' in karte
    assert 'class="ziel-badge">Linux' in karte
    # Risiko als Farbpunkt mit Text, Schrittzahl, Rechte-Hinweis
    assert "risiko-punkt risiko-gelb" in karte and "ändert etwas" in karte
    assert re.search(r"\d+ Schritte", karte)
    assert "braucht sudo" in karte
    # Nicht verfügbare Rezepte stehen unten, abgeschwächt, mit Hinweis
    unten = seite.index('id="nicht-verfuegbar"')
    assert seite.index('data-rezept="windows_update_reparieren"') > unten
    assert seite.index('data-rezept="drucker_einrichten"') < unten
    gesperrt = seite[seite.index('data-rezept="windows_update_reparieren"') :].split("</li>")[0]
    assert (
        "nicht-verfuegbar"
        in seite[: seite.index('data-rezept="windows_update_reparieren"')].rsplit("<li", 1)[1]
    )
    assert "Nicht für macOS verfügbar" in gesperrt and "href=" not in gesperrt
    # Suchtext enthält Schlagworte (für die clientseitige, umlauttolerante Suche)
    assert 'data-suche="' in karte
    # Kategorie-Chips mit aria-pressed
    assert 'class="chip" data-kategorie="Drucker" aria-pressed="false"' in seite


def test_rezeptuebersicht_zuletzt_benutzt(client: TestClient) -> None:
    assert 'id="zuletzt-benutzt"' not in client.get("/rezepte?ziel=zsh").text
    client.post("/rezepte/diagnosepaket_support/erzeugen", data={"ziel": "zsh"}, headers=HX)
    seite = client.get("/rezepte?ziel=zsh").text
    zuletzt = seite[
        seite.index('id="zuletzt-benutzt"') : seite.index("</section>", seite.index('id="zuletzt-benutzt"'))
    ]
    assert 'data-rezept="diagnosepaket_support"' in zuletzt
