"""Backlog P1: Rückgabewerte von Bausteinen und der Parametertyp ``variable``.

Schema, Registry-Prüfungen, Validierung der Verweise, Generierung für alle Ziele und echte
Ausführung (bash, zsh, pwsh) – auch für die Bausteine mit Rückgabe (mit Attrappen im PATH).
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.escaping import Ziel
from app.generators import generator_fuer
from app.ir import ScriptIR
from app.models.block import BlockDef
from app.models.request import ScriptRequest
from app.registry import Registry, RegistryFehler, _pruefe_block, lade_registry
from app.validation import FehlerSammlung, ir_zu_request, validiere_request
from tests import syntax
from tests.conftest import FESTE_ZEIT
from tests.test_ausfuehrung import SH_ZIELE, ausfuehren

ALLE = {"powershell": "", "cmd": "", "bash": "", "zsh": ""}

SETZEN: dict[str, Any] = {
    "id": "test_setzen",
    "name": "Test: Werte setzen",
    "kategorie": "Test",
    "beschreibung": "Setzt Rückgabewerte",
    "risiko": "gruen",
    "parameter": [
        {"id": "zahl", "label": "Zahl", "typ": "text_kurz", "beispiel": "42"},
        {"id": "ok", "label": "OK", "typ": "text_kurz", "beispiel": "ja"},
    ],
    "rueckgabe": [
        {"id": "wert", "typ": "zahl", "beschreibung": "Eine Zahl"},
        {"id": "ok", "typ": "ja_nein", "beschreibung": "Hat geklappt"},
        {"id": "nur_unix", "typ": "zahl", "beschreibung": "Nur bash/zsh", "ziele": ["bash", "zsh"]},
    ],
    "ziele": {
        "powershell": "{{ rueckgabe_wert }} = {{ zahl }}\n{{ rueckgabe_ok }} = {{ ok }}",
        "cmd": "set {{ rueckgabe_wert }}=42\nset {{ rueckgabe_ok }}=1",
        "bash": "{{ rueckgabe_wert }}={{ zahl }}\n{{ rueckgabe_ok }}={{ ok }}\n{{ rueckgabe_nur_unix }}=7",
        "zsh": "{{ rueckgabe_wert }}={{ zahl }}\n{{ rueckgabe_ok }}={{ ok }}\n{{ rueckgabe_nur_unix }}=7",
    },
}

ZEIGEN: dict[str, Any] = {
    "id": "test_zeigen",
    "name": "Test: Werte zeigen",
    "kategorie": "Test",
    "beschreibung": "Gibt Werte aus",
    "risiko": "gruen",
    "parameter": [
        {"id": "zahl", "label": "Zahl", "typ": "variable", "variable_typ": "zahl"},
        {"id": "ok", "label": "OK", "typ": "variable", "variable_typ": "ja_nein"},
    ],
    "ziele": {
        "powershell": "Write-Output ('OKM-ZAHL=' + {{ zahl }} + ' OKM-OK=' + {{ ok }})",
        "cmd": "echo OKM-ZAHL={{ zahl }} OKM-OK={{ ok }}",
        "bash": "printf 'OKM-ZAHL=%s OKM-OK=%s\\n' {{ zahl }} {{ ok }}",
        "zsh": "printf 'OKM-ZAHL=%s OKM-OK=%s\\n' {{ zahl }} {{ ok }}",
    },
}


def mit_bloecken(*daten: dict[str, Any]) -> Registry:
    reg = lade_registry()
    fehler: list[str] = []
    for d in daten:
        block = BlockDef.model_validate({**d, "quelle": f"test/{d['id']}.yaml"})
        reg.bloecke[block.id] = block
        _pruefe_block(block, reg, fehler)
    if fehler:
        raise RegistryFehler(fehler)
    return reg


@pytest.fixture(scope="module")
def reg() -> Registry:
    return mit_bloecken(SETZEN, ZEIGEN)


def ir_aus(reg: Registry, ziel: Ziel, schritte: list[dict[str, Any]]) -> ScriptIR:
    req = ScriptRequest.model_validate({"ziel": ziel.value, "titel": "Rueckgabe", "schritte": schritte})
    return validiere_request(req, reg, autor="pytest", jetzt=FESTE_ZEIT)


def setzen(zahl: str = "42", ok: str = "ja") -> dict[str, Any]:
    return {"block_id": "test_setzen", "parameter": {"zahl": zahl, "ok": ok}}


def zeigen(zahl: str = "1.wert", ok: str = "1.ok") -> dict[str, Any]:
    return {"block_id": "test_zeigen", "parameter": {"zahl": zahl, "ok": ok}}


def meldung(text: str = "x") -> dict[str, Any]:
    return {"block_id": "meldung", "parameter": {"text": text, "pause": False}}


def fehler_von(reg: Registry, ziel: Ziel, schritte: list[dict[str, Any]]) -> list[str]:
    with pytest.raises(FehlerSammlung) as e:
        ir_aus(reg, ziel, schritte)
    return [f.meldung for f in e.value.fehler]


# --- Schema --------------------------------------------------------------------------------


def _block(**aenderung: Any) -> BlockDef:
    return BlockDef.model_validate({**SETZEN, **aenderung})


def test_schema_rueckgabe() -> None:
    b = _block()
    assert [r.id for r in b.rueckgaben(Ziel.BASH)] == ["wert", "ok", "nur_unix"]
    assert [r.id for r in b.rueckgaben(Ziel.CMD)] == ["wert", "ok"]


@pytest.mark.parametrize(
    ("rueckgabe", "meldung_teil"),
    [
        ([{"id": "x", "typ": "text", "beschreibung": "x"}], "typ"),
        ([{"id": "x", "typ": "zahl"}], "beschreibung"),
        ([{"id": "Gross", "typ": "zahl", "beschreibung": "x"}], "id"),
        (
            [
                {"id": "x", "typ": "zahl", "beschreibung": "a"},
                {"id": "x", "typ": "zahl", "beschreibung": "b"},
            ],
            "doppelt",
        ),
        ([{"id": "x", "typ": "zahl", "beschreibung": "x", "ziele": ["macos"]}], "ziele"),
    ],
)
def test_schema_rueckgabe_fehler(rueckgabe: list[dict[str, Any]], meldung_teil: str) -> None:
    with pytest.raises(ValidationError, match=meldung_teil):
        _block(rueckgabe=rueckgabe, ziele={"powershell": "x", "bash": "x"})


def test_schema_rueckgabe_ziel_ohne_template() -> None:
    with pytest.raises(ValidationError, match="ziele"):
        _block(
            rueckgabe=[{"id": "x", "typ": "zahl", "beschreibung": "x", "ziele": ["cmd"]}],
            ziele={"bash": "{{ rueckgabe_x }}=1"},
        )


def test_schema_parameter_reserviert_und_variable_typ() -> None:
    with pytest.raises(ValidationError, match="reserviert"):
        _block(parameter=[{"id": "rueckgabe_x", "label": "x", "typ": "text_kurz", "beispiel": "a"}])
    with pytest.raises(ValidationError, match="variable_typ"):
        _block(parameter=[{"id": "quelle", "label": "x", "typ": "variable"}])
    with pytest.raises(ValidationError, match="variable_typ"):
        _block(parameter=[{"id": "quelle", "label": "x", "typ": "zahl", "variable_typ": "zahl"}])


def test_registry_rueckgabe_muss_gesetzt_werden() -> None:
    kaputt = {**SETZEN, "id": "test_kaputt", "ziele": {**SETZEN["ziele"], "bash": "{{ rueckgabe_wert }}=1"}}
    with pytest.raises(RegistryFehler, match=r"bash.*rueckgabe_ok"):
        mit_bloecken(kaputt)


def test_registry_rueckgabe_nicht_fuer_ziel() -> None:
    kaputt = {**SETZEN, "id": "test_kaputt2"}
    kaputt["ziele"] = {
        **SETZEN["ziele"],
        "cmd": "set {{ rueckgabe_wert }}=1\nset {{ rueckgabe_ok }}=1\nset {{ rueckgabe_nur_unix }}=1",
    }
    with pytest.raises(RegistryFehler, match="unbekannte Platzhalter: rueckgabe_nur_unix"):
        mit_bloecken(kaputt)


def test_echte_bloecke_mit_rueckgabe(registry: Registry) -> None:
    erwartet = {
        "ping": {"erreichbar", "ms"},
        "port_pruefen": {"offen"},
        "dienst_status": {"laeuft"},
        "festplattenbelegung": {"frei_prozent"},
        "uptime_neustart": {"stunden"},
        "update_status": {"ausstehend"},
        "virenschutz_status": {"aktiv"},
        "bitlocker_status": {"verschluesselt"},
    }
    for block_id, ids in erwartet.items():
        assert {r.id for r in registry.bloecke[block_id].rueckgabe} == ids, block_id


# --- Validierung der Verweise --------------------------------------------------------------


def test_verweis_gueltig_und_roundtrip(reg: Registry) -> None:
    ir = ir_aus(reg, Ziel.BASH, [setzen(), meldung(), zeigen("1.wert", "1.ok")])
    b = list(ir.bloecke())[2]
    assert b.parameter["zahl"].wert == "1.wert"
    assert ScriptIR.model_validate_json(ir.model_dump_json()) == ir
    assert ir_aus(reg, Ziel.BASH, ir_zu_request(ir, Ziel.BASH).model_dump()["schritte"]) == ir


@pytest.mark.parametrize(
    ("schritte", "meldung_teil"),
    [
        ([zeigen("1.wert", "1.ok")], "Schritt 1"),  # Verweis auf sich selbst
        ([zeigen("2.wert", "2.ok"), setzen()], "vor diesem"),  # Schritt danach
        ([setzen(), zeigen("1.gibtsnicht", "1.ok")], "gibtsnicht"),
        ([setzen(), zeigen("1.ok", "1.ok")], "ja/nein"),  # Typ passt nicht (zahl erwartet)
        ([meldung(), zeigen("1.wert", "1.ok")], "liefert keine Werte"),
        ([setzen(), zeigen("frei_prozent", "1.ok")], "Schritt-Nummer"),
        ([setzen(), zeigen("", "1.ok")], "ausgefüllt"),
    ],
)
def test_verweis_fehler(reg: Registry, schritte: list[dict[str, Any]], meldung_teil: str) -> None:
    meldungen = fehler_von(reg, Ziel.BASH, schritte)
    assert any(meldung_teil in m for m in meldungen), meldungen


def test_verweis_rueckgabe_nicht_fuer_ziel(reg: Registry) -> None:
    ir_aus(reg, Ziel.BASH, [setzen(), zeigen("1.nur_unix", "1.ok")])
    meldungen = fehler_von(reg, Ziel.POWERSHELL, [setzen(), zeigen("1.nur_unix", "1.ok")])
    assert any("nicht verfügbar" in m for m in meldungen), meldungen


def test_verweis_aus_versuche_nur_innerhalb(reg: Registry) -> None:
    versuche = {"art": "wenn_fehler", "versuche": [setzen(), zeigen()], "sonst": []}
    ir_aus(reg, Ziel.BASH, [versuche])  # im selben „Versuche“: erlaubt
    meldungen = fehler_von(
        reg, Ziel.BASH, [{"art": "wenn_fehler", "versuche": [setzen()], "sonst": [zeigen()]}]
    )
    assert any("Versuche" in m for m in meldungen), meldungen
    meldungen = fehler_von(reg, Ziel.BASH, [{"art": "wenn_fehler", "versuche": [setzen()]}, zeigen()])
    assert any("Versuche" in m for m in meldungen), meldungen
    # aus einer Schleife heraus: erlaubt (letzter Durchlauf gilt)
    ir_aus(reg, Ziel.BASH, [{"art": "wiederhole", "anzahl": 2, "rumpf": [setzen()]}, zeigen()])


# --- Generierung ---------------------------------------------------------------------------

NAMEN = {
    Ziel.POWERSHELL: ("$script:OkmS1_wert", "$script:OkmS1_wert"),
    Ziel.CMD: ("OKM_S1_WERT", '"%OKM_S1_WERT%"'),
    Ziel.BASH: ("okm_s1_wert", '"$okm_s1_wert"'),
    Ziel.ZSH: ("okm_s1_wert", '"$okm_s1_wert"'),
}


@pytest.mark.parametrize("ziel", list(Ziel))
def test_generierte_namen(reg: Registry, ziel: Ziel) -> None:
    text = generator_fuer(ziel, reg).erzeuge(ir_aus(reg, ziel, [setzen(), zeigen()])).text
    setzen_name, lesen = NAMEN[ziel]
    assert setzen_name in text
    assert lesen in text.split("Schritt 2/2")[1]
    # Vorbelegung vor dem ersten Schritt (bash: set -u)
    vorbelegung = text.index(setzen_name)
    assert vorbelegung < text.index("Schritt 1/2")


@pytest.mark.parametrize("ziel", list(Ziel))
def test_syntax_mit_rueckgabe(reg: Registry, ziel: Ziel, tmp_path: Path) -> None:
    s = generator_fuer(ziel, reg).erzeuge(ir_aus(reg, ziel, [setzen(), zeigen()]))
    datei = tmp_path / ("s" + s.dateiname[s.dateiname.rindex(".") :])
    datei.write_bytes(s.inhalt)
    if ziel is Ziel.BASH:
        syntax.bash_n(datei)
        syntax.shellcheck([datei])
    elif ziel is Ziel.ZSH:
        syntax.zsh_n(datei)
    elif ziel is Ziel.POWERSHELL:
        syntax.pwsh_pruefen([datei])
    else:
        assert syntax.cmd_lint(s.inhalt) == []


# --- Ausführung ----------------------------------------------------------------------------


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
@pytest.mark.parametrize(
    ("zahl", "ok", "erwartet"),
    [
        ("42", "ja", "OKM-ZAHL=42 OKM-OK=1"),
        ("x1", "nein", "OKM-ZAHL= OKM-OK=0"),
        ("007", "true", "OKM-ZAHL=007 OKM-OK=1"),
    ],
)
def test_ausfuehrung_sh(
    reg: Registry, tmp_path: Path, shell: str, ziel: Ziel, zahl: str, ok: str, erwartet: str
) -> None:
    s = generator_fuer(ziel, reg).erzeuge(ir_aus(reg, ziel, [setzen(zahl, ok), zeigen()]))
    r = ausfuehren(shell, s.inhalt, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert erwartet in r.stdout


def test_ausfuehrung_powershell(reg: Registry, tmp_path: Path) -> None:
    s = generator_fuer(Ziel.POWERSHELL, reg).erzeuge(
        ir_aus(reg, Ziel.POWERSHELL, [setzen("42", "ja"), zeigen()])
    )
    r = ausfuehren("pwsh", s.inhalt, tmp_path, env={"TEMP": str(tmp_path)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OKM-ZAHL=42 OKM-OK=True" in r.stdout
    s = generator_fuer(Ziel.POWERSHELL, reg).erzeuge(
        ir_aus(reg, Ziel.POWERSHELL, [setzen("x1", "nein"), zeigen()])
    )
    r = ausfuehren("pwsh", s.inhalt, tmp_path, env={"TEMP": str(tmp_path)})
    assert "OKM-ZAHL= OKM-OK=False" in r.stdout


# --- Echte Bausteine (Attrappen im PATH) -----------------------------------------------------

_SH_ZEIGEN = (
    "okm_z={% if zahl %}{{ zahl }}{% else %}''{% endif %};\n"
    "okm_o={% if ok %}{{ ok }}{% else %}''{% endif %};\n"
    'printf \'OKM-ZAHL=%s OKM-OK=%s\\n\' "$okm_z" "$okm_o"'
)
ZEIGEN_ECHT: dict[str, Any] = {
    "id": "test_wert",
    "name": "Test: Wert zeigen",
    "kategorie": "Test",
    "beschreibung": "Gibt einen Wert aus",
    "risiko": "gruen",
    "parameter": [
        {"id": "zahl", "label": "Zahl", "typ": "variable", "variable_typ": "zahl", "pflicht": False},
        {"id": "ok", "label": "OK", "typ": "variable", "variable_typ": "ja_nein", "pflicht": False},
    ],
    "ziele": {
        "powershell": "$okmZ = {% if zahl %}{{ zahl }}{% else %}$null{% endif %};\n"
        "$okmO = {% if ok %}{{ ok }}{% else %}$null{% endif %};\n"
        "Write-Output ('OKM-ZAHL=' + $okmZ + ' OKM-OK=' + $okmO)",
        "bash": _SH_ZEIGEN,
        "zsh": _SH_ZEIGEN,
    },
}


@pytest.fixture(scope="module")
def reg_echt() -> Registry:
    return mit_bloecken(ZEIGEN_ECHT)


def attrappe(ordner: Path, name: str, inhalt: str) -> None:
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / name
    datei.write_text("#!/bin/sh\n" + inhalt + "\n", encoding="utf-8")
    datei.chmod(0o755)


def wert_von(
    reg: Registry,
    tmp_path: Path,
    shell: str,
    ziel: Ziel,
    schritt: dict[str, Any],
    zahl: str | None = None,
    ok: str | None = None,
    attrappen: dict[str, str] | None = None,
) -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    pfad = tmp_path / "bin"
    pfad.mkdir(exist_ok=True)
    for name, inhalt in (attrappen or {}).items():
        attrappe(pfad, name, inhalt)
    parameter = {k: v for k, v in (("zahl", zahl), ("ok", ok)) if v}
    s = generator_fuer(ziel, reg).erzeuge(
        ir_aus(reg, ziel, [schritt, {"block_id": "test_wert", "parameter": parameter}])
    )
    env = {"PATH": f"{pfad}:{os.environ['PATH']}"}
    if shell == "pwsh":
        env["TEMP"] = str(tmp_path)
    r = ausfuehren(shell, s.inhalt, tmp_path, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    m = re.search(r"OKM-ZAHL=(\S*) OKM-OK=(\S*)", r.stdout)
    assert m, r.stdout
    return f"{m.group(1)}|{m.group(2)}"


PING_OK_LINUX = (
    "echo '4 packets transmitted, 4 received, 0% packet loss, time 3004ms'\n"
    "echo 'rtt min/avg/max/mdev = 11.120/12.640/14.010/1.100 ms'"
)
PING_OK_MAC = (
    "echo '4 packets transmitted, 4 packets received, 0.0% packet loss'\n"
    "echo 'round-trip min/avg/max/stddev = 9.811/10.400/11.002/0.400 ms'"
)
PING_WEG = "echo '4 packets transmitted, 0 received, 100% packet loss'\nexit 1"


@pytest.mark.parametrize(
    ("shell", "ziel", "ausgabe", "ms"),
    [("bash", Ziel.BASH, PING_OK_LINUX, "13"), ("zsh", Ziel.ZSH, PING_OK_MAC, "10")],
)
def test_ping_rueckgabe(
    reg_echt: Registry, tmp_path: Path, shell: str, ziel: Ziel, ausgabe: str, ms: str
) -> None:
    ping = {"block_id": "ping", "parameter": {"ziel": "192.0.2.1", "anzahl": 1}}
    assert (
        wert_von(reg_echt, tmp_path, shell, ziel, ping, "1.ms", "1.erreichbar", {"ping": ausgabe})
        == f"{ms}|1"
    )
    assert (
        wert_von(reg_echt, tmp_path / "b", shell, ziel, ping, "1.ms", "1.erreichbar", {"ping": PING_WEG})
        == "|0"
    )


def test_ping_rueckgabe_powershell(reg_echt: Registry, tmp_path: Path) -> None:
    deutsch = (
        "echo 'Ping-Statistik für 192.0.2.1:'\n"
        "echo 'Antwort von 192.0.2.1: Bytes=32 Zeit=8ms TTL=57'\n"
        "echo '    Pakete: Gesendet = 1, Empfangen = 1, Verloren = 0'\n"
        "echo 'Ca. Zeitangaben in Millisek.:'\n"
        "echo '    Minimum = 7ms, Maximum = 9ms, Mittelwert = 8ms'"
    )
    ping = {"block_id": "ping", "parameter": {"ziel": "192.0.2.1", "anzahl": 1}}
    assert (
        wert_von(
            reg_echt, tmp_path, "pwsh", Ziel.POWERSHELL, ping, "1.ms", "1.erreichbar", {"ping.exe": deutsch}
        )
        == "8|True"
    )
    weg = "echo 'Zielhost nicht erreichbar.'\nexit 1"
    assert (
        wert_von(
            reg_echt, tmp_path / "b", "pwsh", Ziel.POWERSHELL, ping, "1.ms", "1.erreichbar", {"ping.exe": weg}
        )
        == "|False"
    )


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_dienst_status_rueckgabe(reg_echt: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    schritt = {"block_id": "dienst_status", "parameter": {"dienst": "cups"}}
    if ziel is Ziel.BASH:
        laeuft, gestoppt = {"systemctl": "exit 0"}, {"systemctl": "exit 3"}
    else:
        laeuft = {"launchctl": "echo '    state = running'"}
        gestoppt = {"launchctl": "echo '    state = not running'"}
    assert wert_von(reg_echt, tmp_path, shell, ziel, schritt, ok="1.laeuft", attrappen=laeuft) == "|1"
    assert wert_von(reg_echt, tmp_path / "b", shell, ziel, schritt, ok="1.laeuft", attrappen=gestoppt) == "|0"


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_port_pruefen_rueckgabe(reg_echt: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    schritt = {"block_id": "port_pruefen", "parameter": {"ziel": "127.0.0.1", "port": 9}}
    attrappen = {"nc": "exit 1"} if ziel is Ziel.ZSH else {}
    assert wert_von(reg_echt, tmp_path, shell, ziel, schritt, ok="1.offen", attrappen=attrappen) == "|0"
    if ziel is Ziel.ZSH:
        assert (
            wert_von(reg_echt, tmp_path / "b", shell, ziel, schritt, ok="1.offen", attrappen={"nc": "exit 0"})
            == "|1"
        )


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_festplatte_rueckgabe(reg_echt: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    df = (
        'if [ "$1" = "-P" ]; then\n'
        "  echo 'Filesystem 1024-blocks Used Available Capacity Mounted on'\n"
        "  echo '/dev/sda1 1000 870 130 87% /'\n"
        "else echo 'Filesystem Size Used Avail Use% Mounted on'; fi"
    )
    schritt = {"block_id": "festplattenbelegung", "parameter": {}}
    assert (
        wert_von(reg_echt, tmp_path, shell, ziel, schritt, zahl="1.frei_prozent", attrappen={"df": df})
        == "13|"
    )


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_uptime_rueckgabe(reg_echt: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    jetzt = 1_800_000_000
    if ziel is Ziel.BASH:
        if not Path("/proc/uptime").exists():
            pytest.skip("/proc/uptime fehlt")
        attrappen = {"uptime": "echo 'up 2 days'"}
        stunden = int(float(Path("/proc/uptime").read_text().split()[0]) // 3600)
    else:
        attrappen = {
            "sysctl": f"echo '{{ sec = {jetzt - 51 * 3600}, usec = 0 }} Thu Jan  1 00:00:00 2027'",
            "uptime": "echo 'up 2 days'",
            "date": f'if [ "$1" = +%s ]; then echo {jetzt}; else exec /bin/date "$@"; fi',
        }
        stunden = 51
    schritt = {"block_id": "uptime_neustart", "parameter": {}}
    assert (
        wert_von(reg_echt, tmp_path, shell, ziel, schritt, zahl="1.stunden", attrappen=attrappen)
        == f"{stunden}|"
    )


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_update_status_rueckgabe(reg_echt: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    if ziel is Ziel.BASH:
        attrappen = {
            "apt": "echo 'Listing...'\necho 'curl/stable 8.1 amd64 [upgradable from: 8.0]'\n"
            "echo 'vim/stable 9.1 amd64 [upgradable from: 9.0]'",
        }
    else:
        attrappen = {
            "softwareupdate": "echo 'Software Update Tool'\necho 'Software Update found the following new or updated software:'\n"
            "echo '* Label: Safari18.1-18.1'\necho '\tTitle: Safari, Version: 18.1'\n"
            "echo '* Label: macOS 15.1-24B83'\necho '\tTitle: macOS Sequoia 15.1'",
        }
    schritt = {"block_id": "update_status", "parameter": {}}
    assert (
        wert_von(reg_echt, tmp_path, shell, ziel, schritt, zahl="1.ausstehend", attrappen=attrappen) == "2|"
    )


@pytest.mark.parametrize(
    "block_id",
    [
        "virenschutz_status",
        "bitlocker_status",
        "update_status",
        "festplattenbelegung",
        "uptime_neustart",
        "port_pruefen",
        "dienst_status",
    ],
)
def test_powershell_bloecke_setzen_rueckgabe(registry: Registry, block_id: str) -> None:
    """PowerShell-Cmdlets wie Get-BitLockerVolume gibt es unter Linux nicht – hier nur Text + Parser."""
    block = registry.bloecke[block_id]
    s = generator_fuer(Ziel.POWERSHELL, registry).erzeuge(
        ir_aus(
            registry,
            Ziel.POWERSHELL,
            [
                {
                    "block_id": block_id,
                    "parameter": {
                        p.id: (p.beispiel if p.beispiel is not None else p.standard)
                        for p in block.parameter
                        if p.beispiel is not None or p.standard is not None
                    },
                }
            ],
        )
    )
    for r in block.rueckgaben(Ziel.POWERSHELL):
        assert re.search(rf"\$script:OkmS1_{r.id} = ", s.text), r.id
    if shutil.which("pwsh"):
        datei = Path(os.environ.get("TMPDIR", "/tmp")) / f"okm-rueckgabe-{block_id}.ps1"
        datei.write_bytes(s.inhalt)
        try:
            syntax.pwsh_pruefen([datei])
        finally:
            datei.unlink()
