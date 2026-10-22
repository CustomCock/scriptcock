#Requires -Version 5.1
# ======================================================================
# Titel:             Incident-Erstsicherung
# Beschreibung:      Sichert bei einem Verdacht auf Schadsoftware oder Einbruch flüchtige Spuren in einen Ordner auf dem Desktop – bevor der Rechner vom Netz geht.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Incident-Erstsicherung [Risiko: gruen, Admin]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

$ErrorActionPreference = 'Stop'
$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$OkmGesamt = 1
$OkmErfolgreich = 0
try { Start-Transcript -Path $OkmLog -Append | Out-Null } catch { Write-Warning 'Protokoll konnte nicht gestartet werden.' }

function Exit-OkmScript {
    param([int]$Code)
    Write-Host ''
    Write-Host ('Protokoll: ' + $OkmLog)
    try { Stop-Transcript | Out-Null } catch { $null = $_ }
    exit $Code
}

# Prüfung: Administratorrechte
$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'Dieses Script braucht Administratorrechte. Bitte PowerShell mit Rechtsklick > "Als Administrator ausführen" öffnen und das Script erneut starten.' -ForegroundColor Red
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 1/1: Incident-Erstsicherung (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/1] Flüchtige Informationen werden gesichert …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmZiel = Join-Path ([Environment]::GetFolderPath('Desktop')) ('okm-incident-' + $env:COMPUTERNAME + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
        New-Item -ItemType Directory -Path $okmZiel -Force | Out-Null
        Get-Date -Format o | Out-File -FilePath (Join-Path $okmZiel 'zeitpunkt.txt') -Encoding UTF8
        Get-CimInstance -ClassName Win32_Process | Select-Object ProcessId, ParentProcessId, Name, ExecutablePath, CommandLine, CreationDate | Export-Csv -Path (Join-Path $okmZiel 'prozesse.csv') -NoTypeInformation -Encoding UTF8
        Get-NetTCPConnection | Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, State, OwningProcess | Export-Csv -Path (Join-Path $okmZiel 'tcp-verbindungen.csv') -NoTypeInformation -Encoding UTF8
        Get-NetUDPEndpoint | Select-Object LocalAddress, LocalPort, OwningProcess | Export-Csv -Path (Join-Path $okmZiel 'udp-endpunkte.csv') -NoTypeInformation -Encoding UTF8
        Get-DnsClientCache -ErrorAction SilentlyContinue | Export-Csv -Path (Join-Path $okmZiel 'dns-cache.csv') -NoTypeInformation -Encoding UTF8
        arp.exe -a | Out-File -FilePath (Join-Path $okmZiel 'arp.txt') -Encoding UTF8
        ipconfig.exe /all | Out-File -FilePath (Join-Path $okmZiel 'ipconfig.txt') -Encoding UTF8
        query.exe user 2>&1 | Out-File -FilePath (Join-Path $okmZiel 'angemeldete-benutzer.txt') -Encoding UTF8
        Get-CimInstance -ClassName Win32_StartupCommand | Export-Csv -Path (Join-Path $okmZiel 'autostart.csv') -NoTypeInformation -Encoding UTF8
        Get-ScheduledTask | Select-Object TaskPath, TaskName, State, @{ Name = 'Aktion'; Expression = { ($_.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -join ' | ' } } | Export-Csv -Path (Join-Path $okmZiel 'geplante-aufgaben.csv') -NoTypeInformation -Encoding UTF8
        Get-CimInstance -ClassName Win32_Service | Select-Object Name, State, StartMode, PathName | Export-Csv -Path (Join-Path $okmZiel 'dienste.csv') -NoTypeInformation -Encoding UTF8
        Get-WinEvent -FilterHashtable @{ LogName = 'Security'; Id = 4624, 4625, 4648, 4672, 4720, 4732 } -MaxEvents 2000 -ErrorAction SilentlyContinue | Select-Object TimeCreated, Id, Message | Export-Csv -Path (Join-Path $okmZiel 'sicherheitsereignisse.csv') -NoTypeInformation -Encoding UTF8
        $global:LASTEXITCODE = 0
        Get-ChildItem -Path $okmZiel -File | Get-FileHash -Algorithm SHA256 | Select-Object Hash, @{ Name = 'Datei'; Expression = { Split-Path $_.Path -Leaf } } | Out-File -FilePath (Join-Path $okmZiel 'hashes.txt') -Encoding UTF8
        Write-Host ('Erstsicherung abgelegt in: ' + $okmZiel) -ForegroundColor Green
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/1 (Incident-Erstsicherung): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
