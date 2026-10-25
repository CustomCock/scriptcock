# Hilfen für „Richtlinie setzen“ und „Admin-Werkzeug bereitstellen“ – nur in Scripten mit diesen Bausteinen
function Clear-OkmRegistrySchluessel([string]$Bereich, [string]$Pfad, [string]$Ansicht = '64', [switch]$Simulation) {
    foreach ($ziel in @(Get-OkmRegistryZiele $Bereich $Pfad)) {
        try {
            Mount-OkmRegistryZiel $ziel $Ansicht
            $schluessel = Open-OkmRegistrySchluessel $ziel $ziel.Unterpfad (-not $Simulation)
            if ($null -eq $schluessel) { continue }
            try {
                $namen = @($schluessel.GetValueNames())
                if ($namen.Count -eq 0) { continue }
                if ($Simulation) { Write-OkmInfo ('[SIMULATION] ' + $ziel.Anzeige + ': ' + $namen.Count + ' Werte würden gelöscht'); continue }
                Backup-OkmRegistrySchluessel $ziel $ziel.Unterpfad $Ansicht $true
                foreach ($name in $namen) { $schluessel.DeleteValue($name) }
                Write-OkmInfo ($ziel.Anzeige + ': ' + $namen.Count + ' Werte gelöscht in ' + (Get-OkmRegistryAnzeigepfad $ziel $ziel.Unterpfad))
            } finally {
                $schluessel.Close()
            }
        } finally {
            Dismount-OkmRegistryZiel $ziel
        }
    }
}

