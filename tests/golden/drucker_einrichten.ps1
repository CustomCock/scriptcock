#Requires -Version 5.1
# ======================================================================
# Titel:             Drucker einrichten
# Beschreibung:      Prüft, ob der Drucker im Netzwerk erreichbar ist, und richtet ihn anschließend über seine IP-Adresse ein.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Ping auf Ziel [Risiko: gruen]
#    2. Drucker per IP hinzufügen [Risiko: gelb, Admin]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

$ErrorActionPreference = 'Stop'
$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$OkmGesamt = 2
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
# Schritt 1/2: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/2] Ping auf 192.168.1.50 (2x) …'
try {
    $global:LASTEXITCODE = 0
    . {
        ping.exe -n 2 '192.168.1.50'
        if ($LASTEXITCODE -ne 0) {
            throw 'Das Ziel antwortet nicht.'
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/2 (Ping auf Ziel): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/2: Drucker per IP hinzufügen (Risiko: gelb)
# --------------------------------------------------------------------
Write-Host '[2/2] Drucker Drucker-Empfang (192.168.1.50) wird eingerichtet …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmPort = 'IP_' + '192.168.1.50'
        if (-not (Get-PrinterPort -Name $okmPort -ErrorAction SilentlyContinue)) {
            Add-PrinterPort -Name $okmPort -PrinterHostAddress '192.168.1.50'
        }
        Add-Printer -Name 'Drucker-Empfang' -PortName $okmPort -DriverName 'Microsoft IPP Class Driver'
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    # Prüfung
    . {
        Get-Printer -Name 'Drucker-Empfang' | Format-Table Name, PortName, DriverName -AutoSize
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Prüfung endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 2/2 (Drucker per IP hinzufügen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
