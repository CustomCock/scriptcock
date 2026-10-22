#Requires -Version 5.1
# ======================================================================
# Titel:             Sicherheits-Schnellprüfung
# Beschreibung:      Prüft die wichtigsten Schutzmechanismen (Firewall, Virenschutz, Verschlüsselung, Admin-Konten) und zeigt Auffälligkeiten.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Sicherheits-Schnellcheck (Ampel) [Risiko: gruen, Admin]
#    2. Virenschutz-Status [Risiko: gruen]
#    3. Lokale Administratoren anzeigen [Risiko: gruen]
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

# Prüfung: Administratorrechte
$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'Dieses Script braucht Administratorrechte. Bitte PowerShell mit Rechtsklick > "Als Administrator ausführen" öffnen und das Script erneut starten.' -ForegroundColor Red
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 1/3: Sicherheits-Schnellcheck (Ampel) (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/3] Sicherheits-Schnellcheck läuft …'
try {
    $global:LASTEXITCODE = 0
    . {
        function Write-OkmAmpel([string]$Punkt, [string]$Status, [string]$Text) {
            $okmFarbe = @{ 'OK' = 'Green'; 'WARN' = 'Yellow'; 'FEHLER' = 'Red' }[$Status]
            Write-Host ('[{0,-6}] {1,-22} {2}' -f $Status, $Punkt, $Text) -ForegroundColor $okmFarbe
        }
        $okmAus = @(Get-NetFirewallProfile | Where-Object { -not $_.Enabled } | ForEach-Object { $_.Name })
        if ($okmAus.Count -eq 0) { Write-OkmAmpel 'Firewall' 'OK' 'alle Profile an' } else { Write-OkmAmpel 'Firewall' 'FEHLER' ('aus: ' + ($okmAus -join ', ')) }
        $okmAv = @(Get-CimInstance -Namespace 'root\SecurityCenter2' -ClassName AntiVirusProduct -ErrorAction SilentlyContinue | Where-Object { ('{0:x6}' -f [int]$_.productState).Substring(2, 2) -in @('10', '11') })
        if ($okmAv.Count -gt 0) { Write-OkmAmpel 'Virenschutz' 'OK' (($okmAv.displayName) -join ', ') } else { Write-OkmAmpel 'Virenschutz' 'FEHLER' 'kein aktiver Virenschutz gemeldet' }
        $okmBl = Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction SilentlyContinue
        if ($okmBl -and $okmBl.ProtectionStatus -eq 'On') { Write-OkmAmpel 'BitLocker' 'OK' ($env:SystemDrive + ' verschlüsselt') } else { Write-OkmAmpel 'BitLocker' 'WARN' ($env:SystemDrive + ' nicht geschützt') }
        $okmLetztes = Get-HotFix | Where-Object { $_.InstalledOn } | Sort-Object InstalledOn -Descending | Select-Object -First 1
        $okmAlter = if ($okmLetztes) { [math]::Floor(((Get-Date) - $okmLetztes.InstalledOn).TotalDays) } else { 999 }
        if ($okmAlter -le 35) { Write-OkmAmpel 'Updates' 'OK' ('letztes Update vor ' + $okmAlter + ' Tagen') } else { Write-OkmAmpel 'Updates' 'WARN' ('letztes Update vor ' + $okmAlter + ' Tagen') }
        $okmUac = (Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System').EnableLUA
        if ($okmUac -eq 1) { Write-OkmAmpel 'Benutzerkontensteuerung' 'OK' 'an' } else { Write-OkmAmpel 'Benutzerkontensteuerung' 'FEHLER' 'aus' }
        if ((Get-SmbServerConfiguration).EnableSMB1Protocol) { Write-OkmAmpel 'SMBv1' 'FEHLER' 'aktiviert' } else { Write-OkmAmpel 'SMBv1' 'OK' 'deaktiviert' }
        $okmRdp = (Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server').fDenyTSConnections -eq 0
        if ($okmRdp) { Write-OkmAmpel 'Remotedesktop' 'WARN' 'erlaubt – nur wenn gewollt' } else { Write-OkmAmpel 'Remotedesktop' 'OK' 'gesperrt' }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/3 (Sicherheits-Schnellcheck (Ampel)): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/3: Virenschutz-Status (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[2/3] Virenschutz-Status wird gelesen …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmProdukte = Get-CimInstance -Namespace 'root\SecurityCenter2' -ClassName AntiVirusProduct -ErrorAction SilentlyContinue
        foreach ($okmProdukt in $okmProdukte) {
            $okmHex = '{0:x6}' -f [int]$okmProdukt.productState
            $okmAktiv = $okmHex.Substring(2, 2) -in @('10', '11')
            $okmAktuell = $okmHex.Substring(4, 2) -eq '00'
            Write-Host ($okmProdukt.displayName + ': ' + $(if ($okmAktiv) { 'aktiv' } else { 'NICHT aktiv' }) + ', Signaturen ' + $(if ($okmAktuell) { 'aktuell' } else { 'VERALTET' })) -ForegroundColor $(if ($okmAktiv -and $okmAktuell) { 'Green' } else { 'Red' })
        }
        if (-not $okmProdukte) { Write-Host 'Kein Eintrag im Sicherheitscenter (Server oder kein Virenschutz).' -ForegroundColor Yellow }
        $okmDefender = Get-MpComputerStatus -ErrorAction SilentlyContinue
        if ($okmDefender) {
            $okmDefender | Format-List AMRunningMode, AntivirusEnabled, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated, QuickScanEndTime
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 2/3 (Virenschutz-Status): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/3: Lokale Administratoren anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[3/3] Lokale Administratoren werden aufgelistet …'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-LocalGroupMember -SID 'S-1-5-32-544' | Format-Table Name, ObjectClass, PrincipalSource -AutoSize
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 3/3 (Lokale Administratoren anzeigen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
