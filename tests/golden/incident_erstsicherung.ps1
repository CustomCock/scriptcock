#Requires -Version 5.1
# ======================================================================
# Titel:             Incident-Erstsicherung
# Beschreibung:      Sichert bei einem Verdacht auf Schadsoftware oder Einbruch flüchtige Spuren in einen Ordner auf dem Desktop – bevor der Rechner vom Netz geht.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  Administrator (Schritt 1)
# Enthaltene Schritte:
#    1. Incident-Erstsicherung [Risiko: gruen, Admin]
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
Write-OkmInfo ' okm Script-Baukasten · Incident-Erstsicherung'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

# Rechte: Administrator für Schritt 1 (Incident-Erstsicherung)
$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if ($OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-OkmInfo 'Rechte: als Administrator gestartet'
} else {
    Write-OkmInfo 'Dieses Script braucht Administratorrechte für: Schritt 1 (Incident-Erstsicherung).'
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
# Schritt 1/1: Incident-Erstsicherung (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/1] Flüchtige Informationen werden gesichert ...'
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
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

$OkmStatus = 'fertig'
Exit-OkmScript 0
