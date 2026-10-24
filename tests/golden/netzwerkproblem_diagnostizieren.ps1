#Requires -Version 5.1
# ======================================================================
# Titel:             Netzwerkproblem diagnostizieren
# Beschreibung:      Prüft Schritt für Schritt Netzwerkeinstellungen, Router, Internet, Namensauflösung und ob ein bestimmter Server erreichbar ist (Ping, Traceroute, Port).
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  keine
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
$OkmGesamt = 7
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
Write-OkmInfo ' okm Script-Baukasten · Netzwerkproblem diagnostizieren'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

Write-OkmInfo 'Rechte: ohne erhöhte Rechte'

# Rückgabewerte der Schritte (Namen vergibt der Baukasten; $null = unbekannt)
$script:OkmS3_erreichbar = $null
$script:OkmS3_ms = $null
$script:OkmS5_erreichbar = $null
$script:OkmS5_ms = $null
$script:OkmS7_offen = $null

# --------------------------------------------------------------------
# Schritt 1/7: IP-Konfiguration anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/7] IP-Konfiguration wird angezeigt ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-NetIPConfiguration | Format-List InterfaceAlias, IPv4Address, IPv4DefaultGateway, DNSServer
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
# Schritt 2/7: Standard-Gateway anpingen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/7] Standard-Gateway wird geprüft ...'
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
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/7: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 3
Write-OkmInfo '[3/7] Ping auf 1.1.1.1 (2x) ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmAusgabe = @(ping.exe -n 2 '1.1.1.1')
        $okmRc = $LASTEXITCODE
        $okmAusgabe
        # ping.exe meldet auch "Zielhost nicht erreichbar" (Antwort eines Routers) mit Exit-Code 0 –
        # erreichbar ist das Ziel nur, wenn eine Antwort mit TTL kam.
        $script:OkmS3_erreichbar = ($okmRc -eq 0) -and (($okmAusgabe -join ' ') -match 'TTL=')
        $okmZeiten = [regex]::Matches(($okmAusgabe -join ' '), '=\s*(\d+)\s*ms')
        if ($script:OkmS3_erreichbar -and $okmZeiten.Count -gt 0) {
            # letzte Angabe = Mittelwert (de: "Mittelwert = 8ms", en: "Average = 8ms")
            $script:OkmS3_ms = $okmZeiten[$okmZeiten.Count - 1].Groups[1].Value
        }
        if (-not $script:OkmS3_erreichbar) {
            Write-Host 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.' -ForegroundColor Yellow
        }
        $global:LASTEXITCODE = 0
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    if ($null -ne $script:OkmS3_erreichbar) { $script:OkmS3_erreichbar = @('1', 'true', 'ja') -contains "$($script:OkmS3_erreichbar)" }
    if ("$($script:OkmS3_ms)" -match '^-?[0-9]+$') { $script:OkmS3_ms = [long]"$($script:OkmS3_ms)" } else { $script:OkmS3_ms = $null }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    Write-OkmInfo '      Tipp: Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping.'
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 4/7: Namensauflösung (DNS) testen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 4
Write-OkmInfo '[4/7] DNS-Auflösung von www.microsoft.com wird geprüft ...'
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
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 5/7: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 5
Write-OkmInfo '[5/7] Ping auf intranet.okm.local (4x) ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmAusgabe = @(ping.exe -n 4 'intranet.okm.local')
        $okmRc = $LASTEXITCODE
        $okmAusgabe
        # ping.exe meldet auch "Zielhost nicht erreichbar" (Antwort eines Routers) mit Exit-Code 0 –
        # erreichbar ist das Ziel nur, wenn eine Antwort mit TTL kam.
        $script:OkmS5_erreichbar = ($okmRc -eq 0) -and (($okmAusgabe -join ' ') -match 'TTL=')
        $okmZeiten = [regex]::Matches(($okmAusgabe -join ' '), '=\s*(\d+)\s*ms')
        if ($script:OkmS5_erreichbar -and $okmZeiten.Count -gt 0) {
            # letzte Angabe = Mittelwert (de: "Mittelwert = 8ms", en: "Average = 8ms")
            $script:OkmS5_ms = $okmZeiten[$okmZeiten.Count - 1].Groups[1].Value
        }
        if (-not $script:OkmS5_erreichbar) {
            Write-Host 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.' -ForegroundColor Yellow
        }
        $global:LASTEXITCODE = 0
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    if ($null -ne $script:OkmS5_erreichbar) { $script:OkmS5_erreichbar = @('1', 'true', 'ja') -contains "$($script:OkmS5_erreichbar)" }
    if ("$($script:OkmS5_ms)" -match '^-?[0-9]+$') { $script:OkmS5_ms = [long]"$($script:OkmS5_ms)" } else { $script:OkmS5_ms = $null }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    Write-OkmInfo '      Tipp: Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping.'
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 6/7: Traceroute (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 6
Write-OkmInfo '[6/7] Traceroute zu intranet.okm.local ...'
try {
    $global:LASTEXITCODE = 0
    . {
        tracert.exe -d -h 30 'intranet.okm.local'
        $global:LASTEXITCODE = 0
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
# Schritt 7/7: Port erreichbar prüfen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 7
Write-OkmInfo '[7/7] Port 443 auf intranet.okm.local wird geprüft ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmTest = Test-NetConnection -ComputerName 'intranet.okm.local' -Port 443 -WarningAction SilentlyContinue
        $script:OkmS7_offen = [bool]$okmTest.TcpTestSucceeded
        if ($script:OkmS7_offen) {
            Write-Host 'Der Port ist erreichbar.' -ForegroundColor Green
        } else {
            Write-Host 'Der Port ist NICHT erreichbar.' -ForegroundColor Yellow
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    if ($null -ne $script:OkmS7_offen) { $script:OkmS7_offen = @('1', 'true', 'ja') -contains "$($script:OkmS7_offen)" }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    Write-OkmInfo '      Tipp: Läuft der Dienst auf dem Zielrechner, und lässt die Firewall den Port durch?'
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

$OkmStatus = 'fertig'
Exit-OkmScript 0
