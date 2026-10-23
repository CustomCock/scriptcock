#Requires -Version 5.1
# ======================================================================
# Titel:             Windows-11-Tauglichkeit prüfen
# Beschreibung:      Prüft TPM, Secure Boot, Prozessor, Arbeitsspeicher und Speicherplatz auf die Windows-11-Anforderungen.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  Administrator (Schritt 1)
# Enthaltene Schritte:
#    1. Windows-11-Kompatibilität prüfen [Risiko: gruen, Admin]
#    2. Windows-Version (Feature-Update) [Risiko: gruen]
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
        'neustart' { Write-Host ' Läuft im neuen Fenster mit Administratorrechten weiter.' }
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
    if ($script:OkmStatus -ne 'neustart') { Wait-OkmEnde }
    exit $Code
}

# Netz für alles, was kein Schritt abfängt: Meldung + Zusammenfassung statt stillem Ende
trap {
    Write-OkmFehler ('Unerwarteter Fehler: ' + $_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $script:OkmStatus = 'fehler'
    Exit-OkmScript 1
}

Write-OkmInfo '=============================================='
Write-OkmInfo ' okm Script-Baukasten · Windows-11-Tauglichkeit prüfen'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

# Rechte: Administrator für Schritt 1 (Windows-11-Kompatibilität prüfen)
$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if ($OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-OkmInfo 'Rechte: als Administrator gestartet'
} else {
    Write-OkmInfo 'Dieses Script braucht Administratorrechte für: Schritt 1 (Windows-11-Kompatibilität prüfen).'
    if (-not $PSCommandPath) {
        Write-OkmFehler 'Bitte PowerShell mit Rechtsklick > "Als Administrator ausführen" öffnen und das Script erneut starten.'
        $OkmStatus = 'rechte'
        Exit-OkmScript 1
    }
    Write-OkmInfo 'Es wird jetzt mit Administratorrechten neu gestartet (Windows fragt gleich nach).'
    # Pfad in Anführungszeichen: Start-Process quotet Argumente mit Leerzeichen nicht
    $OkmArgumente = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
    if ($OkmKeinePause) { $OkmArgumente += '-NoPause' }
    try {
        Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $OkmArgumente | Out-Null
        $OkmStatus = 'neustart'
        Exit-OkmScript 0
    } catch {
        Write-OkmFehler 'Die Administratorrechte wurden abgelehnt (Benutzerkontensteuerung). Ohne sie kann das Script nicht weitermachen.'
        $OkmStatus = 'rechte'
        Exit-OkmScript 1
    }
}

# --------------------------------------------------------------------
# Schritt 1/2: Windows-11-Kompatibilität prüfen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/2] Windows-11-Voraussetzungen werden geprüft ...'
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
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/2: Windows-Version (Feature-Update) (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/2] Windows-Version wird gelesen ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' |
            Format-List ProductName, DisplayVersion, CurrentBuild, UBR, EditionID
        Write-Host 'Hinweis: Windows 11 meldet unter ProductName teils noch "Windows 10" – maßgeblich ist die Build-Nummer (ab 22000 = Windows 11).'
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

$OkmStatus = 'fertig'
Exit-OkmScript 0
