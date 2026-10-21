#Requires -Version 5.1
# ======================================================================
# Titel:             Netzwerkproblem diagnostizieren
# Beschreibung:      Zeigt die Netzwerkeinstellungen und prüft Schritt für Schritt, ob ein Server erreichbar ist (Ping, Traceroute, Port).
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. IP-Konfiguration anzeigen [Risiko: gruen]
#    2. Ping auf Ziel [Risiko: gruen]
#    3. Traceroute [Risiko: gruen]
#    4. Port erreichbar prüfen [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

$ErrorActionPreference = 'Stop'
$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$OkmGesamt = 4
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
# Schritt 1/4: IP-Konfiguration anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/4] IP-Konfiguration wird angezeigt …'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-NetIPConfiguration | Format-List InterfaceAlias, IPv4Address, IPv4DefaultGateway, DNSServer
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/4 (IP-Konfiguration anzeigen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/4: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[2/4] Ping auf intranet.okm.local (4x) …'
try {
    $global:LASTEXITCODE = 0
    . {
        ping.exe -n 4 'intranet.okm.local'
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.' -ForegroundColor Yellow
            $global:LASTEXITCODE = 0
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 2/4 (Ping auf Ziel): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/4: Traceroute (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[3/4] Traceroute zu intranet.okm.local …'
try {
    $global:LASTEXITCODE = 0
    . {
        tracert.exe -d -h 30 'intranet.okm.local'
        $global:LASTEXITCODE = 0
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 3/4 (Traceroute): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 4/4: Port erreichbar prüfen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[4/4] Port 443 auf intranet.okm.local wird geprüft …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmTest = Test-NetConnection -ComputerName 'intranet.okm.local' -Port 443 -WarningAction SilentlyContinue
        if ($okmTest.TcpTestSucceeded) {
            Write-Host 'Der Port ist erreichbar.' -ForegroundColor Green
        } else {
            Write-Host 'Der Port ist NICHT erreichbar.' -ForegroundColor Yellow
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 4/4 (Port erreichbar prüfen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
