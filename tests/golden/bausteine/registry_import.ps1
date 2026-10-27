#Requires -Version 5.1
# ======================================================================
# Titel:             Golden registry_import
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Windows PowerShell 5.1
# Benötigte Rechte:  Administrator (Schritt 1)
# Enthaltene Schritte:
#    1. .reg-Datei importieren [Risiko: rot, Admin]
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
$OkmGesamt = 1
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
        'bit64' { Write-Host ' Lief als 64-Bit-PowerShell (Ausgabe oben).' }
        'rechte' {
            Write-Host ' Abgebrochen: fehlende Administratorrechte.' -ForegroundColor Red
        }
        default {
            Write-Host (' Abgebrochen bei Schritt ' + $script:OkmNr + ' von ' + $OkmGesamt + '.') -ForegroundColor Red
            Write-Host (' Erfolgreich bis dahin: ' + $script:OkmErfolgreich + ' von ' + $OkmGesamt + ' Schritten.')
        }
    }
    if ($script:OkmRegSicherung) {
        Write-Host (' Rückgängig machen: die .reg-Dateien in ' + $script:OkmRegSicherung + ' doppelklicken (höchste Nummer zuerst).')
    }
    if ($script:OkmWirkung -gt 0) {
        Write-Host (' Damit die Änderungen wirken: ' + $script:OkmWirkungText[$script:OkmWirkung]) -ForegroundColor Yellow
    }
    if ($script:OkmWirkungUnbekannt) {
        Write-Host ' Ob alle Änderungen sofort wirken, ist nicht bekannt – im Zweifel neu anmelden.'
    }
    Write-Host (' Protokoll: ' + $OkmLog)
    Write-Host '----------------------------------------------'
    try { Stop-Transcript | Out-Null } catch { $null = $_ }
    if ($script:OkmStatus -notin @('neustart', 'bit64')) { Wait-OkmEnde }
    exit $Code
}

# Netz für alles, was kein Schritt abfängt: Meldung + Zusammenfassung statt stillem Ende
trap {
    Write-OkmFehler ('Unerwarteter Fehler: ' + $_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    $script:OkmStatus = 'fehler'
    Exit-OkmScript 1
}

Write-OkmInfo '=============================================='
Write-OkmInfo ' okm Script-Baukasten · Golden registry_import'
Write-OkmInfo ' Erstellt: 15.01.2026 09:30 · von pytest'
Write-OkmInfo '=============================================='

# 32-Bit-PowerShell auf 64-Bit-Windows: HKLM\SOFTWARE würde nach WOW6432Node umgeleitet
if ([Environment]::Is64BitOperatingSystem -and -not [Environment]::Is64BitProcess -and $PSCommandPath) {
    $OkmPs64 = Join-Path $env:SystemRoot 'Sysnative\WindowsPowerShell\v1.0\powershell.exe'
    if (Test-Path -LiteralPath $OkmPs64) {
        Write-OkmInfo 'Registry: Das Script läuft als 32-Bit-PowerShell – Neustart als 64-Bit, damit HKLM\SOFTWARE nicht in WOW6432Node landet.'
        $OkmArgumente = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
        if ($OkmKeinePause) { $OkmArgumente += '-NoPause' }
        $OkmProzess = Start-Process -FilePath $OkmPs64 -ArgumentList $OkmArgumente -Wait -NoNewWindow -PassThru
        $OkmStatus = 'bit64'
        Exit-OkmScript $OkmProzess.ExitCode
    }
}

# Gesperrte Registry-Bereiche (registry/schutz.yaml) – gilt auch für importierte .reg-Dateien
$script:OkmRegGesperrt = @('HKLM\SAM', 'HKLM\SECURITY', 'HKLM\BCD00000000')
# ===== Registry-Hilfen (okm Script-Baukasten) =========================================
# HKCU wird nie benutzt: Nach dem UAC-Neustart mit einem anderen Admin-Konto wäre das dessen
# Profil. Benutzer-Einstellungen gehen gezielt nach HKU\<SID> (angemeldeter Benutzer, alle
# Profile, Standardprofil). Zugriff über Microsoft.Win32.RegistryKey: CreateSubKey legt fehlende
# Elternschlüssel an und lässt vorhandene Schlüssel samt Inhalt unangetastet.
$script:OkmRegSicherung = $null
$script:OkmRegGesichert = @{}
$script:OkmRegNr = 0
$script:OkmWirkung = 0
$script:OkmWirkungUnbekannt = $false
$script:OkmWirkungRang = @{ 'sofort' = 0; 'explorer_neustart' = 1; 'gpupdate' = 2; 'abmelden' = 3; 'neustart' = 4 }
$script:OkmWirkungText = @('', 'Explorer neu starten', 'Gruppenrichtlinien aktualisieren (gpupdate)', 'neu anmelden', 'Rechner neu starten')
$script:OkmRegWurzeln = @{
    'HKLM' = [Microsoft.Win32.RegistryHive]::LocalMachine
    'HKU'  = [Microsoft.Win32.RegistryHive]::Users
    'HKCR' = [Microsoft.Win32.RegistryHive]::ClassesRoot
    'HKCC' = [Microsoft.Win32.RegistryHive]::CurrentConfig
}
$script:OkmRegLangform = @{ 'HKLM' = 'HKEY_LOCAL_MACHINE'; 'HKU' = 'HKEY_USERS'; 'HKCR' = 'HKEY_CLASSES_ROOT'; 'HKCC' = 'HKEY_CURRENT_CONFIG' }
$script:OkmRegArten = @{
    'REG_SZ'        = [Microsoft.Win32.RegistryValueKind]::String
    'REG_EXPAND_SZ' = [Microsoft.Win32.RegistryValueKind]::ExpandString
    'REG_DWORD'     = [Microsoft.Win32.RegistryValueKind]::DWord
    'REG_QWORD'     = [Microsoft.Win32.RegistryValueKind]::QWord
    'REG_MULTI_SZ'  = [Microsoft.Win32.RegistryValueKind]::MultiString
    'REG_BINARY'    = [Microsoft.Win32.RegistryValueKind]::Binary
}

function Add-OkmWirkung([string]$Wirkung) {
    if ($Wirkung -eq 'unbekannt') { $script:OkmWirkungUnbekannt = $true; return }
    $rang = $script:OkmWirkungRang[$Wirkung]
    if ($rang -gt $script:OkmWirkung) { $script:OkmWirkung = $rang }
}

function Get-OkmRegistryTypname($Art) {
    foreach ($eintrag in $script:OkmRegArten.GetEnumerator()) { if ($eintrag.Value -eq $Art) { return $eintrag.Key } }
    return [string]$Art
}

function ConvertTo-OkmRegistryWert([string]$Typ, $Daten) {
    switch ($Typ) {
        'REG_DWORD' { return [BitConverter]::ToInt32([BitConverter]::GetBytes([uint32]::Parse([string]$Daten)), 0) }
        'REG_QWORD' { return [BitConverter]::ToInt64([BitConverter]::GetBytes([uint64]::Parse([string]$Daten)), 0) }
        'REG_MULTI_SZ' { return , ([string[]]@($Daten)) }
        'REG_BINARY' {
            $hex = [string]$Daten
            $bytes = New-Object byte[] ($hex.Length / 2)
            for ($i = 0; $i -lt $bytes.Length; $i++) { $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16) }
            return , $bytes
        }
        default { return [string]$Daten }
    }
}

