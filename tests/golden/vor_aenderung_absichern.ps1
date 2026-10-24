#Requires -Version 5.1
# ======================================================================
# Titel:             Vor riskanter Änderung absichern
# Beschreibung:      Legt einen Windows-Wiederherstellungspunkt an und sichert einen Registry-Schlüssel – bevor Treiber, Registry oder Software geändert werden.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  Administrator (Schritt 1)
# Enthaltene Schritte:
#    1. Wiederherstellungspunkt anlegen [Risiko: gelb, Admin]
#    2. Registry-Schlüssel sichern [Risiko: gelb]
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
$OkmGesamt = 2
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
Write-OkmInfo ' okm Script-Baukasten · Vor riskanter Änderung absichern'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

# Rechte: Administrator für Schritt 1 (Wiederherstellungspunkt anlegen)
$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if ($OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-OkmInfo 'Rechte: als Administrator gestartet'
} else {
    Write-OkmInfo 'Dieses Script braucht Administratorrechte für: Schritt 1 (Wiederherstellungspunkt anlegen).'
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

# Rückgabewerte der Schritte (Namen vergibt der Baukasten; $null = unbekannt)
$script:OkmS1_erstellt = $null

# --------------------------------------------------------------------
# Schritt 1/2: Wiederherstellungspunkt anlegen (Risiko: gelb)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/2] Wiederherstellungspunkt „Vor Änderung durch okm-Script“ wird angelegt ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmVorher = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue).Count
        Checkpoint-Computer -Description 'Vor Änderung durch okm-Script' -RestorePointType MODIFY_SETTINGS -WarningAction SilentlyContinue
        $okmPunkte = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue | Sort-Object -Property SequenceNumber)
        $script:OkmS1_erstellt = $okmPunkte.Count -gt $okmVorher
        if ($script:OkmS1_erstellt) {
            Write-OkmOk ('Wiederherstellungspunkt angelegt: ' + 'Vor Änderung durch okm-Script')
        } elseif ($okmPunkte.Count -gt 0) {
            $okmLetzter = $okmPunkte[-1]
            $okmZeit = $okmLetzter.ConvertToDateTime($okmLetzter.CreationTime)
            if ($okmZeit -lt (Get-Date).AddHours(-24)) { throw 'Es wurde kein Wiederherstellungspunkt angelegt.' }
            Write-OkmWarnung ('Kein neuer Punkt (Windows: höchstens einer pro 24 Stunden). Letzter vom ' + $okmZeit.ToString('dd.MM.yyyy HH:mm') + ': ' + $okmLetzter.Description)
        } else {
            throw 'Es wurde kein Wiederherstellungspunkt angelegt – ist der Computerschutz eingeschaltet?'
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    if ($null -ne $script:OkmS1_erstellt) { $script:OkmS1_erstellt = @('1', 'true', 'ja') -contains "$($script:OkmS1_erstellt)" }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    Write-OkmInfo '      Tipp: Computerschutz prüfen (Systemsteuerung → System → Computerschutz) und den Dienst „Volumeschattenkopie“ (VSS).'
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/2: Registry-Schlüssel sichern (Risiko: gelb)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/2] Registry HKCU:\Software\Microsoft\Office wird gesichert ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmDatei = Join-Path -Path $env:TEMP -ChildPath ('okm-registry-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.reg')
        reg.exe export 'HKCU\Software\Microsoft\Office' $okmDatei /y
        if ($LASTEXITCODE -eq 0) { Write-Host ('Sicherung: ' + $okmDatei) }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    Write-OkmInfo '      Tipp: Gibt es den Schlüssel, und darf in den Zielordner geschrieben werden?'
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

$OkmStatus = 'fertig'
Exit-OkmScript 0
