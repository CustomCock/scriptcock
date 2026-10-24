#Requires -Version 5.1
# ======================================================================
# Titel:             PC ist langsam
# Beschreibung:      Sucht die typischen Bremsen – CPU- und Speicherlast, volle Festplatte, lange Laufzeit, Autostart-Programme und Festplatten-Gesundheit.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  keine
# Enthaltene Schritte:
#    1. „PC ist langsam“-Check [Risiko: gruen]
#    2. Top-Ressourcenverbraucher [Risiko: gruen]
#    3. Festplattenbelegung anzeigen [Risiko: gruen]
#    4. Autostart-Einträge anzeigen [Risiko: gruen]
#    5. Festplatten-Gesundheit (SMART) [Risiko: gruen]
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
$OkmGesamt = 5
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
Write-OkmInfo ' okm Script-Baukasten · PC ist langsam'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

Write-OkmInfo 'Rechte: ohne erhöhte Rechte'

# Rückgabewerte der Schritte (Namen vergibt der Baukasten; $null = unbekannt)
$script:OkmS3_frei_prozent = $null

# --------------------------------------------------------------------
# Schritt 1/5: „PC ist langsam“-Check (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/5] Rechner wird auf typische Bremsen geprüft ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmOs = Get-CimInstance -ClassName Win32_OperatingSystem
        $okmCpu = [math]::Round((Get-CimInstance -ClassName Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average)
        $okmRamFrei = [math]::Round($okmOs.FreePhysicalMemory / $okmOs.TotalVisibleMemorySize * 100)
        $okmLaufwerk = Get-CimInstance -ClassName Win32_LogicalDisk -Filter ("DeviceID='" + $env:SystemDrive + "'")
        $okmPlatz = [math]::Round($okmLaufwerk.FreeSpace / $okmLaufwerk.Size * 100)
        $okmTage = [math]::Floor(((Get-Date) - $okmOs.LastBootUpTime).TotalDays)
        Write-Host ('CPU-Last:            ' + $okmCpu + ' %') -ForegroundColor $(if ($okmCpu -gt 80) { 'Red' } else { 'Green' })
        Write-Host ('Freier Arbeitsspeicher: ' + $okmRamFrei + ' % von ' + [math]::Round($okmOs.TotalVisibleMemorySize / 1MB) + ' GB') -ForegroundColor $(if ($okmRamFrei -lt 15) { 'Red' } else { 'Green' })
        Write-Host ('Freier Platz ' + $env:SystemDrive + '      ' + $okmPlatz + ' %') -ForegroundColor $(if ($okmPlatz -lt 10) { 'Red' } else { 'Green' })
        Write-Host ('Letzter Neustart:    vor ' + $okmTage + ' Tagen') -ForegroundColor $(if ($okmTage -gt 7) { 'Yellow' } else { 'Green' })
        Write-Host 'Größte Verbraucher (Arbeitsspeicher):'
        Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 | Format-Table ProcessName, @{ Name = 'RAM (MB)'; Expression = { [math]::Round($_.WorkingSet64 / 1MB) } } -AutoSize
        if ($okmTage -gt 7) { Write-Host 'Tipp: Rechner neu starten – er läuft seit über einer Woche.' -ForegroundColor Yellow }
        if ($okmPlatz -lt 10) { Write-Host 'Tipp: Speicherplatz freigeben (Rezept „Speicherplatz freigeben“).' -ForegroundColor Yellow }
        if ($okmRamFrei -lt 15) { Write-Host 'Tipp: Nicht benötigte Programme und Browser-Tabs schließen.' -ForegroundColor Yellow }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/5: Top-Ressourcenverbraucher (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/5] Prozesse werden nach Last sortiert ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Write-Host 'Nach CPU-Zeit:'
        Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 |
            Format-Table ProcessName, Id, @{ Name = 'CPU (s)'; Expression = { [math]::Round($_.CPU) } }, @{ Name = 'RAM (MB)'; Expression = { [math]::Round($_.WorkingSet64 / 1MB) } } -AutoSize
        Write-Host 'Nach Arbeitsspeicher:'
        Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 |
            Format-Table ProcessName, Id, @{ Name = 'RAM (MB)'; Expression = { [math]::Round($_.WorkingSet64 / 1MB) } } -AutoSize
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/5: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 3
Write-OkmInfo '[3/5] Festplattenbelegung wird ermittelt ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-PSDrive -PSProvider FileSystem |
            Where-Object { $null -ne $_.Used } |
            Format-Table Name, Root, @{ Name = 'Belegt (GB)'; Expression = { [math]::Round($_.Used / 1GB, 1) } }, @{ Name = 'Frei (GB)'; Expression = { [math]::Round($_.Free / 1GB, 1) } } -AutoSize
        $okmSystem = Get-PSDrive -Name $env:SystemDrive.Substring(0, 1) -ErrorAction SilentlyContinue
        if ($okmSystem -and ($okmSystem.Used + $okmSystem.Free) -gt 0) {
            $script:OkmS3_frei_prozent = [math]::Floor(100 * $okmSystem.Free / ($okmSystem.Used + $okmSystem.Free))
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    if ("$($script:OkmS3_frei_prozent)" -match '^-?[0-9]+$') { $script:OkmS3_frei_prozent = [long]"$($script:OkmS3_frei_prozent)" } else { $script:OkmS3_frei_prozent = $null }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 4/5: Autostart-Einträge anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 4
Write-OkmInfo '[4/5] Autostart-Einträge werden gelesen ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-CimInstance -ClassName Win32_StartupCommand | Sort-Object Name |
            Format-Table Name, Command, Location, User -AutoSize -Wrap
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 5/5: Festplatten-Gesundheit (SMART) (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 5
Write-OkmInfo '[5/5] Festplatten-Gesundheit wird geprüft ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-PhysicalDisk | Format-Table FriendlyName, MediaType, HealthStatus, OperationalStatus, @{ Name = 'Größe (GB)'; Expression = { [math]::Round($_.Size / 1GB) } } -AutoSize
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