# Vergleichbarer Text: Zahlen vorzeichenlos, MULTI_SZ mit NUL getrennt, BINARY als Hex
function ConvertTo-OkmRegistryText($Art, $Wert) {
    switch ($Art) {
        ([Microsoft.Win32.RegistryValueKind]::DWord) { return [string][BitConverter]::ToUInt32([BitConverter]::GetBytes([int32]$Wert), 0) }
        ([Microsoft.Win32.RegistryValueKind]::QWord) { return [string][BitConverter]::ToUInt64([BitConverter]::GetBytes([int64]$Wert), 0) }
        ([Microsoft.Win32.RegistryValueKind]::MultiString) { return (@($Wert) -join [char]0) }
        ([Microsoft.Win32.RegistryValueKind]::Binary) { return ((@($Wert) | ForEach-Object { '{0:x2}' -f $_ }) -join '') }
        default { return [string]$Wert }
    }
}

function Format-OkmRegistryWert($Art, $Wert) {
    $text = ConvertTo-OkmRegistryText $Art $Wert
    if ($Art -eq [Microsoft.Win32.RegistryValueKind]::DWord -or $Art -eq [Microsoft.Win32.RegistryValueKind]::QWord) {
        $text = $text + ' (0x' + ([uint64]$text).ToString('X') + ')'
    } elseif ($Art -eq [Microsoft.Win32.RegistryValueKind]::MultiString) {
        $text = '[' + ((@($Wert) | ForEach-Object { '"' + $_ + '"' }) -join ', ') + ']'
    }
    return (Get-OkmRegistryTypname $Art) + ' ' + $text
}

