#Requires -Version 5.1
# ======================================================================
# Titel:             Server-Gesundheitscheck
# Beschreibung:      Überblick über Laufzeit, Speicherplatz, Dienste, Fehler im Ereignisprotokoll bzw. Journal, RAID und Updates.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  keine
# Enthaltene Schritte:
#    1. Systeminfo anzeigen [Risiko: gruen]
#    2. Letzter Neustart und ausstehender Neustart [Risiko: gruen]
#    3. Festplattenbelegung anzeigen [Risiko: gruen]
#    4. Gestoppte automatische Dienste finden [Risiko: gruen]
#    5. Ereignisanzeige: letzte Fehler exportieren [Risiko: gelb]
#    6. Update-Status anzeigen [Risiko: gruen]
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
Write-OkmInfo ' okm Script-Baukasten · Server-Gesundheitscheck'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

Write-OkmInfo 'Rechte: ohne erhöhte Rechte'

# Rückgabewerte der Schritte (Namen vergibt der Baukasten; $null = unbekannt)
$script:OkmS2_stunden = $null
$script:OkmS3_frei_prozent = $null
$script:OkmS6_ausstehend = $null

# --------------------------------------------------------------------
# Schritt 1/6: Systeminfo anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/6] Systeminformationen werden gesammelt ...'
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
# Schritt 2/6: Letzter Neustart und ausstehender Neustart (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/6] Startzeit und ausstehende Neustarts werden geprüft ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmStart = (Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime
        $okmLaufzeit = (Get-Date) - $okmStart
        $script:OkmS2_stunden = [math]::Floor($okmLaufzeit.TotalHours)
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
    if ("$($script:OkmS2_stunden)" -match '^-?[0-9]+$') { $script:OkmS2_stunden = [long]"$($script:OkmS2_stunden)" } else { $script:OkmS2_stunden = $null }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/6: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 3
Write-OkmInfo '[3/6] Festplattenbelegung wird ermittelt ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-PSDrive -PSProvider FileSystem |
            Where-Object { $null -ne $_.Used } |
            Format-Table Name, Root, @{ Name = 'Belegt (GB)'; Expression = { [math]::Round($_.Used / 1GB, 1) } }, @{ Name = 'Frei (GB)'; Expression = { [math]::Round($_.Free / 1GB, 1) } } -AutoSize
        $okmSystem = Get-PSDrive -Name $env:SystemDrive.Substring(0, 1) -ErrorAction SilentlyContinue
        if ($okmSystem -and ($okmSystem.Used + $okmSystem.Free) -gt 0) {
            $script:OkmS3_frei_prozent = [math]::Floor(100 * $okmSystem.Free / ($okmSystem.Used + $okmSystem.Free))
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    if ("$($script:OkmS3_frei_prozent)" -match '^-?[0-9]+$') { $script:OkmS3_frei_prozent = [long]"$($script:OkmS3_frei_prozent)" } else { $script:OkmS3_frei_prozent = $null }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 4/6: Gestoppte automatische Dienste finden (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 4
Write-OkmInfo '[4/6] Gestoppte automatische Dienste werden gesucht ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmDienste = Get-CimInstance -ClassName Win32_Service -Filter "StartMode='Auto' AND State<>'Running'"
        if ($okmDienste) {
            $okmDienste | Sort-Object DisplayName | Format-Table Name, DisplayName, State, ExitCode -AutoSize -Wrap
        } else {
            Write-Host 'Alle automatischen Dienste laufen.' -ForegroundColor Green
        }
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
# Schritt 5/6: Ereignisanzeige: letzte Fehler exportieren (Risiko: gelb)
# --------------------------------------------------------------------
$OkmNr = 5
Write-OkmInfo '[5/6] Die letzten 30 Fehlerereignisse werden nach C:\temp\ereignisse.csv exportiert ...'
try {
    $global:LASTEXITCODE = 0
    . {
        New-Item -ItemType Directory -Path (Split-Path -Parent 'C:\temp\ereignisse.csv') -Force | Out-Null
        $okmEreignisse = Get-WinEvent -FilterHashtable @{ LogName = 'System', 'Application'; Level = 1, 2 } -MaxEvents 30 -ErrorAction SilentlyContinue
        $okmEreignisse | Select-Object TimeCreated, LogName, ProviderName, Id, LevelDisplayName, Message |
            Export-Csv -LiteralPath 'C:\temp\ereignisse.csv' -NoTypeInformation -Encoding UTF8 -Delimiter ';'
        $okmEreignisse | Select-Object -First 10 TimeCreated, ProviderName, Id, Message | Format-Table -AutoSize -Wrap
        Write-Host ('Exportiert nach: ' + 'C:\temp\ereignisse.csv')
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
# Schritt 6/6: Update-Status anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 6
Write-OkmInfo '[6/6] Update-Status wird ermittelt ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Write-Host 'Zuletzt installierte Updates:'
        Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10 | Format-Table HotFixID, Description, InstalledOn -AutoSize
        Write-Host 'Suche ausstehende Updates …'
        $okmSuche = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
        $okmOffen = $okmSuche.Search("IsInstalled=0 and IsHidden=0").Updates
        $script:OkmS6_ausstehend = $okmOffen.Count
        if ($okmOffen.Count -eq 0) {
            Write-Host 'Keine ausstehenden Updates.' -ForegroundColor Green
        } else {
            Write-Host ($okmOffen.Count.ToString() + ' ausstehende Updates:') -ForegroundColor Yellow
            foreach ($okmUpdate in $okmOffen) { Write-Host (' - ' + $okmUpdate.Title) }
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    if ("$($script:OkmS6_ausstehend)" -match '^-?[0-9]+$') { $script:OkmS6_ausstehend = [long]"$($script:OkmS6_ausstehend)" } else { $script:OkmS6_ausstehend = $null }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

$OkmStatus = 'fertig'
Exit-OkmScript 0
