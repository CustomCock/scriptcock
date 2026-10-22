#Requires -Version 5.1
# ======================================================================
# Titel:             Windows-11-Tauglichkeit prüfen
# Beschreibung:      Prüft TPM, Secure Boot, Prozessor, Arbeitsspeicher und Speicherplatz auf die Windows-11-Anforderungen.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Windows-11-Kompatibilität prüfen [Risiko: gruen, Admin]
#    2. Windows-Version (Feature-Update) [Risiko: gruen]
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

# Prüfung: Administratorrechte
$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'Dieses Script braucht Administratorrechte. Bitte PowerShell mit Rechtsklick > "Als Administrator ausführen" öffnen und das Script erneut starten.' -ForegroundColor Red
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 1/2: Windows-11-Kompatibilität prüfen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/2] Windows-11-Voraussetzungen werden geprüft …'
try {
    $global:LASTEXITCODE = 0
    . {
        function Write-OkmPruefpunkt([string]$Name, [bool]$Ok, [string]$Wert) {
            $okmFarbe = if ($Ok) { 'Green' } else { 'Red' }
            $okmText = if ($Ok) { 'OK    ' } else { 'FEHLT ' }
            Write-Host ($okmText + $Name + ': ' + $Wert) -ForegroundColor $okmFarbe
        }
        $okmTpm = Get-CimInstance -Namespace 'root/cimv2/security/microsofttpm' -ClassName Win32_Tpm -ErrorAction SilentlyContinue
        $okmTpmVersion = if ($okmTpm) { ($okmTpm.SpecVersion -split ',')[0].Trim() } else { 'nicht gefunden' }
        Write-OkmPruefpunkt 'TPM 2.0' ($okmTpmVersion -like '2.*') $okmTpmVersion
        try { $okmSecureBoot = Confirm-SecureBootUEFI } catch { $okmSecureBoot = $false }
        Write-OkmPruefpunkt 'Secure Boot' $okmSecureBoot ($(if ($okmSecureBoot) { 'aktiv' } else { 'aus oder kein UEFI' }))
        $okmRam = [math]::Round((Get-CimInstance -ClassName Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
        Write-OkmPruefpunkt 'Arbeitsspeicher >= 4 GB' ($okmRam -ge 4) ($okmRam.ToString() + ' GB')
        $okmDisk = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='C:'"
        $okmDiskGb = [math]::Round($okmDisk.Size / 1GB)
        Write-OkmPruefpunkt 'Systemlaufwerk >= 64 GB' ($okmDiskGb -ge 64) ($okmDiskGb.ToString() + ' GB')
        $okmCpu = Get-CimInstance -ClassName Win32_Processor | Select-Object -First 1
        Write-Host ('INFO  Prozessor: ' + $okmCpu.Name.Trim() + ' – bitte mit der Microsoft-Liste abgleichen')
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 1/2 (Windows-11-Kompatibilität prüfen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/2: Windows-Version (Feature-Update) (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[2/2] Windows-Version wird gelesen …'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' |
            Format-List ProductName, DisplayVersion, CurrentBuild, UBR, EditionID
        Write-Host 'Hinweis: Windows 11 meldet unter ProductName teils noch "Windows 10" – maßgeblich ist die Build-Nummer (ab 22000 = Windows 11).'
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 2/2 (Windows-Version (Feature-Update)): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
