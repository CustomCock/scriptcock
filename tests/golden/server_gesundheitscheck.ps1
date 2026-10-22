#Requires -Version 5.1
# ======================================================================
# Titel:             Server-Gesundheitscheck
# Beschreibung:      Überblick über Laufzeit, Speicherplatz, Dienste, Fehler im Ereignisprotokoll bzw. Journal, RAID und Updates.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
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

$ErrorActionPreference = 'Stop'
$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$OkmGesamt = 6
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
# Schritt 1/6: Systeminfo anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/6] Systeminformationen werden gesammelt …'
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
} catch {
    Write-Host ('FEHLER in Schritt 1/6 (Systeminfo anzeigen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/6: Letzter Neustart und ausstehender Neustart (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[2/6] Startzeit und ausstehende Neustarts werden geprüft …'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmStart = (Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime
        $okmLaufzeit = (Get-Date) - $okmStart
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
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 2/6 (Letzter Neustart und ausstehender Neustart): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/6: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[3/6] Festplattenbelegung wird ermittelt …'
try {
    $global:LASTEXITCODE = 0
    . {
        Get-PSDrive -PSProvider FileSystem |
            Where-Object { $null -ne $_.Used } |
            Format-Table Name, Root, @{ Name = 'Belegt (GB)'; Expression = { [math]::Round($_.Used / 1GB, 1) } }, @{ Name = 'Frei (GB)'; Expression = { [math]::Round($_.Free / 1GB, 1) } } -AutoSize
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 3/6 (Festplattenbelegung anzeigen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 4/6: Gestoppte automatische Dienste finden (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[4/6] Gestoppte automatische Dienste werden gesucht …'
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
} catch {
    Write-Host ('FEHLER in Schritt 4/6 (Gestoppte automatische Dienste finden): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 5/6: Ereignisanzeige: letzte Fehler exportieren (Risiko: gelb)
# --------------------------------------------------------------------
Write-Host '[5/6] Die letzten 30 Fehlerereignisse werden nach C:\temp\ereignisse.csv exportiert …'
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
} catch {
    Write-Host ('FEHLER in Schritt 5/6 (Ereignisanzeige: letzte Fehler exportieren): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 6/6: Update-Status anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[6/6] Update-Status wird ermittelt …'
try {
    $global:LASTEXITCODE = 0
    . {
        Write-Host 'Zuletzt installierte Updates:'
        Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10 | Format-Table HotFixID, Description, InstalledOn -AutoSize
        Write-Host 'Suche ausstehende Updates …'
        $okmSuche = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
        $okmOffen = $okmSuche.Search("IsInstalled=0 and IsHidden=0").Updates
        if ($okmOffen.Count -eq 0) {
            Write-Host 'Keine ausstehenden Updates.' -ForegroundColor Green
        } else {
            Write-Host ($okmOffen.Count.ToString() + ' ausstehende Updates:') -ForegroundColor Yellow
            foreach ($okmUpdate in $okmOffen) { Write-Host (' - ' + $okmUpdate.Title) }
        }
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 6/6 (Update-Status anzeigen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
