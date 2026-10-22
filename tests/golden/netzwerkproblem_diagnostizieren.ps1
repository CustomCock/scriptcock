#Requires -Version 5.1
# ======================================================================
# Titel:             Netzwerkproblem diagnostizieren
# Beschreibung:      Prüft Schritt für Schritt Netzwerkeinstellungen, Router, Internet, Namensauflösung und ob ein bestimmter Server erreichbar ist (Ping, Traceroute, Port).
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. IP-Konfiguration anzeigen [Risiko: gruen]
#    2. Standard-Gateway anpingen [Risiko: gruen]
#    3. Ping auf Ziel [Risiko: gruen]
#    4. Namensauflösung (DNS) testen [Risiko: gruen]
#    5. Ping auf Ziel [Risiko: gruen]
#    6. Traceroute [Risiko: gruen]
#    7. Port erreichbar prüfen [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

$ErrorActionPreference = 'Stop'
$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$OkmGesamt = 7
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
# Schritt 1/7: IP-Konfiguration anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/7] IP-Konfiguration wird angezeigt …'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-NetIPConfiguration | Format-List InterfaceAlias, IPv4Address, IPv4DefaultGateway, DNSServer
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/7 (IP-Konfiguration anzeigen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/7: Standard-Gateway anpingen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[2/7] Standard-Gateway wird geprüft …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmGateway = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 1).NextHop
        if (-not $okmGateway) {
            Write-Host 'Kein Standard-Gateway gefunden – keine Netzwerkverbindung?' -ForegroundColor Yellow
        } else {
            Write-Host ('Standard-Gateway: ' + $okmGateway)
            ping.exe -n 4 $okmGateway
            if ($LASTEXITCODE -ne 0) { Write-Host 'Hinweis: Das Gateway antwortet nicht.' -ForegroundColor Yellow; $global:LASTEXITCODE = 0 }
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 2/7 (Standard-Gateway anpingen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/7: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[3/7] Ping auf 1.1.1.1 (2x) …'
try {
    $global:LASTEXITCODE = 0
    . {
        ping.exe -n 2 '1.1.1.1'
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.' -ForegroundColor Yellow
            $global:LASTEXITCODE = 0
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 3/7 (Ping auf Ziel): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 4/7: Namensauflösung (DNS) testen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[4/7] DNS-Auflösung von www.microsoft.com wird geprüft …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmAntwort = Resolve-DnsName -Name 'www.microsoft.com' -ErrorAction SilentlyContinue
        if ($okmAntwort) {
            $okmAntwort | Where-Object { $_.IPAddress } | Format-Table Name, Type, IPAddress -AutoSize
        } else {
            Write-Host 'Der Name kann NICHT aufgelöst werden.' -ForegroundColor Yellow
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 4/7 (Namensauflösung (DNS) testen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 5/7: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[5/7] Ping auf intranet.okm.local (4x) …'
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
    Write-Host ('FEHLER in Schritt 5/7 (Ping auf Ziel): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 6/7: Traceroute (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[6/7] Traceroute zu intranet.okm.local …'
try {
    $global:LASTEXITCODE = 0
    . {
        tracert.exe -d -h 30 'intranet.okm.local'
        $global:LASTEXITCODE = 0
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 6/7 (Traceroute): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 7/7: Port erreichbar prüfen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[7/7] Port 443 auf intranet.okm.local wird geprüft …'
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
    Write-Host ('FEHLER in Schritt 7/7 (Port erreichbar prüfen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
