#Requires -Version 5.1
# ======================================================================
# Titel:             Speicherplatz freigeben
# Beschreibung:      Zeigt die Festplattenbelegung, löscht alte temporäre Dateien und zeigt danach, wie viel Platz frei ist.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Festplattenbelegung anzeigen [Risiko: gruen]
#    2. Temp-Ordner aufräumen [Risiko: rot]
#    3. Festplattenbelegung anzeigen [Risiko: gruen]
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
$OkmGesamt = 3
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
    Wait-OkmEnde
    exit $Code
}

Write-OkmInfo '=============================================='
Write-OkmInfo ' okm Script-Baukasten · Speicherplatz freigeben'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

# --------------------------------------------------------------------
# Schritt 1/3: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/3] Festplattenbelegung wird ermittelt ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-PSDrive -PSProvider FileSystem |
            Where-Object { $null -ne $_.Used } |
            Format-Table Name, Root, @{ Name = 'Belegt (GB)'; Expression = { [math]::Round($_.Used / 1GB, 1) } }, @{ Name = 'Frei (GB)'; Expression = { [math]::Round($_.Free / 1GB, 1) } } -AutoSize
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler $_.Exception.Message
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/3: Temp-Ordner aufräumen (Risiko: rot)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/3] Temporäre Dateien älter als 7 Tage werden gelöscht ...'
Write-OkmWarnung 'ACHTUNG: Dieser Schritt ist destruktiv: Temp-Ordner aufräumen'
$OkmAntwort = Read-Host 'Zum Fortfahren JA eingeben (alles andere bricht ab)'
if ($OkmAntwort -cne 'JA') {
    $OkmStatus = 'abbruch'
    Exit-OkmScript 2
}
try {
    $global:LASTEXITCODE = 0
    . {
        $okmGrenze = (Get-Date).AddDays(-7)
        Get-ChildItem -LiteralPath $env:TEMP -Recurse -Force -File -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -lt $okmGrenze } |
            Remove-Item -Force -ErrorAction SilentlyContinue
        Write-Host 'Aufräumen abgeschlossen.'
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler $_.Exception.Message
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/3: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 3
Write-OkmInfo '[3/3] Festplattenbelegung wird ermittelt ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-PSDrive -PSProvider FileSystem |
            Where-Object { $null -ne $_.Used } |
            Format-Table Name, Root, @{ Name = 'Belegt (GB)'; Expression = { [math]::Round($_.Used / 1GB, 1) } }, @{ Name = 'Frei (GB)'; Expression = { [math]::Round($_.Free / 1GB, 1) } } -AutoSize
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler $_.Exception.Message
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

$OkmStatus = 'fertig'
Exit-OkmScript 0
