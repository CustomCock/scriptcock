"""Richtlinien-Katalog (Teil B): Parser, Katalog/Suche, Operationen, Validierung, Code, Admin-Werkzeuge.

Nur eigene Test-Vorlagen aus ``tests/daten/admx/`` – keine Herstellerdateien.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import werkzeuge
from app.admx import pakete_parsen
from app.config import Einstellungen
from app.db import Datenbank
from app.escaping import Ziel
from app.generators import generator_fuer
from app.ir import BlockSchritt
from app.main import create_app
from app.models.block import ParamTyp, Risiko
from app.registry import Registry, lade_registry
from app.richtlinien import (
    HAEUFIG_FELDER,
    Operation,
    RichtlinienKatalog,
    haeufig,
    haeufig_schritte,
    normalisiere,
    operationen,
    parameter_fuer,
)
from app.validation import FehlerSammlung
from tests.test_kontrolle import blk, ir_aus
from tools import admx_katalog

DATEN = Path(__file__).parent / "daten" / "admx"
EINFACH = "okmtest:okmtest:Einfach"
WERTE = "okmtest:okmtest:MitWerten"
ELEMENTE = "okmtest:okmtest:Elemente"
ENGLISCH = "okmtest:okmtest:NurEnglisch"


@pytest.fixture(scope="module")
def geparst() -> tuple[dict[str, list[dict[str, Any]]], Any, Any]:
    return pakete_parsen({"okmtest": DATEN / "okmtest" / "admx", "zweit": DATEN / "zweit" / "admx"})


@pytest.fixture(scope="module")
def katalog(tmp_path_factory: pytest.TempPathFactory) -> RichtlinienKatalog:
    ziel = tmp_path_factory.mktemp("katalog")
    rc = admx_katalog.main(
        [
            "--quellen",
            str(DATEN),
            "--quellen-yaml",
            str(DATEN / "quellen.yaml"),
            "--ziel",
            str(ziel),
            "--keine-doku",
        ]
    )
    assert rc == 0
    return RichtlinienKatalog(ziel, cache=tmp_path_factory.mktemp("cache"))


@pytest.fixture(scope="module")
def reg(katalog: RichtlinienKatalog) -> Registry:
    r = lade_registry()
    r.richtlinien = katalog
    r.werkzeug_url = "https://baukasten.okm.test"
    return r


def r_von(geparst: Any, rid: str) -> dict[str, Any]:
    ergebnis, _, _ = geparst
    return next(r for liste in ergebnis.values() for r in liste if r["id"] == rid)


def richtlinie(rid: str, **kw: Any) -> dict[str, Any]:
    return blk("richtlinie_setzen", richtlinie=rid, **kw)


def text(reg: Registry, schritte: list[dict[str, Any]], dry: bool = False, **kw: Any) -> str:
    ir = ir_aus(reg, Ziel.POWERSHELL, schritte, rot_bestaetigt=True, dry_run=dry, **kw)
    return generator_fuer(Ziel.POWERSHELL, reg).erzeuge(ir).text


def fehler(reg: Registry, schritte: list[dict[str, Any]], ziel: Ziel = Ziel.POWERSHELL) -> list[str]:
    with pytest.raises(FehlerSammlung) as e:
        ir_aus(reg, ziel, schritte, rot_bestaetigt=True)
    return [f"{f.feld}: {f.meldung}" for f in e.value.fehler]


ALLE_ELEMENTE = {
    "e_stufe": "1",
    "e_schalter": True,
    "e_anzahl": 4,
    "e_alstext": 12,
    "e_gross": 5000000000,
    "e_pfad": "%TEMP%\\okm",
    "e_zeilen": ["eins", "zwei"],
    "e_zuordnung": ["Alpha=1", "Beta = zwei"],
    "e_reihe": ["a", "b"],
}


# --- Parser ---------------------------------------------------------------------------------------


def test_parser_zaehlt_und_laesst_ungueltiges_aus(geparst: Any) -> None:
    ergebnis, _, stat = geparst
    assert [r["name"] for r in ergebnis["okmtest"]] == ["Einfach", "Elemente", "MitWerten", "NurEnglisch"]
    assert stat.richtlinien["okmtest"] == 4
    assert stat.ausgelassen["okmtest"] == 2
    assert stat.gruende["unbekannte class Irgendwas"] == 1
    assert stat.gruende["Schlüssel mit Wurzel"] == 1
    assert stat.ohne_deutsch["okmtest"] == 1


def test_parser_utf16_und_kategorien_ueber_pakete(geparst: Any) -> None:
    zahl = r_von(geparst, "zweit:zweit:Zahl")
    assert zahl["aktiviert"]["wert"] == {"typ": "REG_DWORD", "daten": 2}
    assert zahl["deaktiviert"]["wert"] == {"typ": "REG_DWORD", "daten": 3}
    englisch = r_von(geparst, ENGLISCH)
    assert englisch["sprache"] == "en"
    assert englisch["titel"] == "English only"
    assert englisch["klasse"] == "user"
    # Kategorie aus dem anderen Paket (using prefix="zweit")
    assert englisch["kategorie_pfad"] == ["Second root", "Fremd verankert"]


def test_parser_konvention_nur_wertname(geparst: Any) -> None:
    r = r_von(geparst, EINFACH)
    assert r["aktiviert"]["wert"] == {"typ": "REG_DWORD", "daten": 1}
    assert r["deaktiviert"]["wert"] == {"typ": "REG_DWORD", "daten": 0}
    assert r["unterstuetzt"] == "Mindestens Okm 1"
    assert r["kategorie_pfad"] == ["Okm-Test"]


def test_parser_eigene_werte_und_listen(geparst: Any) -> None:
    r = r_von(geparst, WERTE)
    assert r["klasse"] == "both"
    assert r["aktiviert"]["wert"] == {"typ": "REG_SZ", "daten": "an"}
    assert r["deaktiviert"]["wert"] == {"loeschen": True}
    assert r["aktiviert"]["liste"] == [
        {
            "schluessel": "Software\\Policies\\Okm\\Test\\Extra",
            "wertname": "Zusatz",
            "wert": {"typ": "REG_DWORD", "daten": 7},
        }
    ]


def test_parser_elemente(geparst: Any) -> None:
    r = r_von(geparst, ELEMENTE)
    e = {x["id"]: x for x in r["elemente"]}
    # Reihenfolge aus der Presentation
    assert [x["id"] for x in r["elemente"]][:2] == ["Stufe", "Schalter"]
    assert e["Schalter"]["wahr"]["wert"] == {"typ": "REG_DWORD", "daten": 5}
    assert e["Schalter"]["standard"] is True
    assert (e["Anzahl"]["min"], e["Anzahl"]["max"], e["Anzahl"]["standard"]) == (1, 10, 3)
    assert e["AlsText"]["als_text"] is True
    assert e["Gross"]["art"] == "longDecimal"
    assert e["Pfad"]["erweiterbar"] is True
    assert e["Pfad"]["max_laenge"] == 20
    assert e["Pfad"]["standard"] == "%TEMP%"
    assert e["Zeilen"]["max_eintraege"] == 3
    assert e["Stufe"]["pflicht"] is True
    assert [o["label"] for o in e["Stufe"]["optionen"]] == ["Aus", "Hoch"]
    assert e["Stufe"]["optionen"][1]["liste"][0]["schluessel"] == "Software\\Policies\\Okm\\Elemente\\Hoch"
    assert e["Zuordnung"]["expliziter_wert"] is True
    assert e["Zuordnung"]["schluessel"] == "Software\\Policies\\Okm\\Elemente\\Zuordnung"
    assert (e["Reihe"]["praefix"], e["Reihe"]["additiv"]) == ("R", True)


def test_parameter_fuer(geparst: Any) -> None:
    params = {p.id: p for p, _ in parameter_fuer(r_von(geparst, ELEMENTE))}
    assert set(params) == set(ALLE_ELEMENTE)
    assert params["e_schalter"].typ is ParamTyp.JA_NEIN
    assert params["e_anzahl"].typ is ParamTyp.ZAHL
    assert (params["e_anzahl"].min, params["e_anzahl"].max) == (1, 10)
    assert params["e_pfad"].typ is ParamTyp.REGISTRY_TEXT
    assert params["e_zeilen"].typ is ParamTyp.REGISTRY_ZEILEN
    assert params["e_stufe"].typ is ParamTyp.AUSWAHL
    assert params["e_stufe"].standard == "1"
    assert "Name=Wert" in (params["e_zuordnung"].hilfe or "")


# --- Operationen ----------------------------------------------------------------------------------


def test_operationen_einfach(geparst: Any) -> None:
    r = r_von(geparst, EINFACH)
    pfad = "Software\\Policies\\Okm\\Test"
    assert operationen(r, "aktiviert", {}) == [Operation("setzen", pfad, "Einfach", "REG_DWORD", 1)]
    assert operationen(r, "deaktiviert", {}) == [Operation("setzen", pfad, "Einfach", "REG_DWORD", 0)]
    assert operationen(r, "nicht_konfiguriert", {}) == [
        Operation("loeschen", pfad, "Einfach"),
        Operation("leer_entfernen", pfad),
    ]


def test_operationen_mit_listen(geparst: Any) -> None:
    r = r_von(geparst, WERTE)
    extra = "Software\\Policies\\Okm\\Test\\Extra"
    an = operationen(r, "aktiviert", {})
    assert Operation("setzen", "Software\\Policies\\Okm\\Test", "Modus", "REG_SZ", "an") in an
    assert Operation("setzen", extra, "Zusatz", "REG_DWORD", 7) in an
    aus = operationen(r, "deaktiviert", {})
    assert aus[0] == Operation("loeschen", "Software\\Policies\\Okm\\Test", "Modus")
    # Werte aus der enabledList werden beim Deaktivieren entfernt
    assert Operation("loeschen", extra, "Zusatz") in aus
    nk = operationen(r, "nicht_konfiguriert", {})
    # tiefere Schlüssel zuerst entfernen
    leer = [op.pfad for op in nk if op.art == "leer_entfernen"]
    assert leer == [extra, "Software\\Policies\\Okm\\Test"]


def test_operationen_alle_elemente(geparst: Any) -> None:
    r = r_von(geparst, ELEMENTE)
    k = "Software\\Policies\\Okm\\Elemente"
    ops = operationen(r, "aktiviert", ALLE_ELEMENTE)
    assert Operation("setzen", k, "Stufe", "REG_SZ", "hoch") in ops
    assert Operation("setzen", k + "\\Hoch", "Aktiv", "REG_DWORD", 1) in ops
    assert Operation("setzen", k, "Schalter", "REG_DWORD", 5) in ops
    assert Operation("setzen", k, "Anzahl", "REG_DWORD", 4) in ops
    assert Operation("setzen", k, "AlsText", "REG_SZ", "12") in ops
    assert Operation("setzen", k, "Gross", "REG_QWORD", 5000000000) in ops
    assert Operation("setzen", k, "Pfad", "REG_EXPAND_SZ", "%TEMP%\\okm") in ops
    assert Operation("setzen", k, "Zeilen", "REG_MULTI_SZ", ("eins", "zwei")) in ops
    # explizite Liste: erst leeren, dann Name=Wert
    i = ops.index(Operation("leeren", k + "\\Zuordnung"))
    assert ops[i + 1 : i + 3] == [
        Operation("setzen", k + "\\Zuordnung", "Alpha", "REG_SZ", "1"),
        Operation("setzen", k + "\\Zuordnung", "Beta", "REG_SZ", "zwei"),
    ]
    # additive Liste mit Präfix: nicht leeren, R1, R2
    assert Operation("leeren", k + "\\Reihe") not in ops
    assert Operation("setzen", k + "\\Reihe", "R2", "REG_SZ", "b") in ops
    # Schalter aus → falseValue, leerer Text → löschen
    ops = operationen(r, "aktiviert", {**ALLE_ELEMENTE, "e_schalter": False, "e_pfad": ""})
    assert Operation("setzen", k, "Schalter", "REG_DWORD", 0) in ops
    assert Operation("loeschen", k, "Pfad") in ops


def test_operationen_deaktiviert_loescht_elementwerte(geparst: Any) -> None:
    ops = operationen(r_von(geparst, ELEMENTE), "deaktiviert", {})
    arten = {(op.art, op.name) for op in ops}
    assert ("loeschen", "Anzahl") in arten
    assert ("leeren", "") in arten
    assert not any(op.art == "setzen" for op in ops)


# --- Katalog und Suche ----------------------------------------------------------------------------


def test_normalisiere() -> None:
    assert normalisiere("Ärger-Größe_Café\\Pfad") == "aerger groesse cafe pfad"


def test_katalog_abfragen(katalog: RichtlinienKatalog) -> None:
    assert {p["id"]: p["anzahl"] for p in katalog.pakete()} == {"okmtest": 4, "zweit": 1}
    assert katalog.paket("zweit")["version"] == "2.0"
    assert katalog.richtlinie(EINFACH)["wertname"] == "Einfach"
    assert katalog.richtlinie("gibt:es:nicht") is None
    assert katalog.richtlinie("x" * 400) is None
    assert katalog.admx_dateien("okmtest") == ["okmtest.admx"]


def test_katalog_kategorien(katalog: RichtlinienKatalog) -> None:
    oben = {k["name"]: k for k in katalog.kategorien()}
    assert set(oben) == {"Okm-Test", "Second root"}
    assert oben["Okm-Test"]["anzahl"] == 3  # inkl. Unterkategorie
    assert oben["Second root"]["anzahl"] == 2  # eigene + fremd verankerte
    unter = katalog.kategorien(oben["Okm-Test"]["id"])
    assert [k["name"] for k in unter] == ["Unterkategorie Ärger"]
    assert [k["name"] for k in katalog.kategorien(paket="zweit")] == ["Second root"]


@pytest.mark.parametrize(
    ("q", "erwartet"),
    [
        ("makrosperre internet", EINFACH),  # Erklärungstext
        ("aerger", WERTE),  # Kategoriepfad, Umlaut normalisiert
        ("Ärger alle", ELEMENTE),
        ("zuordnung", ELEMENTE),  # Schlüssel
        ("anzahl", ELEMENTE),  # Element-Wertname
        ("okm benutzer", ENGLISCH),
        ("modu", WERTE),  # Präfix
    ],
)
def test_suche(katalog: RichtlinienKatalog, q: str, erwartet: str) -> None:
    treffer = [t["id"] for t in katalog.suche(q)["treffer"]]
    assert treffer and treffer[0] == erwartet


def test_suche_filter_und_seiten(katalog: RichtlinienKatalog) -> None:
    assert katalog.suche("", paket="zweit")["gesamt"] == 1
    benutzer = {t["id"] for t in katalog.suche("", klasse="user")["treffer"]}
    assert benutzer == {WERTE, ENGLISCH}  # „both“ zählt mit
    seite = katalog.suche("", pro_seite=2, seite=2)
    assert seite["gesamt"] == 5
    assert len(seite["treffer"]) == 2
    assert katalog.suche("!!!")["gesamt"] == 0
    # FTS-Syntax wird nicht durchgereicht
    assert katalog.suche('" OR 1=1 --')["gesamt"] == 0


# --- Validierung ----------------------------------------------------------------------------------


def test_validierung_ok_und_stand(reg: Registry) -> None:
    ir = ir_aus(reg, Ziel.POWERSHELL, [richtlinie(ELEMENTE, **ALLE_ELEMENTE)])
    s = ir.schritte[0]
    assert isinstance(s, BlockSchritt)
    assert s.katalog_stand == "okmtest@1.0"
    assert s.parameter["bereich"].wert == "computer"
    assert s.risiko is None  # „Policies“ allein macht nicht rot


@pytest.mark.parametrize(
    ("schritt", "erwartet"),
    [
        (richtlinie("gibt:es:nicht"), "gibt es im Katalog nicht"),
        (richtlinie(EINFACH, e_quatsch="1"), "Unbekannter Parameter „e_quatsch“"),
        (richtlinie(EINFACH, bereich="alle_benutzer"), "gilt nur für den Computer"),
        (richtlinie(ENGLISCH, bereich="computer"), "gilt nur für Benutzer"),
        (richtlinie(ELEMENTE, **{**ALLE_ELEMENTE, "e_pfad": "x" * 21}), "Höchstens 20 Zeichen"),
        (richtlinie(ELEMENTE, **{**ALLE_ELEMENTE, "e_zeilen": ["a", "b", "c", "d"]}), "Höchstens 3 Einträge"),
        (richtlinie(ELEMENTE, **{**ALLE_ELEMENTE, "e_zuordnung": ["ohne"]}), "Name=Wert"),
        (richtlinie(ELEMENTE, **{**ALLE_ELEMENTE, "e_anzahl": 11}), "e_anzahl"),
        (richtlinie(ELEMENTE, **{**ALLE_ELEMENTE, "e_stufe": "9"}), "e_stufe"),
        (richtlinie(ELEMENTE, **{**ALLE_ELEMENTE, "e_pfad": "a\nb"}), "e_pfad"),
        (richtlinie(EINFACH, methode="lokale_gruppenrichtlinie"), "Admin-Werkzeug bereitstellen"),
    ],
)
def test_validierung_fehler(reg: Registry, schritt: dict[str, Any], erwartet: str) -> None:
    assert any(erwartet in f for f in fehler(reg, [schritt])), fehler(reg, [schritt])


def test_validierung_nur_powershell(reg: Registry) -> None:
    assert any("nur mit PowerShell" in f for f in fehler(reg, [richtlinie(EINFACH)], Ziel.CMD))


def test_validierung_elemente_nur_wenn_aktiviert(reg: Registry) -> None:
    # Ungültige Elementwerte stören nicht, wenn die Richtlinie deaktiviert wird
    ir_aus(reg, Ziel.POWERSHELL, [richtlinie(ELEMENTE, zustand="deaktiviert", e_anzahl=99)])


def test_validierung_standardzustand_prueft_elemente(reg: Registry) -> None:
    # Ohne „zustand“ gilt „aktiviert“ – dann müssen die Elemente auch geprüft werden
    assert any(
        "e_anzahl" in f for f in fehler(reg, [richtlinie(ELEMENTE, **{**ALLE_ELEMENTE, "e_anzahl": 99})])
    )
    ir = ir_aus(reg, Ziel.POWERSHELL, [richtlinie(EINFACH)])
    assert ir.schritte[0].parameter["zustand"].wert == "aktiviert"  # type: ignore[union-attr]
    assert ir.schritte[0].parameter["methode"].wert == "registry_direkt"  # type: ignore[union-attr]


def test_validierung_benutzer_standard(reg: Registry) -> None:
    ir = ir_aus(reg, Ziel.POWERSHELL, [richtlinie(ENGLISCH)])
    assert ir.schritte[0].parameter["bereich"].wert == "angemeldeter_benutzer"  # type: ignore[union-attr]


# --- Code -----------------------------------------------------------------------------------------


def test_code_registry_direkt(reg: Registry) -> None:
    t = text(reg, [richtlinie(ELEMENTE, **ALLE_ELEMENTE)])
    assert (
        "$null = Set-OkmRegistryWert -Bereich 'computer' -Pfad 'HKLM\\Software\\Policies\\Okm\\Elemente' "
        "-Name 'Pfad' -Typ 'REG_EXPAND_SZ' -Daten '%TEMP%\\okm' -WennVorhanden 'ueberschreiben' -Ansicht '64'"
    ) in t
    assert "-Name 'Zeilen' -Typ 'REG_MULTI_SZ' -Daten @('eins', 'zwei')" in t
    assert (
        "Clear-OkmRegistrySchluessel -Bereich 'computer' -Pfad 'HKLM\\Software\\Policies\\Okm\\Elemente\\Zuordnung'"
        in t
    )
    assert "Register-OkmGpupdate 'computer'" in t
    assert t.count("\nInvoke-OkmGpupdate") == 1
    assert "function Invoke-OkmLgpo" in t  # Richtlinien-Hilfen eingebunden
    assert "Richtlinie: Alle Elemente (aktiviert)" in t


def test_code_benutzer_und_nicht_konfiguriert(reg: Registry) -> None:
    t = text(reg, [richtlinie(ENGLISCH, zustand="nicht_konfiguriert", bereich="alle_benutzer")])
    assert (
        "Remove-OkmRegistryWert -Bereich 'alle_benutzer' -Pfad 'Software\\Policies\\Okm\\Benutzer' -Name 'Wert'"
        in t
    )
    assert "Remove-OkmRegistrySchluesselWennLeer -Bereich 'alle_benutzer'" in t
    assert "Register-OkmGpupdate 'user'" in t


def test_code_simulation(reg: Registry) -> None:
    t = text(reg, [richtlinie(EINFACH)], dry=True)
    assert "-Ansicht '64' -Simulation" in t
    assert "Register-OkmGpupdate '" not in t


def test_code_lgpo(reg: Registry) -> None:
    t = text(
        reg,
        [
            blk("admin_werkzeug_bereitstellen", was="lgpo"),
            richtlinie(ELEMENTE, methode="lokale_gruppenrichtlinie", **ALLE_ELEMENTE),
            richtlinie(EINFACH, methode="lokale_gruppenrichtlinie", zustand="nicht_konfiguriert"),
        ],
    )
    assert "'MULTISZ:eins\\0zwei'," in t
    assert "'EXSZ:%TEMP%\\okm'," in t
    assert "'QWORD:5000000000'," in t
    assert "'DELETEALLVALUES'," in t
    assert "'DELETE'," in t
    assert t.count("Invoke-OkmLgpo -Zeilen $okmLgpo") == 2


def test_lgpo_semikolon_abgelehnt() -> None:
    from app.generators.richtlinie_ps import CodeFehler, _lgpo_zeilen

    with pytest.raises(CodeFehler):
        _lgpo_zeilen([Operation("setzen", "Software\\X", ";kommentar", "REG_SZ", "a")], "Computer")


def test_code_ohne_kontrolle_ohne_richtlinien_hilfen(reg: Registry) -> None:
    t = text(reg, [blk("registry_wert_lesen", bereich="computer", pfad="HKLM\\SOFTWARE\\Okm", wertname="x")])
    assert "function Get-OkmRegistryWert" in t
    assert "function Invoke-OkmLgpo" not in t
    assert "OkmLgpoSicherung" not in t


# --- Häufige Einstellungen (echter Katalog) -------------------------------------------------------


def test_haeufig_belegt_und_gueltig(registry: Registry) -> None:
    eintraege = haeufig()
    assert eintraege
    assert len({e["id"] for e in eintraege}) == len(eintraege)
    for e in eintraege:
        assert set(e) <= HAEUFIG_FELDER, e["id"]
        for feld in ("titel", "beschreibung", "gruppe", "bereich", "wirkung", "risiko", "schritte"):
            assert e.get(feld), f"{e['id']}: {feld} fehlt"
        assert e["bereich"] in ("computer", "benutzer")
        werte: set[str] = set()
        for s in e["schritte"]:
            if "richtlinie" in s:
                r = registry.richtlinien.richtlinie(s["richtlinie"])
                assert r is not None, f"{e['id']}: {s['richtlinie']} fehlt im Katalog"
                params = {p.id for p, _ in parameter_fuer(r)}
                assert set(s.get("werte", {})) <= params, e["id"]
                werte |= set(s.get("werte", {}))
            else:
                # Freie Registry-Werte nur mit belegter Quelle (Microsoft Learn / Hersteller)
                assert s["block"].startswith("registry_"), e["id"]
                assert e["quelle"]["url"].startswith("https://learn.microsoft.com/"), e["id"]
                werte |= set(s["parameter"])
        assert set(e.get("anpassen", [])) <= werte, e["id"]
        ir = ir_aus(registry, Ziel.POWERSHELL, haeufig_schritte(e), rot_bestaetigt=True)
        rot = any(getattr(s, "risiko", None) is Risiko.ROT for s in ir.schritte)
        assert rot == (e["risiko"] == "rot"), f"{e['id']}: Risiko {e['risiko']} passt nicht zur Validierung"
        assert generator_fuer(Ziel.POWERSHELL, registry).erzeuge(ir).text


# --- Admin-Werkzeuge ------------------------------------------------------------------------------


def test_werkzeug_lgpo_intranet(reg: Registry) -> None:
    w = werkzeuge.werkzeug("lgpo")
    assert w is not None
    t = text(reg, [blk("admin_werkzeug_bereitstellen", was="lgpo")])
    assert f"-Url 'https://baukasten.okm.test/werkzeuge/lgpo/LGPO.zip' -Sha256 '{w['sha256']}'" in t
    assert f"-EintragSha256 '{w['datei_sha256']}'" in t


def test_werkzeug_lgpo_hersteller(reg: Registry) -> None:
    w = werkzeuge.werkzeug("lgpo")
    assert w is not None
    t = text(reg, [blk("admin_werkzeug_bereitstellen", was="lgpo", quelle="hersteller")])
    assert f"-Url '{w['url']}'" in t
    assert w["url"].startswith("https://download.microsoft.com/")


def test_werkzeug_vorlagen_und_central_store(reg: Registry) -> None:
    lade = lade_registry()
    lade.werkzeug_url = "https://baukasten.okm.test"
    schritt = blk("admin_werkzeug_bereitstellen", was="vorlagen", paket="chrome", central_store=True)
    ir = ir_aus(lade, Ziel.POWERSHELL, [schritt], rot_bestaetigt=True)
    assert ir.schritte[0].risiko is Risiko.ROT  # type: ignore[union-attr]
    t = generator_fuer(Ziel.POWERSHELL, lade).erzeuge(ir).text
    d = werkzeuge.dateien("chrome")[0]
    assert f"Url = 'https://baukasten.okm.test/werkzeuge/{d.spiegel}'; Sha256 = '{d.sha256}'" in t
    assert "-CentralStore" in t
    with pytest.raises(FehlerSammlung):
        ir_aus(lade, Ziel.POWERSHELL, [schritt])  # rot ohne Bestätigung


def test_werkzeug_fehler(reg: Registry) -> None:
    ohne_url = lade_registry()
    assert any("OKM_WERKZEUG_URL" in f for f in fehler(ohne_url, [blk("admin_werkzeug_bereitstellen")]))
    assert any(
        "nur mit PowerShell" in f for f in fehler(reg, [blk("admin_werkzeug_bereitstellen")], Ziel.CMD)
    )


def test_quellen_yaml_vollstaendig() -> None:
    q = werkzeuge.quellen()
    for p in q["pakete"]:
        if p.get("format") == "manuell":
            continue
        for d in p["dateien"]:
            assert d["url"].startswith("https://"), p["id"]
            assert len(d["sha256"]) == 64, p["id"]
    for w in q["werkzeuge"]:
        assert len(w["sha256"]) == 64 and len(w["datei_sha256"]) == 64


def test_spiegel_nur_aus_yaml(tmp_path: Path) -> None:
    (tmp_path / "lgpo" / "download").mkdir(parents=True)
    (tmp_path / "lgpo" / "download" / "LGPO.zip").write_bytes(b"x")
    (tmp_path / "lgpo" / "download" / "anderes.exe").write_bytes(b"x")
    assert (
        werkzeuge.gespiegelt("lgpo/LGPO.zip", tmp_path)
        == (tmp_path / "lgpo" / "download" / "LGPO.zip").resolve()
    )
    assert werkzeuge.gespiegelt("lgpo/anderes.exe", tmp_path) is None
    assert werkzeuge.gespiegelt("lgpo/../lgpo/LGPO.zip", tmp_path) is None
    assert werkzeuge.gespiegelt("gibtsnicht/LGPO.zip", tmp_path) is None


def test_spiegel_route(tmp_path: Path) -> None:
    einst = Einstellungen(AUTH_DISABLED=True, APP_SECRET_KEY="x" * 32, OKM_WERKZEUG_URL="https://b.okm.test/")
    reg = lade_registry()
    app = create_app(einst, reg, Datenbank("sqlite://"))
    assert reg.werkzeug_url == "https://b.okm.test"
    c = TestClient(app)
    assert c.get("/werkzeuge/lgpo/nicht-da.exe").status_code == 404
    assert c.get("/werkzeuge/..%2F..%2Fpyproject.toml").status_code == 404
