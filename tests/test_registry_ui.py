"""Teil C: .reg-Parser, Registry-API, Panel-Einbindung, Richtlinie im Listen-Modus/Blockly/Bibliothek."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.baukasten import lies_formular, rezept_aus_formular
from app.bibliothek import _katalog_hinweis
from app.config import Einstellungen
from app.db import Datenbank
from app.escaping import Ziel
from app.ir import BlockSchritt, ParamValue
from app.main import create_app
from app.models.block import ParamTyp
from app.regdatei import dekodieren, parsen, schritt
from app.registry import Registry, lade_registry
from tests.test_kontrolle import blk, ir_aus

HX = {"HX-Request": "true"}
EDGE = "edge:msedge:HomepageLocation"


@pytest.fixture(scope="module")
def client() -> TestClient:
    einst = Einstellungen(AUTH_DISABLED=True, APP_SECRET_KEY="x" * 32, DEV_ADMIN=False)
    return TestClient(create_app(einst, lade_registry(), Datenbank("sqlite://")))


# --- .reg-Parser ----------------------------------------------------------------------------------

REG = r"""Windows Registry Editor Version 5.00

; Export vom Referenz-PC
[HKEY_LOCAL_MACHINE\SOFTWARE\OkmTest]
"Text"="C:\\Pfad \"zitiert\""
@="Standard"
"Klein"=dword:00000000
"Gross"=dword:ffffffff
"Bin"=hex:0a,1b,\
  ff
"Exp"=hex(2):25,00,54,00,45,00,4d,00,50,00,25,00,00,00
"Multi"=hex(7):61,00,00,00,c4,00,00,00,00,00
"Q"=hex(b):01,00,00,00,01,00,00,00
"Weg"=-

[HKEY_CURRENT_USER\Software\OkmTest\Leer]

