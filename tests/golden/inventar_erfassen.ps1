#Requires -Version 5.1
# ======================================================================
# Titel:             Seriennummer und Inventar erfassen
# Beschreibung:      Sammelt Seriennummer, Hardware, Betriebssystem, Lizenzstatus und installierte Programme für die Inventarisierung.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  keine
# Enthaltene Schritte:
#    1. Seriennummer und Modell [Risiko: gruen]
#    2. Systeminfo anzeigen [Risiko: gruen]
#    3. Windows-Version (Feature-Update) [Risiko: gruen]
#    4. Windows-Lizenzstatus [Risiko: gruen]
#    5. Letzter Neustart und ausstehender Neustart [Risiko: gruen]
#    6. Installierte Software auflisten [Risiko: gruen]
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
$OkmGesamt = 6
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
Write-OkmInfo ' okm Script-Baukasten · Seriennummer und Inventar erfassen'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

Write-OkmInfo 'Rechte: ohne erhöhte Rechte'

# Rückgabewerte der Schritte (Namen vergibt der Baukasten; $null = unbekannt)
$script:OkmS5_stunden = $null

# --------------------------------------------------------------------
# Schritt 1/6: Seriennummer und Modell (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/6] Hardware-Daten werden gelesen ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmCs = Get-CimInstance -ClassName Win32_ComputerSystem
        $okmBios = Get-CimInstance -ClassName Win32_BIOS
        [PSCustomObject]@{
            Hersteller     = $okmCs.Manufacturer
            Modell         = $okmCs.Model
            Seriennummer   = $okmBios.SerialNumber
            'BIOS-Version' = $okmBios.SMBIOSBIOSVersion
            'BIOS-Datum'   = $okmBios.ReleaseDate
        } | Format-List
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
# Schritt 2/6: Systeminfo anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/6] Systeminformationen werden gesammelt ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmOs = Get-CimInstance -ClassName Win32_OperatingSystem
        $okmCs = Get-CimInstance -ClassName Win32_ComputerSystem
        $okmCpu = Get-CimInstance -ClassName Win32_Processor | Select-Object -First 1
        $okmLaufzeit = (Get-Date) - $okmOs.LastBootUpTime
        [PSCustomObject]@{
            Rechnername       = $env:COMPUTERNAME
            Betriebssystem    = $okmOs.Caption
            Version           = $okmOs.Version
            Build             = $okmOs.BuildNumber
            Prozessor         = $okmCpu.Name.Trim()
            'Kerne/Threads'   = '{0}/{1}' -f $okmCpu.NumberOfCores, $okmCpu.NumberOfLogicalProcessors
            'RAM gesamt (GB)' = [math]::Round($okmCs.TotalPhysicalMemory / 1GB, 1)
            'RAM frei (GB)'   = [math]::Round($okmOs.FreePhysicalMemory / 1MB, 1)
            Laufzeit          = '{0} Tage {1} Std. {2} Min.' -f $okmLaufzeit.Days, $okmLaufzeit.Hours, $okmLaufzeit.Minutes
        } | Format-List
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
# Schritt 3/6: Windows-Version (Feature-Update) (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 3
Write-OkmInfo '[3/6] Windows-Version wird gelesen ...'
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

# --------------------------------------------------------------------
# Schritt 4/6: Windows-Lizenzstatus (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 4
Write-OkmInfo '[4/6] Lizenzstatus wird abgefragt ...'
try {
    $global:LASTEXITCODE = 0
    . {
        cscript.exe //nologo "$env:SystemRoot\System32\slmgr.vbs" /dli
        cscript.exe //nologo "$env:SystemRoot\System32\slmgr.vbs" /xpr
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
# Schritt 5/6: Letzter Neustart und ausstehender Neustart (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 5
Write-OkmInfo '[5/6] Startzeit und ausstehende Neustarts werden geprüft ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmStart = (Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime
        $okmLaufzeit = (Get-Date) - $okmStart
        $script:OkmS5_stunden = [math]::Floor($okmLaufzeit.TotalHours)
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
    if ("$($script:OkmS5_stunden)" -match '^-?[0-9]+$') { $script:OkmS5_stunden = [long]"$($script:OkmS5_stunden)" } else { $script:OkmS5_stunden = $null }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 6/6: Installierte Software auflisten (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 6
Write-OkmInfo '[6/6] Installierte Software wird gelesen ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmPfade = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
        $okmSoftware = Get-ItemProperty -Path $okmPfade -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -and -not $_.SystemComponent }
        $okmSoftware | Sort-Object DisplayName -Unique |
            Format-Table @{ Name = 'Name'; Expression = { $_.DisplayName } }, @{ Name = 'Version'; Expression = { $_.DisplayVersion } },
                @{ Name = 'Hersteller'; Expression = { $_.Publisher } }, @{ Name = 'Installiert'; Expression = { $_.InstallDate } } -AutoSize -Wrap
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
