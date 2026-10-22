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
# Schritt 1/2: Office-Version und Updatekanal (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/2] Office-Version wird gelesen …'
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
} catch {
    Write-Host ('FEHLER in Schritt 1/2 (Office-Version und Updatekanal): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/2: Entra-ID-/Azure-AD-Status (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[2/2] Geräte-Registrierung wird geprüft …'
try {
    $global:LASTEXITCODE = 0
    . {
        dsregcmd.exe /status | Select-String -Pattern 'AzureAdJoined|DomainJoined|WorkplaceJoined|EnterpriseJoined|TenantName|AzureAdPrt |DeviceAuthStatus' | ForEach-Object { $_.Line.Trim() }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 2/2 (Entra-ID-/Azure-AD-Status): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
