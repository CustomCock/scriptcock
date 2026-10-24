#Requires -Version 5.1
# ======================================================================
# Titel:             Sicherheits-Schnellprüfung
# Beschreibung:      Prüft die wichtigsten Schutzmechanismen (Firewall, Virenschutz, Verschlüsselung, Admin-Konten) und zeigt Auffälligkeiten.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  Administrator (Schritt 1)
# Enthaltene Schritte:
#    1. Sicherheits-Schnellcheck (Ampel) [Risiko: gruen, Admin]
#    2. Virenschutz-Status [Risiko: gruen]
#    3. Lokale Administratoren anzeigen [Risiko: gruen]
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
$OkmGesamt = 3
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
Write-OkmInfo ' okm Script-Baukasten · Sicherheits-Schnellprüfung'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

# Rechte: Administrator für Schritt 1 (Sicherheits-Schnellcheck (Ampel))
$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if ($OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-OkmInfo 'Rechte: als Administrator gestartet'
} else {
    Write-OkmInfo 'Dieses Script braucht Administratorrechte für: Schritt 1 (Sicherheits-Schnellcheck (Ampel)).'
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

# Rückgabewerte der Schritte (Namen vergibt der Baukasten; $null = unbekannt)
$script:OkmS2_aktiv = $null

# --------------------------------------------------------------------
# Schritt 1/3: Sicherheits-Schnellcheck (Ampel) (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/3] Sicherheits-Schnellcheck läuft ...'
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
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/3: Virenschutz-Status (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/3] Virenschutz-Status wird gelesen ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmProdukte = Get-CimInstance -Namespace 'root\SecurityCenter2' -ClassName AntiVirusProduct -ErrorAction SilentlyContinue
        $script:OkmS2_aktiv = $false
        foreach ($okmProdukt in $okmProdukte) {
            $okmHex = '{0:x6}' -f [int]$okmProdukt.productState
            $okmAktiv = $okmHex.Substring(2, 2) -in @('10', '11')
            $okmAktuell = $okmHex.Substring(4, 2) -eq '00'
            if ($okmAktiv) { $script:OkmS2_aktiv = $true }
            Write-Host ($okmProdukt.displayName + ': ' + $(if ($okmAktiv) { 'aktiv' } else { 'NICHT aktiv' }) + ', Signaturen ' + $(if ($okmAktuell) { 'aktuell' } else { 'VERALTET' })) -ForegroundColor $(if ($okmAktiv -and $okmAktuell) { 'Green' } else { 'Red' })
        }
        if (-not $okmProdukte) { Write-Host 'Kein Eintrag im Sicherheitscenter (Server oder kein Virenschutz).' -ForegroundColor Yellow }
        $okmDefender = Get-MpComputerStatus -ErrorAction SilentlyContinue
        if ($okmDefender -and $okmDefender.AntivirusEnabled -and $okmDefender.RealTimeProtectionEnabled) { $script:OkmS2_aktiv = $true }
        if ($okmDefender) {
            $okmDefender | Format-List AMRunningMode, AntivirusEnabled, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated, QuickScanEndTime
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    if ($null -ne $script:OkmS2_aktiv) { $script:OkmS2_aktiv = @('1', 'true', 'ja') -contains "$($script:OkmS2_aktiv)" }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/3: Lokale Administratoren anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 3
Write-OkmInfo '[3/3] Lokale Administratoren werden aufgelistet ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-LocalGroupMember -SID 'S-1-5-32-544' | Format-Table Name, ObjectClass, PrincipalSource -AutoSize
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
