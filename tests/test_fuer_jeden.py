"""Ablauf-Baustein „Für jeden Wert“ (Knoten ``fuer_jeden``).

Werte werden für jeden Parameter, der sie benutzt, einzeln gegen dessen Typ geprüft; der Generator
rollt den Rumpf pro Wert mit den geprüften Literalen aus. Ausführung in bash, zsh und pwsh.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from app.escaping import Ziel
from app.generators import generator_fuer
from app.ir import FuerJeden
from app.registry import Registry
from app.validation import MAX_SCHLEIFENWERTE, FehlerSammlung, ir_zu_request, validiere_request
from tests import syntax
from tests.conftest import FESTE_ZEIT
from tests.test_ausfuehrung import SH_ZIELE, ausfuehren
from tests.test_kontrolle import blk, ir_aus, meldung, versuche

WERT = {"schleifenwert": True}


def fuer_jeden(werte: Any, rumpf: list[dict[str, Any]]) -> dict[str, Any]:
    return {"art": "fuer_jeden", "werte": werte, "rumpf": rumpf}


def fehler(registry: Registry, ziel: Ziel, schritte: list[dict[str, Any]]) -> list[tuple[Any, Any, str]]:
    with pytest.raises(FehlerSammlung) as e:
        ir_aus(registry, ziel, schritte)
    return [(f.schritt, f.feld, f.meldung) for f in e.value.fehler]


# --- Validierung ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("roh", "erwartet"),
    [
        ("PC-01, PC-02;PC-03", ["PC-01", "PC-02", "PC-03"]),
        ("C:\\Daten\\A B, C:\\Daten\\C", ["C:\\Daten\\A B", "C:\\Daten\\C"]),  # Leerzeichen bleiben
        (["a", 7, " b "], ["a", "7", "b"]),
        ("a,,b, ", ["a", "b"]),
    ],
)
def test_werte(registry: Registry, roh: Any, erwartet: list[str]) -> None:
    ir = ir_aus(registry, Ziel.BASH, [fuer_jeden(roh, [meldung("x")])])
    knoten = ir.schritte[0]
    assert isinstance(knoten, FuerJeden) and knoten.werte == erwartet


@pytest.mark.parametrize(
    ("roh", "teil"),
    [
        ("", "mindestens einen Wert"),
        (None, "mindestens einen Wert"),
        (",;", "mindestens einen Wert"),
        ([True], "kein Text"),
        ("a\u202eb", "Wert 1"),
        (",".join(str(i) for i in range(MAX_SCHLEIFENWERTE + 1)), f"Höchstens {MAX_SCHLEIFENWERTE}"),
    ],
)
def test_werte_ungueltig(registry: Registry, roh: Any, teil: str) -> None:
    meldungen = fehler(registry, Ziel.BASH, [fuer_jeden(roh, [meldung("x")])])
    assert any(feld == "werte" and teil in m for _, feld, m in meldungen), meldungen


def test_leerer_rumpf(registry: Registry) -> None:
    meldungen = fehler(registry, Ziel.BASH, [fuer_jeden("a", [])])
    assert (0, None, "„Für jeden Wert“ braucht mindestens einen Schritt.") in meldungen


def test_jeder_wert_wird_gegen_den_parametertyp_geprueft(registry: Registry) -> None:
    schritte = [fuer_jeden("1.1.1.1, nicht gültig!", [blk("ping", ziel=WERT, anzahl=1)])]
    [(schritt, feld, m)] = fehler(registry, Ziel.BASH, schritte)
    assert (schritt, feld) == (1, "ziel")
    assert m.startswith("Ziel") and "Wert 2 („nicht gültig!“) aus der Liste passt nicht" in m
    # Option-Injection über den Schleifenwert
    [(_, _, m)] = fehler(registry, Ziel.BASH, [fuer_jeden("-oProxyCommand=x", [blk("ping", ziel=WERT)])])
    assert "Wert 1" in m
    # Zielprüfung: Windows-Pfad in bash
    [(_, _, m)] = fehler(registry, Ziel.BASH, [fuer_jeden("C:\\Daten", [blk("ordner_anlegen", pfad=WERT)])])
    assert "Wert 1" in m and "Linux/macOS" in m


def test_schleifenwert_nur_in_schleife_und_passenden_feldern(registry: Registry) -> None:
    [(_, feld, m)] = fehler(registry, Ziel.BASH, [blk("ping", ziel=WERT)])
    assert feld == "ziel" and "nur innerhalb von „Für jeden Wert“" in m
    [(_, feld, m)] = fehler(registry, Ziel.BASH, [fuer_jeden("true", [blk("meldung", text="x", pause=WERT)])])
    assert feld == "pause" and "keinen Wert aus der Liste" in m
    # Kein anderes Objekt als {"schleifenwert": true}
    meldungen = fehler(
        registry, Ziel.BASH, [fuer_jeden("a", [blk("meldung", text={"schleifenwert": True, "x": 1})])]
    )
    assert meldungen and meldungen[0][1] == "text"


def test_werte_je_parameter_normalisiert(registry: Registry) -> None:
    """Derselbe Wert wird pro Feld nach dessen Typ normalisiert (hier: MAC-Schreibweise)."""
    ir = ir_aus(
        registry,
        Ziel.BASH,
        [fuer_jeden("00-1a-2b-3c-4d-5e", [blk("wake_on_lan", mac=WERT, broadcast="127.0.0.1")])],
    )
    text = generator_fuer(Ziel.BASH, registry).erzeuge(ir).text
    assert "'00:1A:2B:3C:4D:5E'" in text  # geprüfter Wert im Code
    assert "'00-1a-2b-3c-4d-5e'" not in text  # Rohwert nur in Kopf-/Fortschrittszeile


def test_rueckweg_ir_zu_request(registry: Registry) -> None:
    schritte = [fuer_jeden("a, b", [blk("meldung", text=WERT, pause=False)]), meldung("Ende")]
    ir = ir_aus(registry, Ziel.BASH, schritte)
    erneut = validiere_request(ir_zu_request(ir, Ziel.BASH), registry, autor="pytest", jetzt=FESTE_ZEIT)
    assert erneut.schritte == ir.schritte


# --- Generierung & Ausführung --------------------------------------------------------------------


def test_cmd_ausgerollt_ohne_for(registry: Registry, tmp_path: Path) -> None:
    schritte = [fuer_jeden("C:\\A B, C:\\100% & mehr", [blk("ordner_anlegen", pfad=WERT)])]
    s = generator_fuer(Ziel.CMD, registry).erzeuge(ir_aus(registry, Ziel.CMD, schritte))
    text = s.text
    assert 'mkdir "C:\\A B"' in text and 'mkdir "C:\\100%% & mehr"' in text
    assert "echo(--- Wert 2 von 2: C:\\100%% ^& mehr ---" in text
    # Werte stehen als Literale in den Schritten, nie in einer for-Schleife
    assert not [z for z in text.splitlines() if z.lstrip().startswith("for ") and "A B" in z]
    assert syntax.cmd_lint(s.inhalt) == []


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_ausfuehrung_mit_sonderzeichen(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    """Pfade dürfen unter Linux fast alles enthalten – sie landen trotzdem nur als Literal im Code."""
    kanarie = tmp_path / "PWNED"
    namen = ["a b", f"$(touch {kanarie.name})", f"`touch {kanarie.name}`", 'it\'s "x" & | %PATH% $HOME']
    pfade = [str(tmp_path / n) for n in namen]
    schritte = [fuer_jeden(pfade, [blk("ordner_anlegen", pfad=WERT)])]
    s = generator_fuer(ziel, registry).erzeuge(ir_aus(registry, ziel, schritte))
    r = ausfuehren(shell, s.inhalt, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    for i, pfad in enumerate(pfade, 1):
        assert Path(pfad).is_dir(), pfad
        assert f"--- Wert {i} von 4: {pfad} ---" in r.stdout
    assert not kanarie.exists()
    assert "Fertig: 4 Schritte erfolgreich" in r.stdout


def test_ausfuehrung_pwsh(registry: Registry, tmp_path: Path) -> None:
    werte = ["Erster Wert", "it's (x) #1", "Größe: 100 / 2 = 50!"]
    schritte = [fuer_jeden(werte, [blk("meldung", text=WERT, pause=False)])]
    s = generator_fuer(Ziel.POWERSHELL, registry).erzeuge(ir_aus(registry, Ziel.POWERSHELL, schritte))
    r = ausfuehren("pwsh", s.inhalt, tmp_path, env={"TEMP": str(tmp_path)})
    assert r.returncode == 0, r.stdout + r.stderr
    ausgabe = r.stdout.split("--- LOG ---")[0]
    for i, w in enumerate(werte, 1):
        assert f"--- Wert {i} von 3: {w} ---" in ausgabe
        assert re.search(rf"^{re.escape(w)}$", ausgabe, re.M)


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_verschachtelt_mit_rueckgabe_und_wenn(
    registry: Registry, tmp_path: Path, shell: str, ziel: Ziel
) -> None:
    """Innerste Schleife liefert den Wert; Rückgabewerte im Rumpf gelten pro Durchlauf."""
    (tmp_path / "da").write_text("x")
    schritte = [
        fuer_jeden(
            "Runde A, Runde B",
            [
                blk("meldung", text=WERT, pause=False),
                fuer_jeden(
                    f"{tmp_path}/da, {tmp_path}/fehlt",
                    [
                        blk("existiert_pruefen", pfad=WERT),
                        {
                            "art": "wenn",
                            "wert": "2.vorhanden",
                            "vergleich": "ja",
                            "dann": [meldung("OKM-JA")],
                            "sonst": [meldung("OKM-NEIN")],
                        },
                    ],
                ),
            ],
        )
    ]
    s = generator_fuer(ziel, registry).erzeuge(ir_aus(registry, ziel, schritte))
    r = ausfuehren(shell, s.inhalt, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    ausgabe = r.stdout.split("--- LOG ---")[0]
    assert re.findall(r"^(OKM-JA|OKM-NEIN|Runde [AB])$", ausgabe, re.M) == [
        "Runde A",
        "OKM-JA",
        "OKM-NEIN",
        "Runde B",
        "OKM-JA",
        "OKM-NEIN",
    ]


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_fehler_im_durchlauf_in_versuche(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    schritte = [
        fuer_jeden(
            f"{tmp_path}/fehlt, {tmp_path}",
            [versuche([blk("existiert_pruefen", pfad=WERT, abbrechen=True)], [meldung("OKM-AUSWEICH")])],
        ),
        meldung("OKM-ENDE"),
    ]
    s = generator_fuer(ziel, registry).erzeuge(ir_aus(registry, ziel, schritte))
    r = ausfuehren(shell, s.inhalt, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    ausgabe = r.stdout.split("--- LOG ---")[0]
    assert re.findall(r"^OKM-\w+$", ausgabe, re.M) == ["OKM-AUSWEICH", "OKM-ENDE"]


def test_kopf_und_simulation(registry: Registry) -> None:
    schritte = [fuer_jeden("/tmp/a, /tmp/b", [blk("ordner_anlegen", pfad=WERT)])]
    ir = ir_aus(registry, Ziel.BASH, schritte, dry_run=True)
    text = generator_fuer(Ziel.BASH, registry).erzeuge(ir).text
    assert "#   Für jeden Wert (/tmp/a, /tmp/b):" in text
    assert "--- Wert 2 von 2: /tmp/b ---" in text and "'/tmp/b'" in text


# --- Bibliothek: „Erneut öffnen“ in Blockly ------------------------------------------------------


def test_baum_wiederherstellen(registry: Registry) -> None:
    from app.bibliothek import SCHLEIFENWERT_BLOCKLY, baum_wiederherstellen
    from app.db import GespeichertesScript

    ir = ir_aus(registry, Ziel.BASH, [fuer_jeden("a, b", [blk("meldung", text=WERT, pause=False)])])
    eintrag = GespeichertesScript(ir_json=ir.model_dump_json())
    _, baum, hinweise = baum_wiederherstellen(registry, eintrag)
    assert hinweise == []
    assert baum == [
        {
            "art": "fuer_jeden",
            "werte": "a, b",
            "rumpf": [
                {
                    "art": "block",
                    "block_id": "meldung",
                    "parameter": {"text": SCHLEIFENWERT_BLOCKLY, "pause": "false"},
                }
            ],
        }
    ]
