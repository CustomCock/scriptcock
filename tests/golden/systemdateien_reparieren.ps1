#Requires -Version 5.1
# ======================================================================
# Titel:             Systemdateien reparieren (DISM + SFC)
# Beschreibung:      Repariert beschädigte Windows-Systemdateien. Hilft bei seltsamen Fehlern, Abstürzen von Windows-Komponenten oder fehlgeschlagenen Updates.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  Administrator (Schritt 1)
# Enthaltene Schritte:
#    1. Systemdateien reparieren (DISM + SFC) [Risiko: gelb, Admin]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================
param(
    # Am Ende nicht auf Enter warten (für Fernwartung/RMM)
    [switch]$NoPause
)

$ErrorActionPreference = 'Stop'
$OkmKeinePause = [bool]$NoPause
# Konsole auf UTF-8: Ausgaben externer Programme (winget, ipconfig, netsh …) werden sonst
# mit der OEM-Codepage gelesen und erscheinen als Zeichensalat (Gr├Â├ƒe statt Größe).
$OkmUtf8 = New-Object System.Text.UTF8Encoding $false
try { [Console]::OutputEncoding = $OkmUtf8 } catch { $null = $_ }
$OutputEncoding = $OkmUtf8
$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$OkmGesamt = 1
$OkmErfolgreich = 0
$OkmNr = 0
$OkmStatus = 'laeuft'
try { Start-Transcript -Path $OkmLog -Append | Out-Null } catch { Write-Warning 'Protokoll konnte nicht gestartet werden.' }

# Meldungen: Werte immer als Argument übergeben, nie in Strings einsetzen
function Write-OkmInfo([string]$Text) { Write-Host $Text }
function Write-OkmOk([string]$Text = '') {
    if ($Text) { Write-Host ('      OK  ' + $Text) -ForegroundColor Green }
    else { Write-Host '      OK' -ForegroundColor Green }
}
function Write-OkmWarnung([string]$Text) { Write-Host ('      WARNUNG  ' + $Text) -ForegroundColor Yellow }
function Write-OkmFehler([string]$Text) { Write-Host ('      FEHLER  ' + $Text) -ForegroundColor Red }

# Fenster offen halten (Rechtsklick > Mit PowerShell ausführen) – aber nicht mit -NoPause,
# ohne Benutzer, bei umgeleiteter Eingabe oder -NonInteractive (Fernwartung/RMM).
function Wait-OkmEnde {
    if ($OkmKeinePause -or -not [Environment]::UserInteractive) { return }
    try { if ([Console]::IsInputRedirected) { return } } catch { return }
    $OkmArgumente = @([Environment]::GetCommandLineArgs() | Where-Object { $_ -like '-NonI*' })
    if ($OkmArgumente.Count -gt 0) { return }
    [void](Read-Host 'Drücke Enter zum Schließen …')
}

function Exit-OkmScript {
    param([int]$Code)
    Write-Host '----------------------------------------------'
    switch ($script:OkmStatus) {
        'fertig' { Write-Host (' Fertig: ' + $script:OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green }
        'abbruch' {
            Write-Host ' Abgebrochen durch Benutzer. Es wurde nichts weiter ausgeführt.' -ForegroundColor Yellow
        }
        'neustart' { Write-Host ' Läuft im neuen Fenster mit Administratorrechten weiter.' }
        'rechte' {
            Write-Host ' Abgebrochen: fehlende Administratorrechte.' -ForegroundColor Red
        }
        default {
            Write-Host (' Abgebrochen bei Schritt ' + $script:OkmNr + ' von ' + $OkmGesamt + '.') -ForegroundColor Red
            Write-Host (' Erfolgreich bis dahin: ' + $script:OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
        }
    }
    Write-Host (' Protokoll: ' + $OkmLog)
    Write-Host '----------------------------------------------'
    try { Stop-Transcript | Out-Null } catch { $null = $_ }
    if ($script:OkmStatus -ne 'neustart') { Wait-OkmEnde }
    exit $Code
}

# Netz für alles, was kein Schritt abfängt: Meldung + Zusammenfassung statt stillem Ende
trap {
    Write-OkmFehler ('Unerwarteter Fehler: ' + $_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $script:OkmStatus = 'fehler'
    Exit-OkmScript 1
}

Write-OkmInfo '=============================================='
Write-OkmInfo ' okm Script-Baukasten · Systemdateien reparieren (DISM + SFC)'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

# Rechte: Administrator für Schritt 1 (Systemdateien reparieren (DISM + SFC))
$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if ($OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-OkmInfo 'Rechte: als Administrator gestartet'
} else {
    Write-OkmInfo 'Dieses Script braucht Administratorrechte für: Schritt 1 (Systemdateien reparieren (DISM + SFC)).'
    if (-not $PSCommandPath) {
        Write-OkmFehler 'Bitte PowerShell mit Rechtsklick > "Als Administrator ausführen" öffnen und das Script erneut starten.'
        $OkmStatus = 'rechte'
        Exit-OkmScript 1
    }
    Write-OkmInfo 'Es wird jetzt mit Administratorrechten neu gestartet (Windows fragt gleich nach).'
    # Pfad in Anführungszeichen: Start-Process quotet Argumente mit Leerzeichen nicht
    $OkmArgumente = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
    if ($OkmKeinePause) { $OkmArgumente += '-NoPause' }
    try {
        Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $OkmArgumente | Out-Null
        $OkmStatus = 'neustart'
        Exit-OkmScript 0
    } catch {
        Write-OkmFehler 'Die Administratorrechte wurden abgelehnt (Benutzerkontensteuerung). Ohne sie kann das Script nicht weitermachen.'
        $OkmStatus = 'rechte'
        Exit-OkmScript 1
    }
}

# --------------------------------------------------------------------
# Schritt 1/1: Systemdateien reparieren (DISM + SFC) (Risiko: gelb)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/1] Systemdateien werden geprüft und repariert (dauert) ...'
try {
    $global:LASTEXITCODE = 0
    . {
        DISM.exe /Online /Cleanup-Image /RestoreHealth
        if ($LASTEXITCODE -ne 0) { throw ('DISM endete mit Code ' + $LASTEXITCODE) }
        # sfc schreibt umgeleitet UTF-16 (sonst erscheint „S y s t e m“ mit Nullzeichen)
        $OkmKodierung = [Console]::OutputEncoding
        [Console]::OutputEncoding = [System.Text.Encoding]::Unicode
        try { sfc.exe /scannow } finally { [Console]::OutputEncoding = $OkmKodierung }
        if ($LASTEXITCODE -ne 0) { Write-Host 'SFC hat Probleme gemeldet – Details in C:\Windows\Logs\CBS\CBS.log.' -ForegroundColor Yellow }
        $global:LASTEXITCODE = 0
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

$OkmStatus = 'fertig'
Exit-OkmScript 0
