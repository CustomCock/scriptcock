"""Backlog P1 (Blockly): neue Ablauf-Knoten „Wenn … dann … sonst“, „Abbrechen“, „Warten“,
„Bestätigung“ und „Kommentar“ – Validierung, Generierung, Syntax und echte Ausführung."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

import pytest

from app.escaping import Ziel
from app.generators import generator_fuer
from app.ir import Abbrechen, Bestaetigung, Kommentar, ScriptIR, Warten, Wenn
from app.registry import Registry
from app.validation import ir_zu_request
from tests import syntax
from tests.test_ausfuehrung import SH_ZIELE, ausfuehren
from tests.test_rueckgabe import SETZEN, ZEIGEN, fehler_von, ir_aus, mit_bloecken, setzen


@pytest.fixture(scope="module")
def reg() -> Registry:
    return mit_bloecken(SETZEN, ZEIGEN)


def meldung(text: str) -> dict[str, Any]:
    return {"block_id": "meldung", "parameter": {"text": text, "pause": False}}


def wenn(
    wert: str, vergleich: str, zahl: Any = None, dann: list[Any] | None = None, sonst: list[Any] | None = None
) -> dict[str, Any]:
    k: dict[str, Any] = {
        "art": "wenn",
        "wert": wert,
        "vergleich": vergleich,
        "dann": dann or [],
        "sonst": sonst or [],
    }
    if zahl is not None:
        k["zahl"] = zahl
    return k


def abbrechen(text: str = "Genug getan", code: Any = 3) -> dict[str, Any]:
    return {"art": "abbrechen", "meldung": text, "code": code}


def warten(sek: Any = 1) -> dict[str, Any]:
    return {"art": "warten", "sekunden": sek}


def bestaetigung(text: str = "Wirklich weitermachen?") -> dict[str, Any]:
    return {"art": "bestaetigung", "meldung": text}


def kommentar(text: str = "Hier beginnt die Druckerprüfung") -> dict[str, Any]:
    return {"art": "kommentar", "text": text}


ALLES = [
    kommentar(),
    setzen("42", "ja"),
    wenn("1.wert", "kleiner", 50, [meldung("KLEIN")], [meldung("GROSS")]),
    wenn("1.ok", "ja", None, [meldung("OK-JA")]),
    warten(1),
    bestaetigung(),
    {"art": "wenn_fehler", "versuche": [meldung("im versuch")], "sonst": []},
    abbrechen("Fertig geprueft", 0),
]


# --- IR & Validierung ------------------------------------------------------------------------


def test_ir_knoten_und_roundtrip(reg: Registry) -> None:
    ir = ir_aus(reg, Ziel.BASH, ALLES)
    arten = [type(k) for k in ir.schritte]
    assert arten[:6] == [Kommentar, type(ir.schritte[1]), Wenn, Wenn, Warten, Bestaetigung]
    assert isinstance(ir.schritte[-1], Abbrechen)
    w = ir.schritte[2]
    assert isinstance(w, Wenn) and w.zahl == 50 and w.vergleich == "kleiner"
    assert [b.parameter["text"].wert for b in ir.bloecke() if b.block_id == "meldung"] == [
        "KLEIN",
        "GROSS",
        "OK-JA",
        "im versuch",
    ]
    assert ir.hat_kontrolle() and ir.hat_verzweigung()
    assert ScriptIR.model_validate_json(ir.model_dump_json()) == ir
    assert ir_aus(reg, Ziel.BASH, ir_zu_request(ir, Ziel.BASH).model_dump()["schritte"]) == ir


def test_ohne_verzweigung(reg: Registry) -> None:
    ir = ir_aus(reg, Ziel.BASH, [kommentar(), meldung("a"), warten(2)])
    assert ir.hat_kontrolle() and not ir.hat_verzweigung()


@pytest.mark.parametrize(
    ("schritte", "teil"),
    [
        ([setzen(), wenn("1.wert", "ja")], "ja/nein"),  # Vergleich passt nicht zum Typ
        ([setzen(), wenn("1.ok", "kleiner", 3)], "Zahl"),
        ([setzen(), wenn("1.wert", "kleiner")], "Vergleichszahl"),
        ([setzen(), wenn("1.wert", "kleiner", "viel")], "ganze Zahl"),
        ([setzen(), wenn("1.wert", "irgendwie", 3)], "Vergleich"),
        ([wenn("1.wert", "gleich", 1), setzen()], "vor diesem"),
        ([setzen(), wenn("1.wert", "gleich", 1, [abbrechen()])], None),  # erlaubt
        ([{"art": "wenn_fehler", "versuche": [abbrechen()]}], "Versuche"),
        ([abbrechen(code=100)], "Exit-Code"),
        ([abbrechen(text="a & b")], "Zeichen"),
        ([warten(0)], "Sekunden"),
        ([warten(4000)], "Sekunden"),
        ([bestaetigung("")], "ausgefüllt"),
        ([kommentar("x" * 400)], "zu lang"),
    ],
)
def test_validierung(reg: Registry, schritte: list[Any], teil: str | None) -> None:
    if teil is None:
        ir_aus(reg, Ziel.BASH, schritte)
        return
    meldungen = fehler_von(reg, Ziel.BASH, schritte)
    assert any(teil in m for m in meldungen), meldungen


def test_fehlerpositionen_vorordnung(reg: Registry) -> None:
    from app.models.request import ScriptRequest
    from app.validation import FehlerSammlung, validiere_request
    from tests.conftest import FESTE_ZEIT

    schritte = [setzen(), kommentar(), wenn("1.wert", "gleich", 1, [warten(0)], [abbrechen(code=200)])]
    req = ScriptRequest.model_validate({"ziel": "bash", "schritte": schritte})
    with pytest.raises(FehlerSammlung) as e:
        validiere_request(req, reg, autor="t", jetzt=FESTE_ZEIT)
    # 0 setzen, 1 kommentar, 2 wenn, 3 warten, 4 abbrechen
    assert sorted(f.schritt for f in e.value.fehler) == [3, 4]


# --- Generierung & Syntax --------------------------------------------------------------------


@pytest.mark.parametrize("ziel", list(Ziel))
def test_syntax_aller_ziele(reg: Registry, ziel: Ziel, tmp_path: Path) -> None:
    s = generator_fuer(ziel, reg).erzeuge(ir_aus(reg, ziel, ALLES))
    datei = tmp_path / ("s" + s.dateiname[s.dateiname.rindex(".") :])
    datei.write_bytes(s.inhalt)
    assert "Hier beginnt die Druckerprüfung" in s.text
    if ziel is Ziel.BASH:
        syntax.bash_n(datei)
        syntax.shellcheck([datei])
    elif ziel is Ziel.ZSH:
        syntax.zsh_n(datei)
    elif ziel is Ziel.POWERSHELL:
        syntax.pwsh_pruefen([datei])
    else:
        assert syntax.cmd_lint(s.inhalt) == []
        labels = set(re.findall(r"^:(\w+)", s.text, re.M))
        for ziel_label in re.findall(r"goto :(\w+)", s.text):
            assert ziel_label in labels, ziel_label


def test_kopf_zeigt_ablauf(reg: Registry) -> None:
    text = generator_fuer(Ziel.BASH, reg).erzeuge(ir_aus(reg, Ziel.BASH, ALLES)).text
    kopf = text.split("Generiert mit dem okm Script-Baukasten")[0]
    for teil in (
        "Notiz: Hier beginnt die Druckerprüfung",
        "Wenn wert aus Schritt 1 < 50:",
        "Sonst:",
        "Wenn ok aus Schritt 1 ist ja:",
        "Warte 1 Sekunde",
        "Bestätigung: Wirklich weitermachen?",
        "Beenden (Exit-Code 0): Fertig geprueft",
    ):
        assert teil in kopf, teil


@pytest.mark.parametrize("ziel", list(Ziel))
def test_flaches_script_mit_notiz_zaehlt_weiter(reg: Registry, ziel: Ziel) -> None:
    """Kommentar/Warten ändern die Zählweise nicht („X von Y Schritten“)."""
    text = generator_fuer(ziel, reg).erzeuge(ir_aus(reg, ziel, [kommentar(), meldung("a"), warten(1)])).text
    assert re.search(r"von.{0,40}Schritten", text), ziel


# --- Ausführung ----------------------------------------------------------------------------


def _lauf(reg: Registry, shell: str, ziel: Ziel, tmp_path: Path, schritte: list[Any], eingabe: str = ""):
    s = generator_fuer(ziel, reg).erzeuge(ir_aus(reg, ziel, schritte))
    env = {"TEMP": str(tmp_path)} if shell == "pwsh" else None
    return ausfuehren(shell, s.inhalt, tmp_path, eingabe=eingabe, env=env)


ALLE_SHELLS = [*SH_ZIELE, ("pwsh", Ziel.POWERSHELL)]


@pytest.mark.parametrize(("shell", "ziel"), ALLE_SHELLS)
@pytest.mark.parametrize(
    ("zahl", "vergleich", "grenze", "erwartet"),
    [
        ("42", "kleiner", 50, "DANN"),
        ("42", "groesser", 50, "SONST"),
        ("42", "gleich", 42, "DANN"),
        ("42", "ungleich", 42, "SONST"),
        ("42", "kleiner_gleich", 42, "DANN"),
        ("42", "groesser_gleich", 43, "SONST"),
        ("x", "unbekannt", None, "DANN"),
        ("x", "kleiner", 50, "SONST"),  # unbekannt: Vergleiche sind immer falsch
        ("x", "ungleich", 1, "SONST"),
    ],
)
def test_wenn_zahl(
    reg: Registry,
    tmp_path: Path,
    shell: str,
    ziel: Ziel,
    zahl: str,
    vergleich: str,
    grenze: Any,
    erwartet: str,
) -> None:
    r = _lauf(
        reg,
        shell,
        ziel,
        tmp_path,
        [
            setzen(zahl, "ja"),
            wenn("1.wert", vergleich, grenze, [meldung("DANN")], [meldung("SONST")]),
            meldung("WEITER"),
        ],
    )
    assert r.returncode == 0, r.stdout + r.stderr
    andere = "SONST" if erwartet == "DANN" else "DANN"
    ausgabe = r.stdout.split("--- LOG ---")[0]
    assert erwartet in ausgabe and andere not in ausgabe.split("[2/")[-1].replace("Bedingung", "")
    assert "WEITER" in ausgabe
    assert "Fertig: 3 Schritte erfolgreich ausgeführt." in ausgabe


@pytest.mark.parametrize(("shell", "ziel"), ALLE_SHELLS)
@pytest.mark.parametrize(
    ("ok", "vergleich", "erwartet"), [("ja", "ja", "DANN"), ("nein", "ja", "SONST"), ("nein", "nein", "DANN")]
)
def test_wenn_ja_nein(
    reg: Registry, tmp_path: Path, shell: str, ziel: Ziel, ok: str, vergleich: str, erwartet: str
) -> None:
    r = _lauf(
        reg,
        shell,
        ziel,
        tmp_path,
        [setzen("1", ok), wenn("1.ok", vergleich, None, [meldung("DANN")], [meldung("SONST")])],
    )
    assert r.returncode == 0, r.stdout + r.stderr
    treffer = re.findall(r"^(DANN|SONST)$", r.stdout.split("--- LOG ---")[0], re.M)
    assert treffer == [erwartet], r.stdout


@pytest.mark.parametrize(("shell", "ziel"), ALLE_SHELLS)
@pytest.mark.parametrize("code", [0, 7])
def test_abbrechen(reg: Registry, tmp_path: Path, shell: str, ziel: Ziel, code: int) -> None:
    r = _lauf(
        reg,
        shell,
        ziel,
        tmp_path,
        [meldung("vorher"), abbrechen("Speicher reicht", code), meldung("NACHHER")],
    )
    assert r.returncode == code, r.stdout + r.stderr
    ausgabe = r.stdout.split("--- LOG ---")[0]
    assert "NACHHER" not in ausgabe
    assert "Planmäßig beendet: Speicher reicht" in ausgabe
    assert "Erfolgreich bis dahin: 1" in ausgabe


@pytest.mark.parametrize(("shell", "ziel"), ALLE_SHELLS)
def test_warten(reg: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    start = time.monotonic()
    r = _lauf(reg, shell, ziel, tmp_path, [warten(1), meldung("danach")])
    assert r.returncode == 0, r.stdout + r.stderr
    assert time.monotonic() - start >= 1
    assert "Warte 1 Sekunde" in r.stdout and "danach" in r.stdout


@pytest.mark.parametrize(("shell", "ziel"), ALLE_SHELLS)
@pytest.mark.parametrize(("eingabe", "rc"), [("JA\n", 0), ("nein\n", 2), ("", 2)])
def test_bestaetigung(reg: Registry, tmp_path: Path, shell: str, ziel: Ziel, eingabe: str, rc: int) -> None:
    r = _lauf(
        reg,
        shell,
        ziel,
        tmp_path,
        [bestaetigung("Drucker wirklich neu anlegen?"), meldung("WEITER")],
        eingabe,
    )
    assert r.returncode == rc, r.stdout + r.stderr
    assert "Drucker wirklich neu anlegen?" in r.stdout
    assert ("WEITER" in r.stdout.split("--- LOG ---")[0]) is (rc == 0)


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_bestaetigung_im_versuch_bricht_alles_ab(
    reg: Registry, tmp_path: Path, shell: str, ziel: Ziel
) -> None:
    schritte = [
        {"art": "wenn_fehler", "versuche": [bestaetigung()], "sonst": [meldung("AUSWEICHEN")]},
        meldung("WEITER"),
    ]
    r = _lauf(reg, shell, ziel, tmp_path, schritte, "nein\n")
    assert r.returncode == 2, r.stdout
    assert "AUSWEICHEN" not in r.stdout and "WEITER" not in r.stdout.split("--- LOG ---")[0]


@pytest.mark.parametrize(("shell", "ziel"), ALLE_SHELLS)
def test_kommentar_nur_im_script(reg: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    r = _lauf(reg, shell, ziel, tmp_path, [kommentar("NUR-IM-SCRIPT"), meldung("a")])
    assert r.returncode == 0
    assert "NUR-IM-SCRIPT" not in r.stdout
    assert "Fertig: 1 von 1 Schritten erfolgreich." in r.stdout


# --- Blockly: Rückweg aus der Bibliothek ------------------------------------------------------


def test_baum_wiederherstellen(reg: Registry, tmp_path: Path) -> None:
    from datetime import datetime

    from app.bibliothek import baum_wiederherstellen
    from app.db import GespeichertesScript

    ir = ir_aus(reg, Ziel.BASH, ALLES)
    eintrag = GespeichertesScript(ir_json=ir.model_dump_json(), ziel="bash", erstellt_am=datetime.now())
    _, baum, _ = baum_wiederherstellen(reg, eintrag)
    arten = [k["art"] for k in baum]
    assert arten == [
        "kommentar",
        "block",
        "wenn",
        "wenn",
        "warten",
        "bestaetigung",
        "wenn_fehler",
        "abbrechen",
    ]
    assert baum[2] == {
        "art": "wenn",
        "wert": "1.wert",
        "vergleich": "kleiner",
        "zahl": 50,
        "dann": [{"art": "block", "block_id": "meldung", "parameter": {"text": "KLEIN", "pause": "false"}}],
        "sonst": [{"art": "block", "block_id": "meldung", "parameter": {"text": "GROSS", "pause": "false"}}],
    }
