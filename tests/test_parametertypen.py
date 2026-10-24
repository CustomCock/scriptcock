"""Backlog P1: neue Parametertypen – Listen (``liste`` + ``listen_typ``), abgeleitete Werte,
Schema, Escaping/Ausführung und Formularfelder. Einzelwerte stehen in ``tests/test_validation.py``."""

from __future__ import annotations

import re
from typing import Any

import pytest
from pydantic import ValidationError

from app.escaping import Ziel, liste
from app.generators import generator_fuer
from app.models.block import ParameterDef, ParamTyp
from app.registry import Registry
from app.validation import ValidierungsFehler, pruefe_wert_fuer_ziel, validiere_wert
from tests.test_ausfuehrung import SH_ZIELE, ausfuehren
from tests.test_rueckgabe import ir_aus, mit_bloecken


def lp(listen_typ: str, **kw: Any) -> ParameterDef:
    return ParameterDef.model_validate(
        {"id": "x", "label": "X", "typ": "liste", "listen_typ": listen_typ, **kw}
    )


# --- Listen: Validierung -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("listen_typ", "roh", "erwartet"),
    [
        ("port", "80, 443;8080", [80, 443, 8080]),
        ("port", "80 443  8443", [80, 443, 8443]),  # ohne Leerzeichen im Typ: auch Leerzeichen trennen
        ("port", [22, "80"], [22, 80]),
        ("port", "443, 443, 80", [443, 80]),  # doppelte fallen weg, Reihenfolge bleibt
        ("ipv4", "1.1.1.1, 9.9.9.9", ["1.1.1.1", "9.9.9.9"]),
        (
            "gruppenname",
            "Domänen-Benutzer, Remote Desktop Users",
            ["Domänen-Benutzer", "Remote Desktop Users"],
        ),
        ("mac", "00-1a-2b-3c-4d-5e", ["00:1A:2B:3C:4D:5E"]),
    ],
)
def test_liste_gueltig(listen_typ: str, roh: Any, erwartet: list[Any]) -> None:
    assert validiere_wert(lp(listen_typ), roh).wert == erwartet


@pytest.mark.parametrize(
    ("param", "roh", "teil"),
    [
        (lp("port"), "80, http", "Eintrag 2 („http“)"),
        (lp("port", max_anzahl=2), "1,2,3", "höchstens 2"),
        (lp("port", min_anzahl=2), "80", "mindestens 2"),
        (lp("port"), ", ,", "ausgefüllt"),
        (lp("ipv4"), "1.1.1.1, $(id)", "Eintrag 2"),
        (lp("port"), [True], "Eintrag 1"),
    ],
)
def test_liste_ungueltig(param: ParameterDef, roh: Any, teil: str) -> None:
    with pytest.raises(ValidierungsFehler, match=re.escape(teil)):
        validiere_wert(param, roh)


def test_liste_optional_leer() -> None:
    assert validiere_wert(lp("port", pflicht=False), "").wert is None


def test_liste_zielpruefung_je_eintrag() -> None:
    wert = validiere_wert(lp("pfad"), "C:\\Daten, D:\\Sicherung")
    pruefe_wert_fuer_ziel(wert, Ziel.POWERSHELL)
    with pytest.raises(ValidierungsFehler):
        pruefe_wert_fuer_ziel(wert, Ziel.BASH)


# --- Schema ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("daten", "teil"),
    [
        ({"typ": "liste"}, "listen_typ"),
        ({"typ": "text", "listen_typ": "port"}, "listen_typ"),
        ({"typ": "liste", "listen_typ": "liste"}, "listen_typ"),
        ({"typ": "liste", "listen_typ": "variable"}, "listen_typ"),
        ({"typ": "liste", "listen_typ": "ja_nein"}, "listen_typ"),
        ({"typ": "liste", "listen_typ": "port", "min_anzahl": 5, "max_anzahl": 2}, "min_anzahl"),
        ({"typ": "text", "max_anzahl": 2}, "min_anzahl"),
        ({"typ": "tage", "min": 0}, "min"),
    ],
)
def test_schema_fehler(daten: dict[str, Any], teil: str) -> None:
    with pytest.raises(ValidationError, match=teil):
        ParameterDef.model_validate({"id": "x", "label": "X", **daten})


def test_schema_min_max_fuer_zahlentypen() -> None:
    p = ParameterDef(id="x", label="X", typ=ParamTyp.TAGE, min=7, max=90)
    with pytest.raises(ValidierungsFehler, match="mindestens 7"):
        validiere_wert(p, "3")
    assert validiere_wert(p, "30").wert == 30


# --- Escaping & Generierung ------------------------------------------------------------------


def test_liste_escaping() -> None:
    assert liste(Ziel.POWERSHELL, ["a b", "it's"]) == "@('a b', 'it''s')"
    assert liste(Ziel.POWERSHELL, [80, 443]) == "@(80, 443)"
    assert liste(Ziel.BASH, ["a b", "it's"]) == "'a b' 'it'\\''s'"
    assert liste(Ziel.ZSH, [80, 443]) == "80 443"
    assert liste(Ziel.CMD, ["a b", "c"]) == '"a b" "c"'
    assert liste(Ziel.CMD, [80, 443]) == "80 443"


