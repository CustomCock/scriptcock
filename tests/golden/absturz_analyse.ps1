#Requires -Version 5.1
# ======================================================================
# Titel:             Absturz-Analyse
# Beschreibung:      Sucht Bluescreens, unerwartete Neustarts und abstürzende Programme bzw. Kernel- und Systemfehler.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Bluescreen-Analyse [Risiko: gruen]
#    2. Unerwartete Neustarts [Risiko: gruen]
#    3. Abstürzende Programme [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

$ErrorActionPreference = 'Stop'
$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$OkmGesamt = 3
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
# Schritt 1/3: Bluescreen-Analyse (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/3] Bluescreens werden gesucht …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmBsod = Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-WER-SystemErrorReporting'; Id = 1001 } -MaxEvents 20 -ErrorAction SilentlyContinue
        if ($okmBsod) {
            $okmBsod | Format-Table TimeCreated, Message -AutoSize -Wrap
        } else {
            Write-Host 'Keine Bluescreens im Ereignisprotokoll gefunden.' -ForegroundColor Green
        }
        $okmDumps = Get-ChildItem -Path (Join-Path $env:SystemRoot 'Minidump') -Filter '*.dmp' -ErrorAction SilentlyContinue
        if ($okmDumps) { $okmDumps | Sort-Object LastWriteTime -Descending | Format-Table Name, LastWriteTime, Length -AutoSize }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/3 (Bluescreen-Analyse): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/3: Unerwartete Neustarts (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[2/3] Unerwartete Neustarts werden gesucht …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmEreignisse = Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = 41, 6008 } -MaxEvents 30 -ErrorAction SilentlyContinue
        if ($okmEreignisse) {
            $okmEreignisse | Format-Table TimeCreated, Id, Message -AutoSize -Wrap
        } else {
            Write-Host 'Keine unerwarteten Neustarts gefunden.' -ForegroundColor Green
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 2/3 (Unerwartete Neustarts): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/3: Abstürzende Programme (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[3/3] Programmabstürze der letzten 14 Tage werden ausgewertet …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmAbstuerze = Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1000; StartTime = (Get-Date).AddDays(-14) } -ErrorAction SilentlyContinue
        if ($okmAbstuerze) {
            $okmAbstuerze | Group-Object { $_.Properties[0].Value } | Sort-Object Count -Descending |
                Format-Table @{ Name = 'Programm'; Expression = { $_.Name } }, @{ Name = 'Abstürze'; Expression = { $_.Count } },
                    @{ Name = 'Zuletzt'; Expression = { ($_.Group | Sort-Object TimeCreated -Descending | Select-Object -First 1).TimeCreated } } -AutoSize
        } else {
            Write-Host 'Keine Programmabstürze gefunden.' -ForegroundColor Green
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 3/3 (Abstürzende Programme): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