function Remove-OkmRegistrySchluesselWennLeer([string]$Bereich, [string]$Pfad, [string]$Ansicht = '64', [switch]$Simulation) {
    foreach ($ziel in @(Get-OkmRegistryZiele $Bereich $Pfad)) {
        try {
            Mount-OkmRegistryZiel $ziel $Ansicht
            $schluessel = Open-OkmRegistrySchluessel $ziel $ziel.Unterpfad $false
            if ($null -eq $schluessel) { continue }
            $leer = ($schluessel.ValueCount -eq 0 -and $schluessel.SubKeyCount -eq 0)
            $schluessel.Close()
            if (-not $leer) { continue }
            $anzeige = Get-OkmRegistryAnzeigepfad $ziel $ziel.Unterpfad
            if ($Simulation) { Write-OkmInfo ('[SIMULATION] leerer Schlüssel würde entfernt: ' + $anzeige); continue }
            $teile = @($ziel.Unterpfad -split '\\')
            if ($teile.Count -lt 2) { continue }
            $eltern = Open-OkmRegistrySchluessel $ziel ($teile[0..($teile.Count - 2)] -join '\') $true
            try { $eltern.DeleteSubKey($teile[-1], $false) } finally { $eltern.Close() }
            Write-OkmInfo ($ziel.Anzeige + ': leerer Schlüssel entfernt: ' + $anzeige)
        } finally {
            Dismount-OkmRegistryZiel $ziel
        }
    }
}

# --- Gruppenrichtlinien ----------------------------------------------------------------------
# Computer-Richtlinien: am Ende einmal gpupdate /target:computer. Benutzer-Richtlinien: kein gpupdate
# (es liefe im Profil des Admin-Kontos) – stattdessen „neu anmelden“ in der Zusammenfassung.
$script:OkmGpupdate = $false
$script:OkmLgpoSicherung = $null
$script:OkmWerkzeuge = @{}

function Register-OkmGpupdate([string]$Ziel) {
    if ($Ziel -eq 'computer') { $script:OkmGpupdate = $true } else { Add-OkmWirkung 'abmelden' }
}

function Invoke-OkmGpupdate {
    if (-not $script:OkmGpupdate) { return }
    Write-OkmInfo 'Gruppenrichtlinien werden aktualisiert (gpupdate /target:computer) …'
    $ausgabe = & gpupdate.exe /target:computer 2>&1
    if ($LASTEXITCODE -ne 0) {
        $ausgabe | Out-Host
        Add-OkmWirkung 'gpupdate'
        Write-OkmWarnung 'gpupdate ist fehlgeschlagen – bitte später „gpupdate /target:computer“ ausführen.'
    }
    $global:LASTEXITCODE = 0
}

function Invoke-OkmLgpo([string[]]$Zeilen, [switch]$Simulation) {
    if ($Simulation) {
        Write-OkmInfo '[SIMULATION] In die lokale Gruppenrichtlinie (LGPO) würde geschrieben:'
        foreach ($zeile in $Zeilen) { Write-OkmInfo ('    ' + $zeile) }
        return
    }
    $exe = $script:OkmWerkzeuge['lgpo']
    if (-not $exe -or -not (Test-Path -LiteralPath $exe)) {
        throw 'LGPO.exe ist nicht bereitgestellt – davor den Baustein „Admin-Werkzeug bereitstellen“ (LGPO) setzen.'
    }
    if (-not $script:OkmLgpoSicherung) {
        $script:OkmLgpoSicherung = Join-Path $env:TEMP ('okm-lgpo-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
        $null = New-Item -ItemType Directory -Path $script:OkmLgpoSicherung -Force
        $null = & $exe /b $script:OkmLgpoSicherung 2>&1
        if ($LASTEXITCODE -ne 0) { throw 'Die lokale Gruppenrichtlinie konnte nicht gesichert werden (LGPO /b).' }
        Write-OkmInfo ('Sicherung der lokalen Gruppenrichtlinie: ' + $script:OkmLgpoSicherung)
    }
    $datei = Join-Path $env:TEMP ('okm-lgpo-' + $PID + '-' + (Get-Random) + '.txt')
    [System.IO.File]::WriteAllLines($datei, $Zeilen, [System.Text.Encoding]::Unicode)
    try {
        $ausgabe = & $exe /t $datei 2>&1
        if ($LASTEXITCODE -ne 0) { $ausgabe | Out-Host; throw ('LGPO.exe endete mit Code ' + $LASTEXITCODE) }
    } finally {
        Remove-Item -LiteralPath $datei -Force -ErrorAction SilentlyContinue
    }
    $global:LASTEXITCODE = 0
    Write-OkmInfo 'In die lokale Gruppenrichtlinie geschrieben (sichtbar in gpedit.msc).'
}

# --- Werkzeuge und Vorlagen herunterladen (immer mit SHA-256-Prüfung) -----------------------------
function Get-OkmDatei([string]$Url, [string]$Ziel, [string]$Sha256) {
    $alt = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $teil = $Ziel + '.teil'
    try {
        Write-OkmInfo ('Lade ' + $Url)
        Invoke-WebRequest -Uri $Url -OutFile $teil -UseBasicParsing
    } finally {
        $ProgressPreference = $alt
    }
    $ist = (Get-FileHash -LiteralPath $teil -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ist -ne $Sha256.ToLowerInvariant()) {
        Remove-Item -LiteralPath $teil -Force
        throw ('Die Prüfsumme passt nicht – die Datei wird NICHT verwendet: ' + $Url)
    }
    Move-Item -LiteralPath $teil -Destination $Ziel -Force
}

function Test-OkmHash([string]$Datei, [string]$Sha256) {
    if (-not (Test-Path -LiteralPath $Datei -PathType Leaf)) { return $false }
    return ((Get-FileHash -LiteralPath $Datei -Algorithm SHA256).Hash.ToLowerInvariant() -eq $Sha256.ToLowerInvariant())
}

function Install-OkmWerkzeug([string]$Name, [string]$Version, [string]$Url, [string]$Sha256, [string]$ZipEintrag, [string]$EintragSha256) {
    $ordner = Join-Path $env:ProgramData ('okm\werkzeuge\' + $Name + '\' + $Version)
    $exe = Join-Path $ordner (Split-Path -Path $ZipEintrag -Leaf)
    if (Test-OkmHash $exe $EintragSha256) {
        Write-OkmInfo ($Name + ' ' + $Version + ' ist schon vorhanden: ' + $exe)
        $script:OkmWerkzeuge[$Name] = $exe
        return
    }
    $null = New-Item -ItemType Directory -Path $ordner -Force
    $zip = Join-Path $env:TEMP ('okm-' + $Name + '-' + $PID + '.zip')
    $entpackt = Join-Path $env:TEMP ('okm-' + $Name + '-' + $PID)
    try {
        Get-OkmDatei $Url $zip $Sha256
        Expand-Archive -LiteralPath $zip -DestinationPath $entpackt -Force
        Copy-Item -LiteralPath (Join-Path $entpackt $ZipEintrag) -Destination $exe -Force
    } finally {
        Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $entpackt -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (-not (Test-OkmHash $exe $EintragSha256)) { Remove-Item -LiteralPath $exe -Force; throw ('Prüfsumme von ' + $exe + ' passt nicht.') }
    Write-OkmInfo ($Name + ' ' + $Version + ' bereitgestellt: ' + $exe)
    $script:OkmWerkzeuge[$Name] = $exe
}

function Get-OkmAdmxRevision([string]$Datei) {
    try {
        $xml = New-Object System.Xml.XmlDocument
        $xml.Load($Datei)
        return [version]$xml.DocumentElement.GetAttribute('revision')
    } catch {
        return [version]'0.0'
    }
}

# ADMX/ADML aus einem entpackten Paket nach PolicyDefinitions (bzw. Central Store) kopieren.
# Neuere vorhandene Vorlagen (revision) bleiben, ältere werden vorher gesichert.
function Copy-OkmVorlagen([string]$Quelle, [string[]]$Admx, [string]$Ziel) {
    $sicherung = Join-Path $env:TEMP ('okm-admx-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    $alle = @(Get-ChildItem -LiteralPath $Quelle -Recurse -File)
    foreach ($name in $Admx) {
        $neu = $alle | Where-Object { $_.Name -eq $name } | Select-Object -First 1
        if (-not $neu) { Write-OkmWarnung ('Im Paket fehlt ' + $name); continue }
        $vorhanden = Join-Path $Ziel $name
        if ((Test-Path -LiteralPath $vorhanden) -and (Get-OkmAdmxRevision $vorhanden) -gt (Get-OkmAdmxRevision $neu.FullName)) {
            Write-OkmInfo ($name + ': vorhandene Vorlage ist neuer – bleibt.')
            continue
        }
        $adml = [System.IO.Path]::ChangeExtension($name, '.adml')
        foreach ($sprache in @('de-DE', 'en-US')) {
            $sprachdatei = $alle | Where-Object { $_.Name -eq $adml -and $_.Directory.Name -eq $sprache } | Select-Object -First 1
            if (-not $sprachdatei) { continue }
            $zielsprache = Join-Path $Ziel $sprache
            $null = New-Item -ItemType Directory -Path $zielsprache -Force
            $altAdml = Join-Path $zielsprache $adml
            if (Test-Path -LiteralPath $altAdml) {
                $null = New-Item -ItemType Directory -Path (Join-Path $sicherung $sprache) -Force
                Copy-Item -LiteralPath $altAdml -Destination (Join-Path $sicherung $sprache) -Force
            }
            Copy-Item -LiteralPath $sprachdatei.FullName -Destination $zielsprache -Force
        }
        if (Test-Path -LiteralPath $vorhanden) {
            $null = New-Item -ItemType Directory -Path $sicherung -Force
            Copy-Item -LiteralPath $vorhanden -Destination $sicherung -Force
        }
        Copy-Item -LiteralPath $neu.FullName -Destination $Ziel -Force
        Write-OkmInfo ($name + ' → ' + $Ziel)
    }
    if (Test-Path -LiteralPath $sicherung) { Write-OkmInfo ('Ersetzte Vorlagen gesichert in ' + $sicherung) }
}

function Install-OkmVorlagen {
    param([string]$Name, [string]$Format, [object[]]$Dateien, [string[]]$Admx, [switch]$CentralStore)
    $arbeit = Join-Path $env:TEMP ('okm-vorlagen-' + $Name + '-' + $PID)
    $null = New-Item -ItemType Directory -Path $arbeit -Force
    try {
        foreach ($d in $Dateien) {
            $ziel = Join-Path $arbeit $d.Ziel
            $null = New-Item -ItemType Directory -Path (Split-Path -Path $ziel -Parent) -Force
            Get-OkmDatei $d.Url $ziel $d.Sha256
        }
        $erste = Join-Path $arbeit $Dateien[0].Ziel
        $entpackt = Join-Path $arbeit 'entpackt'
        switch ($Format) {
            'zip' { Expand-Archive -LiteralPath $erste -DestinationPath $entpackt -Force }
            'cab' {
                $null = New-Item -ItemType Directory -Path $entpackt -Force
                $null = & expand.exe $erste '-F:*' $entpackt 2>&1
                foreach ($inner in @(Get-ChildItem -LiteralPath $entpackt -Filter *.zip -Recurse)) {
                    Expand-Archive -LiteralPath $inner.FullName -DestinationPath (Join-Path $entpackt $inner.BaseName) -Force
                }
            }
            'msi' { Start-Process -FilePath 'msiexec.exe' -ArgumentList ('/a "' + $erste + '" /qn TARGETDIR="' + $entpackt + '"') -Wait }
            'office' { Start-Process -FilePath $erste -ArgumentList ('/extract:"' + $entpackt + '" /quiet') -Wait }
            default { $entpackt = $arbeit }
        }
        $global:LASTEXITCODE = 0
        $ziel = Join-Path $env:SystemRoot 'PolicyDefinitions'
        if ($CentralStore) {
            if (-not $env:USERDNSDOMAIN) { throw 'Der Rechner ist in keiner Domäne – kein Central Store.' }
            $ziel = '\\' + $env:USERDNSDOMAIN + '\SYSVOL\' + $env:USERDNSDOMAIN + '\Policies\PolicyDefinitions'
            Write-OkmWarnung ('Central Store: ' + $ziel + ' – betrifft alle Rechner der Domäne.')
        }
        Copy-OkmVorlagen $entpackt $Admx $ziel
    } finally {
        Remove-Item -LiteralPath $arbeit -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Install-OkmSoftwareFallsFehlt([string]$WingetId) {
    $null = & winget.exe list --id $WingetId -e --accept-source-agreements 2>&1
    if ($LASTEXITCODE -eq 0) { Write-OkmInfo ($WingetId + ' ist installiert.'); $global:LASTEXITCODE = 0; return }
    Write-OkmInfo ($WingetId + ' fehlt – wird installiert.')
    & winget.exe install --id $WingetId -e --source winget --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw ('winget endete mit Code ' + $LASTEXITCODE) }
}
