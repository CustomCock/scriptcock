#Requires -Version 5.1
# ======================================================================
# Titel:             Diagnosepaket für den Support erstellen
# Beschreibung:      Sammelt Systeminformationen, Netzwerkeinstellungen und Protokolle in einer Datei, die du an den Support schicken kannst.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Systeminfo anzeigen [Risiko: gruen]
#    2. Diagnosepaket erstellen [Risiko: gelb]
#    3. Meldung/Pause für den Benutzer [Risiko: gruen]
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
Write-OkmInfo ' okm Script-Baukasten · Diagnosepaket für den Support erstellen'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

# --------------------------------------------------------------------
# Schritt 1/3: Systeminfo anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/3] Systeminformationen werden gesammelt ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmOs = Get-CimInstance -ClassName Win32_OperatingSystem
        $okmCs = Get-CimInstance -ClassName Win32_ComputerSystem
        $okmCpu = Get-CimInstance -ClassName Win32_Processor | Select-Object -First 1
        $okmLaufzeit = (Get-Date) - $okmOs.LastBootUpTime
        [PSCustomObject]@{
            Rechnername       = $env:COMPUTERNAME
            Betriebssystem    = $okmOs.Caption
            Version           = $okmOs.Version
            Build             = $okmOs.BuildNumber
            Prozessor         = $okmCpu.Name.Trim()
            'Kerne/Threads'   = '{0}/{1}' -f $okmCpu.NumberOfCores, $okmCpu.NumberOfLogicalProcessors
            'RAM gesamt (GB)' = [math]::Round($okmCs.TotalPhysicalMemory / 1GB, 1)
            'RAM frei (GB)'   = [math]::Round($okmOs.FreePhysicalMemory / 1MB, 1)
            Laufzeit          = '{0} Tage {1} Std. {2} Min.' -f $okmLaufzeit.Days, $okmLaufzeit.Hours, $okmLaufzeit.Minutes
        } | Format-List
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
# Schritt 2/3: Diagnosepaket erstellen (Risiko: gelb)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/3] Diagnosepaket wird erstellt (das kann etwas dauern) ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmStempel = Get-Date -Format 'yyyyMMdd-HHmmss'
        $okmArbeit = Join-Path $env:TEMP ('okm-diagnose-' + $okmStempel)
        New-Item -ItemType Directory -Path $okmArbeit -Force | Out-Null
        Get-ComputerInfo | Out-File -FilePath (Join-Path $okmArbeit 'systeminfo.txt') -Encoding UTF8
        ipconfig.exe /all | Out-File -FilePath (Join-Path $okmArbeit 'ipconfig.txt') -Encoding UTF8
        Get-NetIPConfiguration -Detailed | Out-File -FilePath (Join-Path $okmArbeit 'netzwerk.txt') -Encoding UTF8
        route.exe print | Out-File -FilePath (Join-Path $okmArbeit 'routen.txt') -Encoding UTF8
        Get-Process | Sort-Object CPU -Descending | Out-File -FilePath (Join-Path $okmArbeit 'prozesse.txt') -Encoding UTF8
        Get-WinEvent -FilterHashtable @{ LogName = 'System', 'Application'; Level = 1, 2, 3 } -MaxEvents 500 -ErrorAction SilentlyContinue |
            Select-Object TimeCreated, LogName, ProviderName, Id, LevelDisplayName, Message |
            Export-Csv -LiteralPath (Join-Path $okmArbeit 'ereignisse.csv') -NoTypeInformation -Encoding UTF8 -Delimiter ';'
        $okmZip = Join-Path ([Environment]::GetFolderPath('Desktop')) ('okm-diagnose-' + $env:COMPUTERNAME + '-' + $okmStempel + '.zip')
        Compress-Archive -Path (Join-Path $okmArbeit '*') -DestinationPath $okmZip -Force
        Remove-Item -LiteralPath $okmArbeit -Recurse -Force
        Write-Host ('Diagnosepaket erstellt: ' + $okmZip) -ForegroundColor Green
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
# Schritt 3/3: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 3
Write-OkmInfo '[3/3] Hinweis für den Benutzer ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Write-Host 'Fertig! Bitte die erstellte Datei an den Support schicken (Pfad siehe oben).' -ForegroundColor Cyan
        [void](Read-Host 'Weiter mit Enter')
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
