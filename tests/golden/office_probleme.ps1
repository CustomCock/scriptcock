#Requires -Version 5.1
# ======================================================================
# Titel:             Office-Probleme eingrenzen
# Beschreibung:      Zeigt Office-Version und Updatekanal sowie den Anmeldestatus des Geräts (Entra ID) – die häufigsten Ursachen für Office- und Teams-Probleme.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Office-Version und Updatekanal [Risiko: gruen]
#    2. Entra-ID-/Azure-AD-Status [Risiko: gruen]
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
$OkmGesamt = 2
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
    Wait-OkmEnde
    exit $Code
}

Write-OkmInfo '=============================================='
Write-OkmInfo ' okm Script-Baukasten · Office-Probleme eingrenzen'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

# --------------------------------------------------------------------
# Schritt 1/2: Office-Version und Updatekanal (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/2] Office-Version wird gelesen ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmC2r = Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration' -ErrorAction SilentlyContinue
        if (-not $okmC2r) { throw 'Kein Klick-und-Los-Office gefunden.' }
        $okmKanalUrl = if ($okmC2r.UpdateChannel) { $okmC2r.UpdateChannel } else { $okmC2r.CDNBaseUrl }
        $okmKanaele = @{
            '492350f6-3a01-4f97-b9c0-c7c6ddf67d60' = 'Aktueller Kanal'
            '64256afe-f5d9-4f86-8936-8840a6a4f5be' = 'Aktueller Kanal (Vorschau)'
            '55336b82-a18d-4dd6-b5f6-9e5095c314a6' = 'Monatlicher Enterprise-Kanal'
            '7ffbc6bf-bc32-4f92-8982-f9dd17fd3114' = 'Halbjährlicher Enterprise-Kanal'
            'b8f9b850-328d-4355-9145-c59439a0c4cf' = 'Halbjährlicher Enterprise-Kanal (Vorschau)'
            '5440fd1f-7ecb-4221-8110-145efaa6372f' = 'Beta-Kanal'
        }
        $okmKanal = 'unbekannt'
        foreach ($okmGuid in $okmKanaele.Keys) { if ($okmKanalUrl -like ('*' + $okmGuid + '*')) { $okmKanal = $okmKanaele[$okmGuid] } }
        Write-Host ('Version:      ' + $okmC2r.VersionToReport)
        Write-Host ('Architektur:  ' + $okmC2r.Platform)
        Write-Host ('Produkte:     ' + $okmC2r.ProductReleaseIds)
        Write-Host ('Updatekanal:  ' + $okmKanal)
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler $_.Exception.Message
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/2: Entra-ID-/Azure-AD-Status (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/2] Geräte-Registrierung wird geprüft ...'
try {
    $global:LASTEXITCODE = 0
    . {
        dsregcmd.exe /status | Select-String -Pattern 'AzureAdJoined|DomainJoined|WorkplaceJoined|EnterpriseJoined|TenantName|AzureAdPrt |DeviceAuthStatus' | ForEach-Object { $_.Line.Trim() }
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
