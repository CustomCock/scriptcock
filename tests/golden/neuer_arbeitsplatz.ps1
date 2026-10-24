#Requires -Version 5.1
# ======================================================================
# Titel:             Neuer Arbeitsplatz einrichten
# Beschreibung:      Gibt einem neuen Rechner seinen Namen, stellt die Uhrzeit richtig und installiert die Standardsoftware. Danach einmal neu starten.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  Administrator (Schritt 1, 2)
# Enthaltene Schritte:
#    1. Rechner umbenennen [Risiko: gelb, Admin]
#    2. Uhrzeit synchronisieren [Risiko: gelb, Admin]
#    3. Mehrere Pakete installieren [Risiko: gelb]
#    4. Meldung/Pause für den Benutzer [Risiko: gruen]
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
$OkmGesamt = 4
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
Write-OkmInfo ' okm Script-Baukasten · Neuer Arbeitsplatz einrichten'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

# Rechte: Administrator für Schritt 1 (Rechner umbenennen), Schritt 2 (Uhrzeit synchronisieren)
$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if ($OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-OkmInfo 'Rechte: als Administrator gestartet'
} else {
    Write-OkmInfo 'Dieses Script braucht Administratorrechte für: Schritt 1 (Rechner umbenennen), Schritt 2 (Uhrzeit synchronisieren).'
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
$script:OkmS3_fehlgeschlagen = $null

# --------------------------------------------------------------------
# Schritt 1/4: Rechner umbenennen (Risiko: gelb)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/4] Rechner wird in PC-EMPFANG-01 umbenannt ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Rename-Computer -NewName 'PC-EMPFANG-01' -Force
        Write-Host 'Der neue Name gilt nach dem nächsten Neustart.' -ForegroundColor Yellow
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    Write-OkmInfo '      Tipp: Ist der Rechner Mitglied einer Domäne? Dann muss die IT ihn umbenennen.'
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/4: Uhrzeit synchronisieren (Risiko: gelb)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/4] Uhrzeit wird mit dem Zeitserver abgeglichen ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Start-Service -Name w32time -ErrorAction SilentlyContinue
        w32tm /resync /force
        w32tm /query /status
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    Write-OkmInfo '      Tipp: Ist der Zeitserver erreichbar (Firewall, UDP-Port 123)? In Domänen gibt der Domänencontroller die Zeit vor.'
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/4: Mehrere Pakete installieren (Risiko: gelb)
# --------------------------------------------------------------------
$OkmNr = 3
Write-OkmInfo '[3/4] Pakete werden installiert: Mozilla.Firefox, 7zip.7zip ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmFehlt = @()
        foreach ($okmPaket in @('Mozilla.Firefox', '7zip.7zip')) {
            Write-OkmInfo ('--- ' + $okmPaket)
            winget.exe install --id $okmPaket -e --source winget --silent --accept-package-agreements --accept-source-agreements
            # -1978335189/-1978335135: schon installiert bzw. kein neueres Paket – kein Fehler
            if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189 -and $LASTEXITCODE -ne -1978335135) { $okmFehlt += $okmPaket }
        }
        $global:LASTEXITCODE = 0
        $script:OkmS3_fehlgeschlagen = $okmFehlt.Count
        if ($okmFehlt.Count -gt 0) { throw ('Nicht installiert: ' + ($okmFehlt -join ', ')) }
        Write-OkmOk 'Alle Pakete installiert.'
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    if ("$($script:OkmS3_fehlgeschlagen)" -match '^-?[0-9]+$') { $script:OkmS3_fehlgeschlagen = [long]"$($script:OkmS3_fehlgeschlagen)" } else { $script:OkmS3_fehlgeschlagen = $null }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    Write-OkmInfo '      Tipp: Die Paket-IDs im Software-Katalog prüfen; die nicht installierten stehen in der Meldung oben.'
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 4/4: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 4
Write-OkmInfo '[4/4] Hinweis für den Benutzer ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Write-Host 'Fertig. Bitte den Rechner jetzt neu starten, damit der neue Name gilt.' -ForegroundColor Cyan
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
