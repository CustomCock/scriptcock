#Requires -Version 5.1
# ======================================================================
# Titel:             Windows Update reparieren
# Beschreibung:      Setzt die Windows-Update-Komponenten zurück. In PowerShell wird zusätzlich SetupDiag zur Fehleranalyse ausgeführt.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Enthaltene Schritte:
#    1. Festplattenbelegung anzeigen [Risiko: gruen]
#    2. Windows-Update-Komponenten zurücksetzen [Risiko: rot, Admin]
#    3. SetupDiag herunterladen und ausführen [Risiko: gelb, Admin]
#    4. Meldung/Pause für den Benutzer [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

$ErrorActionPreference = 'Stop'
$OkmLog = Join-Path $env:TEMP ('okm-script-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$OkmGesamt = 4
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
# Schritt 1/4: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[1/4] Festplattenbelegung wird ermittelt …'
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
    Write-Host ('FEHLER in Schritt 1/4 (Festplattenbelegung anzeigen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 2/4: Windows-Update-Komponenten zurücksetzen (Risiko: rot)
# --------------------------------------------------------------------
Write-Host '[2/4] Windows-Update-Komponenten werden zurückgesetzt …'
Write-Host 'ACHTUNG: Dieser Schritt ist destruktiv: Windows-Update-Komponenten zurücksetzen' -ForegroundColor Yellow
$OkmAntwort = Read-Host 'Zum Fortfahren JA eingeben (alles andere bricht ab)'
if ($OkmAntwort -cne 'JA') {
    Write-Host 'Abgebrochen. Es wurde nichts weiter ausgeführt.' -ForegroundColor Yellow
    Exit-OkmScript 2
}
try {
    $global:LASTEXITCODE = 0
    . {
        $okmDienste = 'wuauserv', 'cryptSvc', 'bits', 'msiserver'
        foreach ($okmD in $okmDienste) { Stop-Service -Name $okmD -Force -ErrorAction SilentlyContinue }
        $okmStempel = Get-Date -Format 'yyyyMMdd-HHmmss'
        Rename-Item -LiteralPath (Join-Path $env:SystemRoot 'SoftwareDistribution') -NewName ('SoftwareDistribution.' + $okmStempel + '.old')
        Rename-Item -LiteralPath (Join-Path $env:SystemRoot 'System32\catroot2') -NewName ('catroot2.' + $okmStempel + '.old')
        foreach ($okmD in $okmDienste) { Start-Service -Name $okmD }
        Write-Host 'Fertig. Bitte den Rechner neu starten und Windows Update erneut ausführen.'
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 2/4 (Windows-Update-Komponenten zurücksetzen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/4: SetupDiag herunterladen und ausführen (Risiko: gelb)
# --------------------------------------------------------------------
Write-Host '[3/4] SetupDiag wird heruntergeladen und ausgeführt …'
try {
    $global:LASTEXITCODE = 0
    . {
        New-Item -ItemType Directory -Path C:\temp -Force | Out-Null
        Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/?linkid=870142' -OutFile C:\temp\SetupDiag.exe -UseBasicParsing
        cd C:\temp
        .\SetupDiag.exe /Output:C:\temp\setupdiag.log
        Get-Content C:\temp\setupdiag.log
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 3/4 (SetupDiag herunterladen und ausführen): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 4/4: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
Write-Host '[4/4] Hinweis für den Benutzer …'
try {
    $global:LASTEXITCODE = 0
    . {
        Write-Host 'Bitte den Rechner jetzt neu starten und Windows Update erneut ausführen.' -ForegroundColor Cyan
        [void](Read-Host 'Weiter mit Enter')
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
} catch {
    Write-Host ('FEHLER in Schritt 4/4 (Meldung/Pause für den Benutzer): ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Erfolgreich bis dahin: ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
    Exit-OkmScript 1
}

Write-Host ''
Write-Host ('Fertig, ' + $OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten erfolgreich.') -ForegroundColor Green
Exit-OkmScript 0
