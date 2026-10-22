"""Software-Katalog: Schema, Laden beim Start, alle IDs durch Validierung, Escaping und Syntax-Checks."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import escaping
from app.db import Datenbank
from app.escaping import Ziel
from app.katalog import KatalogFehler, lade_katalog
from app.main import create_app
from app.models.block import ParameterDef, ParamTyp
from app.models.software import PLATTFORM_FELDER, SoftwareKatalog
from app.registry import Registry
from app.validation import validiere_wert
from tests import syntax
from tests.conftest import erzeuge
from tests.test_web import einst

KATALOG = lade_katalog()
MAX_SCHRITTE = 100  # = validation.MAX_BLOECKE

# Welche Katalogfelder zu welchem Ziel gehören (Paketmanager-Wert = Feldname)
FELDER_JE_ZIEL = {
    Ziel.POWERSHELL: ("winget",),
    Ziel.CMD: ("winget",),
    Ziel.BASH: ("apt", "flatpak"),
    Ziel.ZSH: ("brew", "brew_cask"),
}


def alle_ids() -> list[tuple[str, str]]:
    return [(feld, pid) for p in KATALOG.pakete for feld, pid in p.ids().items()]


def _schreibe(tmp_path: Path, inhalt: str) -> Path:
    datei = tmp_path / "katalog.yaml"
    datei.write_text(inhalt, encoding="utf-8")
    return datei


KOPF = 'version: 1\ngeprueft_am: "2026-10-22"\npakete:\n'


# --- Schema & Laden -----------------------------------------------------------


def test_echter_katalog_ist_gueltig() -> None:
    assert len(KATALOG.pakete) == 259
    assert str(KATALOG.geprueft_am) == "2026-10-22"
    assert all(p.ids() for p in KATALOG.pakete), "jeder Eintrag braucht mindestens eine Paket-ID"
    assert "Sysinternals" in KATALOG.kategorien()


def test_kein_eintrag_doppelt_pro_plattform() -> None:
    for feld in PLATTFORM_FELDER:
        ids = [getattr(p, feld).lower() for p in KATALOG.pakete if getattr(p, feld)]
        assert len(ids) == len(set(ids)), feld


@pytest.mark.parametrize(
    ("eintrag", "erwartet"),
    [
        ('  - kategorie: "X"\n    beschreibung: "y"\n    winget: "A.B"\n', "pakete[0]"),
        ('  - name: "Nix"\n    kategorie: "X"\n    beschreibung: "y"\n', "mindestens eine Paket-ID"),
        (
            '  - name: "Böse"\n    kategorie: "X"\n    beschreibung: "y"\n    apt: "pkg;rm"\n',
            "pakete[0] (Böse): apt",
        ),
        (
            '  - name: "Option"\n    kategorie: "X"\n    beschreibung: "y"\n    apt: "-y"\n',
            "pakete[0] (Option): apt",
        ),
        (
            '  - name: "Tippfehler"\n    kategorie: "X"\n    beschreibung: "y"\n    wingett: "A.B"\n',
            "wingett",
        ),
        (
            '  - name: "Url"\n    kategorie: "X"\n    beschreibung: "y"\n    hersteller_url: "ftp://x"\n',
            "hersteller_url",
        ),
        (
            '  - name: "A"\n    kategorie: "X"\n    beschreibung: "y"\n    winget: "Foo.Bar"\n'
            '  - name: "B"\n    kategorie: "X"\n    beschreibung: "y"\n    winget: "foo.bar"\n',
            "winget-ID 'foo.bar' doppelt ('A' und 'B')",
        ),
    ],
)
def test_fehler_werden_verstaendlich_gemeldet(tmp_path: Path, eintrag: str, erwartet: str) -> None:
    with pytest.raises(KatalogFehler) as info:
        lade_katalog(_schreibe(tmp_path, KOPF + eintrag))
    assert erwartet in str(info.value)
    assert "katalog.yaml" in str(info.value)


def test_yaml_syntaxfehler(tmp_path: Path) -> None:
    with pytest.raises(KatalogFehler, match="YAML-Syntaxfehler"):
        lade_katalog(_schreibe(tmp_path, KOPF + "  - name: [kaputt\n"))


def test_nur_herstellerlink_ist_erlaubt(tmp_path: Path) -> None:
    k = lade_katalog(
        _schreibe(
            tmp_path,
            KOPF + '  - name: "FortiClient"\n    kategorie: "VPN"\n    beschreibung: "VPN"\n'
            '    hersteller_url: "https://www.fortinet.com/support/product-downloads"\n'
            '    intern: "\\\\\\\\fileserver\\\\software\\\\forticlient"\n',
        )
    )
    assert k.pakete[0].intern == "\\\\fileserver\\software\\forticlient"
    assert k.als_daten()[0] == {
        "name": "FortiClient",
        "kategorie": "VPN",
        "beschreibung": "VPN",
        "hersteller_url": "https://www.fortinet.com/support/product-downloads",
        "intern": "\\\\fileserver\\software\\forticlient",
    }


def test_app_startet_nicht_mit_kaputtem_katalog(tmp_path: Path) -> None:
    with pytest.raises(KatalogFehler):
        lade_katalog(_schreibe(tmp_path, "version: 2\n"))


# --- Alle IDs: Validierung und Escaping -------------------------------------------


PAKETNAME = ParameterDef(id="paket", label="Paket", typ=ParamTyp.PAKETNAME, beispiel="x")


@pytest.mark.parametrize("ziel", list(Ziel), ids=[z.value for z in Ziel])
def test_alle_ids_bestehen_validierung_und_escaping(ziel: Ziel) -> None:
    for _feld, pid in alle_ids():
        assert validiere_wert(PAKETNAME, pid).wert == pid
        literal = escaping.literal(ziel, pid)
        # Keine der erlaubten Zeichen muss escaped werden – die ID steht 1:1 in Quotes.
        assert str(literal) == (f'"{pid}"' if ziel is Ziel.CMD else f"'{pid}'")


def test_sonderzeichen_aus_dem_katalog_sind_dabei() -> None:
    ids = {pid for _, pid in alle_ids()}
    assert any("+" in i for i in ids) and any("@" in i for i in ids)


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_ids_kommen_in_der_shell_unveraendert_an(shell: str) -> None:
    pfad = shutil.which(shell)
    if pfad is None:
        pytest.skip(f"{shell} ist nicht installiert")
    ids = [pid for _, pid in alle_ids()]
    code = "printf '%s\\n' " + " ".join(str(escaping.literal(Ziel.BASH, i)) for i in ids)
    r = subprocess.run([pfad, "-c", code], capture_output=True, text=True, check=True)
    assert r.stdout.splitlines() == ids


def test_ids_kommen_in_powershell_unveraendert_an() -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("pwsh ist nicht installiert")
    ids = [pid for _, pid in alle_ids()]
    code = (
        "@("
        + ",".join(str(escaping.literal(Ziel.POWERSHELL, i)) for i in ids)
        + ") | ConvertTo-Json -Compress"
    )
    r = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", code], capture_output=True, text=True, check=True
    )
    assert json.loads(r.stdout) == ids


# --- Erzeugte Scripte mit allen IDs ---------------------------------------------------


def _scripte(registry: Registry, ziel: Ziel) -> list[tuple[bytes, list[str]]]:
    schritte: list[tuple[str, dict[str, Any]]] = [
        ("paket_installieren", {"paket": pid, "paketmanager": feld})
        for feld, pid in alle_ids()
        if feld in FELDER_JE_ZIEL[ziel]
    ]
    ergebnis = []
    for start in range(0, len(schritte), MAX_SCHRITTE):
        teil = schritte[start : start + MAX_SCHRITTE]
        ergebnis.append((erzeuge(registry, ziel, teil).inhalt, [p["paket"] for _, p in teil]))
    return ergebnis


@pytest.mark.parametrize("ziel", list(Ziel), ids=[z.value for z in Ziel])
def test_scripte_mit_allen_ids(registry: Registry, ziel: Ziel, tmp_path: Path) -> None:
    dateien = []
    for nr, (inhalt, ids) in enumerate(_scripte(registry, ziel)):
        text = inhalt.decode("utf-8-sig")
        for pid in ids:
            gequotet = f'"{pid}"' if ziel is Ziel.CMD else f"'{pid}'"
            assert gequotet in text, pid
        datei = (
            tmp_path
            / f"alle-{nr}{'.cmd' if ziel is Ziel.CMD else '.ps1' if ziel is Ziel.POWERSHELL else '.sh'}"
        )
        datei.write_bytes(inhalt)
        dateien.append(datei)
        if ziel is Ziel.CMD:
            assert syntax.cmd_lint(inhalt) == []
    if ziel is Ziel.BASH:
        for d in dateien:
            syntax.bash_n(d)
        syntax.shellcheck(dateien)
    elif ziel is Ziel.ZSH:
        for d in dateien:
            syntax.zsh_n(d)
    elif ziel is Ziel.POWERSHELL:
        syntax.pwsh_pruefen(dateien, analyzer=False)


def test_winget_immer_exakt_aus_winget_quelle(registry: Registry) -> None:
    for ziel in (Ziel.POWERSHELL, Ziel.CMD):
        text = erzeuge(
            registry, ziel, [("paket_installieren", {"paket": "Notepad++.Notepad++"})]
        ).inhalt.decode()
        assert re.search(r"install --id ['\"]Notepad\+\+\.Notepad\+\+['\"] -e --source winget", text)


@pytest.mark.parametrize(
    ("ziel", "manager", "erwartet"),
    [
        (Ziel.BASH, "flatpak", "flatpak install -y --noninteractive flathub 'org.videolan.VLC'"),
        (Ziel.BASH, "dnf", "dnf install -y 'org.videolan.VLC'"),
        (Ziel.BASH, "standard", "apt-get install -y 'org.videolan.VLC'"),
        (Ziel.BASH, "brew_cask", "unter Linux nicht verfügbar"),
        (Ziel.ZSH, "brew_cask", "brew install --cask 'org.videolan.VLC'"),
        (Ziel.ZSH, "standard", "brew install 'org.videolan.VLC'"),
        (Ziel.ZSH, "apt", "unter macOS nicht verfügbar"),
    ],
)
def test_paketmanager_zweige(registry: Registry, ziel: Ziel, manager: str, erwartet: str) -> None:
    text = erzeuge(
        registry, ziel, [("paket_installieren", {"paket": "org.videolan.VLC", "paketmanager": manager})]
    ).inhalt.decode()
    assert erwartet in text


# --- Oberfläche -------------------------------------------------------------------


@pytest.fixture
def client(registry: Registry, tmp_path: Path) -> TestClient:
    return TestClient(create_app(einst(), registry, Datenbank(f"sqlite:///{tmp_path}/t.db"), KATALOG))


def _eingebettet(html: str) -> list[dict[str, Any]]:
    treffer = re.search(
        r'<script type="application/json" id="software-katalog-daten">(.*?)</script>', html, re.S
    )
    assert treffer, "eingebettetes Katalog-JSON fehlt"
    daten: list[dict[str, Any]] = json.loads(treffer.group(1))
    return daten


def test_seite_software(client: TestClient) -> None:
    r = client.get("/software")
    assert r.status_code == 200
    assert 'data-modus="seite"' in r.text and "IDs geprüft am 22.10.2026" in r.text
    assert len(_eingebettet(r.text)) == 259
    assert 'class="aktiv" aria-current="page"' in r.text and "Software</span>" in r.text
    assert "script-src 'self'" in r.headers["content-security-policy"]
    for k in KATALOG.kategorien():
        assert f'data-kategorie="{k}"' in r.text.replace("&amp;", "&")


def test_panel_im_baukasten_und_rezept(client: TestClient) -> None:
    r = client.get("/baukasten?ziel=zsh")
    assert (
        'data-modus="baukasten"' in r.text
        and 'data-ziel="zsh"' in r.text
        and "data-katalog-auswahl" in r.text
    )
    r = client.get("/rezepte/software_installieren?ziel=bash")
    assert 'data-modus="rezept"' in r.text and "data-katalog-auswahl" not in r.text
    assert 'data-typ="paketname"' in r.text


def test_eingebettetes_json_kann_script_nicht_verlassen(registry: Registry, tmp_path: Path) -> None:
    boese = lade_katalog(
        _schreibe(
            tmp_path,
            KOPF + '  - name: "</script><script>alert(1)</script>"\n    kategorie: "X"\n'
            '    beschreibung: "<b>&"\n    winget: "A.B"\n',
        )
    )
    app = create_app(einst(), registry, Datenbank(f"sqlite:///{tmp_path}/t.db"), boese)
    html = TestClient(app).get("/software").text
    assert "<script>alert(1)" not in html
    assert _eingebettet(html)[0]["name"] == "</script><script>alert(1)</script>"


def test_schritt_mit_vorbelegten_werten(client: TestClient) -> None:
    r = client.get(
        "/baukasten/schritt",
        params={
            "block": "paket_installieren",
            "ziel": "zsh",
            "p.paket": "firefox@esr",
            "p.paketmanager": "brew_cask",
            "p.gibtsnicht": "x",
        },
    )
    assert 'value="firefox@esr"' in r.text
    assert '<option value="brew_cask" selected>' in r.text
    assert "gibtsnicht" not in r.text
    # Vorbelegung ist nur ein Formularwert – HTML-escaped, geprüft wird erst beim Erzeugen
    r = client.get(
        "/baukasten/schritt", params={"block": "paket_installieren", "ziel": "zsh", "p.paket": '"><b>x'}
    )
    assert '"><b>x' not in r.text and "&#34;&gt;&lt;b&gt;x" in r.text


def test_katalog_modell_direkt() -> None:
    k = SoftwareKatalog.model_validate(
        {
            "version": 1,
            "geprueft_am": "2026-01-01",
            "pakete": [{"name": "a", "kategorie": "b", "beschreibung": "c", "brew": "python@3.13"}],
        }
    )
    assert k.pakete[0].ids() == {"brew": "python@3.13"}
