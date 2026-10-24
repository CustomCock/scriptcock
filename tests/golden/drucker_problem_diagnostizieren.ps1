#Requires -Version 5.1
# ======================================================================
# Titel:             Drucker-Problem diagnostizieren
# Beschreibung:      Prüft, ob der Drucker im Netz erreichbar ist, ob der Druckdienst läuft und welche Drucker eingerichtet sind.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  keine
# Enthaltene Schritte:
#    1. Ping auf Ziel [Risiko: gruen]
#    2. Drucker-Erreichbarkeit prüfen [Risiko: gruen]
#    3. Dienst-Status prüfen [Risiko: gruen]
#    4. Installierte Drucker auflisten [Risiko: gruen]
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
$OkmGesamt = 4
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
Write-OkmInfo ' okm Script-Baukasten · Drucker-Problem diagnostizieren'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

Write-OkmInfo 'Rechte: ohne erhöhte Rechte'

# Rückgabewerte der Schritte (Namen vergibt der Baukasten; $null = unbekannt)
$script:OkmS1_erreichbar = $null
$script:OkmS1_ms = $null
$script:OkmS3_laeuft = $null

# --------------------------------------------------------------------
# Schritt 1/4: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/4] Ping auf 192.168.1.50 (2x) ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmAusgabe = @(ping.exe -n 2 '192.168.1.50')
        $okmRc = $LASTEXITCODE
        $okmAusgabe
        # ping.exe meldet auch "Zielhost nicht erreichbar" (Antwort eines Routers) mit Exit-Code 0 –
        # erreichbar ist das Ziel nur, wenn eine Antwort mit TTL kam.
        $script:OkmS1_erreichbar = ($okmRc -eq 0) -and (($okmAusgabe -join ' ') -match 'TTL=')
        $okmZeiten = [regex]::Matches(($okmAusgabe -join ' '), '=\s*(\d+)\s*ms')
        if ($script:OkmS1_erreichbar -and $okmZeiten.Count -gt 0) {
            # letzte Angabe = Mittelwert (de: "Mittelwert = 8ms", en: "Average = 8ms")
            $script:OkmS1_ms = $okmZeiten[$okmZeiten.Count - 1].Groups[1].Value
        }
        if (-not $script:OkmS1_erreichbar) {
            Write-Host 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.' -ForegroundColor Yellow
        }
        $global:LASTEXITCODE = 0
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    if ($null -ne $script:OkmS1_erreichbar) { $script:OkmS1_erreichbar = @('1', 'true', 'ja') -contains "$($script:OkmS1_erreichbar)" }
    if ("$($script:OkmS1_ms)" -match '^-?[0-9]+$') { $script:OkmS1_ms = [long]"$($script:OkmS1_ms)" } else { $script:OkmS1_ms = $null }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    Write-OkmInfo '      Tipp: Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping.'
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/4: Drucker-Erreichbarkeit prüfen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/4] Drucker 192.168.1.50 wird geprüft ...'
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
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/4: Dienst-Status prüfen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 3
Write-OkmInfo '[3/4] Status von Dienst Spooler wird abgefragt ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmDienst = Get-Service -Name 'Spooler' -ErrorAction SilentlyContinue
        $script:OkmS3_laeuft = ($null -ne $okmDienst) -and ($okmDienst.Status -eq 'Running')
        if (-not $okmDienst) {
            Write-OkmWarnung 'Diesen Dienst gibt es nicht.'
        } else {
            $okmDienst | Format-Table Name, DisplayName, Status, StartType -AutoSize
            if ($okmDienst.Status -ne 'Running') { Write-OkmWarnung 'Der Dienst ist vorhanden, läuft aber nicht.' }
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    if ($null -ne $script:OkmS3_laeuft) { $script:OkmS3_laeuft = @('1', 'true', 'ja') -contains "$($script:OkmS3_laeuft)" }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 4/4: Installierte Drucker auflisten (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 4
Write-OkmInfo '[4/4] Drucker werden aufgelistet ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-CimInstance -ClassName Win32_Printer | Sort-Object Name |
            Format-Table Name, PortName, DriverName, @{ Name = 'Standard'; Expression = { if ($_.Default) { 'ja' } else { '' } } }, Shared -AutoSize -Wrap
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