# Wert lesen (ohne %Variablen% aufzulösen); $null = nicht vorhanden. '' = Standardwert.
function Get-OkmRegistryWertRoh($Schluessel, [string]$Name) {
    if ($null -eq $Schluessel) { return $null }
    if (@($Schluessel.GetValueNames()) -notcontains $Name) { return $null }
    $optionen = [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames
    return [pscustomobject]@{ Art = $Schluessel.GetValueKind($Name); Wert = $Schluessel.GetValue($Name, $null, $optionen) }
}

function Get-OkmKonsolenBenutzer {
    $namen = @()
    foreach ($prozess in @(Get-CimInstance -ClassName Win32_Process -Filter "Name = 'explorer.exe'" -ErrorAction SilentlyContinue)) {
        $besitzer = Invoke-CimMethod -InputObject $prozess -MethodName GetOwner -ErrorAction SilentlyContinue
        if ($besitzer -and $besitzer.User) { $namen += ($besitzer.Domain + '\' + $besitzer.User) }
    }
    $namen = @($namen | Sort-Object -Unique)
    if ($namen.Count -eq 0) {
        $konsole = (Get-CimInstance -ClassName Win32_ComputerSystem).UserName
        if ($konsole) { $namen = @($konsole) }
    }
    if ($namen.Count -eq 0) {
        throw 'Es ist kein Benutzer angemeldet. Für „Angemeldeter Benutzer“ muss jemand angemeldet sein – sonst Bereich „Alle Benutzerprofile“ wählen.'
    }
    if ($namen.Count -gt 1) {
        throw ('Mehrere Benutzer sind angemeldet (' + ($namen -join ', ') + '). Bitte Bereich „Alle Benutzerprofile“ wählen.')
    }
    $konto = New-Object System.Security.Principal.NTAccount($namen[0])
    $sid = $konto.Translate([System.Security.Principal.SecurityIdentifier]).Value
    return [pscustomobject]@{ Name = $namen[0]; Sid = $sid }
}

function New-OkmRegistryZiel([string]$Anzeige, [string]$Wurzel, [string]$Unterpfad, [string]$Datei) {
    return [pscustomobject]@{
        Anzeige = $Anzeige; Wurzel = $Wurzel; Unterpfad = $Unterpfad; Datei = $Datei
        Geladen = $null; Basis = $null
    }
}

# Wessen Registry? Liefert ein Ziel pro Profil (Pfad bei Benutzer-Bereichen ohne Wurzel).
function Get-OkmRegistryZiele([string]$Bereich, [string]$Pfad) {
    $profilListe = 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList'
    $ziele = @()
    if (-not $Bereich -or $Bereich -eq 'computer') {
        $teile = $Pfad -split '\\', 2
        return , @(New-OkmRegistryZiel 'Computer' $teile[0] $teile[1] $null)
    }
    if ($Bereich -eq 'angemeldeter_benutzer') {
        $benutzer = Get-OkmKonsolenBenutzer
        if (-not (Test-Path -LiteralPath ('Registry::HKEY_USERS\' + $benutzer.Sid))) {
            throw ('Das Profil von ' + $benutzer.Name + ' ist nicht geladen.')
        }
        return , @(New-OkmRegistryZiel ('Benutzer ' + $benutzer.Name) 'HKU' ($benutzer.Sid + '\' + $Pfad) $null)
    }
    if ($Bereich -eq 'alle_benutzer' -or $Bereich -eq 'alle_benutzer_und_standardprofil') {
        foreach ($eintrag in @(Get-ChildItem -LiteralPath $profilListe | Where-Object { $_.PSChildName -match '^S-1-5-21-[0-9-]+$' })) {
            $sid = $eintrag.PSChildName
            $ordner = [Environment]::ExpandEnvironmentVariables([string](Get-ItemProperty -LiteralPath $eintrag.PSPath).ProfileImagePath)
            $anzeige = 'Profil ' + (Split-Path -Path $ordner -Leaf)
            if (Test-Path -LiteralPath ('Registry::HKEY_USERS\' + $sid)) {
                $ziele += New-OkmRegistryZiel $anzeige 'HKU' ($sid + '\' + $Pfad) $null
            } elseif (Test-Path -LiteralPath (Join-Path $ordner 'NTUSER.DAT')) {
                $ziele += New-OkmRegistryZiel $anzeige 'HKU' $Pfad (Join-Path $ordner 'NTUSER.DAT')
            } else {
                Write-OkmWarnung ($anzeige + ': keine NTUSER.DAT gefunden – übersprungen.')
            }
        }
    }
    if ($Bereich -eq 'standardprofil' -or $Bereich -eq 'alle_benutzer_und_standardprofil') {
        $standard = [Environment]::ExpandEnvironmentVariables([string](Get-ItemProperty -LiteralPath $profilListe).Default)
        $ziele += New-OkmRegistryZiel 'Standardprofil (neue Benutzer)' 'HKU' $Pfad (Join-Path $standard 'NTUSER.DAT')
    }
    if ($ziele.Count -eq 0) { throw 'Kein Benutzerprofil gefunden.' }
    return , $ziele
}

# Öffnet die Wurzel (lädt eine NTUSER.DAT bei Bedarf unter HKU\OkmTemp_<n>)
function Mount-OkmRegistryZiel($Ziel, [string]$Ansicht) {
    if ($Ziel.Datei) {
        $script:OkmRegNr++
        $Ziel.Geladen = 'OkmTemp_' + $PID + '_' + $script:OkmRegNr
        $null = & reg.exe load ('HKU\' + $Ziel.Geladen) $Ziel.Datei 2>&1
        if ($LASTEXITCODE -ne 0) {
            $Ziel.Geladen = $null
            throw ($Ziel.Anzeige + ': Profil konnte nicht geladen werden (wird es gerade benutzt?).')
        }
        $Ziel.Unterpfad = $Ziel.Geladen + '\' + $Ziel.Unterpfad
    }
    $sicht = [Microsoft.Win32.RegistryView]::Registry64
    if ($Ansicht -eq '32') { $sicht = [Microsoft.Win32.RegistryView]::Registry32 }
    $Ziel.Basis = [Microsoft.Win32.RegistryKey]::OpenBaseKey($script:OkmRegWurzeln[$Ziel.Wurzel], $sicht)
}

# Schließt die Wurzel und entlädt geladene Profile – immer (finally), sonst bleibt NTUSER.DAT gesperrt
function Dismount-OkmRegistryZiel($Ziel) {
    if ($Ziel.Basis) { $Ziel.Basis.Close(); $Ziel.Basis = $null }
    if ($Ziel.Geladen) {
        $ok = $false
        for ($versuch = 0; $versuch -lt 5 -and -not $ok; $versuch++) {
            [gc]::Collect()
            [gc]::WaitForPendingFinalizers()
            Start-Sleep -Milliseconds 500
            $null = & reg.exe unload ('HKU\' + $Ziel.Geladen) 2>&1
            $ok = ($LASTEXITCODE -eq 0)
        }
        if (-not $ok) { Write-OkmWarnung ($Ziel.Anzeige + ': Profil konnte nicht entladen werden (HKU\' + $Ziel.Geladen + ').') }
        $Ziel.Geladen = $null
    }
    $global:LASTEXITCODE = 0
}

function Get-OkmRegistryAnzeigepfad($Ziel, [string]$Unterpfad) {
    if ($Unterpfad) { return $Ziel.Wurzel + '\' + $Unterpfad }
    return $Ziel.Wurzel
}

function Open-OkmRegistrySchluessel($Ziel, [string]$Unterpfad, [bool]$Schreiben) {
    try {
        return $Ziel.Basis.OpenSubKey($Unterpfad, $Schreiben)
    } catch [System.Security.SecurityException], [System.UnauthorizedAccessException] {
        throw ('Dieser Schlüssel ist von Windows geschützt (Zugriff verweigert): ' + (Get-OkmRegistryAnzeigepfad $Ziel $Unterpfad) + '. Es wird kein Besitz übernommen.')
    }
}

# Rückgängig-Datei: vorhandener Schlüssel → reg export; neuer Schlüssel → .reg, die ihn wieder löscht
function Backup-OkmRegistrySchluessel($Ziel, [string]$Unterpfad, [string]$Ansicht, [bool]$Vorhanden) {
    $regpfad = Get-OkmRegistryAnzeigepfad $Ziel $Unterpfad
    $merker = $regpfad.ToUpperInvariant() + '|' + $Ansicht
    if ($script:OkmRegGesichert.ContainsKey($merker)) { return }
    if (-not $script:OkmRegSicherung) {
        $script:OkmRegSicherung = Join-Path $env:TEMP ('okm-registry-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
        $null = New-Item -ItemType Directory -Path $script:OkmRegSicherung -Force
    }
    $datei = Join-Path $script:OkmRegSicherung (('{0:D3}' -f ($script:OkmRegGesichert.Count + 1)) + '.reg')
    if ($Vorhanden) {
        $null = & reg.exe export $regpfad $datei /y ('/reg:' + $Ansicht) 2>&1
        if ($LASTEXITCODE -ne 0) { throw ('Sicherung fehlgeschlagen: ' + $regpfad) }
    } else {
        $zeilen = @('Windows Registry Editor Version 5.00', '', ('[-' + $script:OkmRegLangform[$Ziel.Wurzel] + '\' + $Unterpfad + ']'), '')
        [System.IO.File]::WriteAllLines($datei, [string[]]$zeilen, [System.Text.Encoding]::Unicode)
    }
    $global:LASTEXITCODE = 0
    $script:OkmRegGesichert[$merker] = $datei
    Write-OkmInfo ('Sicherung: ' + $datei)
    if ($Ziel.Geladen) { Write-OkmWarnung ('Zum Zurückspielen muss das Profil wieder als HKU\' + $Ziel.Geladen + ' geladen sein.') }
}

# Neuer Wert in einem vorhandenen Schlüssel: die Sicherung (reg export) kennt ihn nicht – eine eigene
# .reg-Datei löscht ihn beim Zurückspielen wieder („Name“=- bzw. @=- für den Standardwert).
function Add-OkmRueckgaengigNeuerWert($Ziel, [string]$Unterpfad, [string]$Name, [string]$Ansicht) {
    $merker = 'NEU|' + (Get-OkmRegistryAnzeigepfad $Ziel $Unterpfad).ToUpperInvariant() + '|' + $Name.ToUpperInvariant() + '|' + $Ansicht
    if ($script:OkmRegGesichert.ContainsKey($merker)) { return }
    if (-not $script:OkmRegSicherung) {
        $script:OkmRegSicherung = Join-Path $env:TEMP ('okm-registry-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
        $null = New-Item -ItemType Directory -Path $script:OkmRegSicherung -Force
    }
    $datei = Join-Path $script:OkmRegSicherung (('{0:D3}' -f ($script:OkmRegGesichert.Count + 1)) + '.reg')
    if ($Name) { $zeile = '"' + $Name.Replace('\', '\\') + '"=-' } else { $zeile = '@=-' }
    $zeilen = @('Windows Registry Editor Version 5.00', '', ('[' + $script:OkmRegLangform[$Ziel.Wurzel] + '\' + $Unterpfad + ']'), $zeile, '')
    [System.IO.File]::WriteAllLines($datei, [string[]]$zeilen, [System.Text.Encoding]::Unicode)
    $script:OkmRegGesichert[$merker] = $datei
}

# Obersten fehlenden Schlüssel finden (für die Rückgängig-Datei eines neu angelegten Pfads)
function Get-OkmFehlenderSchluessel($Ziel) {
    $teile = $Ziel.Unterpfad -split '\\'
    $bisher = ''
    foreach ($teil in $teile) {
        if ($bisher) { $bisher = $bisher + '\' + $teil } else { $bisher = $teil }
        $schluessel = Open-OkmRegistrySchluessel $Ziel $bisher $false
        if ($null -eq $schluessel) { return $bisher }
        $schluessel.Close()
    }
    return $null
}

function New-OkmRegistryPfad($Ziel, [string]$Ansicht, [switch]$Simulation) {
    $fehlt = Get-OkmFehlenderSchluessel $Ziel
    if (-not $fehlt) { return $false }
    if ($Simulation) {
        Write-OkmInfo ('[SIMULATION] ' + $Ziel.Anzeige + ': Schlüssel würde angelegt: ' + (Get-OkmRegistryAnzeigepfad $Ziel $Ziel.Unterpfad))
        return $true
    }
    Backup-OkmRegistrySchluessel $Ziel $fehlt $Ansicht $false
    try {
        $neu = $Ziel.Basis.CreateSubKey($Ziel.Unterpfad)
    } catch [System.Security.SecurityException], [System.UnauthorizedAccessException] {
        throw ('Dieser Schlüssel ist von Windows geschützt (Zugriff verweigert): ' + (Get-OkmRegistryAnzeigepfad $Ziel $fehlt) + '. Es wird kein Besitz übernommen.')
    }
    $neu.Close()
    Write-OkmInfo ($Ziel.Anzeige + ': Schlüssel ' + (Get-OkmRegistryAnzeigepfad $Ziel $Ziel.Unterpfad) + ' angelegt')
    return $true
}

function Set-OkmRegistryWert {
    param(
        [string]$Bereich, [string]$Pfad, [string]$Name, [string]$Typ, $Daten,
        [string]$WennVorhanden = 'ueberschreiben', [string]$Ansicht = '64', [switch]$Simulation
    )
    $neuArt = $script:OkmRegArten[$Typ]
    $neuWert = ConvertTo-OkmRegistryWert $Typ $Daten
    $neuText = ConvertTo-OkmRegistryText $neuArt $neuWert
    $wertname = $Name
    if (-not $wertname) { $wertname = '(Standard)' }
    $geaendert = $false
    foreach ($ziel in @(Get-OkmRegistryZiele $Bereich $Pfad)) {
        try {
            Mount-OkmRegistryZiel $ziel $Ansicht
            $neuerPfad = New-OkmRegistryPfad $ziel $Ansicht -Simulation:$Simulation
            $schluessel = $null
            if (-not ($neuerPfad -and $Simulation)) { $schluessel = Open-OkmRegistrySchluessel $ziel $ziel.Unterpfad (-not $Simulation) }
            try {
                $alt = Get-OkmRegistryWertRoh $schluessel $Name
                $titel = $ziel.Anzeige + ': ' + $wertname
                if ($alt) { Write-OkmInfo ($titel + ' vorher: ' + (Format-OkmRegistryWert $alt.Art $alt.Wert)) }
                else { Write-OkmInfo ($titel + ' vorher: nicht vorhanden') }
                $schreiben = $true
                if ($alt) {
                    if ($WennVorhanden -eq 'nur_wenn_fehlt') {
                        Write-OkmInfo ($titel + ': bereits vorhanden, nicht geändert')
                        $schreiben = $false
                    } elseif ($WennVorhanden -eq 'abbrechen') {
                        throw ($titel + ' ist bereits vorhanden – laut Einstellung wird abgebrochen.')
                    } elseif ($alt.Art -eq $neuArt -and (ConvertTo-OkmRegistryText $alt.Art $alt.Wert) -ceq $neuText) {
                        Write-OkmInfo ($titel + ': bereits richtig gesetzt')
                        $schreiben = $false
                    } elseif ($WennVorhanden -eq 'nachfragen' -and -not $Simulation) {
                        $antwort = Read-Host ($titel + ' überschreiben? (J/N)')
                        if ($antwort -notmatch '^[JjYy]') {
                            Write-OkmInfo ($titel + ': nicht geändert')
                            $schreiben = $false
                        }
                    }
                }
                if ($schreiben) {
                    $neuAnzeige = Format-OkmRegistryWert $neuArt $neuWert
                    if ($Simulation) {
                        Write-OkmInfo ('[SIMULATION] ' + $titel + ' würde gesetzt: ' + $neuAnzeige)
                    } else {
                        if (-not $neuerPfad) {
                            Backup-OkmRegistrySchluessel $ziel $ziel.Unterpfad $Ansicht $true
                            if (-not $alt) { Add-OkmRueckgaengigNeuerWert $ziel $ziel.Unterpfad $Name $Ansicht }
                        }
                        if ($alt -and $alt.Art -ne $neuArt) {
                            Write-OkmWarnung ($titel + ': Typ geändert: ' + (Get-OkmRegistryTypname $alt.Art) + ' → ' + $Typ)
                            $schluessel.DeleteValue($Name)
                        }
                        try {
                            $schluessel.SetValue($Name, $neuWert, $neuArt)
                        } catch [System.Security.SecurityException], [System.UnauthorizedAccessException] {
                            throw ('Dieser Schlüssel ist von Windows geschützt (Zugriff verweigert). Es wird kein Besitz übernommen.')
                        }
                        $zurueck = Get-OkmRegistryWertRoh $schluessel $Name
                        if (-not $zurueck -or $zurueck.Art -ne $neuArt -or (ConvertTo-OkmRegistryText $zurueck.Art $zurueck.Wert) -cne $neuText) {
                            throw ($titel + ': Zurücklesen ergibt einen anderen Wert – Änderung nicht wirksam.')
                        }
                        Write-OkmInfo ($titel + ' jetzt: ' + $neuAnzeige)
                        $geaendert = $true
                    }
                }
            } finally {
                if ($schluessel) { $schluessel.Close() }
            }
        } finally {
            Dismount-OkmRegistryZiel $ziel
        }
    }
    return $geaendert
}

function Get-OkmRegistryWert([string]$Bereich, [string]$Pfad, [string]$Name, [string]$Ansicht = '64') {
    $ergebnisse = @()
    $wertname = $Name
    if (-not $wertname) { $wertname = '(Standard)' }
    foreach ($ziel in @(Get-OkmRegistryZiele $Bereich $Pfad)) {
        try {
            Mount-OkmRegistryZiel $ziel $Ansicht
            $schluessel = Open-OkmRegistrySchluessel $ziel $ziel.Unterpfad $false
            try {
                $wert = Get-OkmRegistryWertRoh $schluessel $Name
                if ($null -eq $schluessel) { Write-OkmInfo ($ziel.Anzeige + ': Schlüssel nicht vorhanden') }
                elseif ($wert) { Write-OkmInfo ($ziel.Anzeige + ': ' + $wertname + ' = ' + (Format-OkmRegistryWert $wert.Art $wert.Wert)) }
                else { Write-OkmInfo ($ziel.Anzeige + ': ' + $wertname + ' nicht vorhanden') }
                $ergebnisse += [pscustomobject]@{ Anzeige = $ziel.Anzeige; Wert = $wert }
            } finally {
                if ($schluessel) { $schluessel.Close() }
            }
        } finally {
            Dismount-OkmRegistryZiel $ziel
        }
    }
    return , $ergebnisse
}

function Show-OkmRegistrySchluessel([string]$Bereich, [string]$Pfad, [string]$Ansicht = '64') {
    foreach ($ziel in @(Get-OkmRegistryZiele $Bereich $Pfad)) {
        try {
            Mount-OkmRegistryZiel $ziel $Ansicht
            $schluessel = Open-OkmRegistrySchluessel $ziel $ziel.Unterpfad $false
            Write-OkmInfo ($ziel.Anzeige + ': ' + (Get-OkmRegistryAnzeigepfad $ziel $ziel.Unterpfad))
            if ($null -eq $schluessel) { Write-OkmInfo '  Schlüssel nicht vorhanden'; continue }
            try {
                $namen = @($schluessel.GetValueNames() | Sort-Object)
                Write-OkmInfo ('  Werte: ' + $namen.Count)
                foreach ($name in $namen) {
                    $wert = Get-OkmRegistryWertRoh $schluessel $name
                    $anzeige = $name
                    if (-not $anzeige) { $anzeige = '(Standard)' }
                    Write-OkmInfo ('    ' + $anzeige + ' = ' + (Format-OkmRegistryWert $wert.Art $wert.Wert))
                }
                $unter = @($schluessel.GetSubKeyNames() | Sort-Object)
                Write-OkmInfo ('  Unterschlüssel: ' + $unter.Count)
                foreach ($name in $unter) { Write-OkmInfo ('    ' + $name) }
            } finally {
                $schluessel.Close()
            }
        } finally {
            Dismount-OkmRegistryZiel $ziel
        }
    }
}

function Test-OkmRegistryWert([string]$Bereich, [string]$Pfad, [string]$Name, [string]$Typ, $Daten, [string]$Ansicht = '64') {
    $sollArt = $script:OkmRegArten[$Typ]
    $sollWert = ConvertTo-OkmRegistryWert $Typ $Daten
    $sollText = ConvertTo-OkmRegistryText $sollArt $sollWert
    $alleOk = $true
    foreach ($ergebnis in @(Get-OkmRegistryWert $Bereich $Pfad $Name $Ansicht)) {
        $ist = $ergebnis.Wert
        if ($ist -and $ist.Art -eq $sollArt -and (ConvertTo-OkmRegistryText $ist.Art $ist.Wert) -ceq $sollText) {
            Write-OkmInfo ($ergebnis.Anzeige + ': OK')
        } else {
            $alleOk = $false
            Write-OkmWarnung ($ergebnis.Anzeige + ': ABWEICHUNG – erwartet ' + (Format-OkmRegistryWert $sollArt $sollWert))
        }
    }
    return $alleOk
}

function New-OkmRegistrySchluessel([string]$Bereich, [string]$Pfad, [string]$Ansicht = '64', [switch]$Simulation) {
    foreach ($ziel in @(Get-OkmRegistryZiele $Bereich $Pfad)) {
        try {
            Mount-OkmRegistryZiel $ziel $Ansicht
            if (-not (New-OkmRegistryPfad $ziel $Ansicht -Simulation:$Simulation)) {
                Write-OkmInfo ($ziel.Anzeige + ': Schlüssel ist schon vorhanden – nichts zu tun')
            }
        } finally {
            Dismount-OkmRegistryZiel $ziel
        }
    }
}

function Remove-OkmRegistryWert([string]$Bereich, [string]$Pfad, [string]$Name, [string]$Ansicht = '64', [switch]$Simulation) {
    $wertname = $Name
    if (-not $wertname) { $wertname = '(Standard)' }
    foreach ($ziel in @(Get-OkmRegistryZiele $Bereich $Pfad)) {
        try {
            Mount-OkmRegistryZiel $ziel $Ansicht
            $schluessel = Open-OkmRegistrySchluessel $ziel $ziel.Unterpfad (-not $Simulation)
            try {
                $alt = Get-OkmRegistryWertRoh $schluessel $Name
                if (-not $alt) {
                    Write-OkmInfo ($ziel.Anzeige + ': ' + $wertname + ' ist nicht vorhanden – nichts zu tun')
                } elseif ($Simulation) {
                    Write-OkmInfo ('[SIMULATION] ' + $ziel.Anzeige + ': ' + $wertname + ' würde gelöscht (' + (Format-OkmRegistryWert $alt.Art $alt.Wert) + ')')
                } else {
                    Backup-OkmRegistrySchluessel $ziel $ziel.Unterpfad $Ansicht $true
                    $schluessel.DeleteValue($Name)
                    Write-OkmInfo ($ziel.Anzeige + ': ' + $wertname + ' gelöscht (war ' + (Format-OkmRegistryWert $alt.Art $alt.Wert) + ')')
                }
            } finally {
                if ($schluessel) { $schluessel.Close() }
            }
        } finally {
            Dismount-OkmRegistryZiel $ziel
        }
    }
}

function Measure-OkmRegistrySchluessel($Schluessel) {
    $ergebnis = [pscustomobject]@{ Unterschluessel = 0; Werte = $Schluessel.ValueCount }
    foreach ($name in $Schluessel.GetSubKeyNames()) {
        $unter = $Schluessel.OpenSubKey($name, $false)
        if ($unter) {
            $teil = Measure-OkmRegistrySchluessel $unter
            $unter.Close()
            $ergebnis.Unterschluessel += 1 + $teil.Unterschluessel
            $ergebnis.Werte += $teil.Werte
        }
    }
    return $ergebnis
}

function Show-OkmRegistryLoeschVorschau([string]$Bereich, [string]$Pfad, [string]$Ansicht = '64') {
    foreach ($ziel in @(Get-OkmRegistryZiele $Bereich $Pfad)) {
        try {
            Mount-OkmRegistryZiel $ziel $Ansicht
            $schluessel = Open-OkmRegistrySchluessel $ziel $ziel.Unterpfad $false
            if ($null -eq $schluessel) { Write-OkmInfo ($ziel.Anzeige + ': Schlüssel nicht vorhanden'); continue }
            $umfang = Measure-OkmRegistrySchluessel $schluessel
            $schluessel.Close()
            Write-OkmWarnung ($ziel.Anzeige + ': Wird gelöscht: ' + (Get-OkmRegistryAnzeigepfad $ziel $ziel.Unterpfad) + ' mit ' + $umfang.Unterschluessel + ' Unterschlüsseln und ' + $umfang.Werte + ' Werten')
        } finally {
            Dismount-OkmRegistryZiel $ziel
        }
    }
}

function Remove-OkmRegistrySchluessel([string]$Bereich, [string]$Pfad, [string]$Ansicht = '64', [switch]$Simulation) {
    foreach ($ziel in @(Get-OkmRegistryZiele $Bereich $Pfad)) {
        try {
            Mount-OkmRegistryZiel $ziel $Ansicht
            $schluessel = Open-OkmRegistrySchluessel $ziel $ziel.Unterpfad $false
            if ($null -eq $schluessel) { Write-OkmInfo ($ziel.Anzeige + ': Schlüssel nicht vorhanden – nichts zu tun'); continue }
            $schluessel.Close()
            $anzeige = Get-OkmRegistryAnzeigepfad $ziel $ziel.Unterpfad
            if ($Simulation) { Write-OkmInfo ('[SIMULATION] ' + $ziel.Anzeige + ': ' + $anzeige + ' würde gelöscht'); continue }
            Backup-OkmRegistrySchluessel $ziel $ziel.Unterpfad $Ansicht $true
            $teile = @($ziel.Unterpfad -split '\\')
            if ($teile.Count -lt 2) { throw 'Ein Schlüssel direkt unter der Wurzel wird nicht gelöscht.' }
            $elternPfad = ($teile[0..($teile.Count - 2)] -join '\')
            $eltern = Open-OkmRegistrySchluessel $ziel $elternPfad $true
            try {
                $eltern.DeleteSubKeyTree($teile[-1])
            } catch [System.Security.SecurityException], [System.UnauthorizedAccessException] {
                throw ('Dieser Schlüssel ist von Windows geschützt (Zugriff verweigert): ' + $anzeige + '. Es wird kein Besitz übernommen.')
            } finally {
                $eltern.Close()
            }
            Write-OkmInfo ($ziel.Anzeige + ': ' + $anzeige + ' gelöscht')
        } finally {
            Dismount-OkmRegistryZiel $ziel
        }
    }
}

function Export-OkmRegistrySchluessel([string]$Bereich, [string]$Pfad, [string]$Datei, [string]$Ansicht = '64') {
    if (-not $Datei) { $Datei = Join-Path $env:TEMP ('okm-registry-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.reg') }
    $nr = 0
    foreach ($ziel in @(Get-OkmRegistryZiele $Bereich $Pfad)) {
        try {
            Mount-OkmRegistryZiel $ziel $Ansicht
            $nr++
            $zielDatei = $Datei
            if ($nr -gt 1) { $zielDatei = [System.IO.Path]::ChangeExtension($Datei, $null) + '-' + $nr + '.reg' }
            $regpfad = Get-OkmRegistryAnzeigepfad $ziel $ziel.Unterpfad
            $null = & reg.exe export $regpfad $zielDatei /y ('/reg:' + $Ansicht) 2>&1
            if ($LASTEXITCODE -ne 0) { throw ($ziel.Anzeige + ': Export fehlgeschlagen – gibt es den Schlüssel ' + $regpfad + '?') }
            Write-OkmInfo ($ziel.Anzeige + ': gesichert nach ' + $zielDatei)
        } finally {
            Dismount-OkmRegistryZiel $ziel
        }
    }
}

function Show-OkmRegistryRechte([string]$Bereich, [string]$Pfad, [string]$Ansicht = '64') {
    foreach ($ziel in @(Get-OkmRegistryZiele $Bereich $Pfad)) {
        try {
            Mount-OkmRegistryZiel $ziel $Ansicht
            $schluessel = Open-OkmRegistrySchluessel $ziel $ziel.Unterpfad $false
            if ($null -eq $schluessel) { Write-OkmInfo ($ziel.Anzeige + ': Schlüssel nicht vorhanden'); continue }
            try {
                $acl = $schluessel.GetAccessControl()
                Write-OkmInfo ($ziel.Anzeige + ': ' + (Get-OkmRegistryAnzeigepfad $ziel $ziel.Unterpfad))
                Write-OkmInfo ('  Besitzer: ' + $acl.Owner)
                $acl.Access | Format-Table -Property IdentityReference, RegistryRights, AccessControlType, IsInherited -AutoSize | Out-Host
            } finally {
                $schluessel.Close()
            }
        } finally {
            Dismount-OkmRegistryZiel $ziel
        }
    }
}

# .reg-Datei lesen (regedit speichert UTF-16 LE mit BOM; ältere Dateien ANSI) → Schlüssel und Werte zählen
function Read-OkmRegDatei([string]$Datei) {
    $text = [System.IO.File]::ReadAllText($Datei)
    $schluessel = @()
    $werte = 0
    foreach ($zeile in ($text -split "`r?`n")) {
        $z = $zeile.Trim()
        if ($z -match '^\[(-?)([^\]]+)\]$') { $schluessel += [pscustomobject]@{ Loeschen = ($Matches[1] -eq '-'); Pfad = $Matches[2] } }
        elseif ($z -match '^("|@=)') { $werte++ }
    }
    return [pscustomobject]@{ Schluessel = $schluessel; Werte = $werte }
}

function Import-OkmRegistryDatei([string]$Datei, [string]$Ansicht = '64', [switch]$Simulation) {
    if (-not (Test-Path -LiteralPath $Datei -PathType Leaf)) { throw ('Die Datei gibt es nicht: ' + $Datei) }
    $inhalt = Read-OkmRegDatei $Datei
    Write-OkmInfo ('Datei: ' + $Datei + ' – ' + $inhalt.Schluessel.Count + ' Schlüssel, ' + $inhalt.Werte + ' Werte')
    if ($inhalt.Schluessel.Count -eq 0) { throw 'Die Datei enthält keine Registry-Schlüssel (keine .reg-Datei?).' }
    $kurz = @{ 'HKEY_LOCAL_MACHINE' = 'HKLM'; 'HKEY_USERS' = 'HKU'; 'HKEY_CLASSES_ROOT' = 'HKCR'; 'HKEY_CURRENT_CONFIG' = 'HKCC' }
    $ziele = @()
    foreach ($eintrag in $inhalt.Schluessel) {
        $teile = $eintrag.Pfad -split '\\', 2
        if ($teile[0] -eq 'HKEY_CURRENT_USER' -or $teile[0] -eq 'HKCU') {
            throw 'Die Datei enthält HKEY_CURRENT_USER – nach dem Admin-Neustart wäre das das Profil des Admin-Kontos. Bitte die Einstellung mit „Registry-Wert setzen“ (Bereich Benutzer) übernehmen.'
        }
        if (-not $kurz.ContainsKey($teile[0])) { throw ('Unbekannte Wurzel in der Datei: ' + $teile[0]) }
        $pfad = $kurz[$teile[0]] + '\' + $teile[1]
        foreach ($gesperrt in $script:OkmRegGesperrt) {
            if (($pfad + '\').StartsWith($gesperrt + '\', [StringComparison]::OrdinalIgnoreCase)) { throw ('Die Datei schreibt in einen gesperrten Bereich: ' + $pfad) }
        }
        $aktion = 'ändern'
        if ($eintrag.Loeschen) { $aktion = 'LÖSCHEN' }
        Write-OkmInfo ('  ' + $aktion + ': ' + $pfad)
        $ziele += $pfad
    }
    if ($Simulation) { Write-OkmInfo '[SIMULATION] Die Datei würde importiert.'; return }
    foreach ($pfad in @($ziele | Sort-Object -Unique)) {
        $teile = $pfad -split '\\', 2
        $ziel = New-OkmRegistryZiel 'Computer' $teile[0] $teile[1] $null
        try {
            Mount-OkmRegistryZiel $ziel $Ansicht
            $schluessel = Open-OkmRegistrySchluessel $ziel $ziel.Unterpfad $false
            if ($schluessel) { $schluessel.Close(); Backup-OkmRegistrySchluessel $ziel $ziel.Unterpfad $Ansicht $true }
            else {
                $fehlt = Get-OkmFehlenderSchluessel $ziel
                Backup-OkmRegistrySchluessel $ziel $fehlt $Ansicht $false
            }
        } finally {
            Dismount-OkmRegistryZiel $ziel
        }
    }
    $null = & reg.exe import $Datei ('/reg:' + $Ansicht) 2>&1
    if ($LASTEXITCODE -ne 0) { throw ('reg import ist fehlgeschlagen (Exit-Code ' + $LASTEXITCODE + ').') }
    $global:LASTEXITCODE = 0
    Write-OkmInfo 'Importiert.'
}
# ===== Ende Registry-Hilfen ============================================================

# Rechte: Administrator für Schritt 1 (.reg-Datei importieren)
$OkmPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if ($OkmPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-OkmInfo 'Rechte: als Administrator gestartet'
} else {
    Write-OkmInfo 'Dieses Script braucht Administratorrechte für: Schritt 1 (.reg-Datei importieren).'
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
# Schritt 1/1: .reg-Datei importieren (Risiko: rot)
# --------------------------------------------------------------------
$OkmNr = 1
Write-OkmInfo '[1/1] Registry: \\fileserver\IT\Einstellungen\app.reg wird importiert ...'
# Vorschau (vor der Bestätigung)
. {
    Import-OkmRegistryDatei -Datei '\\fileserver\IT\Einstellungen\app.reg' -Ansicht '64' -Simulation
} | Out-Host
Write-OkmWarnung 'ACHTUNG: Dieser Schritt ist destruktiv: .reg-Datei importieren'
$OkmAntwort = Read-Host 'Zum Fortfahren JA eingeben (alles andere bricht ab)'
if ($OkmAntwort -cne 'JA') {
    $OkmStatus = 'abbruch'
    Exit-OkmScript 2
}
try {
    $global:LASTEXITCODE = 0
    . {
        Import-OkmRegistryDatei -Datei '\\fileserver\IT\Einstellungen\app.reg' -Ansicht '64'
        Add-OkmWirkung 'sofort'
    } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('Befehl endete mit Exit-Code ' + $LASTEXITCODE) }
    $OkmErfolgreich++
    Write-OkmOk
} catch {
    Write-OkmFehler ($_.Exception.Message + ' (Zeile ' + $_.InvocationInfo.ScriptLineNumber + ')')
    Write-OkmInfo '      Tipp: Ist die Datei erreichbar und eine echte .reg-Datei (Windows Registry Editor Version 5.00)?'
    $OkmStatus = 'fehler'
    Exit-OkmScript 1
}

$OkmStatus = 'fertig'
Exit-OkmScript 0
