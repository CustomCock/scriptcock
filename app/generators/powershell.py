"""Generator für Windows PowerShell 5.1 (``.ps1``, CRLF, UTF-8 mit BOM).

Kein PS7-only-Syntax (``??``, ``?.``, Ternary, ``-Parallel``)!
Farben nur über ``Write-Host -ForegroundColor`` – nie ANSI-Sequenzen (conhost zeigt sie als Text).
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from app.escaping import Escaped, Ziel, powershell_literal
from app.generators.base import EINZUG, LINIE, PLANMAESSIG, Generator, SchrittInfo, einruecken
from app.ir import ScriptIR, Vergleich
from app.models.block import BlockDef, RueckgabeDef, RueckgabeTyp
from app.regschutz import lade_schutz

# Hilfsfunktionen für Registry-Bausteine (nur im Script, wenn ein Registry-Baustein vorkommt);
# die für Richtlinien/Admin-Werkzeuge nur, wenn ein dynamischer Baustein vorkommt
_HILFEN = Path(__file__).parent / "hilfen"
REGISTRY_HILFEN = (_HILFEN / "registry.ps1").read_text(encoding="utf-8").splitlines()
RICHTLINIEN_HILFEN = (_HILFEN / "richtlinien.ps1").read_text(encoding="utf-8").splitlines()


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
        return [
            "#Requires -Version 5.1",
            *[f"# {z}".rstrip() for z in self.kommentar_zeilen(ir, defs)],
            "param(",
            "    # Am Ende nicht auf Enter warten (für Fernwartung/RMM)",
            "    [switch]$NoPause",
            ")",
            "",
        ]

    def _zusammenfassung(self) -> list[str]:
        if self.mit_kontrolle:
            fertig = "(' Fertig: ' + $script:OkmErfolgreich + ' Schritte erfolgreich ausgeführt.')"
            fehler = "(' Abgebrochen bei Schritt ' + $script:OkmNr + '.')"
            bisher = "(' Erfolgreich bis dahin: ' + $script:OkmErfolgreich + ' Schritte.')"
        else:
            fertig = (
                "(' Fertig: ' + $script:OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.')"
            )
            fehler = "(' Abgebrochen bei Schritt ' + $script:OkmNr + ' von ' + $OkmGesamt + '.')"
            bisher = (
                "(' Erfolgreich bis dahin: ' + $script:OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')"
            )
        return [
            "# Fenster offen halten (Rechtsklick > Mit PowerShell ausführen) – aber nicht mit -NoPause,",
            "# ohne Benutzer, bei umgeleiteter Eingabe oder -NonInteractive (Fernwartung/RMM).",
            "function Wait-OkmEnde {",
            "    if ($OkmKeinePause -or -not [Environment]::UserInteractive) { return }",
            "    try { if ([Console]::IsInputRedirected) { return } } catch { return }",
            "    $OkmArgumente = @([Environment]::GetCommandLineArgs() | Where-Object { $_ -like '-NonI*' })",
            "    if ($OkmArgumente.Count -gt 0) { return }",
            "    [void](Read-Host 'Drücke Enter zum Schließen …')",
            "}",
            "",
            "function Exit-OkmScript {",
            "    param([int]$Code)",
            f"    Write-Host {_lit(LINIE)}",
            "    switch ($script:OkmStatus) {",
            f"        'fertig' {{ Write-Host {fertig} -ForegroundColor Green }}",
            "        'abbruch' {",
            "            Write-Host ' Abgebrochen durch Benutzer. Es wurde nichts weiter ausgeführt.' "
            "-ForegroundColor Yellow",
            "        }",
            "        'neustart' { Write-Host ' Läuft im neuen Fenster mit Administratorrechten weiter.' }",
            *(
                ["        'bit64' { Write-Host ' Lief als 64-Bit-PowerShell (Ausgabe oben).' }"]
                if self.mit_registry
                else []
            ),
            *(
                [
                    "        'beendet' {",
                    f"            Write-Host ({_lit(PLANMAESSIG)} + $script:OkmGrund)",
                    f"            Write-Host {bisher}",
                    "        }",
                ]
                if self.hat_abbrechen
                else []
            ),
            "        'rechte' {",
            "            Write-Host ' Abgebrochen: fehlende Administratorrechte.' -ForegroundColor Red",
            "        }",
            "        default {",
            f"            Write-Host {fehler} -ForegroundColor Red",
            f"            Write-Host {bisher}",
            "        }",
            "    }",
            *(self._registry_hinweise() if self.mit_registry else []),
            "    Write-Host (' Protokoll: ' + $OkmLog)",
            f"    Write-Host {_lit(LINIE)}",
            "    try { Stop-Transcript | Out-Null } catch { $null = $_ }",
            (
                "    if ($script:OkmStatus -notin @('neustart', 'bit64')) { Wait-OkmEnde }"
                if self.mit_registry
                else "    if ($script:OkmStatus -ne 'neustart') { Wait-OkmEnde }"
            ),
            "    exit $Code",
            "}",
        ]

    def praeambel(self, ir: ScriptIR, gesamt: int, braucht_admin: bool) -> list[str]:
        zeilen = [
            "$ErrorActionPreference = 'Stop'",
            "$OkmKeinePause = [bool]$NoPause",
            "# Konsole auf UTF-8: Ausgaben externer Programme (winget, ipconfig, netsh …) werden sonst",
            "# mit der OEM-Codepage gelesen und erscheinen als Zeichensalat (Gr├Â├ƒe statt Größe).",
            "$OkmUtf8 = New-Object System.Text.UTF8Encoding $false",
            "try { [Console]::OutputEncoding = $OkmUtf8 } catch { $null = $_ }",
            "$OutputEncoding = $OkmUtf8",
            "$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))",
            *([] if self.mit_kontrolle else [f"$OkmGesamt = {gesamt}"]),
            "$OkmErfolgreich = 0",
            "$OkmNr = 0",
            "$OkmStatus = 'laeuft'",
            "try { Start-Transcript -Path $OkmLog -Append | Out-Null } "
            "catch { Write-Warning 'Protokoll konnte nicht gestartet werden.' }",
            "",
            "# Meldungen: Werte immer als Argument übergeben, nie in Strings einsetzen",
            "function Write-OkmInfo([string]$Text) { Write-Host $Text }",
            "function Write-OkmOk([string]$Text = '') {",
            f"    if ($Text) {{ Write-Host ({_lit(EINZUG + 'OK  ')} + $Text) -ForegroundColor Green }}",
            f"    else {{ Write-Host {_lit(EINZUG + 'OK')} -ForegroundColor Green }}",
            "}",
            f"function Write-OkmWarnung([string]$Text) {{ Write-Host ({_lit(EINZUG + 'WARNUNG  ')} + $Text) "
            "-ForegroundColor Yellow }",
            f"function Write-OkmFehler([string]$Text) {{ Write-Host ({_lit(EINZUG + 'FEHLER  ')} + $Text) "
            "-ForegroundColor Red }",
            "",
            *self._zusammenfassung(),
            "",
            "# Netz für alles, was kein Schritt abfängt: Meldung + Zusammenfassung statt stillem Ende",
            "trap {",
            "    Write-OkmFehler ('Unerwarteter Fehler: ' + $_.Exception.Message + ' (Zeile ' + "
            "$_.InvocationInfo.ScriptLineNumber + ')')",
            "    $script:OkmStatus = 'fehler'",
            "    Exit-OkmScript 1",
            "}",
            "",
            *[f"Write-OkmInfo {_lit(z)}" for z in self.kopf_ausgabe(ir)],
            "",
        ]
        if self.mit_registry:
            zeilen += self._registry_praeambel()
        zeilen += self._rechte() if braucht_admin else ["Write-OkmInfo 'Rechte: ohne erhöhte Rechte'", ""]
        return zeilen

    def _registry_praeambel(self) -> list[str]:
        gesperrt = ", ".join(_lit("\\".join(teile).upper()) for teile in lade_schutz().gesperrt)
        neustart = (
            "Registry: Das Script läuft als 32-Bit-PowerShell – Neustart als 64-Bit, damit HKLM\\SOFTWARE "
            "nicht in WOW6432Node landet."
        )
        return [
            "# 32-Bit-PowerShell auf 64-Bit-Windows: HKLM\\SOFTWARE würde nach WOW6432Node umgeleitet",
            "if ([Environment]::Is64BitOperatingSystem -and -not [Environment]::Is64BitProcess "
            "-and $PSCommandPath) {",
            "    $OkmPs64 = Join-Path $env:SystemRoot 'Sysnative\\WindowsPowerShell\\v1.0\\powershell.exe'",
            "    if (Test-Path -LiteralPath $OkmPs64) {",
            f"        Write-OkmInfo {_lit(neustart)}",
            "        $OkmArgumente = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "
            "('\"' + $PSCommandPath + '\"'))",
            "        if ($OkmKeinePause) { $OkmArgumente += '-NoPause' }",
            "        $OkmProzess = Start-Process -FilePath $OkmPs64 -ArgumentList $OkmArgumente "
            "-Wait -NoNewWindow -PassThru",
            "        $OkmStatus = 'bit64'",
            "        Exit-OkmScript $OkmProzess.ExitCode",
            "    }",
            "}",
            "",
            "# Gesperrte Registry-Bereiche (registry/schutz.yaml) – gilt auch für importierte .reg-Dateien",
            f"$script:OkmRegGesperrt = @({gesperrt})",
            *REGISTRY_HILFEN,
            *(RICHTLINIEN_HILFEN if self.mit_dynamisch else []),
            "# ===== Ende Registry-Hilfen ============================================================",
            "",
        ]

    def _registry_hinweise(self) -> list[str]:
        rueck = "' Rückgängig machen: die .reg-Dateien in ' + $script:OkmRegSicherung"
        lgpo = [
            "    if ($script:OkmLgpoSicherung) {",
            "        Write-Host (' Gruppenrichtlinie zurück: LGPO.exe /g ' + $script:OkmLgpoSicherung)",
            "    }",
        ]
        return [
            "    if ($script:OkmRegSicherung) {",
            f"        Write-Host ({rueck} + ' doppelklicken (höchste Nummer zuerst).')",
            "    }",
            *(lgpo if self.mit_dynamisch else []),
            "    if ($script:OkmWirkung -gt 0) {",
            "        Write-Host (' Damit die Änderungen wirken: ' + "
            "$script:OkmWirkungText[$script:OkmWirkung]) -ForegroundColor Yellow",
            "    }",
            "    if ($script:OkmWirkungUnbekannt) {",
            "        Write-Host ' Ob alle Änderungen sofort wirken, ist nicht bekannt – im Zweifel "
            "neu anmelden.'",
            "    }",
        ]

    def _rechte(self) -> list[str]:
        """Fehlen Administratorrechte, startet sich das Script per UAC selbst neu."""
        liste = self.schritt_liste(self._admin_schritte)
        kein_pfad = (
            'Bitte PowerShell mit Rechtsklick > "Als Administrator ausführen" öffnen und das Script '
            "erneut starten."
        )
        abgelehnt = (
            "Die Administratorrechte wurden abgelehnt (Benutzerkontensteuerung). Ohne sie kann das "
            "Script nicht weitermachen."
        )
        return [
            f"# Rechte: Administrator für {liste}",
            "$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal("
            "[Security.Principal.WindowsIdentity]::GetCurrent())",
            "if ($OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {",
            "    Write-OkmInfo 'Rechte: als Administrator gestartet'",
            "} else {",
            f"    Write-OkmInfo {_lit(f'Dieses Script braucht Administratorrechte für: {liste}.')}",
            "    if (-not $PSCommandPath) {",
            f"        Write-OkmFehler {_lit(kein_pfad)}",
            "        $OkmStatus = 'rechte'",
            "        Exit-OkmScript 1",
            "    }",
            "    Write-OkmInfo 'Es wird jetzt mit Administratorrechten neu gestartet "
            "(Windows fragt gleich nach).'",
            "    # Pfad in Anführungszeichen: Start-Process quotet Argumente mit Leerzeichen nicht",
            "    $OkmArgumente = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "
            "('\"' + $PSCommandPath + '\"'))",
            "    if ($OkmKeinePause) { $OkmArgumente += '-NoPause' }",
            "    try {",
            "        Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $OkmArgumente "
            "| Out-Null",
            "        $OkmStatus = 'neustart'",
            "        Exit-OkmScript 0",
            "    } catch {",
            f"        Write-OkmFehler {_lit(abgelehnt)}",
            "        $OkmStatus = 'rechte'",
            "        Exit-OkmScript 1",
            "    }",
            "}",
            "",
        ]

    def schritt(self, info: SchrittInfo) -> list[str]:
        b = info.block
        zeilen = [
            "# " + "-" * 68,
            f"# Schritt {info.bezeichnung}: {b.name} (Risiko: {info.risiko.value})",
            "# " + "-" * 68,
            f"$OkmNr = {info.nr}",
            f"Write-OkmInfo {_lit(self.schritt_titel(info))}",
        ]
        if info.vorschau:
            zeilen += [
                "# Vorschau (vor der Bestätigung)",
                ". {",
                *einruecken(info.vorschau, 4),
                "} | Out-Host",
            ]
        if info.bestaetigen:
            warnung = _lit(f"ACHTUNG: Dieser Schritt ist destruktiv: {b.name}")
            zeilen += [
                f"Write-OkmWarnung {warnung}",
                "$OkmAntwort = Read-Host 'Zum Fortfahren JA eingeben (alles andere bricht ab)'",
                "if ($OkmAntwort -cne 'JA') {",
                "    $OkmStatus = 'abbruch'",
                "    Exit-OkmScript 2",
                "}",
            ]
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
        zeilen += einruecken(info.nachher, 4)
        zeilen += [
            "    $OkmErfolgreich++",
            "    Write-OkmOk",
            "} catch {",
            "    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + "
            "$_.InvocationInfo.ScriptLineNumber + ')')",
        ]
        if b.tipp:
            zeilen.append(f"    Write-OkmInfo {_lit(EINZUG + 'Tipp: ' + b.tipp)}")
        if self.im_versuch:
            # Fehler an den umgebenden „Versuche“-Block weitergeben
            zeilen += ["    throw"]
        else:
            zeilen += ["    $OkmStatus = 'fehler'", "    Exit-OkmScript 1"]
        return [*zeilen, "}", ""]

    def wenn_fehler(self, nr: int, versuch: list[str], sonst: list[str]) -> list[str]:
        return [
            f"# ===== Versuche (Block {nr}) =====",
            "try {",
            *einruecken(versuch, 4),
            "} catch {",
            f"    Write-OkmWarnung {_lit(self.meldung_ausweichen(bool(sonst)))}",
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
            f"    Write-OkmInfo ('--- Durchlauf ' + {var} + ' von {anzahl} ---')",
            *einruecken(rumpf, 4),
            "}",
            "",
        ]

    def abschluss(self, ir: ScriptIR) -> list[str]:
        gpupdate = (
            ["# Computer-Richtlinien einmal anwenden", "Invoke-OkmGpupdate"] if self.mit_richtlinien else []
        )
        return [*gpupdate, "$OkmStatus = 'fertig'", "Exit-OkmScript 0"]

    def rueckgaben_vorbelegen(self, rueckgaben: list[tuple[Escaped, RueckgabeDef]]) -> list[str]:
        return [
            "# Rückgabewerte der Schritte (Namen vergibt der Baukasten; $null = unbekannt)",
            *(f"{name} = $null" for name, _ in rueckgaben),
            "",
        ]

    def rueckgabe_normalisieren(self, name: Escaped, r: RueckgabeDef) -> list[str]:
        if r.typ is RueckgabeTyp.ZAHL:
            return [
                f'if ("$({name})" -match \'^-?[0-9]+$\') {{ {name} = [long]"$({name})" }} '
                f"else {{ {name} = $null }}"
            ]
        return [f"if ($null -ne {name}) {{ {name} = @('1', 'true', 'ja') -contains \"$({name})\" }}"]

    _OPERATOR: ClassVar[dict[Vergleich, str]] = {
        Vergleich.GLEICH: "-eq",
        Vergleich.UNGLEICH: "-ne",
        Vergleich.KLEINER: "-lt",
        Vergleich.GROESSER: "-gt",
        Vergleich.KLEINER_GLEICH: "-le",
        Vergleich.GROESSER_GLEICH: "-ge",
    }

    def wenn(
        self,
        nr: int,
        name: str,
        typ: RueckgabeTyp,
        vergleich: Vergleich,
        zahl: int | None,
        text: str,
        dann: list[str],
        sonst: list[str],
    ) -> list[str]:
        v = f"$script:{name}"
        if vergleich is Vergleich.UNBEKANNT:
            bedingung = f"$null -eq {v}"
        elif vergleich is Vergleich.JA:
            bedingung = f"{v} -eq $true"
        elif vergleich is Vergleich.NEIN:
            bedingung = f"{v} -eq $false"
        else:
            bedingung = f"($null -ne {v}) -and ({v} {self._OPERATOR[vergleich]} {int(zahl or 0)})"
        return [
            f"# ===== Wenn {text} (Block {nr}) =====",
            f"if ({bedingung}) {{",
            f"    Write-OkmInfo {_lit('Bedingung erfüllt: ' + text)}",
            *einruecken(dann, 4),
            "} else {",
            f"    Write-OkmInfo {_lit('Bedingung nicht erfüllt: ' + text)}",
            *einruecken(sonst, 4),
            "}",
            f"# ===== Ende Wenn (Block {nr}) =====",
            "",
        ]

    def abbrechen(self, meldung: str, code: int) -> list[str]:
        return [
            f"# ===== Beenden (Exit-Code {code}) =====",
            f"$script:OkmGrund = {_lit(meldung)}",
            "$OkmStatus = 'beendet'",
            f"Exit-OkmScript {int(code)}",
            "",
        ]

    def warten(self, sekunden: int, text: str) -> list[str]:
        return [f"Write-OkmInfo {_lit(text)}", f"Start-Sleep -Seconds {int(sekunden)}", ""]

    def bestaetigung(self, meldung: str) -> list[str]:
        return [
            f"Write-OkmWarnung {_lit(meldung)}",
            "$OkmAntwort = Read-Host 'Zum Fortfahren JA eingeben (alles andere bricht ab)'",
            "if ($OkmAntwort -cne 'JA') {",
            "    $OkmStatus = 'abbruch'",
            "    Exit-OkmScript 2",
            "}",
            "",
        ]

    def kommentar(self, text: str) -> str:
        return f"# Notiz: {text}"
