"""Generator für Windows PowerShell 5.1 (``.ps1``, CRLF, UTF-8 mit BOM).

Kein PS7-only-Syntax (``??``, ``?.``, Ternary, ``-Parallel``)!
"""

from __future__ import annotations

from typing import ClassVar

from app.escaping import Ziel, powershell_literal
from app.generators.base import Generator, SchrittInfo, einruecken
from app.ir import ScriptIR
from app.models.block import BlockDef


def _lit(text: str) -> str:
    return str(powershell_literal(text))


class PowerShellGenerator(Generator):
    ziel: ClassVar[Ziel] = Ziel.POWERSHELL
    endung: ClassVar[str] = ".ps1"
    zeilenende: ClassVar[str] = "\r\n"
    bom: ClassVar[bool] = True

    def ist_kommentar(self, zeile: str) -> bool:
        return zeile.lstrip().startswith("#")

    def kopf(self, ir: ScriptIR, defs: list[BlockDef]) -> list[str]:
        return ["#Requires -Version 5.1", *[f"# {z}".rstrip() for z in self.kommentar_zeilen(ir, defs)], ""]

    def praeambel(self, ir: ScriptIR, gesamt: int, braucht_admin: bool) -> list[str]:
        zeilen = [
            "$ErrorActionPreference = 'Stop'",
            "$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))",
            *([] if self.mit_kontrolle else [f"$OkmGesamt = {gesamt}"]),
            "$OkmErfolgreich = 0",
            "try { Start-Transcript -Path $OkmLog -Append | Out-Null } "
            "catch { Write-Warning 'Protokoll konnte nicht gestartet werden.' }",
            "",
            "function Exit-OkmScript {",
            "    param([int]$Code)",
            "    Write-Host ''",
            "    Write-Host ('Protokoll: ' + $OkmLog)",
            "    try { Stop-Transcript | Out-Null } catch { $null = $_ }",
            "    exit $Code",
            "}",
            "",
        ]
        if ir.optionen.dry_run:
            zeilen += [
                "Write-Host 'NUR SIMULATION: Es wird nichts verändert.' -ForegroundColor Cyan",
                "",
            ]
        if braucht_admin:
            meldung = (
                "Dieses Script braucht Administratorrechte. Bitte PowerShell mit Rechtsklick > "
                '"Als Administrator ausführen" öffnen und das Script erneut starten.'
            )
            zeilen += [
                "# Prüfung: Administratorrechte",
                "$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal("
                "[Security.Principal.WindowsIdentity]::GetCurrent())",
                "if (-not $OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {",
                f"    Write-Host {_lit(meldung)} -ForegroundColor Red",
                "    Exit-OkmScript 1",
                "}",
                "",
            ]
        return zeilen

    def schritt(self, info: SchrittInfo) -> list[str]:
        b = info.block
        zeilen = [
            "# " + "-" * 68,
            f"# Schritt {info.bezeichnung}: {b.name} (Risiko: {b.risiko.value})",
            "# " + "-" * 68,
            f"Write-Host {_lit(f'[{info.bezeichnung}] {info.fortschritt} …')}",
        ]
        if info.bestaetigen:
            warnung = _lit(f"ACHTUNG: Dieser Schritt ist destruktiv: {b.name}")
            zeilen += [
                f"Write-Host {warnung} -ForegroundColor Yellow",
                "$OkmAntwort = Read-Host 'Zum Fortfahren JA eingeben (alles andere bricht ab)'",
                "if ($OkmAntwort -cne 'JA') {",
                "    Write-Host 'Abgebrochen. Es wurde nichts weiter ausgeführt.' -ForegroundColor Yellow",
                "    Exit-OkmScript 2",
                "}",
            ]
        fehlertext = f"FEHLER in Schritt {info.bezeichnung} ({b.name}): "
        zeilen += [
            "try {",
            "    $global:LASTEXITCODE = 0",
            "    . {",
            *einruecken(info.koerper, 8),
            "    } | Out-Host",
            "    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }",
        ]
        if info.pruefung:
            zeilen += [
                "    # Prüfung",
                "    . {",
                *einruecken(info.pruefung, 8),
                "    } | Out-Host",
                "    if ($LASTEXITCODE -ne 0) { throw ('Prüfung endete mit Exit-Code ' + $LASTEXITCODE) }",
            ]
        zeilen += [
            "    $OkmErfolgreich++",
            "} catch {",
            f"    Write-Host ({_lit(fehlertext)} + $_.Exception.Message) -ForegroundColor Red",
        ]
        if self.im_versuch:
            # Fehler an den umgebenden „Versuche“-Block weitergeben
            zeilen += ["    throw"]
        elif self.mit_kontrolle:
            zeilen += [
                "    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' Schritte.')",
                "    Exit-OkmScript 1",
            ]
        else:
            zeilen += [
                "    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + "
                "' Schritten.')",
                "    Exit-OkmScript 1",
            ]
        return [*zeilen, "}", ""]

    def wenn_fehler(self, nr: int, versuch: list[str], sonst: list[str]) -> list[str]:
        return [
            f"# ===== Versuche (Block {nr}) =====",
            "try {",
            *einruecken(versuch, 4),
            "} catch {",
            f"    Write-Host {_lit(self.meldung_ausweichen(bool(sonst)))} -ForegroundColor Yellow",
            *einruecken(sonst, 4),
            "}",
            f"# ===== Ende Versuche (Block {nr}) =====",
            "",
        ]

    def wiederhole(self, nr: int, anzahl: int, rumpf: list[str]) -> list[str]:
        var = f"$OkmDurchlauf{nr}"
        return [
            f"# ===== Wiederhole {anzahl}-mal (Block {nr}) =====",
            f"for ({var} = 1; {var} -le {anzahl}; {var}++) {{",
            f"    Write-Host ('--- Durchlauf ' + {var} + ' von {anzahl} ---') -ForegroundColor Cyan",
            *einruecken(rumpf, 4),
            "}",
            "",
        ]

    def abschluss(self, ir: ScriptIR) -> list[str]:
        if self.mit_kontrolle:
            schluss = "('Fertig, ' + $OkmErfolgreich + ' Schritte erfolgreich ausgeführt.')"
        else:
            schluss = "('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.')"
        return ["Write-Host ''", f"Write-Host {schluss} -ForegroundColor Green", "Exit-OkmScript 0"]
