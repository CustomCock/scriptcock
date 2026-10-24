"""Syntax-Prüfung von Script-Text – dieselben Checks wie in den Tests (``tests/syntax.py``).

Genutzt vom Knopf „Syntax prüfen“ im Editor (``POST /api/script/pruefen``). Die Werkzeuge
**parsen** nur (``bash -n``, ``zsh -n``, shellcheck, PowerShell-Parser + PSScriptAnalyzer);
ausgeführt wird nichts. Fehlt ein Werkzeug, steht das als Hinweis im Ergebnis – es wird nie so
getan, als wäre alles in Ordnung.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.escaping import Ziel
from app.export import _mit_chcp, _normalisiert, exportiere

# Bewusst ausgeschlossene PSScriptAnalyzer-Regeln:
# - PSAvoidUsingWriteHost: die Scripte sind interaktive Konsolen-Scripte
# - PSAvoidUsingComputerNameHardcoded: Rechnernamen sind Benutzereingaben
# - PSAvoidUsingCmdletAliases: SetupDiag-Block soll laut Vorgabe exakt "cd" enthalten
# - PSUseShouldProcessForStateChangingFunctions: Script-interne Hilfsfunktionen (Registry); die
#   Simulation läuft über den Dry-Run des Baukastens (Schalter -Simulation), nicht über -WhatIf
PSSA_AUSNAHMEN = [
    "PSAvoidUsingWriteHost",
    "PSAvoidUsingComputerNameHardcoded",
    "PSAvoidUsingCmdletAliases",
    "PSUseShouldProcessForStateChangingFunctions",
]
ZEITLIMIT = 60  # Sekunden je Werkzeug


@dataclass
class Befund:
    zeile: int | None
    meldung: str
    werkzeug: str


@dataclass
class Pruefergebnis:
    befunde: list[Befund] = field(default_factory=list)
    geprueft: list[str] = field(default_factory=list)  # Werkzeuge, die gelaufen sind
    hinweise: list[str] = field(default_factory=list)  # z. B. fehlende Werkzeuge

    @property
    def ok(self) -> bool:
        return not self.befunde and bool(self.geprueft)


# --- Befehle (auch von den Tests genutzt) ------------------------------------------------


def shellcheck_befehl(programm: str, dateien: list[Path]) -> list[str]:
    return [programm, "-s", "bash", "-S", "warning", "-f", "gcc", *map(str, dateien)]


def pwsh_skript(dateien: list[Path], analyzer: bool = True) -> str:
    """PowerShell-Befehl: Parser (+ PSScriptAnalyzer) für alle Dateien, Ergebnis als JSON."""
    liste = ",".join("'" + str(d).replace("'", "''") + "'" for d in dateien)
    ausnahmen = ",".join(f"'{r}'" for r in PSSA_AUSNAHMEN)
    return f"""
