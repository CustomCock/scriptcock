"""Externe Syntax-Prüfer. Fehlt ein Werkzeug, wird der Test mit Hinweis übersprungen."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

# Bewusst ausgeschlossene PSScriptAnalyzer-Regeln (siehe CLAUDE.md):
# - PSAvoidUsingWriteHost: die Scripte sind interaktive Konsolen-Scripte
# - PSAvoidUsingComputerNameHardcoded: Rechnernamen sind Benutzereingaben
# - PSAvoidUsingCmdletAliases: SetupDiag-Block soll laut Vorgabe exakt "cd" enthalten
PSSA_AUSNAHMEN = [
    "PSAvoidUsingWriteHost",
    "PSAvoidUsingComputerNameHardcoded",
    "PSAvoidUsingCmdletAliases",
]


def werkzeug(name: str) -> str:
    pfad = shutil.which(name)
    if pfad is None:
        pytest.skip(f"{name} ist nicht installiert – Syntax-Check übersprungen")
    return pfad


def bash_n(datei: Path) -> None:
    r = subprocess.run([werkzeug("bash"), "-n", str(datei)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def zsh_n(datei: Path) -> None:
    r = subprocess.run([werkzeug("zsh"), "-n", str(datei)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def shellcheck(dateien: list[Path]) -> None:
    r = subprocess.run(
        [werkzeug("shellcheck"), "-s", "bash", "-S", "warning", "-f", "gcc", *map(str, dateien)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def pwsh_pruefen(dateien: list[Path], analyzer: bool = True) -> None:
    """Parser-Check (+ PSScriptAnalyzer) für alle Dateien in einem pwsh-Aufruf."""
    pwsh = werkzeug("pwsh")
    liste = ",".join("'" + str(d).replace("'", "''") + "'" for d in dateien)
    ausnahmen = ",".join(f"'{r}'" for r in PSSA_AUSNAHMEN)
    befehl = f"""
$ergebnis = @()
foreach ($d in @({liste})) {{
    $t = $null; $e = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($d, [ref]$t, [ref]$e)
    foreach ($f in $e) {{ $ergebnis += "PARSER ${{d}}:$($f.Extent.StartLineNumber): $($f.Message)" }}
}}
$hatPssa = [bool](Get-Module -ListAvailable PSScriptAnalyzer)
if ({"$true" if analyzer else "$false"} -and $hatPssa) {{
    foreach ($d in @({liste})) {{
        foreach ($f in (Invoke-ScriptAnalyzer -Path $d -Severity Error,Warning -ExcludeRule {ausnahmen})) {{
            $ergebnis += "PSSA ${{d}}:$($f.Line): $($f.RuleName): $($f.Message)"
        }}
    }}
}}
@{{ fehler = $ergebnis; pssa = $hatPssa }} | ConvertTo-Json -Compress
"""
    r = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", befehl], capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    daten = json.loads(r.stdout.strip().splitlines()[-1])
    fehler = daten["fehler"] or []
    if isinstance(fehler, str):
        fehler = [fehler]
    assert not fehler, "\n".join(fehler)


# --- CMD: kein Parser unter Linux, daher Lint-Regeln --------------------------


def cmd_lint(inhalt: bytes) -> list[str]:
    probleme = []
    if inhalt.startswith(b"\xef\xbb\xbf"):
        probleme.append("CMD-Datei darf keine BOM haben")
    text = inhalt.decode("utf-8")
    if "\n" in text.replace("\r\n", ""):
        probleme.append("Zeilenenden müssen CRLF sein")
    zeilen = text.split("\r\n")
    if zeilen[0] != "@echo off" or zeilen[1] != "chcp 65001 >nul":
        probleme.append("Script muss mit '@echo off' und 'chcp 65001 >nul' beginnen")
    if not any("DisableDelayedExpansion" in z for z in zeilen[:5]):
        probleme.append("Delayed Expansion muss abgeschaltet sein")
    for nr, zeile in enumerate(zeilen, 1):
        if re.search(r"(?i)EnableDelayedExpansion", zeile):
            probleme.append(f"Zeile {nr}: EnableDelayedExpansion")
        # In gequoteten Argumenten darf kein einzelnes % stehen (muss %% sein),
        # außer bei bekannten Variablen des Generators bzw. %%X-Schleifenvariablen.
        if zeile == 'set "OKM_ANTWORT=%OKM_ANTWORT:"=%"':  # Quotes aus der Antwort entfernen
            continue
        for arg in re.findall(r'"([^"]*)"', zeile):
            ohne = re.sub(r"%%", "", arg)
            # Absichtliche Umgebungsvariablen im Template (%USERPROFILE%, %OKM_LOG% …) sind erlaubt;
            # gesucht werden einzelne % aus Parameterwerten (die müssten %% sein).
            ohne = re.sub(r"%[A-Za-z_][A-Za-z0-9_]*%", "", ohne)
            ohne = re.sub(r"%~?[0-9]", "", ohne)  # Script-Argumente (%1, %~1)
            if "%" in ohne and not zeile.lstrip().lower().startswith(("rem", "for /f")):
                probleme.append(f"Zeile {nr}: einzelnes % in Argument: {zeile}")
    return probleme
