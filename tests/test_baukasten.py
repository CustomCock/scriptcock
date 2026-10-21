"""Freier Baukasten (Listen-Modus): Formular, Vorschau, Erzeugen, Als-Rezept-Speichern."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlencode

import pytest
import yaml
from fastapi.testclient import TestClient

from app.baukasten import FormularFehler, lade_db_rezepte, lies_formular, rezept_aus_formular
from app.config import Einstellungen
from app.db import Datenbank
from app.escaping import Ziel
from app.main import create_app
from app.models.recipe import RezeptDef
from app.registry import Registry, lade_registry
from app.validation import FehlerSammlung

HX = {"HX-Request": "true", "Content-Type": "application/x-www-form-urlencoded"}


def einst(**kw) -> Einstellungen:
    basis = {"AUTH_DISABLED": True, "DEV_BENUTZER": "tester", "DEV_ADMIN": False, "APP_SECRET_KEY": "x" * 32}
    return Einstellungen(**{**basis, **kw})


@pytest.fixture
def reg() -> Registry:
    # Eigene Registry: Tests fügen Rezepte hinzu
    return lade_registry()


def client(reg: Registry, db: Datenbank, admin: bool = False) -> TestClient:
    return TestClient(create_app(einst(DEV_ADMIN=admin), reg, db))


def post(c: TestClient, url: str, daten: list[tuple[str, str]]):
    return c.post(url, content=urlencode(daten), headers=HX)


def schritt(c: TestClient, block: str, ziel: str = "bash") -> str:
    r = c.get(f"/baukasten/schritt?block={block}&ziel={ziel}")
    assert r.status_code == 200
    return re.search(rf'value="([a-f0-9]{{8}}):{block}"', r.text).group(1)


# --- Formular lesen ----------------------------------------------------------------


def test_lies_formular_reihenfolge_und_letzter_wert() -> None:
    f = lies_formular(
        [
            ("ziel", "zsh"),
            ("schritt", "aaaaaaaa:ping"),
            ("p.aaaaaaaa.ziel", "10.0.0.1"),
            ("p.aaaaaaaa.abbrechen", "false"),
            ("p.aaaaaaaa.abbrechen", "true"),
            ("schritt", "bbbbbbbb:systeminfo"),
            ("p.cccccccc.fremd", "ignoriert"),
            ("dry_run", "false"),
            ("dry_run", "true"),
        ]
    )
    assert f.ziel is Ziel.ZSH and f.dry_run
    assert f.bloecke == ["ping", "systeminfo"]
    assert f.werte[0] == {"ziel": "10.0.0.1", "abbrechen": "true"}
    assert f.werte[1] == {}


@pytest.mark.parametrize(
    "daten",
    [
        [("ziel", "amiga")],
        [("ziel", "bash"), ("schritt", "kaputt:ping")],
        [("ziel", "bash"), ("schritt", "aaaaaaaa:ping"), ("schritt", "aaaaaaaa:ping")],
        [("ziel", "bash")] + [("schritt", f"{i:08x}:ping") for i in range(101)],
    ],
)
def test_lies_formular_lehnt_ab(daten) -> None:
    with pytest.raises(FormularFehler):
        lies_formular(daten)


# --- Seiten & Vorschau --------------------------------------------------------------


def test_seite_und_palette(reg: Registry, tmp_path: Path) -> None:
    c = client(reg, Datenbank(f"sqlite:///{tmp_path}/a.db"))
    r = c.get("/baukasten?ziel=zsh")
    assert r.status_code == 200
    assert "Sortable.min.js" in r.text and "cdn" not in r.text.lower()
    # SetupDiag gibt es nur für PowerShell → in der Palette ausgegraut
    zeile = re.search(r'<li class="palette-block([^"]*)" data-block="setupdiag"', r.text)
    assert zeile and "nicht-verfuegbar" in zeile.group(1)
    assert "Unter macOS (zsh) nicht verfügbar" in r.text
    assert "Als Rezept speichern" not in r.text  # nur für Admins


def test_vorschau_live_und_nicht_gespeichert(reg: Registry, tmp_path: Path) -> None:
    db = Datenbank(f"sqlite:///{tmp_path}/a.db")
    c = client(reg, db)
    uid = schritt(c, "ping")
    daten = [("ziel", "bash"), ("titel", "Live"), ("schritt", f"{uid}:ping"), (f"p.{uid}.ziel", "10.0.0.1")]
    r = post(c, "/baukasten/vorschau", daten)
    assert "ping -c 4 &#39;10.0.0.1&#39;" in r.text
    assert (
        "Script erzeugen" in r.text
        and "disabled" not in r.text.split("Script erzeugen")[0].rsplit("<button", 1)[1]
    )
    # Live-Vorschau speichert nichts → Download-ID 1 existiert noch nicht
    assert c.get("/skripte/1/download").status_code == 404


def test_vorschau_ordnet_fehler_feldern_zu(reg: Registry, tmp_path: Path) -> None:
    c = client(reg, Datenbank(f"sqlite:///{tmp_path}/a.db"))
    uid = schritt(c, "ping")
    r = post(
        c, "/baukasten/vorschau", [("ziel", "bash"), ("schritt", f"{uid}:ping"), (f"p.{uid}.ziel", "$(id)")]
    )
    assert "Bitte noch korrigieren" in r.text
    assert "Schritt 1 (Ping auf Ziel)" in r.text
    assert re.search(rf'id="status-{uid}-ziel" hx-swap-oob="innerHTML"><span class="fehlertext">', r.text)
    knopf = r.text.split("Script erzeugen")[0].rsplit("<button", 1)[1]
    assert "disabled" in knopf


def test_zielwechsel_markiert_und_sperrt(reg: Registry, tmp_path: Path) -> None:
    c = client(reg, Datenbank(f"sqlite:///{tmp_path}/a.db"))
    uid = schritt(c, "setupdiag", "powershell")
    uid2 = schritt(c, "ping", "powershell")
    daten = [
        ("ziel", "bash"),
        ("schritt", f"{uid}:setupdiag"),
        ("schritt", f"{uid2}:ping"),
        (f"p.{uid2}.ziel", "10.0.0.1"),
    ]
    liste = post(c, "/baukasten/liste", daten).text
    assert 'class="schritt schritt-gesperrt" id="schritt-' + uid in liste
    assert "Unter Linux (Bash 4+) nicht verfügbar" in liste
    # Werte bleiben beim Umschalten erhalten
    assert 'value="10.0.0.1"' in liste
    r = post(c, "/baukasten/vorschau", daten)
    assert "Download gesperrt" in r.text and "SetupDiag" in r.text
    assert post(c, "/baukasten/erzeugen", daten).text.count("fehlerbox") == 1


def test_versteckte_parameter_bleiben_erhalten(reg: Registry, tmp_path: Path) -> None:
    c = client(reg, Datenbank(f"sqlite:///{tmp_path}/a.db"))
    uid = schritt(c, "paket_installieren", "bash")
    daten = [
        ("ziel", "powershell"),
        ("schritt", f"{uid}:paket_installieren"),
        (f"p.{uid}.paket", "Mozilla.Firefox"),
        (f"p.{uid}.paketmanager", "dnf"),
    ]
    liste = post(c, "/baukasten/liste", daten).text
    # Paketmanager wird unter Windows nicht gebraucht → verstecktes Feld mit Wert
    assert f'<input type="hidden" name="p.{uid}.paketmanager" value="dnf">' in liste
    assert f'id="f-{uid}-paketmanager"' not in liste


def test_rote_bestaetigung_und_erzeugen(reg: Registry, tmp_path: Path) -> None:
    c = client(reg, Datenbank(f"sqlite:///{tmp_path}/a.db"))
    uid = schritt(c, "prozess_beenden")
    daten = [
        ("ziel", "bash"),
        ("titel", "Beenden"),
        ("schritt", f"{uid}:prozess_beenden"),
        (f"p.{uid}.name", "notepad"),
    ]
    vorschau = post(c, "/baukasten/vorschau", daten).text
    assert 'id="bk-bestaetigung" hx-swap-oob="innerHTML">' in vorschau
    assert "Ich weiß, was dieses Script tut" in vorschau
    assert "Ich weiß, was dieses Script tut" in post(c, "/baukasten/erzeugen", daten).text  # Fehler
    r = post(c, "/baukasten/erzeugen", [*daten, ("rot_bestaetigt", "true")])
    assert "beenden.sh herunterladen" in r.text and "SHA-256" in r.text
    d = c.get("/skripte/1/download")
    assert d.status_code == 200 and b"pkill -x -- 'notepad'" in d.content


def test_reihenfolge_bestimmt_script(reg: Registry, tmp_path: Path) -> None:
    c = client(reg, Datenbank(f"sqlite:///{tmp_path}/a.db"))
    a, b = schritt(c, "systeminfo"), schritt(c, "ip_konfiguration")
    vorwaerts = post(
        c,
        "/baukasten/vorschau",
        [("ziel", "bash"), ("schritt", f"{a}:systeminfo"), ("schritt", f"{b}:ip_konfiguration")],
    ).text
    rueckwaerts = post(
        c,
        "/baukasten/vorschau",
        [("ziel", "bash"), ("schritt", f"{b}:ip_konfiguration"), ("schritt", f"{a}:systeminfo")],
    ).text
    assert vorwaerts.index("Systeminfo anzeigen (Risiko") < vorwaerts.index(
        "IP-Konfiguration anzeigen (Risiko"
    )
    assert rueckwaerts.index("IP-Konfiguration anzeigen (Risiko") < rueckwaerts.index(
        "Systeminfo anzeigen (Risiko"
    )


# --- Als Rezept speichern ----------------------------------------------------------


def test_rezept_aus_formular(reg: Registry) -> None:
    f = lies_formular(
        [
            ("ziel", "bash"),
            ("schritt", "aaaaaaaa:ping"),
            ("p.aaaaaaaa.ziel", ""),
            ("p.aaaaaaaa.anzahl", "2"),
            ("schritt", "bbbbbbbb:ordner_anlegen"),
            ("p.bbbbbbbb.pfad", "/tmp/$test"),
        ]
    )
    r = rezept_aus_formular(
        reg, f, name="Test Rezept", kategorie="Test", beschreibung="Ein Test.", autor="admin"
    )
    assert r.id.startswith("eigen_test_rezept_")
    assert [x.id for x in r.felder] == ["s1_ziel"]
    assert r.felder[0].label == "Ping auf Ziel: Ziel (IP-Adresse oder Rechnername)"
    assert r.schritte[0].parameter == {"ziel": "$s1_ziel", "anzahl": 2}
    assert r.schritte[1].parameter == {"pfad": "/tmp/$test"}  # $ mitten im Wert ist kein Feldverweis
    reg.rezept_hinzufuegen(r)
    # Unix-Pfad als fester Wert → nur für Linux/macOS verfügbar
    assert reg.rezept_ziele(r) == [Ziel.BASH, Ziel.ZSH]


def test_rezept_aus_formular_fehler(reg: Registry) -> None:
    f = lies_formular([("ziel", "bash"), ("schritt", "aaaaaaaa:ping"), ("p.aaaaaaaa.ziel", "a;b")])
    with pytest.raises(FehlerSammlung) as e:
        rezept_aus_formular(reg, f, name="", kategorie="x;y", beschreibung="", autor="a")
    meldungen = " ".join(x.meldung for x in e.value.fehler)
    assert "Name" in meldungen and "Kategorie" in meldungen and "Ziel" in meldungen


def test_als_rezept_nur_admin(reg: Registry, tmp_path: Path) -> None:
    c = client(reg, Datenbank(f"sqlite:///{tmp_path}/a.db"))
    r = post(c, "/baukasten/als-rezept", [("ziel", "bash"), ("rezept_name", "x")])
    assert r.status_code == 403


def test_als_rezept_speichern_und_neu_laden(reg: Registry, tmp_path: Path) -> None:
    db = Datenbank(f"sqlite:///{tmp_path}/a.db")
    c = client(reg, db, admin=True)
    assert "Als Rezept speichern" in c.get("/baukasten").text
    uid = schritt(c, "ping")
    r = post(
        c,
        "/baukasten/als-rezept",
        [
            ("ziel", "bash"),
            ("schritt", f"{uid}:ping"),
            (f"p.{uid}.ziel", ""),
            (f"p.{uid}.anzahl", "3"),
            ("rezept_name", "Server anpingen"),
            ("rezept_kategorie", "Netzwerk"),
            ("rezept_beschreibung", "Pingt einen Server dreimal."),
        ],
    )
    assert "gespeichert" in r.text
    rid = re.search(r"/rezepte/(eigen_[a-z0-9_]+)", r.text).group(1)
    assert "Server anpingen" in c.get("/rezepte?ziel=bash").text
    formular = c.get(f"/rezepte/{rid}?ziel=bash").text
    assert 'name="s1_ziel"' in formular

    # YAML-Export ist ein gültiges Rezept
    daten = yaml.safe_load(c.get(f"/rezepte/{rid}/yaml").text)
    RezeptDef.model_validate(daten)

    # Nach einem Neustart (frische Registry, gleiche DB) ist das Rezept wieder da
    neu = lade_registry()
    with db.neue_sitzung() as s:
        assert lade_db_rezepte(neu, s) == 1
    assert rid in neu.rezepte
    c2 = TestClient(create_app(einst(), lade_registry(), db))
    assert "Server anpingen" in c2.get("/rezepte?ziel=bash").text


def test_kaputtes_db_rezept_wird_uebersprungen(reg: Registry, tmp_path: Path) -> None:
    from datetime import datetime

    from app.db import GespeichertesRezept

    db = Datenbank(f"sqlite:///{tmp_path}/a.db")
    with db.neue_sitzung() as s:
        s.add(
            GespeichertesRezept(
                rezept_id="eigen_kaputt",
                name="Kaputt",
                daten_json='{"id": "eigen_kaputt", "name": "K", "kategorie": "K", "beschreibung": "K", '
                '"schritte": [{"block": "gibt_es_nicht"}]}',
                autor="a",
                erstellt_am=datetime.now(),
                freigegeben=True,
            )
        )
        s.commit()
        assert lade_db_rezepte(reg, s) == 0
    assert "eigen_kaputt" not in reg.rezepte
