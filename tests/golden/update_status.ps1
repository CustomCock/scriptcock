#Requires -Version 5.1
# ======================================================================
# Titel:             Update-Status prüfen
# Beschreibung:      Zeigt die zuletzt installierten und die noch ausstehenden Updates.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Update-Status anzeigen [Risiko: gruen]
#    2. Letzter Neustart und ausstehender Neustart [Risiko: gruen]
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

# --------------------------------------------------------------------
# Schritt 1/2: Update-Status anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/2] Update-Status wird ermittelt …'
try {
    $global:LASTEXITCODE = 0
    . {
        Write-Host 'Zuletzt installierte Updates:'
        Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10 | Format-Table HotFixID, Description, InstalledOn -AutoSize
        Write-Host 'Suche ausstehende Updates …'
        $okmSuche = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
        $okmOffen = $okmSuche.Search("IsInstalled=0 and IsHidden=0").Updates
        if ($okmOffen.Count -eq 0) {
            Write-Host 'Keine ausstehenden Updates.' -ForegroundColor Green
        } else {
            Write-Host ($okmOffen.Count.ToString() + ' ausstehende Updates:') -ForegroundColor Yellow
            foreach ($okmUpdate in $okmOffen) { Write-Host (' - ' + $okmUpdate.Title) }
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/2 (Update-Status anzeigen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/2: Letzter Neustart und ausstehender Neustart (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[2/2] Startzeit und ausstehende Neustarts werden geprüft …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmStart = (Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime
        $okmLaufzeit = (Get-Date) - $okmStart
        Write-Host ('Letzter Start: ' + $okmStart.ToString('dd.MM.yyyy HH:mm') + ' (vor ' + $okmLaufzeit.Days + ' Tagen)')
        $okmGruende = @()
        if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') { $okmGruende += 'Windows-Komponenten' }
        if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') { $okmGruende += 'Windows Update' }
        if (Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations -ErrorAction SilentlyContinue) { $okmGruende += 'Ausstehende Dateioperationen' }
        if ($okmGruende) {
            Write-Host ('Neustart ausstehend: JA (' + ($okmGruende -join ', ') + ')') -ForegroundColor Yellow
        } else {
            Write-Host 'Neustart ausstehend: nein' -ForegroundColor Green
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 2/2 (Letzter Neustart und ausstehender Neustart): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
