#Requires -Version 5.1
# ======================================================================
# Titel:             Drucker-Problem diagnostizieren
# Beschreibung:      Prüft, ob der Drucker im Netz erreichbar ist, ob der Druckdienst läuft und welche Drucker eingerichtet sind.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Ping auf Ziel [Risiko: gruen]
#    2. Drucker-Erreichbarkeit prüfen [Risiko: gruen]
#    3. Dienst-Status prüfen [Risiko: gruen]
#    4. Installierte Drucker auflisten [Risiko: gruen]
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
# Schritt 1/4: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/4] Ping auf 192.168.1.50 (2x) …'
try {
    $global:LASTEXITCODE = 0
    . {
        ping.exe -n 2 '192.168.1.50'
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.' -ForegroundColor Yellow
            $global:LASTEXITCODE = 0
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/4 (Ping auf Ziel): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/4: Drucker-Erreichbarkeit prüfen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[2/4] Drucker 192.168.1.50 wird geprüft …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmErreichbar = Test-Connection -ComputerName '192.168.1.50' -Count 2 -Quiet
        Write-Host ('Ping: ' + $(if ($okmErreichbar) { 'antwortet' } else { 'keine Antwort' }))
        foreach ($okmPort in 9100, 631, 515) {
            $okmTest = Test-NetConnection -ComputerName '192.168.1.50' -Port $okmPort -WarningAction SilentlyContinue
            Write-Host ('Port ' + $okmPort + ': ' + $(if ($okmTest.TcpTestSucceeded) { 'offen' } else { 'geschlossen' }))
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 2/4 (Drucker-Erreichbarkeit prüfen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/4: Dienst-Status prüfen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[3/4] Status von Dienst Spooler wird abgefragt …'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-Service -Name 'Spooler' | Format-Table Name, DisplayName, Status, StartType -AutoSize
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 3/4 (Dienst-Status prüfen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 4/4: Installierte Drucker auflisten (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[4/4] Drucker werden aufgelistet …'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-CimInstance -ClassName Win32_Printer | Sort-Object Name |
            Format-Table Name, PortName, DriverName, @{ Name = 'Standard'; Expression = { if ($_.Default) { 'ja' } else { '' } } }, Shared -AutoSize -Wrap
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 4/4 (Installierte Drucker auflisten): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
