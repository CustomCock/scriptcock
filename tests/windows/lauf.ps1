# Windows-CI (windows-latest, Windows PowerShell 5.1): führt die von tools/windows_test.py erzeugten
# Scripte wirklich aus und prüft danach die Registry.
#
#   python tools/windows_test.py C:\okm-ci
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests\windows\lauf.ps1 -Ordner C:\okm-ci
#
# Je Lauf (manifest.json): Vorbedingungen per reg.exe, Script starten (PowerShell: -NoPause, CMD: /nopause;
# rote Schritte bekommen „JA“ über die umgeleitete Eingabe), Exit-Code und Ausgabe prüfen, Werte prüfen
# (reg query für vorhanden/fehlt, exakter Vergleich von Typ und Daten über .NET), bei „rueckgaengig“ die
# .reg-Dateien aus dem Sicherungsordner zurückspielen (höchste Nummer zuerst) und erneut prüfen.
# Ergebnis als Tabelle (auch in $env:GITHUB_STEP_SUMMARY); Exit-Code 1, wenn etwas fehlschlägt.

param([string]$Ordner = 'C:\okm-ci')

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$manifest = Get-Content -LiteralPath (Join-Path $Ordner 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$ergebnisse = New-Object System.Collections.ArrayList

# --- Voraussetzungen -----------------------------------------------------------------------------
$identitaet = [Security.Principal.WindowsIdentity]::GetCurrent()
$admin = (New-Object Security.Principal.WindowsPrincipal($identitaet)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Host '::error::Der Runner läuft nicht mit Administratorrechten – die Scripte würden sich per UAC neu starten.'
    exit 1
}

function Get-Konsolenbenutzer {
    # Wie Get-OkmKonsolenBenutzer im Script: Besitzer von explorer.exe
    $sids = @()
    foreach ($p in @(Get-CimInstance -ClassName Win32_Process -Filter "Name = 'explorer.exe'" -ErrorAction SilentlyContinue)) {
        $b = Invoke-CimMethod -InputObject $p -MethodName GetOwner -ErrorAction SilentlyContinue
        if ($b -and $b.User) {
            $sids += (New-Object Security.Principal.NTAccount($b.Domain, $b.User)).Translate([Security.Principal.SecurityIdentifier]).Value
        }
    }
    return @($sids | Sort-Object -Unique)
}
$konsole = @(Get-Konsolenbenutzer)
if ($konsole.Count -eq 0) {
    # Auf dem Runner gibt es oft keinen Desktop: Explorer als Runner-Benutzer starten
    Write-Host 'Kein explorer.exe – starte ihn für die Tests von „Angemeldeter Benutzer“.'
    Start-Process -FilePath 'explorer.exe' -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 8
    $konsole = @(Get-Konsolenbenutzer)
}
$benutzerSid = $null
if ($konsole.Count -eq 1) { $benutzerSid = $konsole[0] }
Write-Host ('Runner: ' + $identitaet.Name + ' · Konsolenbenutzer-SID: ' + $(if ($benutzerSid) { $benutzerSid } else { '(keiner/mehrere)' }))

# --- Registry lesen ------------------------------------------------------------------------------
$arten = @{
    REG_SZ = 'String'; REG_EXPAND_SZ = 'ExpandString'; REG_DWORD = 'DWord'; REG_QWORD = 'QWord'
    REG_MULTI_SZ = 'MultiString'; REG_BINARY = 'Binary'
}

function Get-RegPfad([string]$Pfad) {
    # HKLM\… bzw. HKCU\… → (Basisschlüssel, Unterpfad, reg.exe-Pfad); HKCU = Konsolenbenutzer (HKU\<SID>)
    $wurzel, $rest = $Pfad -split '\\', 2
    if ($wurzel -eq 'HKLM') {
        return @([Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', 'Registry64'), $rest, $Pfad)
    }
    if ($wurzel -eq 'HKCU') {
        if (-not $benutzerSid) { throw 'Kein Konsolenbenutzer' }
        $basis = [Microsoft.Win32.RegistryKey]::OpenBaseKey('Users', 'Registry64')
        return @($basis, ($benutzerSid + '\' + $rest), ('HKU\' + $benutzerSid + '\' + $rest))
    }
    throw ('Unbekannte Wurzel: ' + $Pfad)
}

function Test-RegQuery([string]$RegPfad, [string]$Name) {
    if ($Name) { $null = & reg.exe query $RegPfad /v $Name /reg:64 2>&1 } else { $null = & reg.exe query $RegPfad /ve /reg:64 2>&1 }
    $code = $LASTEXITCODE
    $global:LASTEXITCODE = 0
    return ($code -eq 0)
}

function Format-Wert($Art, $Wert) {
    switch ($Art) {
        'DWord' { return [string][BitConverter]::ToUInt32([BitConverter]::GetBytes([int32]$Wert), 0) }
        'QWord' { return [string][BitConverter]::ToUInt64([BitConverter]::GetBytes([int64]$Wert), 0) }
        'Binary' { return (($Wert | ForEach-Object { '{0:x2}' -f $_ }) -join '') }
        'MultiString' { return ($Wert -join "`n") }
        default { return [string]$Wert }
    }
}

function Test-Pruefung($P) {
    # Liefert $null bei Erfolg, sonst eine Meldung
    if ($P.art -eq 'datei_enthaelt') {
        $datei = $P.datei
        if (-not (Test-Path -LiteralPath $datei)) { return ('Datei fehlt: ' + $datei) }
        $inhalt = [IO.File]::ReadAllText($datei)  # reg export: UTF-16 mit BOM
        if ($inhalt -notlike ('*' + $P.text + '*')) { return ('„' + $P.text + '“ fehlt in ' + $datei) }
        return $null
    }
    $basis, $unter, $regPfad = Get-RegPfad $P.pfad
    $schluessel = $basis.OpenSubKey($unter)
    try {
        switch ($P.art) {
            'kein_schluessel' {
                if ($schluessel) { return ('Schlüssel sollte fehlen: ' + $regPfad) }
                return $null
            }
            'kein_wert' {
                if (Test-RegQuery $regPfad $P.name) { return ('reg query findet ' + $regPfad + ' → ' + $P.name) }
                if ($schluessel -and ($schluessel.GetValueNames() -contains $P.name)) { return ('Wert sollte fehlen: ' + $P.name) }
                return $null
            }
            'wert' {
                if (-not (Test-RegQuery $regPfad $P.name)) { return ('reg query findet nicht: ' + $regPfad + ' → ' + $P.name) }
                if (-not $schluessel) { return ('Schlüssel fehlt: ' + $regPfad) }
                $art = [string]$schluessel.GetValueKind($P.name)
                if ($art -ne $arten[$P.typ]) { return ($P.name + ': Typ ' + $art + ' statt ' + $P.typ) }
                $ist = Format-Wert $art ($schluessel.GetValue($P.name, $null, 'DoNotExpandEnvironmentNames'))
                if ($P.typ -eq 'REG_MULTI_SZ') { $soll = (@($P.daten) -join "`n") } else { $soll = [string]$P.daten }
                if ($ist -cne $soll) { return ($P.name + ': „' + $ist + '“ statt „' + $soll + '“') }
                return $null
            }
        }
        return ('Unbekannte Prüfung: ' + $P.art)
    } finally {
        if ($schluessel) { $schluessel.Close() }
        $basis.Close()
    }
}

# --- Script ausführen ------------------------------------------------------------------------------
function Invoke-TestScript([string]$Datei, [string]$Ziel, [bool]$Ja) {
    $info = New-Object Diagnostics.ProcessStartInfo
    if ($Ziel -eq 'powershell') {
        $info.FileName = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $info.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $Datei + '" -NoPause'
    } else {
        $info.FileName = Join-Path $env:SystemRoot 'System32\cmd.exe'
        $info.Arguments = '/d /c ""' + $Datei + '" /nopause"'
    }
    $info.UseShellExecute = $false
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = [Text.Encoding]::UTF8  # PS: OutputEncoding UTF-8, CMD: chcp 65001
    $info.StandardErrorEncoding = [Text.Encoding]::UTF8
    $prozess = [Diagnostics.Process]::Start($info)
    $aus = $prozess.StandardOutput.ReadToEndAsync()
    $err = $prozess.StandardError.ReadToEndAsync()
    if ($Ja) { for ($i = 0; $i -lt 10; $i++) { $prozess.StandardInput.WriteLine('JA') } }
    $prozess.StandardInput.Close()
    if (-not $prozess.WaitForExit(600000)) {
        $prozess.Kill()
        throw ('Zeitüberschreitung: ' + $Datei)
    }
    $prozess.WaitForExit()
    return [pscustomobject]@{ Code = $prozess.ExitCode; Ausgabe = ($aus.Result + $err.Result) }
}

function Get-Sicherungsordner {
    return @(Get-ChildItem -LiteralPath $env:TEMP -Directory -Filter 'okm-registry-backup-*' -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FullName })
}

# --- Aufräumen und Läufe ---------------------------------------------------------------------------
function Clear-Testschluessel {
    $null = & reg.exe delete 'HKLM\SOFTWARE\OkmTest' /f /reg:64 2>&1
    if ($benutzerSid) { $null = & reg.exe delete ('HKU\' + $benutzerSid + '\Software\OkmTest') /f 2>&1 }
    $global:LASTEXITCODE = 0
}
Clear-Testschluessel

foreach ($lauf in $manifest.laeufe) {
    $datei = Join-Path $Ordner $lauf.datei
    $titel = $lauf.name + ' (' + $lauf.ziel + ')'
    $fehler = New-Object System.Collections.ArrayList
    $status = 'ok'
    Write-Host ''
    Write-Host ('=== ' + $titel + ': ' + $lauf.beschreibung)
    $benutzerLauf = ($lauf.PSObject.Properties.Name -contains 'benutzer') -and $lauf.benutzer
    if ($benutzerLauf -and -not $benutzerSid) {
        Write-Host ('::warning::' + $titel + ' übersprungen – auf dem Runner ist kein (eindeutiger) Konsolenbenutzer angemeldet.')
        [void]$ergebnisse.Add([pscustomobject]@{ Lauf = $titel; Status = 'übersprungen'; Details = 'kein Konsolenbenutzer' })
        continue
    }
    try {
        foreach ($argumente in $lauf.vorher) {
            $null = & reg.exe @($argumente) 2>&1
            if ($LASTEXITCODE -ne 0) { throw ('Vorbedingung fehlgeschlagen: reg ' + ($argumente -join ' ')) }
        }
        $vorher = Get-Sicherungsordner
        $ja = ($lauf.PSObject.Properties.Name -contains 'ja') -and $lauf.ja
        $r = Invoke-TestScript $datei $lauf.ziel $ja
        Write-Host $r.Ausgabe
        if ([string]$lauf.exit -eq 'ungleich0') {
            if ($r.Code -eq 0) { [void]$fehler.Add('Exit-Code 0, erwartet ≠ 0') }
        } elseif ($r.Code -ne [int]$lauf.exit) {
            [void]$fehler.Add('Exit-Code ' + $r.Code + ', erwartet ' + $lauf.exit)
        }
        if ($lauf.PSObject.Properties.Name -contains 'ausgabe') {
            foreach ($text in $lauf.ausgabe) {
                if ($r.Ausgabe -notlike ('*' + $text + '*')) { [void]$fehler.Add('Ausgabe ohne „' + $text + '“') }
            }
        }
        foreach ($p in $lauf.pruefungen) {
            $m = Test-Pruefung $p
            if ($m) { [void]$fehler.Add($m) }
        }
        if ($lauf.PSObject.Properties.Name -contains 'rueckgaengig') {
            $neu = @(Get-Sicherungsordner | Where-Object { $vorher -notcontains $_ })
            if ($neu.Count -ne 1) {
                [void]$fehler.Add('Sicherungsordner: ' + $neu.Count + ' neue gefunden, erwartet 1')
            } else {
                Write-Host ('Rückgängig aus ' + $neu[0])
                foreach ($reg in @(Get-ChildItem -LiteralPath $neu[0] -Filter '*.reg' | Sort-Object Name -Descending)) {
                    $null = & reg.exe import $reg.FullName /reg:64 2>&1
                    if ($LASTEXITCODE -ne 0) { [void]$fehler.Add('reg import fehlgeschlagen: ' + $reg.Name) }
                }
                $global:LASTEXITCODE = 0
                foreach ($p in $lauf.rueckgaengig) {
                    $m = Test-Pruefung $p
                    if ($m) { [void]$fehler.Add('nach Rückgängig: ' + $m) }
                }
            }
        }
    } catch {
        [void]$fehler.Add('Fehler im Testlauf: ' + $_.Exception.Message)
    }
    if ($fehler.Count) {
        $status = 'FEHLER'
        foreach ($f in $fehler) { Write-Host ('::error::' + $titel + ': ' + $f) }
    }
    [void]$ergebnisse.Add([pscustomobject]@{ Lauf = $titel; Status = $status; Details = ($fehler -join '; ') })
}
Clear-Testschluessel
# Protokolle der Scripte (okm-script-*.log in %TEMP%) und Sicherungen fürs CI-Artefakt aufheben
$ablage = Join-Path $Ordner 'protokolle'
$null = New-Item -ItemType Directory -Path $ablage -Force
Get-ChildItem -LiteralPath $env:TEMP -Filter 'okm-*' -ErrorAction SilentlyContinue |
    Copy-Item -Destination $ablage -Recurse -Force -ErrorAction SilentlyContinue

# --- Ergebnis ------------------------------------------------------------------------------------------
Write-Host ''
$ergebnisse | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
if ($env:GITHUB_STEP_SUMMARY) {
    $zeilen = @('### Windows: Registry-Bausteine und Checkliste', '', '| Lauf | Status | Details |', '|---|---|---|')
    foreach ($e in $ergebnisse) { $zeilen += ('| ' + $e.Lauf + ' | ' + $e.Status + ' | ' + ($e.Details -replace '\|', '/') + ' |') }
    Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Value $zeilen -Encoding UTF8
}
$fehlgeschlagen = @($ergebnisse | Where-Object { $_.Status -eq 'FEHLER' }).Count
Write-Host ('Fehlgeschlagen: ' + $fehlgeschlagen + ' von ' + $ergebnisse.Count)
if ($fehlgeschlagen -gt 0) { exit 1 }
exit 0
