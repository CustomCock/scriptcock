#Requires -Version 5.1
# ======================================================================
# Titel:             PC ist langsam
# Beschreibung:      Sucht die typischen Bremsen – CPU- und Speicherlast, volle Festplatte, lange Laufzeit, Autostart-Programme und Festplatten-Gesundheit.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. „PC ist langsam“-Check [Risiko: gruen]
#    2. Top-Ressourcenverbraucher [Risiko: gruen]
#    3. Festplattenbelegung anzeigen [Risiko: gruen]
#    4. Autostart-Einträge anzeigen [Risiko: gruen]
#    5. Festplatten-Gesundheit (SMART) [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

$ErrorActionPreference = 'Stop'
$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$OkmGesamt = 5
$OkmErfolgreich = 0
try { Start-Transcript -Path $OkmLog -Append | Out-Null } catch { Write-Warning 'Protokoll konnte nicht gestartet werden.' }

function Exit-OkmScript {
    param([int]$Code)
    Write-Host ''
    Write-Host ('Protokoll: ' + $OkmLog)
    try { Stop-Transcript | Out-Null } catch { $null = $_ }
    exit $Code
}

# --------------------------------------------------------------------
# Schritt 1/5: „PC ist langsam“-Check (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/5] Rechner wird auf typische Bremsen geprüft …'
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
} catch {
    Write-Host ('FEHLER in Schritt 1/5 („PC ist langsam“-Check): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/5: Top-Ressourcenverbraucher (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[2/5] Prozesse werden nach Last sortiert …'
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
} catch {
    Write-Host ('FEHLER in Schritt 2/5 (Top-Ressourcenverbraucher): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/5: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[3/5] Festplattenbelegung wird ermittelt …'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-PSDrive -PSProvider FileSystem |
            Where-Object { $null -ne $_.Used } |
            Format-Table Name, Root, @{ Name = 'Belegt (GB)'; Expression = { [math]::Round($_.Used / 1GB, 1) } }, @{ Name = 'Frei (GB)'; Expression = { [math]::Round($_.Free / 1GB, 1) } } -AutoSize
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 3/5 (Festplattenbelegung anzeigen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 4/5: Autostart-Einträge anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[4/5] Autostart-Einträge werden gelesen …'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-CimInstance -ClassName Win32_StartupCommand | Sort-Object Name |
            Format-Table Name, Command, Location, User -AutoSize -Wrap
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 4/5 (Autostart-Einträge anzeigen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 5/5: Festplatten-Gesundheit (SMART) (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[5/5] Festplatten-Gesundheit wird geprüft …'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-PhysicalDisk | Format-Table FriendlyName, MediaType, HealthStatus, OperationalStatus, @{ Name = 'Größe (GB)'; Expression = { [math]::Round($_.Size / 1GB) } } -AutoSize
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 5/5 (Festplatten-Gesundheit (SMART)): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
