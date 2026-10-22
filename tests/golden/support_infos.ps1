#Requires -Version 5.1
# ======================================================================
# Titel:             Support-Infos anzeigen
# Beschreibung:      Zeigt Rechnername, Benutzer, IP-Adresse, Betriebssystem, Seriennummer und ggf. TeamViewer-/AnyDesk-ID – alles, was der Support am Telefon fragt.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Support-Infos anzeigen [Risiko: gruen]
#    2. Meldung/Pause für den Benutzer [Risiko: gruen]
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
# Schritt 1/2: Support-Infos anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/2] Support-Infos werden gesammelt …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmOs = Get-CimInstance -ClassName Win32_OperatingSystem
        $okmIps = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' }).IPAddress -join ', '
        Write-Host ('Rechnername:     ' + $env:COMPUTERNAME)
        Write-Host ('Benutzer:        ' + $env:USERDOMAIN + '\' + $env:USERNAME)
        Write-Host ('IP-Adresse(n):   ' + $okmIps)
        Write-Host ('Betriebssystem:  ' + $okmOs.Caption + ' (' + $okmOs.Version + ')')
        Write-Host ('Seriennummer:    ' + (Get-CimInstance -ClassName Win32_BIOS).SerialNumber)
        foreach ($okmSchluessel in 'HKLM:\SOFTWARE\TeamViewer', 'HKLM:\SOFTWARE\WOW6432Node\TeamViewer') {
            $okmTv = (Get-ItemProperty -Path $okmSchluessel -ErrorAction SilentlyContinue).ClientID
            if ($okmTv) { Write-Host ('TeamViewer-ID:   ' + $okmTv); break }
        }
        $okmAnyDesk = Join-Path $env:ProgramData 'AnyDesk\system.conf'
        if (Test-Path -LiteralPath $okmAnyDesk) {
            $okmAd = Select-String -LiteralPath $okmAnyDesk -Pattern '^ad\.anynet\.id=' | Select-Object -First 1
            if ($okmAd) { Write-Host ('AnyDesk-ID:      ' + $okmAd.Line.Split('=')[1]) }
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/2 (Support-Infos anzeigen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/2: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[2/2] Hinweis für den Benutzer …'
try {
    $global:LASTEXITCODE = 0
    . {
        Write-Host 'Diese Angaben bitte dem Support durchgeben.' -ForegroundColor Cyan
        [void](Read-Host 'Weiter mit Enter')
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 2/2 (Meldung/Pause für den Benutzer): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
