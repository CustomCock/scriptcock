#Requires -Version 5.1
# ======================================================================
# Titel:             Benutzerdaten sichern
# Beschreibung:      Kopiert Desktop, Dokumente, Bilder, Downloads usw. des angemeldeten Benutzers in einen Ordner – z. B. vor einer Neuinstallation.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Benutzerdaten sichern [Risiko: gelb]
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

# --------------------------------------------------------------------
# Schritt 1/1: Benutzerdaten sichern (Risiko: gelb)
# --------------------------------------------------------------------
Write-Host '[1/1] Benutzerdaten werden nach D:\Sicherung gesichert …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmZiel = Join-Path 'D:\Sicherung' ($env:USERNAME + '_' + (Get-Date -Format 'yyyy-MM-dd_HHmm'))
        $okmOrdner = [ordered]@{
            Desktop   = [Environment]::GetFolderPath('Desktop')
            Dokumente = [Environment]::GetFolderPath('MyDocuments')
            Bilder    = [Environment]::GetFolderPath('MyPictures')
            Favoriten = [Environment]::GetFolderPath('Favorites')
        }
        foreach ($okmEintrag in $okmOrdner.GetEnumerator()) {
            if (-not $okmEintrag.Value -or -not (Test-Path -LiteralPath $okmEintrag.Value)) { continue }
            Write-Host ('Sichere ' + $okmEintrag.Key + ' …')
            robocopy.exe $okmEintrag.Value (Join-Path $okmZiel $okmEintrag.Key) /E /R:1 /W:1 /NP /NFL /NDL /XJ
            if ($LASTEXITCODE -ge 8) { throw ('Robocopy-Fehler bei ' + $okmEintrag.Key) }
            $global:LASTEXITCODE = 0
        }
        Write-Host ('Gesichert nach: ' + $okmZiel) -ForegroundColor Green
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/1 (Benutzerdaten sichern): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
