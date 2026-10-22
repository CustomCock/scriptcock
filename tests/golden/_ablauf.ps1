#Requires -Version 5.1
# ======================================================================
# Titel:             Ablauf
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Meldung/Pause für den Benutzer [Risiko: gruen]
#   Versuche:
#       2. Ordner anlegen [Risiko: gelb]
#      Versuche:
#          3. Ping auf Ziel [Risiko: gruen]
#      Fehler darin übergehen.
#   Wenn das fehlschlägt:
#       4. Meldung/Pause für den Benutzer [Risiko: gruen]
#      Wiederhole 2-mal:
#          5. Prozess beenden [Risiko: rot]
#   Wiederhole 3-mal:
#       6. Meldung/Pause für den Benutzer [Risiko: gruen]
#      Versuche:
#          7. Dienst-Status prüfen [Risiko: gruen]
#      Fehler darin übergehen.
#    8. Meldung/Pause für den Benutzer [Risiko: gruen]
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
        'fertig' { Write-Host (' Fertig: ' + $script:OkmErfolgreich + ' Schritte erfolgreich ausgeführt.') -ForegroundColor Green }
        'abbruch' {
            Write-Host ' Abgebrochen durch Benutzer. Es wurde nichts weiter ausgeführt.' -ForegroundColor Yellow
        }
        'rechte' {
            Write-Host ' Abgebrochen: fehlende Administratorrechte.' -ForegroundColor Red
        }
        default {
            Write-Host (' Abgebrochen bei Schritt ' + $script:OkmNr + '.') -ForegroundColor Red
            Write-Host (' Erfolgreich bis dahin: ' + $script:OkmErfolgreich + ' Schritte.')
        }
    }
    Write-Host (' Protokoll: ' + $OkmLog)
    Write-Host '----------------------------------------------'
    try { Stop-Transcript | Out-Null } catch { $null = $_ }
    Wait-OkmEnde
    exit $Code
}

Write-OkmInfo '=============================================='
Write-OkmInfo ' okm Script-Baukasten · Ablauf'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

# --------------------------------------------------------------------
# Schritt 1/8: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/8] Hinweis für den Benutzer ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Write-Host 'Start' -ForegroundColor Cyan
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler $_.Exception.Message
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# ===== Versuche (Block 1) =====
try {
    # --------------------------------------------------------------------
    # Schritt 2/8: Ordner anlegen (Risiko: gelb)
    # --------------------------------------------------------------------
    $OkmNr = 2
    Write-OkmInfo '[2/8] Ordner C:\temp\okm wird angelegt ...'
    try {
        $global:LASTEXITCODE = 0
        . {
            New-Item -ItemType Directory -Path 'C:\temp\okm' -Force | Out-Null
        } | Out-Host
        if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
        $OkmErfolgreich++
        Write-OkmOk
    } catch {
        Write-OkmFehler $_.Exception.Message
        throw
    }

    # ===== Versuche (Block 2) =====
    try {
        # --------------------------------------------------------------------
        # Schritt 3/8: Ping auf Ziel (Risiko: gruen)
        # --------------------------------------------------------------------
        $OkmNr = 3
        Write-OkmInfo '[3/8] Ping auf 10.0.0.1 (4x) ...'
        try {
            $global:LASTEXITCODE = 0
            . {
                ping.exe -n 4 '10.0.0.1'
                if ($LASTEXITCODE -ne 0) {
                    throw 'Das Ziel antwortet nicht.'
                }
            } | Out-Host
            if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
            $OkmErfolgreich++
            Write-OkmOk
        } catch {
            Write-OkmFehler $_.Exception.Message
            Write-OkmInfo '      Tipp: Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping.'
            throw
        }

    } catch {
        Write-OkmWarnung 'Ein Schritt ist fehlgeschlagen - der Fehler wird wie vorgesehen übergangen.'
    }
    # ===== Ende Versuche (Block 2) =====

} catch {
    Write-OkmWarnung 'Ein Schritt ist fehlgeschlagen - es geht mit den Ausweichschritten weiter.'
    # --------------------------------------------------------------------
    # Schritt 4/8: Meldung/Pause für den Benutzer (Risiko: gruen)
    # --------------------------------------------------------------------
    $OkmNr = 4
    Write-OkmInfo '[4/8] Hinweis für den Benutzer ...'
    try {
        $global:LASTEXITCODE = 0
        . {
            Write-Host 'Ausweichen' -ForegroundColor Cyan
        } | Out-Host
        if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
        $OkmErfolgreich++
        Write-OkmOk
    } catch {
        Write-OkmFehler $_.Exception.Message
        $OkmStatus = 'fehler'
        Exit-OkmScript 1
    }

    # ===== Wiederhole 2-mal (Block 3) =====
    for ($OkmDurchlauf3 = 1; $OkmDurchlauf3 -le 2; $OkmDurchlauf3++) {
        Write-OkmInfo ('--- Durchlauf ' + $OkmDurchlauf3 + ' von 2 ---')
        # --------------------------------------------------------------------
        # Schritt 5/8: Prozess beenden (Risiko: rot)
        # --------------------------------------------------------------------
        $OkmNr = 5
        Write-OkmInfo '[5/8] Prozess notepad wird beendet ...'
        Write-OkmWarnung 'ACHTUNG: Dieser Schritt ist destruktiv: Prozess beenden'
        $OkmAntwort = Read-Host 'Zum Fortfahren JA eingeben (alles andere bricht ab)'
        if ($OkmAntwort -cne 'JA') {
            $OkmStatus = 'abbruch'
            Exit-OkmScript 2
        }
        try {
            $global:LASTEXITCODE = 0
            . {
                $okmProzesse = Get-Process -Name 'notepad' -ErrorAction SilentlyContinue
                if (-not $okmProzesse) {
                    Write-Host 'Kein passender Prozess gefunden - nichts zu tun.'
                } else {
                    $okmProzesse | Stop-Process -Force
                }
            } | Out-Host
            if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
            $OkmErfolgreich++
            Write-OkmOk
        } catch {
            Write-OkmFehler $_.Exception.Message
            $OkmStatus = 'fehler'
            Exit-OkmScript 1
        }

    }

}
# ===== Ende Versuche (Block 1) =====

