"""Teil E: Baustein-Suche (static/js/baustein-suche.js) unter Node und Aufbau der Palette.

Der Node-Teil wird übersprungen, wenn ``node`` fehlt (auf GitHub-Runnern ist es vorhanden).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Einstellungen
from app.db import Datenbank
from app.main import create_app
from app.registry import lade_registry

PROJEKT = Path(__file__).resolve().parent.parent
MODUL = PROJEKT / "static" / "js" / "baustein-suche.js"


@pytest.fixture(scope="module")
def js(tmp_path_factory: pytest.TempPathFactory) -> Any:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node ist nicht installiert – JS-Suchtest übersprungen")
    reg = lade_registry()
    daten = tmp_path_factory.mktemp("js") / "bausteine.json"
    bausteine = [
        {"id": b.id, "name": b.name, "beschreibung": b.beschreibung, "kategorie": b.kategorie}
        for b in sorted(reg.bloecke.values(), key=lambda b: (b.kategorie, b.name))
    ]
    daten.write_text(json.dumps(bausteine), encoding="utf-8")

    def aufruf(ausdruck: str) -> Any:
        code = (
            f"const S = require({json.dumps(str(MODUL))});"
            f"const K = require({json.dumps(str(daten))});"
            "const I = S.baueIndex(K);"
            "const ids = q => S.suche(I, q).map(t => t.baustein.id);"
            f"process.stdout.write(JSON.stringify({ausdruck}));"
        )
        r = subprocess.run([node, "-e", code], capture_output=True, text=True, check=True)
        return json.loads(r.stdout)

    return aufruf


def test_umlaute_und_gross_klein(js: Any) -> None:
    assert js("ids('LOESCHEN')") == js("ids('löschen')")
    assert "registry_schluessel_loeschen" in js("ids('schlüssel löschen')")


def test_teilwoerter_alle_muessen_passen(js: Any) -> None:
    treffer = js("ids('regist wert')")
    assert treffer and all(t.startswith("registry_") for t in treffer)
    assert js("ids('registry xyzzy')") == []


def test_auch_id_kategorie_und_beschreibung(js: Any) -> None:
    assert "dns_cache_leeren" in js("ids('dns_cache')")  # Baustein-ID mit Unterstrich
    assert "registry_wert_setzen" in js("ids('Registry')")  # Kategorie
    assert js("ids('zurücklesen')")  # nur in der Beschreibung


def test_ranking_name_vor_beschreibung(js: Any) -> None:
    treffer = js("ids('ping')")
    assert treffer[0] == "ping"


def test_ohne_suchwort_alles_in_reihenfolge(js: Any) -> None:
    assert js("ids('').length") == js("K.length")


def test_zuletzt_benutzt(js: Any) -> None:
    assert js("S.zuletztDazu(['a','b','c'], 'b', 8)") == ["b", "a", "c"]
    assert js("S.zuletztDazu(['a','b','c','d','e','f','g','h'], 'x', 8)") == [
        "x",
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
    ]


# --- Aufbau der Palette ---------------------------------------------------------------------------


def test_palette_markup() -> None:
    c = TestClient(
        create_app(
            Einstellungen(AUTH_DISABLED=True, APP_SECRET_KEY="x" * 32),
            lade_registry(),
            Datenbank("sqlite://"),
        )
    )
    html = c.get("/baukasten", params={"ziel": "powershell"}).text
    gruppen = re.findall(r'<details class="palette-gruppe"( open)? data-kategorie="([^"]+)"', html)
    assert gruppen and not any(offen for offen, _ in gruppen)  # standardmäßig alle zu
    assert '<details class="palette-gruppe palette-fest" data-fest="favoriten"' in html
    assert '<details class="palette-gruppe palette-fest" data-fest="zuletzt"' in html
    assert 'id="bk-nur-ziel" checked' in html
    assert "data-alle-auf" in html and "data-alle-zu" in html
    # Kompakt: Beschreibung als Tooltip und für den Tastaturfokus
    assert re.search(r'title="[^"]+" aria-describedby="bk-beschr-ping"', html)
    assert 'class="palette-beschreibung" id="bk-beschr-ping"' in html
    assert "baustein-suche.js" in html
    bl = c.get("/blockly").text
    assert 'id="bl-suche"' in bl and "baustein-suche.js" in bl
