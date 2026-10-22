"""Clientseitige Katalog-Suche (static/js/katalog-suche.js) unter Node – Akzeptanzkriterien der Spec.

Wird übersprungen, wenn ``node`` nicht installiert ist (auf GitHub-Runnern ist es vorhanden).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from app.katalog import lade_katalog

PROJEKT = Path(__file__).resolve().parent.parent
MODUL = PROJEKT / "static" / "js" / "katalog-suche.js"


@pytest.fixture(scope="module")
def js(tmp_path_factory: pytest.TempPathFactory) -> Any:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node ist nicht installiert – JS-Suchtest übersprungen")
    daten = tmp_path_factory.mktemp("js") / "katalog.json"
    daten.write_text(json.dumps(lade_katalog().als_daten()), encoding="utf-8")

    def aufruf(ausdruck: str) -> Any:
        code = (
            f"const S = require({json.dumps(str(MODUL))});"
            f"const K = require({json.dumps(str(daten))});"
            "const I = S.baueIndex(K);"
            "const namen = (q, o) => S.suche(I, Object.assign({anfrage: q, plattform: 'alle'}, o || {}))"
            ".map(t => t.paket.name);"
            f"process.stdout.write(JSON.stringify({ausdruck}));"
        )
        r = subprocess.run([node, "-e", code], capture_output=True, text=True, check=True)
        return json.loads(r.stdout)

    return aufruf


def test_pdf_findet_die_klassiker(js: Any) -> None:
    treffer = js("namen('pdf')")
    for name in ["Adobe Acrobat Reader (64 Bit)", "SumatraPDF", "PDF24 Creator", "PDFsam Basic", "Okular"]:
        assert name in treffer


def test_umlaute_gleichwertig(js: Any) -> None:
    assert js("namen('loeschen')") == js("namen('löschen')") != []
    assert js("S.normalisiere('Größe Übersicht')") == "groesseuebersicht"


def test_paket_ids_werden_durchsucht(js: Any) -> None:
    assert js("namen('Mozilla.Fire')")[:2] == ["Mozilla Firefox", "Mozilla Firefox ESR"]
    assert "VSCodium" in js("namen('vscodium')")


def test_bindestriche_punkte_leerzeichen_egal(js: Any) -> None:
    assert js("namen('7zip')")[0] == "7-Zip"
    assert "Microsoft OneDrive" in js("namen('one drive')")
    assert "Microsoft OneDrive" in js("namen('onedrive')")


def test_mehrere_woerter_und_verknuepft(js: Any) -> None:
    alle = js("namen('pdf reader')")
    assert alle and all(n in js("namen('pdf')") for n in alle)
    assert js("namen('pdf reader')") == js("namen('reader pdf')")
    assert js("namen('pdf gibtesnicht')") == []


def test_ranking(js: Any) -> None:
    # exakter Name vor „beginnt mit“ vor „enthält“
    assert js("namen('vlc')")[0] == "VLC"
    treffer = js("S.suche(I, {anfrage: 'firefox', plattform: 'alle'}).map(t => t.punkte)")
    assert treffer == sorted(treffer)


def test_plattform_und_kategorien(js: Any) -> None:
    mac = js("S.suche(I, {anfrage: '', plattform: 'macos'}).map(t => t.paket.kategorie)")
    assert "Sysinternals" not in mac and len(mac) > 100
    assert js("namen('', {plattform: 'windows'}).length") == 205
    nur = js(
        "S.suche(I, {anfrage: '', plattform: 'alle', kategorien: ['PDF', 'VPN']}).map(t => t.paket.kategorie)"
    )
    assert set(nur) == {"PDF", "VPN"}


def test_hervorheben_bezieht_sich_auf_originaltext(js: Any) -> None:
    assert js("S.trefferBereiche('Datei löschen', 'loeschen')") == [[6, 13]]
    assert js("S.trefferBereiche('7-Zip', '7zip')") == [[0, 5]]
    assert js("S.trefferBereiche('PDF-Reader für PDF', 'pdf')") == [[0, 3], [15, 18]]


def test_befehle_zum_kopieren(js: Any) -> None:
    assert js("S.befehl('winget', '7zip.7zip')") == (
        "winget install --id 7zip.7zip -e --source winget --accept-package-agreements --accept-source-agreements"
    )
    assert js("S.befehl('brew_cask', 'firefox@esr')") == "brew install --cask firefox@esr"
    assert js("S.befehl('apt', 'vlc')") == "sudo apt install -y vlc"
    assert js("S.befehl('flatpak', 'org.videolan.VLC')") == "flatpak install -y flathub org.videolan.VLC"


def test_suche_ist_schnell(js: Any) -> None:
    # 1000 Suchen über den ganzen Katalog – grob 1 ms pro Tastendruck reicht auch für schwache PCs
    dauer = js(
        "(() => { const t = Date.now(); for (let i = 0; i < 1000; i++) S.suche(I, {anfrage: 'pdf re', plattform: 'alle'});"
        " return Date.now() - t; })()"
    )
    assert dauer < 3000