$ergebnis = @()
foreach ($d in @({liste})) {{
    $t = $null; $e = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($d, [ref]$t, [ref]$e)
    foreach ($f in $e) {{
        $z = $f.Extent.StartLineNumber
        $ergebnis += @{{ datei = $d; zeile = $z; art = 'PARSER'; meldung = $f.Message }}
    }}
}}
$hatPssa = [bool](Get-Module -ListAvailable PSScriptAnalyzer)
if ({"$true" if analyzer else "$false"} -and $hatPssa) {{
    foreach ($d in @({liste})) {{
        foreach ($f in (Invoke-ScriptAnalyzer -Path $d -Severity Error,Warning -ExcludeRule {ausnahmen})) {{
            $m = $f.RuleName + ': ' + $f.Message
            $ergebnis += @{{ datei = $d; zeile = $f.Line; art = 'PSSA'; meldung = $m }}
        }}
    }}
}}
@{{ fehler = @($ergebnis); pssa = $hatPssa }} | ConvertTo-Json -Compress -Depth 4
"""


def pwsh_auswerten(stdout: str) -> tuple[list[dict[str, object]], bool]:
    daten = json.loads(stdout.strip().splitlines()[-1])
    fehler = daten.get("fehler") or []
    if isinstance(fehler, dict):
        fehler = [fehler]
    return fehler, bool(daten.get("pssa"))


# --- CMD: kein Parser unter Linux, daher Regeln ----------------------------------------------


def cmd_lint(inhalt: bytes) -> list[str]:
    probleme = []
    if inhalt.startswith(b"\xef\xbb\xbf"):
        probleme.append("CMD-Datei darf keine BOM haben")
    text = inhalt.decode("utf-8")
    if "\n" in text.replace("\r\n", ""):
        probleme.append("Zeilenenden müssen CRLF sein")
    zeilen = text.split("\r\n")
    if zeilen[0] != "@echo off" or len(zeilen) < 2 or zeilen[1] != "chcp 65001 >nul":
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
            # Absichtliche Umgebungsvariablen (%USERPROFILE%, %OKM_LOG% …) sind erlaubt;
            # gesucht werden einzelne % aus Parameterwerten (die müssten %% sein).
            ohne = re.sub(r"%[A-Za-z_][A-Za-z0-9_]*%", "", ohne)
            ohne = re.sub(r"%~?[a-z]*[0-9]", "", ohne)  # Script-Argumente/-Pfad (%1, %~1, %~f0)
            if "%" in ohne and not zeile.lstrip().lower().startswith(("rem", "for /f")):
                probleme.append(f"Zeile {nr}: einzelnes % in Argument: {zeile}")
    return probleme


# --- Prüfung eines Textes -------------------------------------------------------------------


def _ausfuehren(befehl: list[str], ordner: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        befehl,
        capture_output=True,
        text=True,
        cwd=ordner,
        timeout=ZEITLIMIT,
        env=_umgebung(ordner),
    )


def _umgebung(ordner: Path) -> dict[str, str]:
    """Schlanke Umgebung; HOME/PSModulePath bleiben, damit benutzerweit installierte Module
    (PSScriptAnalyzer per ``Install-Module -Scope CurrentUser``) gefunden werden."""
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "LANG": "C.UTF-8"}
    env["HOME"] = os.environ.get("HOME", str(ordner))
    if "PSModulePath" in os.environ:
        env["PSModulePath"] = os.environ["PSModulePath"]
    return env


def _zeilen_befunde(ausgabe: str, muster: str, werkzeug: str) -> list[Befund]:
    befunde = []
    for zeile in ausgabe.splitlines():
        m = re.search(muster, zeile)
        if m:
            befunde.append(Befund(int(m.group(1)), m.group(2).strip(), werkzeug))
        elif zeile.strip():
            befunde.append(Befund(None, zeile.strip(), werkzeug))
    return befunde


def pruefe(text: str, ziel: Ziel) -> Pruefergebnis:
    """Prüft ``text`` mit den Werkzeugen des Ziels. Zeilennummern beziehen sich auf den Text."""
    erg = Pruefergebnis()
    inhalt = exportiere(text, ziel)
    if ziel is Ziel.CMD:
        erg.geprueft.append("CMD-Regeln")
        # Fehlt „chcp 65001“, ergänzt der Export es – Dateizeilen danach sind im Editor eine weiter oben.
        zeilen = _normalisiert(text)
        echo_off = bool(zeilen) and zeilen[0].strip().lower() == "@echo off"
        chcp_zeile = None if _mit_chcp(zeilen) is zeilen else (2 if echo_off else 1)
        for p in cmd_lint(inhalt):
            m = re.match(r"Zeile (\d+): (.*)", p)
            nr = int(m.group(1)) if m else None
            if nr is not None and chcp_zeile is not None:
                nr = None if nr == chcp_zeile else nr - (nr > chcp_zeile)
            erg.befunde.append(Befund(nr, m.group(2) if m else p, "CMD-Regeln"))
        erg.hinweise.append(
            "Für CMD gibt es unter Linux keinen echten Parser – geprüft werden die Baukasten-Regeln."
        )
        return erg

    with tempfile.TemporaryDirectory(prefix="okm-pruefen-") as tmp:
        ordner = Path(tmp)
        datei = ordner / ("script.ps1" if ziel is Ziel.POWERSHELL else "script.sh")
        datei.write_bytes(inhalt)

        def fehlt(name: str) -> None:
            erg.hinweise.append(f"{name} ist auf dem Server nicht installiert – diese Prüfung fehlt.")

        try:
            if ziel is Ziel.BASH:
                if (bash := shutil.which("bash")) is None:
                    fehlt("bash")
                else:
                    r = _ausfuehren([bash, "-n", str(datei)], ordner)
                    erg.geprueft.append("bash -n")
                    erg.befunde += _zeilen_befunde(r.stderr, r"line (\d+): (.*)", "bash -n")
                if (sc := shutil.which("shellcheck")) is None:
                    fehlt("shellcheck")
                else:
                    r = _ausfuehren(shellcheck_befehl(sc, [datei]), ordner)
                    erg.geprueft.append("shellcheck")
                    erg.befunde += _zeilen_befunde(r.stdout, r":(\d+):\d+: (.*)", "shellcheck")
            elif ziel is Ziel.ZSH:
                if (zsh := shutil.which("zsh")) is None:
                    fehlt("zsh")
                else:
                    r = _ausfuehren([zsh, "-n", str(datei)], ordner)
                    erg.geprueft.append("zsh -n")
                    erg.befunde += _zeilen_befunde(r.stderr, r"script\.sh:(\d+): (.*)", "zsh -n")
            else:
                if (pwsh := shutil.which("pwsh")) is None:
                    fehlt("PowerShell (pwsh)")
                else:
                    r = _ausfuehren(
                        [pwsh, "-NoProfile", "-NonInteractive", "-Command", pwsh_skript([datei])], ordner
                    )
                    fehler, pssa = pwsh_auswerten(r.stdout)
                    erg.geprueft.append("PowerShell-Parser")
                    if pssa:
                        erg.geprueft.append("PSScriptAnalyzer")
                    else:
                        fehlt("Das Modul PSScriptAnalyzer")
                    for f in fehler:
                        werkzeug = "PSScriptAnalyzer" if f.get("art") == "PSSA" else "PowerShell-Parser"
                        zeile = f.get("zeile")
                        erg.befunde.append(
                            Befund(
                                int(zeile) if isinstance(zeile, int) else None, str(f["meldung"]), werkzeug
                            )
                        )
        except subprocess.TimeoutExpired:
            erg.hinweise.append("Die Prüfung hat zu lange gedauert und wurde abgebrochen.")
        except (OSError, ValueError, KeyError) as e:
            erg.hinweise.append(f"Prüfwerkzeug konnte nicht ausgeführt werden: {e}")
    # PowerShell-Datei beginnt mit BOM – Zeilennummern bleiben gleich; bash/zsh sowieso
    return erg
