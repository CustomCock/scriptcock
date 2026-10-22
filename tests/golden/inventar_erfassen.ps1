#Requires -Version 5.1
# ======================================================================
# Titel:             Seriennummer und Inventar erfassen
# Beschreibung:      Sammelt Seriennummer, Hardware, Betriebssystem, Lizenzstatus und installierte Programme für die Inventarisierung.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
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
# Schritt 1/6: Seriennummer und Modell (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/6] Hardware-Daten werden gelesen …'
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
} catch {
    Write-Host ('FEHLER in Schritt 1/6 (Seriennummer und Modell): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/6: Systeminfo anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[2/6] Systeminformationen werden gesammelt …'
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
    Write-Host ('FEHLER in Schritt 2/6 (Systeminfo anzeigen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/6: Windows-Version (Feature-Update) (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[3/6] Windows-Version wird gelesen …'
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
    Write-Host ('FEHLER in Schritt 3/6 (Windows-Version (Feature-Update)): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 4/6: Windows-Lizenzstatus (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[4/6] Lizenzstatus wird abgefragt …'
try {
    $global:LASTEXITCODE = 0
    . {
        cscript.exe //nologo "$env:SystemRoot\System32\slmgr.vbs" /dli
        cscript.exe //nologo "$env:SystemRoot\System32\slmgr.vbs" /xpr
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 4/6 (Windows-Lizenzstatus): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 5/6: Letzter Neustart und ausstehender Neustart (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[5/6] Startzeit und ausstehende Neustarts werden geprüft …'
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
    Write-Host ('FEHLER in Schritt 5/6 (Letzter Neustart und ausstehender Neustart): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 6/6: Installierte Software auflisten (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[6/6] Installierte Software wird gelesen …'
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
} catch {
    Write-Host ('FEHLER in Schritt 6/6 (Installierte Software auflisten): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