LISTE_BLOCK: dict[str, Any] = {
    "id": "test_liste",
    "name": "Test: Liste",
    "kategorie": "Test",
    "beschreibung": "Gibt jeden Eintrag aus",
    "risiko": "gruen",
    "fortschritt": "Gruppen {{ gruppen }}",
    "parameter": [
        {
            "id": "gruppen",
            "label": "Gruppen",
            "typ": "liste",
            "listen_typ": "gruppenname",
            "beispiel": "a, b",
        },
        {
            "id": "schluessel",
            "label": "Schlüssel",
            "typ": "registry_pfad",
            "beispiel": "HKLM:\\SOFTWARE\\OKM",
        },
    ],
    "ziele": {
        "powershell": "foreach ($okmG in {{ gruppen }}) { Write-Output ('OKM-G=' + $okmG) }\n"
        "Write-Output ('OKM-PS=' + {{ schluessel }})",
        "cmd": "for %%g in ({{ gruppen }}) do echo OKM-G=%%~g\necho OKM-REG={{ schluessel_reg }}",
        "bash": 'okm_gruppen=({{ gruppen }})\nfor okm_g in "${okm_gruppen[@]}"; do printf \'OKM-G=%s\\n\' "$okm_g"; done',
        "zsh": 'okm_gruppen=({{ gruppen }})\nfor okm_g in "${okm_gruppen[@]}"; do printf \'OKM-G=%s\\n\' "$okm_g"; done',
    },
}


@pytest.fixture(scope="module")
def reg() -> Registry:
    return mit_bloecken(LISTE_BLOCK)


SCHRITT = {
    "block_id": "test_liste",
    "parameter": {
        "gruppen": "Domänen-Benutzer, Remote Desktop Users",
        "schluessel": "HKEY_LOCAL_MACHINE\\SOFTWARE\\OKM",
    },
}


@pytest.mark.parametrize(("shell", "ziel"), [*SH_ZIELE, ("pwsh", Ziel.POWERSHELL)])
def test_liste_ausfuehrung(reg: Registry, tmp_path: Any, shell: str, ziel: Ziel) -> None:
    s = generator_fuer(ziel, reg).erzeuge(ir_aus(reg, ziel, [SCHRITT]))
    r = ausfuehren(shell, s.inhalt, tmp_path, env={"TEMP": str(tmp_path)} if shell == "pwsh" else None)
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.findall(r"^OKM-G=(.*)$", r.stdout.split("--- LOG ---")[0], re.M) == [
        "Domänen-Benutzer",
        "Remote Desktop Users",
    ]
    assert "Gruppen Domänen-Benutzer, Remote Desktop Users" in r.stdout  # Fortschritt
    if ziel is Ziel.POWERSHELL:
        assert "OKM-PS=HKLM:\\SOFTWARE\\OKM" in r.stdout


def test_cmd_liste_und_reg_form(reg: Registry) -> None:
    text = generator_fuer(Ziel.CMD, reg).erzeuge(ir_aus(reg, Ziel.CMD, [SCHRITT])).text
    assert 'for %%g in ("Domänen-Benutzer" "Remote Desktop Users") do' in text
    assert 'echo OKM-REG="HKLM\\SOFTWARE\\OKM"' in text  # reg.exe-Schreibweise ohne Doppelpunkt


# --- Formularfelder ----------------------------------------------------------------------------


def test_formularfelder(registry: Registry) -> None:
    from fastapi.testclient import TestClient

    from app.config import Einstellungen
    from app.db import Datenbank
    from app.main import create_app

    reg = mit_bloecken(
        LISTE_BLOCK,
        {
            "id": "test_felder",
            "name": "Test: Felder",
            "kategorie": "Test",
            "beschreibung": "Felder",
            "risiko": "gruen",
            "parameter": [
                {"id": "tage", "label": "Tage", "typ": "tage", "standard": 30},
                {"id": "datum", "label": "Datum", "typ": "datum", "beispiel": "2026-12-24"},
                {"id": "uhrzeit", "label": "Uhrzeit", "typ": "uhrzeit", "beispiel": "08:30"},
            ],
            "ziele": {"bash": "printf '%s %s %s\\n' {{ tage }} {{ datum }} {{ uhrzeit }}"},
        },
    )
    c = TestClient(
        create_app(Einstellungen(AUTH_DISABLED=True, APP_SECRET_KEY="x" * 32), reg, Datenbank("sqlite://"))
    )
    html = c.get("/baukasten/schritt?block=test_felder&ziel=bash").text
    assert re.search(r'name="p\.\w+\.tage" type="number"[^>]*min="1" max="3650"', html)
    assert re.search(r'name="p\.\w+\.datum" type="date"', html)
    assert re.search(r'name="p\.\w+\.uhrzeit" type="time"', html)
    html = c.get("/baukasten/schritt?block=test_liste&ziel=bash").text
    assert re.search(r'name="p\.\w+\.gruppen" type="text"[^>]*data-typ="liste"', html)
    assert "mehrere mit Komma trennen" in html
