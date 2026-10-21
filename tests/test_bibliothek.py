"""Phase 3: Bibliothek, Bewertungen, Erneut öffnen, Rollen und Rezept-Freigabe."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.baukasten import BaukastenFormular, neue_uid
from app.bibliothek import tags_lesen, wiederherstellen
from app.config import Einstellungen
from app.db import Datenbank, GespeichertesScript
from app.main import create_app
from app.registry import Registry, lade_registry
from app.service import Benutzer, generiere
from app.validation import ValidierungsFehler

FORM = {"HX-Request": "true", "Content-Type": "application/x-www-form-urlencoded"}


def einst(name: str, admin: bool = False) -> Einstellungen:
    return Einstellungen(AUTH_DISABLED=True, DEV_BENUTZER=name, DEV_ADMIN=admin, APP_SECRET_KEY="x" * 32)


@pytest.fixture
def reg() -> Registry:
    return lade_registry()


@pytest.fixture
def db(tmp_path: Path) -> Datenbank:
    return Datenbank(f"sqlite:///{tmp_path}/bib.db")


def als(reg: Registry, db: Datenbank, name: str, admin: bool = False) -> TestClient:
    return TestClient(create_app(einst(name, admin), reg, db))


def post(c: TestClient, url: str, daten: list[tuple[str, str]] | None = None):
    return c.post(url, content=urlencode(daten or []), headers=FORM)


def erzeuge_rezept(c: TestClient, rezept: str, ziel: str, felder: dict[str, str]) -> int:
    daten = {"ziel": ziel, **{(k if k == "rot_bestaetigt" else f"f.{k}"): v for k, v in felder.items()}}
    r = c.post(f"/rezepte/{rezept}/erzeugen", data=daten, headers={"HX-Request": "true"})
    assert "SHA-256" in r.text, r.text
    return int(re.search(r"/skripte/(\d+)/download", r.text).group(1))


def speichern(c: TestClient, sid: int, titel: str, tags: str = "", beschreibung: str = ""):
    return post(
        c, f"/skripte/{sid}/bibliothek", [("titel", titel), ("beschreibung", beschreibung), ("tags", tags)]
    )


# --- Tags ----------------------------------------------------------------------


def test_tags_lesen() -> None:
    assert tags_lesen(" Drucker, netzwerk  drucker ,test-1") == ["drucker", "netzwerk", "test-1"]
    assert tags_lesen("") == []
    with pytest.raises(ValidierungsFehler):
        tags_lesen("a;b")
    with pytest.raises(ValidierungsFehler):
        tags_lesen(" ".join(f"t{i}" for i in range(11)))


# --- Speichern, Sichtbarkeit, Suche --------------------------------------------


def test_speichern_und_sichtbarkeit(reg: Registry, db: Datenbank) -> None:
    anna, bernd = als(reg, db, "anna"), als(reg, db, "bernd")
    sid = erzeuge_rezept(
        anna, "drucker_einrichten", "bash", {"druckername": "Empfang", "drucker_ip": "10.0.0.5"}
    )
    # Nach dem Erzeugen wird das Speichern angeboten
    assert "In Bibliothek speichern" in anna.get(f"/skripte/{sid}").text

    # Privat: nur Anna sieht es
    assert bernd.get(f"/skripte/{sid}").status_code == 404
    assert bernd.get(f"/skripte/{sid}/download").status_code == 404
    assert "Drucker einrichten" in anna.get("/bibliothek?meine=true").text
    assert "Drucker einrichten" not in anna.get("/bibliothek").text

    # Nur der Ersteller darf speichern
    assert speichern(bernd, sid, "Fremd").status_code == 404
    r = speichern(anna, sid, "Drucker Empfang – „EG“", "drucker, empfang", "Für den Empfang im EG.")
    assert "In der Bibliothek gespeichert" in r.text

    # Jetzt für alle sichtbar und herunterladbar
    liste = bernd.get("/bibliothek").text
    assert "Drucker Empfang – „EG“" in liste and "#empfang" in liste
    assert bernd.get(f"/skripte/{sid}/download").status_code == 200
    # Bernd darf es nicht entfernen, Anna schon
    assert post(bernd, f"/skripte/{sid}/entfernen").status_code == 404
    assert post(anna, f"/skripte/{sid}/entfernen").status_code == 204
    assert "Drucker Empfang" not in bernd.get("/bibliothek").text


def test_speichern_prueft_eingaben(reg: Registry, db: Datenbank) -> None:
    c = als(reg, db, "anna")
    sid = erzeuge_rezept(c, "diagnosepaket_support", "zsh", {})
    r = speichern(c, sid, "", "a;b")
    assert "Bitte noch korrigieren" in r.text and "Titel" in r.text and "Tag" in r.text
    r = speichern(c, sid, "Zeile\nUmbruch")
    assert "Bitte noch korrigieren" in r.text


def test_suche_und_filter(reg: Registry, db: Datenbank) -> None:
    c = als(reg, db, "anna")
    a = erzeuge_rezept(c, "drucker_einrichten", "bash", {"druckername": "Empfang", "drucker_ip": "10.0.0.5"})
    b = erzeuge_rezept(c, "diagnosepaket_support", "powershell", {})
    speichern(c, a, "Drucker Empfang", "drucker")
    speichern(c, b, "Diagnose 100% komplett", "support")

    def treffer(query: str) -> str:
        return c.get(
            f"/bibliothek?{query}", headers={"HX-Request": "true", "HX-Target": "bibliotheksliste"}
        ).text

    assert "Drucker Empfang" in treffer("q=empfang") and "Diagnose" not in treffer("q=empfang")
    assert "Diagnose" in treffer("ziel=powershell") and "Drucker Empfang" not in treffer("ziel=powershell")
    assert "Drucker Empfang" in treffer("tag=drucker") and "Diagnose" not in treffer("tag=drucker")
    assert "Diagnose" in treffer("q=support")  # Suche auch in Tags
    # SQL-Platzhalter werden wörtlich gesucht
    assert "Drucker Empfang" not in treffer("q=%25")
    assert "Diagnose" in treffer("q=100%25")
    assert "<html" not in treffer("q=x")


# --- Hat funktioniert ✓ -----------------------------------------------------------


def test_funktioniert_eine_stimme_pro_benutzer(reg: Registry, db: Datenbank) -> None:
    anna, bernd = als(reg, db, "anna"), als(reg, db, "bernd")
    sid = erzeuge_rezept(anna, "diagnosepaket_support", "bash", {})
    speichern(anna, sid, "Diagnose")
    assert "Hat funktioniert (1)" in post(anna, f"/skripte/{sid}/funktioniert").text
    assert "Hat funktioniert (2)" in post(bernd, f"/skripte/{sid}/funktioniert").text
    # Erneuter Klick nimmt die Stimme zurück
    r = post(bernd, f"/skripte/{sid}/funktioniert")
    assert "Hat funktioniert (1)" in r.text and 'aria-pressed="false"' in r.text
    assert "✓ 1 (auch von dir)" in anna.get("/bibliothek").text


# --- Erneut öffnen (aus der IR) --------------------------------------------------


def test_erneut_oeffnen_vorbelegt(reg: Registry, db: Datenbank) -> None:
    c = als(reg, db, "anna")
    sid = erzeuge_rezept(
        c, "netzwerkproblem_diagnostizieren", "zsh", {"ziel": "server01.okm.local", "port": "8443"}
    )
    seite = c.get(f"/baukasten?aus={sid}").text
    assert "Gespeichertes Script geöffnet" in seite
    assert 'value="zsh" data-anzeige="macOS (zsh)"\n          checked' in seite or re.search(
        r'value="zsh"[^>]*checked', seite
    )
    assert seite.count('name="schritt"') == 4
    assert 'value="server01.okm.local"' in seite and 'value="8443"' in seite
    # Fremde private Scripte lassen sich nicht öffnen
    assert als(reg, db, "bernd").get(f"/baukasten?aus={sid}").status_code == 404


def test_erneut_oeffnen_ergibt_gleiche_schritte(reg: Registry, db: Datenbank) -> None:
    c = als(reg, db, "anna")
    sid = erzeuge_rezept(c, "speicherplatz_freigeben", "cmd", {"tage": "30", "rot_bestaetigt": "true"})
    with db.neue_sitzung() as s:
        eintrag = s.get(GespeichertesScript, sid)
        w = wiederherstellen(reg, eintrag)
        original = eintrag.inhalt
    formular = BaukastenFormular(
        ziel=w.ziel,
        titel=w.titel,
        beschreibung=w.beschreibung,
        dry_run=w.dry_run,
        rot_bestaetigt=True,
        uids=[neue_uid() for _ in w.schritte],
        bloecke=[b for b, _ in w.schritte],
        werte=[werte for _, werte in w.schritte],
    )
    _, neu = generiere(reg, formular.als_request(), Benutzer("anna", "anna", False))

    def ohne_kopf(daten: bytes) -> str:
        return "\n".join(z for z in daten.decode().splitlines() if "Erstellt am" not in z)

    assert w.hinweise == []
    assert ohne_kopf(neu.inhalt) == ohne_kopf(original)


def test_erneut_oeffnen_meldet_aenderungen(reg: Registry, db: Datenbank) -> None:
    c = als(reg, db, "anna")
    sid = erzeuge_rezept(
        c, "drucker_einrichten", "bash", {"druckername": "Empfang", "drucker_ip": "10.0.0.5"}
    )
    # Bausteine haben sich seit dem Speichern geändert
    reg.bloecke["ping"] = reg.bloecke["ping"].model_copy(update={"version": 2})
    del reg.bloecke["drucker_ip"]
    seite = c.get(f"/baukasten?aus={sid}").text
    assert "„Ping auf Ziel“ wurde seit dem Speichern geändert (Version 1 → 2)" in seite
    assert "Den Baustein „drucker_ip“ gibt es nicht mehr" in seite
    assert seite.count('name="schritt"') == 1
    detail = c.get(f"/skripte/{sid}").text
    assert "2 (geändert)" in detail and "entfernt" in detail


# --- Rollen & Rezept-Freigabe ----------------------------------------------------


def _vorschlag(c: TestClient, name: str = "Infos zeigen") -> None:
    uid = re.search(
        r'value="([a-f0-9]{8}):systeminfo"', c.get("/baukasten/schritt?block=systeminfo&ziel=bash").text
    )[1]
    r = post(
        c,
        "/baukasten/als-rezept",
        [
            ("ziel", "bash"),
            ("schritt", f"{uid}:systeminfo"),
            ("rezept_name", name),
            ("rezept_kategorie", "System"),
            ("rezept_beschreibung", "Zeigt Infos."),
        ],
    )
    assert "eingereicht" in r.text or "gespeichert" in r.text


def test_verwaltung_nur_fuer_admins(reg: Registry, db: Datenbank) -> None:
    nutzer = als(reg, db, "anna")
    assert nutzer.get("/verwaltung").status_code == 403
    assert post(nutzer, "/verwaltung/rezepte/1/freigeben").status_code == 403
    assert 'href="/verwaltung"' not in nutzer.get("/").text
    assert 'href="/verwaltung"' in als(reg, db, "chef", admin=True).get("/").text


def test_vorschlag_freigeben_und_loeschen(reg: Registry, db: Datenbank) -> None:
    anna, chef = als(reg, db, "anna"), als(reg, db, "chef", admin=True)
    _vorschlag(anna)
    seite = chef.get("/verwaltung").text
    assert "Rezept-Vorschläge (1)" in seite and "Infos zeigen" in seite and "von anna" in seite
    assert "Infos zeigen" not in anna.get("/rezepte?ziel=bash").text

    r = post(chef, "/verwaltung/rezepte/1/freigeben")
    assert r.status_code == 204
    assert "Infos zeigen" in anna.get("/rezepte?ziel=bash").text
    assert "Rezept-Vorschläge (0)" in chef.get("/verwaltung").text
    assert chef.get("/verwaltung/rezepte/1/yaml").text.startswith("# Exportiert")

    assert post(chef, "/verwaltung/rezepte/1/loeschen").status_code == 204
    assert "Infos zeigen" not in anna.get("/rezepte?ziel=bash").text
    assert chef.get("/verwaltung/rezepte/1/yaml").status_code == 404


def test_vorschlag_ablehnen(reg: Registry, db: Datenbank) -> None:
    anna, chef = als(reg, db, "anna"), als(reg, db, "chef", admin=True)
    _vorschlag(anna)
    assert post(chef, "/verwaltung/rezepte/1/loeschen").status_code == 204
    assert "Rezept-Vorschläge (0)" in chef.get("/verwaltung").text


def test_ungueltiger_vorschlag_kann_nicht_freigegeben_werden(reg: Registry, db: Datenbank) -> None:
    anna, chef = als(reg, db, "anna"), als(reg, db, "chef", admin=True)
    _vorschlag(anna)
    del reg.bloecke["systeminfo"]  # Baustein wurde inzwischen entfernt
    seite = chef.get("/verwaltung").text
    assert "Kann so nicht freigegeben werden" in seite
    assert "/verwaltung/rezepte/1/freigeben" not in seite
    r = post(chef, "/verwaltung/rezepte/1/freigeben")
    assert "Bitte noch korrigieren" in r.text and "unbekannter Block" in r.text
