"""Phase 4: Kontrollknoten in der IR („Versuche / Wenn das fehlschlägt“, „Wiederhole N-mal“).

Validierung, Generierung, Syntax-Checks und echte Ausführung (bash, zsh, pwsh).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from app.escaping import Ziel
from app.generators import generator_fuer
from app.ir import ScriptIR, WennFehler, Wiederhole
from app.models.request import ScriptRequest
from app.registry import Registry
from app.validation import MAX_TIEFE, FehlerSammlung, ir_zu_request, validiere_request
from tests import syntax
from tests.conftest import FESTE_ZEIT
from tests.test_ausfuehrung import ausfuehren


def ir_aus(registry: Registry, ziel: Ziel, schritte: list[dict[str, Any]], **kw: Any) -> ScriptIR:
    req = ScriptRequest.model_validate({"ziel": ziel.value, "titel": "Ablauf", "schritte": schritte, **kw})
    return validiere_request(req, registry, autor="pytest", jetzt=FESTE_ZEIT)


def blk(block_id: str, **parameter: Any) -> dict[str, Any]:
    return {"block_id": block_id, "parameter": parameter}


def versuche(versuch: list[dict[str, Any]], sonst: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"art": "wenn_fehler", "versuche": versuch, "sonst": sonst or []}


def wiederhole(anzahl: Any, rumpf: list[dict[str, Any]]) -> dict[str, Any]:
    return {"art": "wiederhole", "anzahl": anzahl, "rumpf": rumpf}


def meldung(text: str) -> dict[str, Any]:
    return blk("meldung", text=text, pause=False)


# --- IR & Validierung ------------------------------------------------------------


def test_ir_baum_und_roundtrip(registry: Registry) -> None:
    ir = ir_aus(
        registry,
        Ziel.BASH,
        [meldung("a"), wiederhole(2, [versuche([meldung("b")], [meldung("c")])])],
    )
    assert ir.hat_kontrolle()
    assert isinstance(ir.schritte[1], Wiederhole)
    assert isinstance(ir.schritte[1].rumpf[0], WennFehler)
    assert [b.parameter["text"].wert for b in ir.bloecke()] == ["a", "b", "c"]
    # JSON-Roundtrip (Speichern in der DB) und Rückweg zum Request
    assert ScriptIR.model_validate_json(ir.model_dump_json()) == ir
    ir2 = validiere_request(ir_zu_request(ir, Ziel.BASH), registry, autor="pytest", jetzt=FESTE_ZEIT)
    assert ir2.schritte == ir.schritte


def test_alte_ir_ohne_kontrolle_bleibt_lesbar() -> None:
    alt = (
        '{"ir_version":1,"meta":{"titel":"x","beschreibung":"","autor":"a","erstellt_am":"2026-01-01T00:00:00",'
        '"baukasten_version":"0.1.0","quelle":"frei"},"optionen":{"dry_run":false,"rot_bestaetigt":false},'
        '"schritte":[{"art":"block","block_id":"systeminfo","block_version":1,"parameter":{}}]}'
    )
    assert ScriptIR.model_validate_json(alt).schritte[0].block_id == "systeminfo"


def test_fehler_positionen_in_vorordnung(registry: Registry) -> None:
    # Positionen: 0 meldung, 1 wiederhole, 2 versuche, 3 ping(fehlerhaft), 4 setupdiag(nicht verfügbar)
    with pytest.raises(FehlerSammlung) as e:
        ir_aus(
            registry,
            Ziel.BASH,
            [meldung("a"), wiederhole(0, [versuche([blk("ping", ziel="$(id)")], [blk("setupdiag")])])],
        )
    positionen = {(f.schritt, f.feld) for f in e.value.fehler}
    assert (1, "anzahl") in positionen
    assert (3, "ziel") in positionen
    assert (4, None) in positionen


@pytest.mark.parametrize(
    ("schritte", "meldung_teil"),
    [
        ([versuche([])], "„Versuche“ braucht mindestens einen Schritt"),
        ([wiederhole(3, [])], "„Wiederhole“ braucht mindestens einen Schritt"),
        ([wiederhole(51, [meldung("x")])], "höchstens 50"),
        ([wiederhole("viele", [meldung("x")])], "ganze Zahl"),
    ],
)
def test_grenzen(registry: Registry, schritte: list[dict[str, Any]], meldung_teil: str) -> None:
    with pytest.raises(Exception) as e:
        ir_aus(registry, Ziel.BASH, schritte)
    assert meldung_teil in str(e.value)


def test_maximale_tiefe(registry: Registry) -> None:
    knoten: dict[str, Any] = meldung("innen")
    for _ in range(MAX_TIEFE + 1):
        knoten = wiederhole(1, [knoten])
    with pytest.raises(FehlerSammlung, match="Ebenen"):
        ir_aus(registry, Ziel.BASH, [knoten])


def test_viele_bloecke_verschachtelt(registry: Registry) -> None:
    with pytest.raises(FehlerSammlung, match="Höchstens 100 Bausteine"):
        ir_aus(registry, Ziel.BASH, [wiederhole(1, [meldung(f"m{i}") for i in range(60)]) for _ in range(2)])


def test_rot_in_verschachtelung_braucht_bestaetigung(registry: Registry) -> None:
    with pytest.raises(FehlerSammlung, match="Ich weiß"):
        ir_aus(registry, Ziel.BASH, [versuche([blk("prozess_beenden", name="x")])])


# --- Generierung & Syntax ----------------------------------------------------------


def beispiel_baum(ziel: Ziel) -> list[dict[str, Any]]:
    windows = ziel in (Ziel.POWERSHELL, Ziel.CMD)
    pfad = "C:\\temp\\okm" if windows else "/tmp/okm-test"
    return [
        meldung("Start"),
        versuche(
            [blk("ordner_anlegen", pfad=pfad), versuche([blk("ping", ziel="10.0.0.1", abbrechen=True)])],
            [meldung("Ausweichen"), wiederhole(2, [blk("prozess_beenden", name="notepad")])],
        ),
        wiederhole(3, [meldung("Schleife"), versuche([blk("dienst_status", dienst="Spooler")], [])]),
        meldung("Ende"),
    ]


@pytest.fixture(scope="module")
def kontroll_scripte(registry: Registry, tmp_path_factory: pytest.TempPathFactory) -> dict[Ziel, Path]:
    ordner = tmp_path_factory.mktemp("kontrolle")
    dateien = {}
    for ziel in Ziel:
        for dry in (False, True):
            ir = ir_aus(registry, ziel, beispiel_baum(ziel), rot_bestaetigt=True, dry_run=dry)
            s = generator_fuer(ziel, registry).erzeuge(ir)
            endung = {Ziel.POWERSHELL: ".ps1", Ziel.CMD: ".cmd", Ziel.BASH: ".sh", Ziel.ZSH: ".zsh"}[ziel]
            pfad = ordner / f"kontrolle{'-dry' if dry else ''}{endung}"
            pfad.write_bytes(s.inhalt)
            if not dry:
                dateien[ziel] = pfad
            else:
                dateien[ziel] = dateien.get(ziel, pfad)
    return dateien


def test_syntax_aller_ziele(kontroll_scripte: dict[Ziel, Path]) -> None:
    ordner = kontroll_scripte[Ziel.BASH].parent
    bash = sorted(ordner.glob("*.sh"))
    for d in bash:
        syntax.bash_n(d)
    syntax.shellcheck(bash)
    for d in ordner.glob("*.zsh"):
        syntax.zsh_n(d)
    for d in ordner.glob("*.cmd"):
        assert syntax.cmd_lint(d.read_bytes()) == [], d.name
    syntax.pwsh_pruefen(sorted(ordner.glob("*.ps1")))


def test_cmd_sprungmarken_konsistent(kontroll_scripte: dict[Ziel, Path]) -> None:
    for d in kontroll_scripte[Ziel.BASH].parent.glob("*.cmd"):
        text = d.read_text(encoding="utf-8")
        labels = re.findall(r"^:(\w+)$", text, flags=re.M)
        assert len(labels) == len(set(labels)), "doppelte Sprungmarke"
        for ziel in re.findall(r"goto :(\w+)", text):
            assert ziel in labels, f"Sprungziel :{ziel} fehlt"
        # Keine for-Schleifen um Schritte (dort würden %VAR% nur einmal expandiert)
        assert "for /L" not in text


def test_kopf_zeigt_struktur(registry: Registry) -> None:
    s = generator_fuer(Ziel.BASH, registry).erzeuge(
        ir_aus(registry, Ziel.BASH, beispiel_baum(Ziel.BASH), rot_bestaetigt=True)
    )
    kopf = s.text.split("Generiert mit")[0]
    assert "#   Versuche:" in kopf and "Wenn das fehlschlägt:" in kopf
    assert "Wiederhole 2-mal:" in kopf and "Fehler darin übergehen." in kopf
    assert re.search(r"#\s+8\. Meldung", kopf)


def test_flache_scripte_unveraendert(registry: Registry) -> None:
    for ziel in Ziel:
        t = generator_fuer(ziel, registry).erzeuge(ir_aus(registry, ziel, [meldung("x")])).text
        assert "Versuche" not in t and "OKM_ZAEHLER" not in t and "Schritten erfolgreich" in t


# --- Ausführung ------------------------------------------------------------------------

SH = [("bash", Ziel.BASH), ("zsh", Ziel.ZSH)]


def script(registry: Registry, ziel: Ziel, schritte: list[dict[str, Any]], **kw: Any) -> bytes:
    return generator_fuer(ziel, registry).erzeuge(ir_aus(registry, ziel, schritte, **kw)).inhalt


def fehlschlag(tmp: Path, ziel: Ziel = Ziel.BASH) -> dict[str, Any]:
    if ziel is Ziel.POWERSHELL:
        return blk("ping", ziel="192.0.2.1", anzahl=1, abbrechen=True)  # ping.exe fehlt unter Linux
    return blk("kopieren", art="datei", quelle=f"{tmp}/gibtsnicht", ziel=f"{tmp}/x")


@pytest.mark.parametrize(("shell", "ziel"), SH)
def test_ausweichschritte_bei_fehler(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    inhalt = script(
        registry,
        ziel,
        [
            meldung("vorher"),
            versuche(
                [
                    blk("ordner_anlegen", pfad=f"{tmp_path}/a"),
                    fehlschlag(tmp_path),
                    blk("ordner_anlegen", pfad=f"{tmp_path}/b"),
                ],
                [meldung("AUSWEICHEN"), blk("ordner_anlegen", pfad=f"{tmp_path}/c")],
            ),
            meldung("danach"),
        ],
    )
    r = ausfuehren(shell, inhalt, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "a").exists() and not (tmp_path / "b").exists() and (tmp_path / "c").exists()
    assert "Schritt 3/7 (Datei/Ordner kopieren) ist fehlgeschlagen" in r.stdout
    assert "es geht mit den Ausweichschritten weiter" in r.stdout
    assert "AUSWEICHEN" in r.stdout and "danach" in r.stdout
    # vorher, a, AUSWEICHEN, c, danach = 5 erfolgreiche Schritte
    assert "Fertig: 5 Schritte erfolgreich ausgeführt." in r.stdout


@pytest.mark.parametrize(("shell", "ziel"), SH)
def test_ohne_fehler_keine_ausweichschritte(
    registry: Registry, tmp_path: Path, shell: str, ziel: Ziel
) -> None:
    inhalt = script(registry, ziel, [versuche([meldung("ok")], [meldung("AUSWEICHEN")]), meldung("danach")])
    r = ausfuehren(shell, inhalt, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "AUSWEICHEN" not in r.stdout.split("--- LOG ---")[0].replace("printf", "")
    assert "Fertig: 2 Schritte erfolgreich ausgeführt." in r.stdout


@pytest.mark.parametrize(("shell", "ziel"), SH)
def test_fehler_ignorieren_und_fehler_in_ausweichschritten(
    registry: Registry, tmp_path: Path, shell: str, ziel: Ziel
) -> None:
    # Leeres "sonst" = Fehler übergehen
    r = ausfuehren(
        shell, script(registry, ziel, [versuche([fehlschlag(tmp_path)]), meldung("weiter")]), tmp_path
    )
    assert r.returncode == 0 and "übergangen" in r.stdout and "weiter" in r.stdout
    # Fehler in den Ausweichschritten bricht das Script ab
    inhalt = script(
        registry,
        ziel,
        [versuche([fehlschlag(tmp_path)], [fehlschlag(tmp_path)]), meldung("NIE")],
    )
    r = ausfuehren(shell, inhalt, tmp_path)
    assert r.returncode != 0
    assert "Abgebrochen bei Schritt 2." in r.stdout
    assert "NIE" not in r.stdout.split("--- LOG ---")[0]


@pytest.mark.parametrize(("shell", "ziel"), SH)
def test_verschachtelte_versuche(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    inhalt = script(
        registry,
        ziel,
        [
            versuche(
                [versuche([fehlschlag(tmp_path)], [meldung("INNEN")]), fehlschlag(tmp_path), meldung("NIE")],
                [meldung("AUSSEN")],
            ),
            meldung("ENDE"),
        ],
    )
    r = ausfuehren(shell, inhalt, tmp_path)
    out = r.stdout.split("--- LOG ---")[0]
    assert r.returncode == 0, r.stdout + r.stderr
    assert out.index("INNEN") < out.index("AUSSEN") < out.index("ENDE")
    assert "NIE" not in out


@pytest.mark.parametrize(("shell", "ziel"), SH)
def test_rote_abfrage_in_versuch_bricht_alles_ab(
    registry: Registry, tmp_path: Path, shell: str, ziel: Ziel
) -> None:
    inhalt = script(
        registry,
        ziel,
        [versuche([blk("prozess_beenden", name="okmgibtsnicht")], [meldung("AUSWEICHEN")]), meldung("NIE")],
        rot_bestaetigt=True,
    )
    r = ausfuehren(shell, inhalt, tmp_path, eingabe="nein\n")
    out = r.stdout.split("--- LOG ---")[0]
    assert r.returncode == 2, r.stdout + r.stderr
    assert "Abgebrochen" in out and "AUSWEICHEN" not in out and "NIE" not in out


@pytest.mark.parametrize(("shell", "ziel"), SH)
def test_wiederhole(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    inhalt = script(
        registry,
        ziel,
        [wiederhole(3, [meldung("RUNDE"), versuche([fehlschlag(tmp_path)])]), meldung("ENDE")],
    )
    r = ausfuehren(shell, inhalt, tmp_path)
    out = r.stdout.split("--- LOG ---")[0]
    assert r.returncode == 0, r.stdout + r.stderr
    assert out.count("RUNDE\n") == 3
    assert "--- Durchlauf 3 von 3 ---" in out
    assert "Fertig: 4 Schritte erfolgreich ausgeführt." in out


def test_powershell_ablauf(registry: Registry, tmp_path: Path) -> None:
    inhalt = script(
        registry,
        Ziel.POWERSHELL,
        [
            wiederhole(2, [meldung("RUNDE")]),
            versuche([fehlschlag(tmp_path, Ziel.POWERSHELL), meldung("NIE")], [meldung("AUSWEICHEN")]),
            versuche([fehlschlag(tmp_path, Ziel.POWERSHELL)]),
            meldung("ENDE"),
        ],
    )
    r = ausfuehren("pwsh", inhalt, tmp_path, env={"TEMP": str(tmp_path)})
    out = r.stdout.split("--- LOG ---")[0]
    assert r.returncode == 0, r.stdout + r.stderr
    assert out.count("RUNDE") == 2 and "--- Durchlauf 2 von 2 ---" in out
    assert "AUSWEICHEN" in out and "NIE" not in out and "übergangen" in out and "ENDE" in out
    assert "Fertig: 4 Schritte erfolgreich ausgeführt." in out


def test_powershell_fehler_in_ausweichschritten(registry: Registry, tmp_path: Path) -> None:
    f = fehlschlag(tmp_path, Ziel.POWERSHELL)
    r = ausfuehren(
        "pwsh",
        script(registry, Ziel.POWERSHELL, [versuche([f], [f]), meldung("NIE")]),
        tmp_path,
        env={"TEMP": str(tmp_path)},
    )
    assert r.returncode == 1
    assert "NIE" not in r.stdout.split("--- LOG ---")[0]
