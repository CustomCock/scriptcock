"""Teil D: Registry-Rezepte, bedingte Rezeptschritte (``nur_wenn``) und die Soll/Ist-Liste."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from app.config import Einstellungen
from app.db import Datenbank
from app.escaping import Ziel
from app.generators import generator_fuer
from app.main import create_app
from app.models.block import ParameterDef, ParamTyp
from app.models.recipe import RezeptDef
from app.registry import Registry, _pruefe_rezept, lade_registry
from app.service import rezept_zu_request
from app.validation import (
    FehlerSammlung,
    ValidierungsFehler,
    soll_liste_script,
    validiere_request,
    validiere_wert,
)
from tests.conftest import FESTE_ZEIT
from tests.test_kontrolle import blk, ir_aus

SOLL = ParameterDef(id="eintraege", label="Werte", typ=ParamTyp.REGISTRY_SOLL_LISTE)


def script(
    registry: Registry, rezept_id: str, formular: dict[str, Any], ziel: Ziel = Ziel.POWERSHELL
) -> tuple[list[str], str]:
    rezept = registry.rezepte[rezept_id]
    req = rezept_zu_request(registry, rezept, ziel, formular, rot_bestaetigt=True)
    ir = validiere_request(req, registry, autor="pytest", jetzt=FESTE_ZEIT)
    schritte = [
        s.block_id + (":" + str(s.parameter["richtlinie"].wert) if "richtlinie" in s.parameter else "")
        for s in ir.bloecke()
    ]
    return schritte, generator_fuer(ziel, registry).erzeuge(ir).text


# --- Soll/Ist-Liste --------------------------------------------------------------------------------


def test_soll_liste_normalisiert_und_idempotent() -> None:
    roh = "HKEY_LOCAL_MACHINE\\SOFTWARE\\X ; Wert ; dword ; 0x10\n\nHKLM:\\SOFTWARE\\Y ;  ; REG_SZ ; a;b|c"
    wert = validiere_wert(SOLL, roh).wert
    assert wert == ["HKLM\\SOFTWARE\\X ; Wert ; REG_DWORD ; 16", "HKLM\\SOFTWARE\\Y ;  ; REG_SZ ; a;b|c"]
    assert validiere_wert(SOLL, wert).wert == wert  # Rezeptfeld → Baustein: zweimal geprüft
    assert soll_liste_script(wert) == [
        "HKLM\\SOFTWARE\\X|Wert|REG_DWORD|16",
        "HKLM\\SOFTWARE\\Y||REG_SZ|a;b|c",
    ]


@pytest.mark.parametrize(
    ("roh", "erwartet"),
    [
        ("HKLM\\SOFTWARE\\X ; Wert ; REG_DWORD", "Pfad ; Wertname ; Typ ; Soll"),
        ("HKLM\\SOFTWARE\\X ; Wert ; REG_DWORD ; 4294967296", "Zeile 1"),
        ("HKLM\\SOFTWARE\\X ; Wert ; REG_MULTI_SZ ; a", "einzeln"),
        ("HKLM\\SOFTWARE\\X ; We|rt ; REG_SZ ; a", "„|“"),
        ("HKLM\\SOFTWARE\\X ; Wert ; REG_TEXT ; a", "Typ"),
        ("\n\n", "ausgefüllt"),
        ("\n".join(f"HKLM\\SOFTWARE\\X ; W{i} ; REG_SZ ; a" for i in range(51)), "Höchstens 50"),
    ],
)
def test_soll_liste_fehler(roh: str, erwartet: str) -> None:
    with pytest.raises(ValidierungsFehler, match=erwartet):
        validiere_wert(SOLL, roh)


def test_soll_liste_bereich(registry: Registry) -> None:
    ir = ir_aus(
        registry,
        Ziel.POWERSHELL,
        [
            blk(
                "registry_soll_ist_liste",
                bereich="alle_benutzer",
                eintraege="HKCU\\Software\\X ; A ; REG_SZ ; 1",
            )
        ],
    )
    assert ir.schritte[0].parameter["eintraege"].wert == ["Software\\X ; A ; REG_SZ ; 1"]  # type: ignore[union-attr]
    with pytest.raises(FehlerSammlung, match="HKLM"):
        ir_aus(
            registry,
            Ziel.POWERSHELL,
            [
                blk(
                    "registry_soll_ist_liste",
                    bereich="computer",
                    eintraege="HKCU\\Software\\X ; A ; REG_SZ ; 1",
                )
            ],
        )


# --- Bedingte Rezeptschritte -----------------------------------------------------------------------


def _rezept(schritte: list[dict[str, Any]]) -> RezeptDef:
    return RezeptDef.model_validate(
        {
            "id": "test_bedingt",
            "name": "Test",
            "kategorie": "Test",
            "beschreibung": "x",
            "quelle": "test",
            "felder": [
                {"id": "an", "label": "An", "typ": "ja_nein", "pflicht": False, "standard": False},
                {
                    "id": "art",
                    "label": "Art",
                    "typ": "auswahl",
                    "standard": "a",
                    "optionen": [{"wert": "a", "label": "A"}, {"wert": "b", "label": "B"}],
                },
            ],
            "schritte": schritte,
        }
    )


def test_nur_wenn_pruefung(registry: Registry) -> None:
    fehler: list[str] = []
    _pruefe_rezept(
        _rezept([{"block": "ping", "parameter": {"ziel": "1.1.1.1"}, "nur_wenn": {"gibts": True}}]),
        registry,
        fehler,
    )
    assert any("'gibts' existiert nicht" in f for f in fehler)
    fehler = []
    _pruefe_rezept(
        _rezept([{"block": "ping", "parameter": {"ziel": "1.1.1.1"}, "nur_wenn": {"art": "c"}}]),
        registry,
        fehler,
    )
    assert any("nur_wenn.art" in f for f in fehler)
    fehler = []
    _pruefe_rezept(
        _rezept(
            [{"block": "ping", "parameter": {"ziel": "1.1.1.1"}, "nur_wenn": {"art": ["a", "b"], "an": True}}]
        ),
        registry,
        fehler,
    )
    assert fehler == []


def test_nur_wenn_auswertung() -> None:
    schritt = _rezept([{"block": "ping", "nur_wenn": {"art": ["a", "b"], "an": True}}]).schritte[0]
    assert schritt.bedingung_erfuellt({"art": "b", "an": True})
    assert not schritt.bedingung_erfuellt({"art": "b", "an": False})
    assert not schritt.bedingung_erfuellt({"art": "c", "an": True})


# --- Die fünf Rezepte ------------------------------------------------------------------------------


def test_registry_einstellung_setzen(registry: Registry) -> None:
    formular = {
        "bereich": "angemeldeter_benutzer",
        "pfad": "HKCU\\Software\\Firma",
        "wertname": "Modus",
        "typ": "REG_SZ",
        "daten": "an",
    }
    schritte, text = script(registry, "registry_einstellung_setzen", formular)
    assert schritte == ["registry_wert_setzen"]
    assert "-Bereich 'angemeldeter_benutzer' -Pfad 'Software\\Firma'" in text
    schritte, _ = script(
        registry, "registry_einstellung_setzen", {**formular, "wiederherstellungspunkt": True}
    )
    assert schritte == ["wiederherstellungspunkt", "registry_wert_setzen"]
    schritte, text = script(registry, "registry_einstellung_setzen", formular, Ziel.CMD)
    assert schritte == ["registry_wert_setzen"] and "reg add" in text


def test_registry_einstellung_pruefen(registry: Registry) -> None:
    formular = {
        "eintraege": "HKLM\\SOFTWARE\\A ; X ; REG_DWORD ; 1\nHKLM\\SOFTWARE\\B ; Y ; REG_SZ ; z",
        "bericht": "C:\\Temp\\b.html",
    }
    schritte, text = script(registry, "registry_einstellung_pruefen", formular)
    assert schritte == ["registry_soll_ist_liste", "bericht_html"]
    assert "@('HKLM\\SOFTWARE\\A|X|REG_DWORD|1', 'HKLM\\SOFTWARE\\B|Y|REG_SZ|z')" in text


def test_reg_datei_importieren(registry: Registry) -> None:
    schritte, _ = script(registry, "reg_datei_importieren", {"datei": "\\\\srv\\it\\a.reg"})
    assert schritte == ["wiederherstellungspunkt", "registry_import"]
    schritte, _ = script(
        registry,
        "reg_datei_importieren",
        {"datei": "\\\\srv\\it\\a.reg", "wiederherstellungspunkt": False},
        Ziel.CMD,
    )
    assert schritte == ["registry_import"]


@pytest.mark.parametrize(
    ("formular", "erwartet"),
    [
        (
            {"browser": "edge", "startseite": "https://intra"},
            [
                "software_version",
                "richtlinie_setzen:edge:msedge:HomepageLocation",
                "richtlinie_setzen:edge:msedge:HomepageIsNewTabPage",
                "richtlinie_setzen:edge:msedgeupdate:Pol_UpdatePolicyMicrosoftEdge",
            ],
        ),
        (
            {
                "browser": "chrome",
                "startseite": "https://intra",
                "updates": False,
                "erweiterungen_setzen": True,
                "erweiterungen": "abc;https://clients2.google.com/service/update2/crx",
            },
            [
                "software_version",
                "richtlinie_setzen:chrome:chrome:HomepageLocation",
                "richtlinie_setzen:chrome:chrome:HomepageIsNewTabPage",
                "richtlinie_setzen:chrome:chrome:ExtensionInstallForcelist",
            ],
        ),
        (
            {
                "browser": "firefox",
                "startseite": "https://intra",
                "erweiterungen_setzen": True,
                "erweiterungen": "https://addons.mozilla.org/x.xpi",
            },
            [
                "software_version",
                "richtlinie_setzen:firefox:firefox:HomepageURL",
                "richtlinie_setzen:firefox:firefox:AppAutoUpdate",
                "richtlinie_setzen:firefox:firefox:DisableAppUpdate",
                "richtlinie_setzen:firefox:firefox:Extensions_Install",
            ],
        ),
    ],
)
def test_browser_richtlinien(registry: Registry, formular: dict[str, Any], erwartet: list[str]) -> None:
    schritte, text = script(registry, "browser_richtlinien", formular)
    assert schritte == erwartet
    assert "'https://intra'" in text


def test_office_makros(registry: Registry) -> None:
    schritte, text = script(registry, "office_makros_internet", {"bereich": "standardprofil"})
    assert len(schritte) == 7 and all("L_BlockMacroExecutionFromInternet" in s for s in schritte)
    assert text.count("-Name 'blockcontentexecutionfrominternet' -Typ 'REG_DWORD' -Daten '1'") == 7
    with pytest.raises(FehlerSammlung, match="nur für Benutzer"):
        script(registry, "office_makros_internet", {"bereich": "computer"})


def test_rezeptseite_zeigt_bedingungen() -> None:
    c = TestClient(
        create_app(
            Einstellungen(AUTH_DISABLED=True, APP_SECRET_KEY="x" * 32),
            lade_registry(),
            Datenbank("sqlite://"),
        )
    )
    html = c.get("/rezepte/browser_richtlinien", params={"ziel": "powershell"}).text
    assert "nur wenn „Browser“ = Mozilla Firefox" in html
    assert "Homepage-URL konfigurieren" in html


def test_rezepte_yaml_lesbar() -> None:
    for name in (
        "registry_einstellung_setzen",
        "registry_einstellung_pruefen",
        "reg_datei_importieren",
        "browser_richtlinien",
        "office_makros_internet",
    ):
        daten = yaml.safe_load(
            (Path(__file__).parent.parent / "recipes" / f"{name}.yaml").read_text(encoding="utf-8")
        )
        assert daten["id"] == name
