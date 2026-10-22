#Requires -Version 5.1
# ======================================================================
# Titel:             Systemdateien reparieren (DISM + SFC)
# Beschreibung:      Repariert beschädigte Windows-Systemdateien. Hilft bei seltsamen Fehlern, Abstürzen von Windows-Komponenten oder fehlgeschlagenen Updates.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Systemdateien reparieren (DISM + SFC) [Risiko: gelb, Admin]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

$ErrorActionPreference = 'Stop'
$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$OkmGesamt = 1
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
# Schritt 1/1: Systemdateien reparieren (DISM + SFC) (Risiko: gelb)
# --------------------------------------------------------------------
Write-Host '[1/1] Systemdateien werden geprüft und repariert (dauert) …'
try {
    $global:LASTEXITCODE = 0
    . {
        DISM.exe /Online /Cleanup-Image /RestoreHealth
        if ($LASTEXITCODE -ne 0) { throw ('DISM endete mit Code ' + $LASTEXITCODE) }
        sfc.exe /scannow
        if ($LASTEXITCODE -ne 0) { Write-Host 'SFC hat Probleme gemeldet – Details in C:\Windows\Logs\CBS\CBS.log.' -ForegroundColor Yellow }
        $global:LASTEXITCODE = 0
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/1 (Systemdateien reparieren (DISM + SFC)): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
