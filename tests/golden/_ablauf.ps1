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

$ErrorActionPreference = 'Stop'
$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
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
# Schritt 1/8: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/8] Hinweis für den Benutzer …'
try {
    $global:LASTEXITCODE = 0
    . {
        Write-Host 'Start' -ForegroundColor Cyan
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/8 (Meldung/Pause für den Benutzer): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' Schritte.')
    Exit-OkmScript 1
}

# ===== Versuche (Block 1) =====
try {
    # --------------------------------------------------------------------
    # Schritt 2/8: Ordner anlegen (Risiko: gelb)
    # --------------------------------------------------------------------
    Write-Host '[2/8] Ordner C:\temp\okm wird angelegt …'
    try {
        $global:LASTEXITCODE = 0
        . {
            New-Item -ItemType Directory -Path 'C:\temp\okm' -Force | Out-Null
        } | Out-Host
        if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
        $OkmErfolgreich++
    } catch {
        Write-Host ('FEHLER in Schritt 2/8 (Ordner anlegen): ' + $_.Exception.Message) -ForegroundColor Red
        throw
    }

    # ===== Versuche (Block 2) =====
    try {
        # --------------------------------------------------------------------
        # Schritt 3/8: Ping auf Ziel (Risiko: gruen)
        # --------------------------------------------------------------------
        Write-Host '[3/8] Ping auf 10.0.0.1 (4x) …'
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
        } catch {
            Write-Host ('FEHLER in Schritt 3/8 (Ping auf Ziel): ' + $_.Exception.Message) -ForegroundColor Red
            throw
        }

    } catch {
        Write-Host 'Ein Schritt ist fehlgeschlagen - der Fehler wird wie vorgesehen übergangen.' -ForegroundColor Yellow
    }
    # ===== Ende Versuche (Block 2) =====

} catch {
    Write-Host 'Ein Schritt ist fehlgeschlagen - es geht mit den Ausweichschritten weiter.' -ForegroundColor Yellow
    # --------------------------------------------------------------------
    # Schritt 4/8: Meldung/Pause für den Benutzer (Risiko: gruen)
    # --------------------------------------------------------------------
    Write-Host '[4/8] Hinweis für den Benutzer …'
    try {
        $global:LASTEXITCODE = 0
        . {
            Write-Host 'Ausweichen' -ForegroundColor Cyan
        } | Out-Host
        if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
        $OkmErfolgreich++
    } catch {
        Write-Host ('FEHLER in Schritt 4/8 (Meldung/Pause für den Benutzer): ' + $_.Exception.Message) -ForegroundColor Red
        Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' Schritte.')
        Exit-OkmScript 1
    }

    # ===== Wiederhole 2-mal (Block 3) =====
    for ($OkmDurchlauf3 = 1; $OkmDurchlauf3 -le 2; $OkmDurchlauf3++) {
        Write-Host ('--- Durchlauf ' + $OkmDurchlauf3 + ' von 2 ---') -ForegroundColor Cyan
        # --------------------------------------------------------------------
        # Schritt 5/8: Prozess beenden (Risiko: rot)
        # --------------------------------------------------------------------
        Write-Host '[5/8] Prozess notepad wird beendet …'
        Write-Host 'ACHTUNG: Dieser Schritt ist destruktiv: Prozess beenden' -ForegroundColor Yellow
        $OkmAntwort = Read-Host 'Zum Fortfahren JA eingeben (alles andere bricht ab)'
        if ($OkmAntwort -cne 'JA') {
            Write-Host 'Abgebrochen. Es wurde nichts weiter ausgeführt.' -ForegroundColor Yellow
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
        } catch {
            Write-Host ('FEHLER in Schritt 5/8 (Prozess beenden): ' + $_.Exception.Message) -ForegroundColor Red
            Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' Schritte.')
            Exit-OkmScript 1
        }

    }

}
# ===== Ende Versuche (Block 1) =====

# ===== Wiederhole 3-mal (Block 4) =====
for ($OkmDurchlauf4 = 1; $OkmDurchlauf4 -le 3; $OkmDurchlauf4++) {
    Write-Host ('--- Durchlauf ' + $OkmDurchlauf4 + ' von 3 ---') -ForegroundColor Cyan
    # --------------------------------------------------------------------
    # Schritt 6/8: Meldung/Pause für den Benutzer (Risiko: gruen)
    # --------------------------------------------------------------------
    Write-Host '[6/8] Hinweis für den Benutzer …'
    try {
        $global:LASTEXITCODE = 0
        . {
            Write-Host 'Schleife' -ForegroundColor Cyan
        } | Out-Host
        if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
        $OkmErfolgreich++
    } catch {
        Write-Host ('FEHLER in Schritt 6/8 (Meldung/Pause für den Benutzer): ' + $_.Exception.Message) -ForegroundColor Red
        Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' Schritte.')
        Exit-OkmScript 1
    }

    # ===== Versuche (Block 5) =====
    try {
        # --------------------------------------------------------------------
        # Schritt 7/8: Dienst-Status prüfen (Risiko: gruen)
        # --------------------------------------------------------------------
        Write-Host '[7/8] Status von Dienst Spooler wird abgefragt …'
        try {
            $global:LASTEXITCODE = 0
            . {
                Get-Service -Name 'Spooler' | Format-Table Name, DisplayName, Status, StartType -AutoSize
            } | Out-Host
            if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
            $OkmErfolgreich++
        } catch {
            Write-Host ('FEHLER in Schritt 7/8 (Dienst-Status prüfen): ' + $_.Exception.Message) -ForegroundColor Red
            throw
        }

    } catch {
        Write-Host 'Ein Schritt ist fehlgeschlagen - der Fehler wird wie vorgesehen übergangen.' -ForegroundColor Yellow
    }
    # ===== Ende Versuche (Block 5) =====

}

# --------------------------------------------------------------------
# Schritt 8/8: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[8/8] Hinweis für den Benutzer …'
try {
    $global:LASTEXITCODE = 0
    . {
        Write-Host 'Ende' -ForegroundColor Cyan
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 8/8 (Meldung/Pause für den Benutzer): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' Schritte.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' Schritte erfolgreich ausgeführt.') -ForegroundColor Green
Exit-OkmScript 0
