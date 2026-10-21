"""Escaping-Testsuite mit Injection-Payloads.

Jeder Payload muss in allen vier Zielen als harmloser String im Script landen
oder abgelehnt werden. Für bash, zsh und PowerShell wird das mit der echten
Shell geprüft (Round-Trip: Literal ausgeben → muss exakt den Payload ergeben).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app import escaping
from app.escaping import Escaped, UnsicherError, Ziel

PAYLOADS = [
    'test"; Remove-Item C:\\ -Recurse; "',
    "$(rm -rf ~)",
    "`whoami`",
    "a & del /q *",
    "%PATH%",
    "'; drop",
    "it's",
    "\u2018unicode\u2019 \u201cquotes\u201d \u201a\u201b",
    "\u2019; Remove-Item C:\\ -Recurse; \u2019",
    "$env:USERNAME",
    "${HOME}",
    "$((1+1))",
    "a | b",
    "a > b < c",
    "^&^|",
    "!PATH!",
    "\\\\server\\share\\",
    "C:\\temp\\",
    "a;b",
    "*",
    "~",
    "a'b\"c`d$e%f!g^h&i|j<k>l(m)n",
    "ünïcödé € ß",
    "@(1,2)",
    "#kommentar",
    "-rf",
    "$null",
    "' + (Remove-Item C:\\) + '",
    "'\"'\"'",
    "\\'",
    "%%",
    "%~dp0",
    "%1",
    "",
    " ",
]

ABGELEHNT = ["a\nb", "a\rb", "a\x00b", "\t", "a\u2028b", "a\u2029b", "a\u202eb", "a\x1bb", "a\x85b"]


@pytest.mark.parametrize("payload", ABGELEHNT)
@pytest.mark.parametrize("ziel", list(Ziel))
def test_steuerzeichen_werden_abgelehnt(ziel: Ziel, payload: str) -> None:
    with pytest.raises(UnsicherError):
        escaping.literal(ziel, payload)


@pytest.mark.parametrize("payload", PAYLOADS)
def test_powershell_literal_aufbau(payload: str) -> None:
    lit = escaping.powershell_literal(payload)
    assert isinstance(lit, Escaped)
    assert lit.startswith("'") and lit.endswith("'")
    innen = lit[1:-1]
    # Jedes Single-Quote-Zeichen (inkl. Unicode-Varianten) kommt nur verdoppelt vor.
    for q in "'\u2018\u2019\u201a\u201b":
        assert all(len(m) % 2 == 0 for m in re.findall(re.escape(q) + "+", innen))


@pytest.mark.parametrize("payload", PAYLOADS)
def test_sh_literal_aufbau(payload: str) -> None:
    lit = escaping.sh_literal(payload)
    assert lit.startswith("'") and lit.endswith("'")
    # Nach Entfernen der '\''-Sequenzen darf kein ' mehr innen stehen.
    assert "'" not in lit[1:-1].replace("'\\''", "")


def _cmd_dekodieren(lit: str) -> str:
    """Modell der CMD-Verarbeitung eines gequoteten Arguments in einer Batch-Datei."""
    assert lit.startswith('"') and lit.endswith('"')
    innen = lit[1:-1]
    assert '"' not in innen, "Quote im Inneren würde den Quote-Modus verlassen"
    assert re.fullmatch(r"(?:[^%]|%%)*", innen), "einzelnes % würde Variablen expandieren"
    return innen.replace("%%", "%")


@pytest.mark.parametrize("payload", PAYLOADS)
def test_cmd_literal_harmlos_oder_abgelehnt(payload: str) -> None:
    if '"' in payload:
        with pytest.raises(UnsicherError):
            escaping.cmd_literal(payload)
        return
    lit = escaping.cmd_literal(payload)
    dekodiert = _cmd_dekodieren(lit)
    assert dekodiert.rstrip("\\") == payload.rstrip("\\")
    # Abschließende Backslashes werden verdoppelt (MSVCRT würde sonst das Quote escapen).
    if payload.endswith("\\"):
        assert dekodiert.endswith("\\\\")


@pytest.mark.parametrize("text", [*PAYLOADS, "Fertig (100%) & weiter > Datei", 'mit "Quotes"'])
def test_echo_cmd(text: str) -> None:
    zeile = escaping.echo_cmd(text)
    assert zeile.startswith("echo(")
    rest = zeile[len("echo(") :]
    # Jedes Sonderzeichen steht mit Caret; Prozent ist verdoppelt.
    ausgabe = []
    i = 0
    while i < len(rest):
        z = rest[i]
        if z == "^":
            assert rest[i + 1] in '^&|<>()"'
            ausgabe.append(rest[i + 1])
            i += 2
            continue
        assert z not in '&|<>()"', f"unescaptes {z!r} in {zeile!r}"
        if z == "%":
            assert rest[i + 1] == "%"
            ausgabe.append("%")
            i += 2
            continue
        ausgabe.append(z)
        i += 1
    assert "".join(ausgabe) == text


def test_kommentar_text_cmd_entschaerft() -> None:
    text = escaping.kommentar_text(Ziel.CMD, 'a % b ^ & c | d " e !')
    assert not set(text) & set('%^&|"!')


def test_zahl_lehnt_bool_ab() -> None:
    with pytest.raises(UnsicherError):
        escaping.zahl(True)  # type: ignore[arg-type]
    assert escaping.zahl(42) == "42"


def test_wahrheitswert_ist_bedingung() -> None:
    assert not escaping.wahrheitswert(Ziel.BASH, False)
    assert escaping.wahrheitswert(Ziel.POWERSHELL, True) == "$true"
    assert not escaping.leer()


# --- Round-Trip mit echten Shells ------------------------------------------------


def _shell(name: str) -> str:
    pfad = shutil.which(name)
    if pfad is None:
        pytest.skip(f"{name} ist nicht installiert")
    return pfad


@pytest.mark.parametrize("payload", PAYLOADS)
@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_sh_roundtrip(shell: str, payload: str, tmp_path: Path) -> None:
    kanarie = tmp_path / "PWNED"
    lit = escaping.sh_literal(payload.replace("rm -rf ~", f"touch {kanarie}"))
    erwartet = payload.replace("rm -rf ~", f"touch {kanarie}")
    r = subprocess.run([_shell(shell), "-c", f"printf '%s' {lit}"], capture_output=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert r.stdout.decode("utf-8") == erwartet
    assert not kanarie.exists()


def test_powershell_roundtrip(tmp_path: Path) -> None:
    pwsh = _shell("pwsh")
    kanarie = tmp_path / "PWNED"
    payloads = [p.replace("rm -rf ~", f"New-Item {kanarie}") for p in PAYLOADS]
    zeilen = ["[Console]::OutputEncoding = [System.Text.Encoding]::UTF8"]
    for p in payloads:
        zeilen.append(
            f"[Console]::Out.Write({escaping.powershell_literal(p)}); [Console]::Out.Write([char]0)"
        )
    datei = tmp_path / "rt.ps1"
    datei.write_bytes(b"\xef\xbb\xbf" + "\r\n".join(zeilen).encode("utf-8"))
    r = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-File", str(datei)], capture_output=True, cwd=tmp_path
    )
    assert r.returncode == 0, r.stderr.decode()
    ausgaben = r.stdout.decode("utf-8").split("\0")[:-1]
    assert ausgaben == payloads
    assert not kanarie.exists()


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_echo_sh_roundtrip(shell: str) -> None:
    for text in PAYLOADS:
        r = subprocess.run([_shell(shell), "-c", escaping.echo_sh(text)], capture_output=True)
        assert r.stdout.decode("utf-8") == text + "\n"