# ===== Wiederhole 3-mal (Block 4) =====
for ($OkmDurchlauf4 = 1; $OkmDurchlauf4 -le 3; $OkmDurchlauf4++) {
    Write-OkmInfo ('--- Durchlauf ' + $OkmDurchlauf4 + ' von 3 ---')
    # --------------------------------------------------------------------
    # Schritt 6/8: Meldung/Pause für den Benutzer (Risiko: gruen)
    # --------------------------------------------------------------------
    $OkmNr = 6
    Write-OkmInfo '[6/8] Hinweis für den Benutzer ...'
    try {
        $global:LASTEXITCODE = 0
        . {
            Write-Host 'Schleife' -ForegroundColor Cyan
        } | Out-Host
        if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
        $OkmErfolgreich++
        Write-OkmOk
    } catch {
        Write-OkmFehler $_.Exception.Message
        $OkmStatus = 'fehler'
        Exit-OkmScript 1
    }

    # ===== Versuche (Block 5) =====
    try {
        # --------------------------------------------------------------------
        # Schritt 7/8: Dienst-Status prüfen (Risiko: gruen)
        # --------------------------------------------------------------------
        $OkmNr = 7
        Write-OkmInfo '[7/8] Status von Dienst Spooler wird abgefragt ...'
        try {
            $global:LASTEXITCODE = 0
            . {
                Get-Service -Name 'Spooler' | Format-Table Name, DisplayName, Status, StartType -AutoSize
            } | Out-Host
            if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
            $OkmErfolgreich++
            Write-OkmOk
        } catch {
            Write-OkmFehler $_.Exception.Message
            throw
        }

    } catch {
        Write-OkmWarnung 'Ein Schritt ist fehlgeschlagen - der Fehler wird wie vorgesehen übergangen.'
    }
    # ===== Ende Versuche (Block 5) =====

}

# --------------------------------------------------------------------
# Schritt 8/8: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 8
Write-OkmInfo '[8/8] Hinweis für den Benutzer ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Write-Host 'Ende' -ForegroundColor Cyan
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