[-HKEY_LOCAL_MACHINE\SOFTWARE\OkmTest\Alt]
"""


def test_reg_alle_typen() -> None:
    erg = parsen(REG)
    assert erg.fehler == []
    s = [schritt(e) for e in erg.eintraege]
    werte = {
        x["parameter"].get("wertname"): x["parameter"] for x in s if x["block_id"] == "registry_wert_setzen"
    }
    assert werte["Text"]["daten"] == 'C:\\Pfad "zitiert"'
    assert werte[""]["daten"] == "Standard"  # @ = Standardwert
    assert werte["Klein"] == {**werte["Klein"], "typ": "REG_DWORD", "daten": "0"}
    assert werte["Gross"]["daten"] == "4294967295"
    assert werte["Bin"] == {**werte["Bin"], "typ": "REG_BINARY", "daten": "0a 1b ff"}  # Fortsetzungszeile
    assert werte["Exp"] == {**werte["Exp"], "typ": "REG_EXPAND_SZ", "daten": "%TEMP%"}  # unaufgelöst
    assert werte["Multi"] == {**werte["Multi"], "typ": "REG_MULTI_SZ", "daten": ["a", "Ä"]}
    assert werte["Q"] == {**werte["Q"], "typ": "REG_QWORD", "daten": str(2**32 + 1)}
    arten = [(x["block_id"], x["parameter"]["pfad"]) for x in s if x["block_id"] != "registry_wert_setzen"]
    assert arten == [
        ("registry_wert_loeschen", "HKLM\\SOFTWARE\\OkmTest"),
        ("registry_schluessel_anlegen", "Software\\OkmTest\\Leer"),
        ("registry_schluessel_loeschen", "HKLM\\SOFTWARE\\OkmTest\\Alt"),
    ]
    leer = next(x for x in s if x["block_id"] == "registry_schluessel_anlegen")
    assert leer["parameter"]["bereich"] == "angemeldeter_benutzer"  # HKCU nie direkt
    assert any("HKEY_CURRENT_USER" in h for h in erg.hinweise)


def test_reg_utf16_mit_bom_wie_regedit() -> None:
    roh = REG.replace("\n", "\r\n").encode("utf-16-le")
    text = dekodieren(b"\xff\xfe" + roh)
    assert parsen(text).eintraege == parsen(REG).eintraege


def test_reg_regedit4_ansi() -> None:
    text = 'REGEDIT4\n\n[HKEY_LOCAL_MACHINE\\SOFTWARE\\OkmTest]\n"E"=hex(2):25,54,4d,50,25,00\n'
    e = parsen(dekodieren(text.encode("cp1252"))).eintraege[0]
    assert (e.typ, e.daten) == ("REG_EXPAND_SZ", "%TMP%")


@pytest.mark.parametrize(
    ("zeilen", "erwartet"),
    [
        ('[HKEY_USERS\\S-1-5-21\\x]\n"a"=dword:1', "HKEY_USERS"),
        ("[HKEY_CURRENT_CONFIG\\x]", "nicht unterstützt"),
        ('[HKEY_LOCAL_MACHINE\\SOFTWARE\\X]\n"a"=dword:123456789', "1–8 Hex-Ziffern"),
        ('[HKEY_LOCAL_MACHINE\\SOFTWARE\\X]\n"a"=hex(0):', "nicht unterstützt"),
        ('[HKEY_LOCAL_MACHINE\\SOFTWARE\\X]\n"a"=hex:zz', "Hex"),
        ('[HKEY_LOCAL_MACHINE\\SOFTWARE\\X]\n"a=1', "Anführungszeichen"),
        ('"a"="b"', "ohne gültigen Schlüssel"),
        ("[HKEY_LOCAL_MACHINE\\SOFTWARE\\X", "]"),
    ],
)
def test_reg_fehler_mit_zeilennummer(zeilen: str, erwartet: str) -> None:
    erg = parsen("Windows Registry Editor Version 5.00\n" + zeilen)
    assert any(erwartet in f and f.startswith("Zeile ") for f in erg.fehler), erg.fehler


def test_reg_ohne_kopf_und_grenzen() -> None:
    erg = parsen('[HKLM\\SOFTWARE\\X]\n"a"=dword:1')
    assert erg.eintraege and erg.hinweise
    viele = "Windows Registry Editor Version 5.00\n[HKLM\\SOFTWARE\\X]\n" + "".join(
        f'"w{i}"=dword:1\n' for i in range(150)
    )
    erg = parsen(viele)
    assert len(erg.eintraege) == 100 and erg.fehler
    assert parsen("x" * 1_000_001).fehler


def test_reg_roundtrip_durch_validierung(registry: Registry) -> None:
    schritte = [schritt(e) for e in parsen(REG).eintraege]
    ir = ir_aus(registry, Ziel.POWERSHELL, schritte, rot_bestaetigt=True)
    assert len(ir.schritte) == len(schritte)


# --- API ------------------------------------------------------------------------------------------


def test_seite_und_einbindung(client: TestClient) -> None:
    seite = client.get("/registry")
    assert seite.status_code == 200
    assert 'id="registry-katalog"' in seite.text and 'data-modus="seite"' in seite.text
    for url, modus in (("/baukasten", "baukasten"), ("/blockly", "blockly")):
        html = client.get(url).text
        assert (
            f'id="registry-katalog" class="katalog regkat katalog-eingebettet" data-modus="{modus}"' in html
        )
        # Registry-Panel steht unter dem Software-Katalog
        assert html.index('id="software-katalog"') < html.index('id="registry-katalog"')
    assert "registry-katalog.js" in seite.text


def test_api_suche_kategorien_details(client: TestClient) -> None:
    j = client.get("/api/registry/suche", params={"q": "startseite edge", "paket": "edge"}).json()
    assert j["gesamt"] > 0 and j["treffer"][0]["paket"] == "edge"
    assert (
        client.get("/api/registry/suche", params={"q": "makro internet", "klasse": "user"}).json()["gesamt"]
        > 0
    )
    oben = client.get("/api/registry/kategorien").json()["kategorien"]
    assert oben and all("anzahl" in k for k in oben)
    kind = next(k for k in oben if k["hat_kinder"])
    assert client.get("/api/registry/kategorien", params={"eltern": kind["id"]}).json()["kategorien"]
    d = client.get("/api/registry/richtlinie", params={"id": EDGE}).json()
    assert d["titel"] and d["klasse"] == "both"
    assert {"schluessel": "HKLM\\Software\\Policies\\Microsoft\\Edge", "wertname": "HomepageLocation"} in d[
        "orte"
    ]
    assert [p["id"] for p in d["parameter"]] == ["e_homepagelocation"]
    assert client.get("/api/registry/richtlinie", params={"id": "gibt:es:nicht"}).status_code == 404
    assert client.get("/api/registry/pakete").json()["pakete"]


def test_api_haeufig(client: TestClient) -> None:
    j = client.get("/api/registry/haeufig").json()
    assert j["eintraege"]
    smb = next(e for e in j["eintraege"] if e["id"] == "smb1_aus")
    assert smb["quelle"]["url"].startswith("https://learn.microsoft.com/")
    assert smb["schritte"][0]["block_id"] == "registry_wert_setzen"
    rids = {
        s["parameter"]["richtlinie"]
        for e in j["eintraege"]
        for s in e["schritte"]
        if "richtlinie" in s["parameter"]
    }
    assert rids <= set(j["richtlinien"])


def test_api_pfad_vorschau(client: TestClient) -> None:
    j = client.get(
        "/api/registry/pfad", params={"pfad": "HKEY_LOCAL_MACHINE\\SOFTWARE\\Firma", "bereich": "computer"}
    ).json()
    assert j == {"ok": True, "reg": "HKLM\\SOFTWARE\\Firma", "ps": "HKLM:\\SOFTWARE\\Firma"}
    j = client.get(
        "/api/registry/pfad", params={"pfad": "HKCU\\Software\\X", "bereich": "angemeldeter_benutzer"}
    ).json()
    assert j["ok"] and j["reg"] == "HKU\\<SID>\\Software\\X" and "Admin" in j["hinweis"]
    j = client.get("/api/registry/pfad", params={"pfad": "HKCU\\Software\\X", "bereich": "computer"}).json()
    assert not j["ok"] and "HKLM" in j["fehler"]


def test_api_reg_import(client: TestClient) -> None:
    assert client.post("/api/registry/reg", json={"text": REG}).status_code == 403  # CSRF-Schutz
    j = client.post("/api/registry/reg", json={"text": REG}, headers={"X-Okm-Request": "1"}).json()
    assert len(j["schritte"]) == 11 and j["fehler"] == []
    loeschen = next(s for s in j["schritte"] if s["block_id"] == "registry_schluessel_loeschen")
    assert loeschen["risiko"] == "rot" and loeschen["zeile"] == 18
    # Gesperrter Bereich: Schritt kommt mit Fehler zurück
    j = client.post(
        "/api/registry/reg",
        json={"text": 'Windows Registry Editor Version 5.00\n[HKEY_LOCAL_MACHINE\\SAM\\X]\n"a"=dword:1'},
        headers={"X-Okm-Request": "1"},
    ).json()
    assert j["schritte"][0]["fehler"]


# --- Listen-Modus ---------------------------------------------------------------------------------


def test_listen_modus_richtlinie_schritt(client: TestClient) -> None:
    html = client.get(
        "/baukasten/schritt",
        params={
            "block": "richtlinie_setzen",
            "ziel": "powershell",
            "p.richtlinie": EDGE,
            "p.e_homepagelocation": "https://intra.okm",
        },
        headers=HX,
    ).text
    assert "Homepage-URL konfigurieren" in html
    assert "data-richtlinie-waehlen" in html
    uid = re.search(r'name="schritt" value="([0-9a-f]{8}):richtlinie_setzen"', html)[1]
    assert f'name="p.{uid}.e_homepagelocation"' in html and 'value="https://intra.okm"' in html
    # Unbekannte Parameter fliegen raus, auch e_… ohne passende Richtlinie
    html = client.get(
        "/baukasten/schritt",
        params={"block": "richtlinie_setzen", "ziel": "powershell", "p.e_quatsch": "1"},
        headers=HX,
    ).text
    assert "e_quatsch" not in html and "Noch keine Richtlinie gewählt" in html


def test_listen_modus_benutzer_richtlinie_bereich(client: TestClient) -> None:
    html = client.get(
        "/baukasten/schritt",
        params={
            "block": "richtlinie_setzen",
            "ziel": "powershell",
            "p.richtlinie": "windows:windowscopilot:TurnOffWindowsCopilot",
        },
        headers=HX,
    ).text
    assert re.search(r'<option value="angemeldeter_benutzer"\s+selected', html)
    html = client.get(
        "/baukasten/schritt",
        params={
            "block": "richtlinie_setzen",
            "ziel": "powershell",
            "p.richtlinie": "windows:filesys:LongPathsEnabled",
        },
        headers=HX,
    ).text
    assert ".bereich" not in html  # Computer-Richtlinie: kein Bereich


def test_listen_modus_vorschau_mit_elementen(client: TestClient) -> None:
    uid = "0a1b2c3d"
    daten = [
        ("ziel", "powershell"),
        ("schritt", f"{uid}:richtlinie_setzen"),
        (f"p.{uid}.richtlinie", EDGE),
        (f"p.{uid}.zustand", "aktiviert"),
        (f"p.{uid}.methode", "registry_direkt"),
        (f"p.{uid}.e_homepagelocation", "https://intra.okm"),
    ]
    antwort = client.post(
        "/baukasten/vorschau",
        content=urlencode(daten),
        headers={**HX, "Content-Type": "application/x-www-form-urlencoded"},
    )
    assert antwort.status_code == 200
    assert "https://intra.okm" in antwort.text


def test_rezept_aus_liste_behaelt_elemente(registry: Registry) -> None:
    uid = "0a1b2c3d"
    formular = lies_formular(
        [
            ("ziel", "powershell"),
            ("schritt", f"{uid}:richtlinie_setzen"),
            (f"p.{uid}.richtlinie", EDGE),
            (f"p.{uid}.e_homepagelocation", "https://intra.okm"),
        ]
    )
    rezept = rezept_aus_formular(
        registry, formular, name="Edge", kategorie="Test", beschreibung="x", autor="t"
    )
    assert rezept.schritte[0].parameter["e_homepagelocation"] == "https://intra.okm"
    assert registry.rezept_pruefen(rezept) == []


def test_katalog_hinweis_beim_oeffnen(registry: Registry) -> None:
    def s(stand: str, rid: str = EDGE) -> BlockSchritt:
        return BlockSchritt(
            block_id="richtlinie_setzen",
            block_version=1,
            parameter={"richtlinie": ParamValue(typ=ParamTyp.RICHTLINIE, wert=rid)},
            katalog_stand=stand,
        )

    paket = registry.richtlinien.paket("edge") or {}
    assert _katalog_hinweis(registry, s(f"edge@{paket['version']}")) is None
    assert "älteren Vorlagen-Stand" in (_katalog_hinweis(registry, s("edge@1.0")) or "")
    assert "nicht mehr" in (_katalog_hinweis(registry, s("x@1", "edge:msedge:GibtEsNicht")) or "")


def test_blockly_daten_mit_richtlinien(client: TestClient, registry: Registry) -> None:
    # Script mit Richtlinie speichern, im Blockly-Modus wieder öffnen → Titel + Optionen im JSON
    anfrage: dict[str, Any] = {
        "ziel": "powershell",
        "titel": "Edge",
        "schritte": [blk("richtlinie_setzen", richtlinie=EDGE, e_homepagelocation="https://intra.okm")],
    }
    r = client.post("/api/v1/skripte", json=anfrage, headers={"X-Okm-Request": "1"})
    assert r.status_code == 200, r.text
    html = client.get("/blockly", params={"aus": r.json()["id"]}).text
    daten = json.loads(
        re.search(r'<script type="application/json" id="bl-daten">(.*?)</script>', html, re.S)[1]
    )
    schritt0 = daten["vorbelegung"]["schritte"][0]
    assert schritt0["parameter"]["e_homepagelocation"] == "https://intra.okm"
    assert daten["richtlinien"][EDGE]["parameter"][0]["id"] == "e_homepagelocation"
    # Listen-Modus „Erneut öffnen“ behält die Option ebenfalls
    html = client.get("/baukasten", params={"aus": r.json()["id"]}).text
    assert 'value="https://intra.okm"' in html
