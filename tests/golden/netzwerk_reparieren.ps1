#Requires -Version 5.1
# ======================================================================
# Titel:             Netzwerk reparieren
# Beschreibung:      Die üblichen Handgriffe bei Netzwerkproblemen – DNS-Cache leeren, Netzwerkadapter neu starten, IP-Adresse neu holen – und danach prüfen, ob Internet und Namensauflösung wieder gehen.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  Administrator (Schritt 1, 2)
# Enthaltene Schritte:
#    1. DNS-Cache leeren [Risiko: gelb, Admin]
#    2. Netzwerkadapter neu starten [Risiko: gelb, Admin]
#    3. IP-Adresse erneuern (DHCP) [Risiko: gelb]
#    4. Ping auf Ziel [Risiko: gruen]
#    5. Namensauflösung (DNS) testen [Risiko: gruen]
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
$OkmGesamt = 5
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
Write-OkmInfo ' okm Script-Baukasten · Netzwerk reparieren'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

# Rechte: Administrator für Schritt 1 (DNS-Cache leeren), Schritt 2 (Netzwerkadapter neu starten)
$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if ($OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-OkmInfo 'Rechte: als Administrator gestartet'
} else {
    Write-OkmInfo 'Dieses Script braucht Administratorrechte für: Schritt 1 (DNS-Cache leeren), Schritt 2 (Netzwerkadapter neu starten).'
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
$script:OkmS4_erreichbar = $null
$script:OkmS4_ms = $null

# --------------------------------------------------------------------
# Schritt 1/5: DNS-Cache leeren (Risiko: gelb)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/5] DNS-Cache wird geleert ...'
try {
    $global:LASTEXITCODE = 0
    . {
        Clear-DnsClientCache
        Write-Host 'DNS-Cache wurde geleert.'
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
# Schritt 2/5: Netzwerkadapter neu starten (Risiko: gelb)
# --------------------------------------------------------------------
$OkmNr = 2
Write-OkmInfo '[2/5] Netzwerkadapter Ethernet wird neu gestartet ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmAdapter = @(Get-NetAdapter -Name 'Ethernet' -ErrorAction Stop)
        foreach ($okmA in $okmAdapter) {
            Write-OkmInfo ('Neustart: ' + $okmA.Name + ' (' + $okmA.InterfaceDescription + ')')
            Restart-NetAdapter -InputObject $okmA -Confirm:$false
        }
        Start-Sleep -Seconds 5
        Get-NetAdapter -Name ($okmAdapter | ForEach-Object { $_.Name }) | Format-Table Name, Status, LinkSpeed -AutoSize
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    Write-OkmInfo '      Tipp: Stimmt der Adaptername? Bei WLAN danach ggf. kurz warten, bis die Verbindung wieder steht.'
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 3/5: IP-Adresse erneuern (DHCP) (Risiko: gelb)
# --------------------------------------------------------------------
$OkmNr = 3
Write-OkmInfo '[3/5] IP-Adresse wird erneuert ...'
try {
    $global:LASTEXITCODE = 0
    . {
        ipconfig.exe /release
        ipconfig.exe /renew
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
# Schritt 4/5: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 4
Write-OkmInfo '[4/5] Ping auf 1.1.1.1 (4x) ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmAusgabe = @(ping.exe -n 4 '1.1.1.1')
        $okmRc = $LASTEXITCODE
        $okmAusgabe
        # ping.exe meldet auch "Zielhost nicht erreichbar" (Antwort eines Routers) mit Exit-Code 0 –
        # erreichbar ist das Ziel nur, wenn eine Antwort mit TTL kam.
        $script:OkmS4_erreichbar = ($okmRc -eq 0) -and (($okmAusgabe -join ' ') -match 'TTL=')
        $okmZeiten = [regex]::Matches(($okmAusgabe -join ' '), '=\s*(\d+)\s*ms')
        if ($script:OkmS4_erreichbar -and $okmZeiten.Count -gt 0) {
            # letzte Angabe = Mittelwert (de: "Mittelwert = 8ms", en: "Average = 8ms")
            $script:OkmS4_ms = $okmZeiten[$okmZeiten.Count - 1].Groups[1].Value
        }
        if (-not $script:OkmS4_erreichbar) {
            Write-Host 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.' -ForegroundColor Yellow
        }
        $global:LASTEXITCODE = 0
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    if ($null -ne $script:OkmS4_erreichbar) { $script:OkmS4_erreichbar = @('1', 'true', 'ja') -contains "$($script:OkmS4_erreichbar)" }
    if ("$($script:OkmS4_ms)" -match '^-?[0-9]+$') { $script:OkmS4_ms = [long]"$($script:OkmS4_ms)" } else { $script:OkmS4_ms = $null }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    Write-OkmInfo '      Tipp: Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping.'
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

# --------------------------------------------------------------------
# Schritt 5/5: Namensauflösung (DNS) testen (Risiko: gruen)
# --------------------------------------------------------------------
$OkmNr = 5
Write-OkmInfo '[5/5] DNS-Auflösung von www.microsoft.com wird geprüft ...'
try {
    $global:LASTEXITCODE = 0
    . {
        $okmAntwort = Resolve-DnsName -Name 'www.microsoft.com' -ErrorAction SilentlyContinue
        if ($okmAntwort) {
            $okmAntwort | Where-Object { $_.IPAddress } | Format-Table Name, Type, IPAddress -AutoSize
        } else {
            Write-Host 'Der Name kann NICHT aufgelöst werden.' -ForegroundColor Yellow
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

$OkmStatus = 'fertig'
Exit-OkmScript 0
