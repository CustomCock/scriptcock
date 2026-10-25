# Einen neuen Baustein (Block) anlegen

Für einen neuen Baustein brauchst du **keinen Python-Code** – nur eine YAML-Datei.
Diese Anleitung führt Schritt für Schritt durch.

## 1. Datei anlegen

Lege unter `blocks/<kategorie>/` eine Datei `<id>.yaml` an, z. B.
`blocks/netzwerk/ping.yaml`. Der Ordnername ist frei wählbar, die Kategorie in der UI
kommt aus dem Feld `kategorie`.

## 2. Vollständiges Beispiel

```yaml
id: dienst_neustarten          # eindeutig, nur a-z, 0-9, _ (beginnt mit Buchstabe)
version: 1                     # bei inhaltlichen Änderungen hochzählen
name: Dienst neu starten       # Anzeigename in der UI
kategorie: Dienste             # Gruppierung in der UI
beschreibung: Stoppt einen Systemdienst und startet ihn wieder.
hilfe: |                       # optional, erscheint als Hilfetext
  Den Dienstnamen findest du unter Windows in services.msc (Feld "Dienstname").
risiko: gelb                   # gruen = nur lesen | gelb = ändert etwas | rot = löscht/destruktiv
rechte:                        # optional, pro Ziel – siehe unten
  powershell: admin
  cmd: admin
  bash: root
  zsh: root
fortschritt: "Dienst {{ dienst }} wird neu gestartet"   # optional, Text für "[3/7] …"
parameter:
  - id: dienst
    label: Dienstname
    typ: dienstname
    pflicht: true              # Standard: true
    beispiel: Spooler          # Pflicht, wenn kein "standard" gesetzt ist
    hilfe: z. B. Spooler (Druckwarteschlange)
ziele:
  powershell: |
    Restart-Service -Name {{ dienst }} -Force{{ whatif }}
  cmd: |
    net stop {{ dienst }}
    net start {{ dienst }}
  bash: |
    {{ sudo }}systemctl restart {{ dienst }}
  zsh: |
    {{ sudo }}launchctl kickstart -k system/{{ dienst }}
pruefung:                      # optional: läuft nach dem Block (nicht in der Simulation)
  powershell: |
    if ((Get-Service -Name {{ dienst }}).Status -ne 'Running') { throw 'Dienst läuft nicht.' }
dry_run:                       # optional: eigener Simulationscode pro Ziel
  bash: |
    systemctl status --no-pager {{ dienst }} || true
hinweise:                      # optional: Hinweis in der UI, nur für dieses Ziel
  zsh: Unter macOS ist der Dienstname das launchd-Label, z. B. org.cups.cupsd.
```

Fehlt ein Ziel unter `ziele`, ist der Block dort **nicht verfügbar** und wird ausgegraut.

## 3. Die wichtigste Regel: Platzhalter nie in Anführungszeichen

Werte werden **automatisch** sicher gequotet. `{{ dienst }}` wird z. B. zu `'Spooler'`
(PowerShell, bash, zsh) bzw. `"Spooler"` (CMD).

| Richtig | Falsch |
|---|---|
| `Restart-Service -Name {{ dienst }}` | `Restart-Service -Name '{{ dienst }}'` |
| `ping -c {{ anzahl }} {{ ziel }}` | `ping -c {{ anzahl }} "{{ ziel }}"` |
| `cp -a -- {{ quelle }}/. {{ ziel }}/` | `cp -a "{{ quelle }}/." "{{ ziel }}/"` |

Text direkt an einen Platzhalter zu hängen, funktioniert in allen Shells
(`ipp://{{ ip }}/ipp/print` → `ipp://'10.0.0.5'/ipp/print`; die Shell setzt das zu einem
Wort zusammen). In CMD z. B. `taskkill /IM {{ name }}.exe`.

Brauchst du einen Wert innerhalb von Anführungszeichen (z. B. in `"$( … )"`), weise ihn zuerst
einer Variablen zu und verwende dann die Variable:

```yaml
  bash: |
    okm_url={{ dienst }}
    okm_ip="$(curl -fsS "$okm_url")"
```

Weitere Regeln, die beim Start geprüft werden:

- Nur deklarierte Parameter als Platzhalter; `{{ whatif }}` gibt es nur in PowerShell.
- In `{{ … }}` steht immer nur ein Parametername – keine Filter, kein `~`, keine Konstanten.
- Bedingungen sind erlaubt: `{% if abbrechen %}…{% endif %}`; Auswahlwerte vergleicht man
  über `.wert`: `{% if paketmanager.wert == 'dnf' %}`.
- **PowerShell:** kein `Invoke-Expression`/`iex`, keine Here-Strings (`@'…'@`), kein `exit`.
  Nur PowerShell-5.1-Syntax (kein `??`, `?.`, Ternary, `-Parallel`).
  Für native Programme (`ping.exe`, `net.exe`) wertet der Generator `$LASTEXITCODE` aus.
- **CMD:** kein `%ERRORLEVEL%` (stattdessen `if errorlevel N`), kein `goto`, kein `exit`
  (außer `cmd /c exit N`, um den Fehlercode zu setzen), kein `EnableDelayedExpansion`,
  kein `call` mit Platzhaltern, Klammern müssen ausgeglichen sein. Das Ergebnis eines
  Schritts ist der Fehlercode des **letzten** Befehls.
- **bash/zsh:** kein `eval`, keine Backticks, kein `exit`, kein `sudo` (stattdessen
  `rechte: {bash: root}` und `{{ sudo }}` vor die privilegierten Befehle, siehe Abschnitt 5). Achtung: Die Scripte
  laufen mit `set -e`; ein Befehl, der „nichts gefunden“ mit Fehlercode meldet (`grep`,
  `pgrep`), braucht `|| true` oder eine `if`-Abfrage.
- **Prüf-Blöcke dürfen das Script nicht abbrechen**, nur weil das Ergebnis negativ ist (Ping ohne
  Antwort, Dienst gestoppt oder unbekannt, Suche ohne Treffer). Den Befehl dafür in ein `if`
  setzen bzw. den Exit-Code auswerten und das Ergebnis melden:

  ```yaml
    bash: |
      okm_rc=0
      systemctl --no-pager status {{ dienst }} || okm_rc=$?
      case "$okm_rc" in
        0) ;;
        3) okm_warn 'Der Dienst ist vorhanden, läuft aber nicht.' ;;
        *) okm_fehler "systemctl endete mit Exit-Code $okm_rc."; false ;;
      esac
  ```

- Für Meldungen stehen in jedem Script Hilfsfunktionen bereit – Werte immer als Argument:
  bash/zsh `okm_info`, `okm_ok`, `okm_warn`, `okm_fehler`; PowerShell `Write-OkmInfo`,
  `Write-OkmOk`, `Write-OkmWarnung`, `Write-OkmFehler`. CMD: `echo Hinweis: …`.
- `tipp:` (optional) erscheint bei einem Fehler unter der Fehlermeldung, z. B.
  `tipp: Ist das Gerät eingeschaltet und im selben Netz?`
- Keine Farbcodes (ANSI) in Templates – nur `Write-Host -ForegroundColor` in PowerShell.
- Interne Variablen bitte mit `okm` beginnen (`$okmErgebnis`, `okm_arbeit`), damit sie nicht
  mit anderen Blöcken kollidieren.

## 4. Parametertypen

| Typ | Erlaubt | Beispiel |
|---|---|---|
| `text_kurz` | Buchstaben, Ziffern, Leerzeichen, `- _ .` (max. 100) | `Max Mustermann` |
| `text` | zusätzlich `. , : ; ! ? ( ) / + # ' @ = *` (max. 300) – für Meldungen | `Bitte neu starten!` |
| `zahl` | ganze Zahl, optional `min`/`max` | `4` |
| `ipv4` | IPv4-Adresse | `192.168.1.10` |
| `hostname` | Rechnername (RFC 1123) | `drucker01.okm.local` |
| `ip_oder_hostname` | eins von beiden | `intranet` |
| `port` | 1–65535 | `443` |
| `pfad` | Windows- **oder** Unix-Pfad, muss zum Zielsystem passen | `C:\temp` / `/tmp` |
| `pfad_windows` | `C:\…` (keine `< > : " \| ? *`) | `C:\Daten\Ordner` |
| `pfad_unix` | beginnt mit `/`, kein `~` | `/home/max/Dokumente` |
| `unc_pfad` | `\\server\freigabe[\…]` | `\\fileserver\abteilung` |
| `laufwerksbuchstabe` | ein Buchstabe, wird zu `Z:` | `Z` |
| `dienstname` | Buchstaben, Ziffern, `_ . @ -` | `Spooler`, `cups` |
| `prozessname` | Buchstaben, Ziffern, Leerzeichen, `_ . -`; `.exe` wird entfernt | `notepad` |
| `paketname` | Buchstaben, Ziffern, `_ . + - @` (max. 128) | `Mozilla.Firefox` |
| `druckername` | Buchstaben, Ziffern, `_ . -` (keine Leerzeichen) | `Drucker-Empfang` |
| `benutzername` | Buchstaben, Ziffern, `_ . -` (max. 20) | `max.mustermann` |
| `url` | nur `http://` und `https://` | `https://intranet.okm.local` |
| `sha256` | 64 Hex-Zeichen (wird kleingeschrieben) | `e3b0c442…b855` |
| `auswahl` | einer der Werte aus `optionen` | siehe unten |
| `ja_nein` | Ja/Nein, im Template als Bedingung | `true` |
| `tage` | ganze Tage 1–3650 (mit `min`/`max` enger) | `30` |
| `dauer_sek` | Sekunden 1–86400 (mit `min`/`max` enger) | `90` |
| `datum` | wird zu `JJJJ-MM-TT` (Eingabe auch `TT.MM.JJJJ`), 1970–2100 | `2026-12-24` |
| `uhrzeit` | wird zu `HH:MM` (24 h) | `08:30` |
| `gruppenname` | Buchstaben (auch Umlaute), Ziffern, Leerzeichen, `_ . -` (max. 64) | `Domänen-Benutzer` |
| `dateimuster` | Dateiname mit `*`/`?`, **ohne** Ordner; nicht nur Platzhalter (`*`, `*.*`) | `*.log` |
| `cidr` | IPv4-Netz, Präfix 8–32, muss die Netzadresse sein | `192.168.1.0/24` |
| `mac` | wird zu `AA:BB:CC:DD:EE:FF` (Eingabe auch mit `-`, `.` oder ohne Trenner) | `00:1A:2B:3C:4D:5E` |
| `domain` | DNS-Domain mit mindestens einem Punkt, wird kleingeschrieben | `okm.local` |
| `registry_pfad` | wird zu `HKLM\…` (HKLM, HKCU, HKCR, HKU, HKCC; auch `HKLM:\`, `HKEY_…\`, `Registry::`); ohne Wurzel = relativ (Benutzer-Bereich, siehe unten); Teil ≤ 255, gesamt ≤ 512, kein `"` | `HKLM\SOFTWARE\Firma` |
| `registry_wertname` | ≤ 255 Zeichen, kein `"`; leer oder `(Standard)` = Standardwert | `InstallPath` |
| `registry_typ` | feste Auswahl `REG_SZ`, `REG_EXPAND_SZ`, `REG_DWORD`, `REG_QWORD`, `REG_MULTI_SZ`, `REG_BINARY` | `REG_DWORD` |
| `registry_daten` | je nach Typ (Parameter `bezug`, Standard `typ`): DWORD/QWORD 0 … 2³²−1 bzw. 2⁶⁴−1 (auch `0x…`), Text ≤ 4096, MULTI_SZ eine Zeile pro Eintrag (kein `\0`), BINARY Hex-Bytes | `1` |
| `registry_bereich` | feste Auswahl: `computer`, `angemeldeter_benutzer`, `alle_benutzer`, `standardprofil`, `alle_benutzer_und_standardprofil` | `computer` |
| `dateiname` | ein Name ohne Ordner; nicht `.`/`..`, kein Punkt am Ende, keine Windows-Gerätenamen (`CON`, `nul.txt`) | `Bericht 2026.docx` |
| `rechnername` | 1–15 Zeichen, Buchstaben/Ziffern/`-`, nicht nur Ziffern; wird großgeschrieben | `PC-EMPFANG-01` |
| `dnsname` | Name für DNS-Abfragen; ein Teil darf mit `_` beginnen (SRV), wird kleingeschrieben | `_ldap._tcp.okm.local` |
| `pfad_oder_unc` | Windows-Pfad **oder** `\\server\freigabe\…` (Setup-Dateien vom Fileserver) | `\\fs01\Software\app.msi` |
| `version` | 1 bis 4 Zahlen mit Punkt | `115.3.0` |
| `kb_nummer` | Windows-Update-Nummer (`KB` davor optional); Wert = nur die Ziffern, im Template `KB` selbst voranstellen | `KB5034441` |
| `msi_eigenschaft` | `NAME=wert`: Name in Großbuchstaben, Wert ohne Leerzeichen/Quotes | `ALLUSERS=1` |
| `liste` | mehrere Werte vom Typ `listen_typ`, siehe unten | `80, 443` |
| `variable` | Rückgabewert eines Schritts davor, siehe Abschnitt 6 | `3.frei_prozent` |

Kein Wert darf mit `-` beginnen, Zeilenumbrüche und Steuerzeichen sind nie erlaubt.

```yaml
  - id: paketmanager
    label: Paketmanager
    typ: auswahl
    standard: apt
    optionen:
      - wert: apt              # nur a-z A-Z 0-9 _ . -
        label: apt (Debian, Ubuntu)
      - wert: dnf
        label: dnf (Fedora, RHEL)
  - id: anzahl
    label: Anzahl
    typ: zahl
    min: 1
    max: 100
    standard: 4
  - id: abbrechen
    label: Bei Fehler abbrechen
    typ: ja_nein
    pflicht: false
    standard: false
```

Für `unc_pfad`-Parameter gibt es zusätzlich `{{ <id>_smb }}` – die Freigabe als
`smb://server/freigabe`-Adresse (für macOS). Für `registry_pfad` gibt es `{{ <id>_reg }}` in der
Schreibweise von `reg.exe` (`HKLM\SOFTWARE\Firma`) und `{{ <id>_ps }}` für den PowerShell-Provider
(`Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Firma`).

### Registry-Bausteine (`registry:`)

Registry-Bausteine setzen `registry: lesen | schreiben | wert_loeschen | schluessel_loeschen | import`.
Das schaltet ein:

- **Bereich:** Hat der Block einen `registry_bereich`-Parameter, verweist der Pfad mit `bezug: bereich`
  darauf. `computer` verlangt `HKLM\…` (lesend auch HKCR/HKCC/HKU); die Benutzer-Bereiche verlangen
  einen Pfad ohne Wurzel (`HKCU\…` wird umgeschrieben). **HKCU wird im Script nie benutzt** – nach dem
  UAC-Neustart mit einem anderen Admin-Konto wäre das dessen Profil. CMD kennt nur `computer` und
  `angemeldeter_benutzer`.
- **Schutzliste** `registry/schutz.yaml`: gesperrte Pfade (Fehler), rote Pfade (der Schritt wird rot),
  Mindesttiefe beim Löschen von Schlüsseln.
- **PowerShell-Hilfen** (`app/generators/hilfen/registry.ps1`, nur im Script, wenn ein Registry-Baustein
  vorkommt): `Set-OkmRegistryWert`, `Get-OkmRegistryWert`, `Remove-OkmRegistryWert`, … – sie lösen den
  Bereich auf (HKU\<SID>, geladene NTUSER.DAT), sichern vor Änderungen und lesen zurück. Templates
  rufen nur diese Funktionen auf. Dazu der Neustart als 64-Bit-PowerShell.
- **CMD:** `{{ benutzer_anfang }}` … `{{ benutzer_ende }}` umschließen die `reg`-Befehle (bei
  „angemeldeter Benutzer“ eine `for /f`-Schleife über die SID, sonst eine Klammer), der Pfad heißt dann
  `{{ <id>_reg }}`. Errorlevel 9 = Benutzer nicht ermittelbar. `{{ wirkung_rang }}` (Parameter
  `wirkung`), `{{ regschutz_cmd }}` (findstr-Muster der gesperrten Pfade) und `{{ <daten>_abfrage }}`
  (erwartete `reg query`-Ausgabe) erzeugt der Generator.
- `vorschau:` (je Ziel) läuft bei roten Schritten **vor** der JA-Abfrage und darf nichts ändern.
- **Soll/Ist-Liste** (`typ: registry_soll_liste`): eine Zeile pro Wert `Pfad ; Wertname ; Typ ; Soll`
  (Blockly: Einträge mit `|` getrennt). Jeder Teil wird wie im Einzelbaustein geprüft, die Pfade gegen den
  Bereich des Blocks. Im Template ist der Wert ein PowerShell-Array mit Einträgen `Pfad|Wertname|Typ|Soll`
  (Beispiel: `blocks/registry/registry_soll_ist_liste.yaml`). REG_MULTI_SZ geht dort nicht.

### Listen (`typ: liste`)

```yaml
  - id: ports
    label: Ports
    typ: liste
    listen_typ: port        # jeder Einfachtyp außer ja_nein, variable, liste
    min_anzahl: 1           # optional (Standard 1)
    max_anzahl: 10          # optional (Standard 20, höchstens 100)
    beispiel: [80, 443]
```

- Eingabe getrennt mit `,` oder `;` – bei Typen ohne Leerzeichen (z. B. `port`, `ipv4`) auch mit
  Leerzeichen. Jeder Eintrag wird einzeln geprüft („Eintrag 2 („http“): …“), doppelte fallen weg.
- Im Template ist `{{ ports }}` ein fertiger Ausdruck:
  PowerShell `@(80, 443)` → `foreach ($okmPort in {{ ports }}) { … }`,
  bash/zsh `80 443` bzw. `'a' 'b'` → `okm_ports=({{ ports }})` und `"${okm_ports[@]}"`,
  CMD `80 443` bzw. `"a" "b"` → `for %%p in ({{ ports }}) do …` (`%%~p` entfernt die Quotes).
- In der Oberfläche erscheint ein Tag-Feld (Enter oder Komma fügt hinzu, × bzw. Rücktaste entfernt).

Parameter, die das Template eines Ziels gar nicht verwendet, werden für dieses Ziel in der
UI ausgeblendet und sind dort keine Pflicht.

## 5. `rechte` pro Ziel

```yaml
rechte:
  powershell: admin     # Windows: Administrator
  cmd: admin
  bash: root            # Linux/macOS: privilegierte Befehle mit {{ sudo }}
  zsh: nie_root         # darf NICHT als root laufen (z. B. Homebrew)
```

Werte: `benutzer` (Standard für nicht genannte Ziele), `admin` (nur powershell/cmd), `root`
und `nie_root` (nur bash/zsh). Der alte Schlüssel `admin_noetig` wird mit Fehlermeldung abgelehnt.

Was das Script daraus macht:

- **Windows:** Fehlen die Rechte, erklärt das Script, für welche Schritte es sie braucht, und
  startet sich per UAC selbst als Administrator neu. Abgelehnt → Meldung, kein stiller Abbruch.
- **Linux/macOS:** Kein Neustart mit sudo (das würde `brew` kaputtmachen und `~` auf `/root`
  umbiegen). Stattdessen fragt das Script am Anfang einmal `sudo -v` ab und hält sudo im
  Hintergrund frisch. In `root`-Blöcken **muss** jeder privilegierte Befehl mit `{{ sudo }}`
  beginnen (die Registry prüft das): `{{ sudo }}systemctl restart {{ dienst }}`. Für
  Umgebungsvariablen `{{ sudo }}env DEBIAN_FRONTEND=noninteractive apt-get …`.
- Enthält ein Script einen `nie_root`-Block und wird trotzdem als root gestartet, bricht es mit
  Erklärung ab.
- Kopfkommentar: `Benötigte Rechte:  Administrator (Schritt 2, 4)` bzw. `sudo (…)` bzw. `keine`.

## 6. Rückgabewerte (`rueckgabe`)

Ein Block kann Werte liefern, die spätere Schritte verwenden (z. B. „Wenn freier Speicher < 10 % …“):

```yaml
rueckgabe:
  - id: frei_prozent
    typ: zahl                  # nur zahl oder ja_nein
    beschreibung: "Freier Speicher des Systemlaufwerks in Prozent"
    ziele: [powershell, bash, zsh]   # optional; fehlt es, gilt die Rückgabe für alle Ziele
ziele:
  powershell: |
    {{ rueckgabe_frei_prozent }} = [math]::Floor(100 * $okmSystem.Free / $okmGesamt)
  bash: |
    {{ rueckgabe_frei_prozent }}=$(df -P / | awk 'NR == 2 { sub(/%/, "", $5); print 100 - $5 }')
```

- `{{ rueckgabe_<id> }}` wird zum Variablennamen, den **nur der Generator** vergibt:
  `$script:OkmS3_frei_prozent` (PowerShell), `okm_s3_frei_prozent` (bash/zsh),
  `OKM_S3_FREI_PROZENT` (CMD, Zuweisung mit `set {{ rueckgabe_x }}=1` – ohne Quotes).
- Jede Rückgabe muss im Template jedes ihrer Ziele gesetzt werden (die Registry prüft das). Lässt
  sie sich für ein Ziel nicht sicher ermitteln, `ziele:` der Rückgabe einschränken.
- Alle Rückgaben stehen vor dem ersten Schritt auf „unbekannt“ (`$null` bzw. leer). Nach einem
  erfolgreichen Schritt normalisiert der Generator: `zahl` → nur Ziffern (sonst unbekannt),
  `ja_nein` → PowerShell `$true`/`$false`, sonst `1`/`0` (`1`, `true`, `ja` gelten als ja; CMD nur `1`).
- **CMD:** `set` setzt in `.cmd`-Dateien den Errorlevel auf 0 – Rückgabe zuerst setzen, danach
  `cmd /c exit N`. Werte nicht im selben `( … )`-Block wieder lesen (`%VAR%` wird beim Einlesen
  des Blocks ersetzt).
- **bash/zsh:** Zuweisungen nicht in einer Pipe oder `( … )` machen (Subshell – der Wert ginge verloren).

### Werte aus früheren Schritten verwenden (`typ: variable`)

```yaml
parameter:
  - id: frei
    label: Freier Speicher (aus einem früheren Schritt)
    typ: variable
    variable_typ: zahl           # zahl oder ja_nein
```

Der Wert im Request ist `"<schritt>.<rueckgabe_id>"`, z. B. `"3.frei_prozent"` (Schritt-Nummer wie in
`[3/7]`). Geprüft wird: Der Schritt liegt davor, liefert den Wert für das Zielsystem, der Typ passt,
und er steht nicht in einem „Versuche“-Block, der den aktuellen Schritt nicht umfasst (bash/zsh führen
„Versuche“ in einer Subshell aus). Im Template wird `{{ frei }}` zum lesenden Ausdruck
(`$script:OkmS3_frei_prozent`, `"$okm_s3_frei_prozent"`, `"%OKM_S3_FREI_PROZENT%"`) – wie ein
Literal ohne eigene Quotes verwenden.

## 7. Dry-Run (Simulation)

Im Modus „Nur simulieren“ gilt pro Block:

1. Gibt es `dry_run:` für das Ziel, wird dieser Code verwendet.
2. Sonst laufen grüne Blöcke normal (sie lesen nur).
3. PowerShell-Templates mit `{{ whatif }}` laufen mit `-WhatIf`. Setze `{{ whatif }}` an jedes
   Cmdlet, das `-WhatIf` unterstützt (direkt ans Ende, ohne Leerzeichen davor:
   `-Force{{ whatif }}`).
4. Sonst wird jede Zeile zu einer Ausgabe „[SIMULATION] würde ausführen: …“.

## 8. Testen

```bash
pytest -q -rs
```

Die Tests erzeugen jeden Block für jedes Ziel mit den `beispiel`-Werten und prüfen die
Syntax (`bash -n`, `shellcheck`, `zsh -n`, PowerShell-Parser + PSScriptAnalyzer, CMD-Regeln).
Startet die Anwendung nicht, nennt die Fehlermeldung Datei, Feld und Problem, z. B.:

```
blocks/netzwerk/ping.yaml: ziele.bash: Zeile 1: Platzhalter steht in Anführungszeichen …
```

Bevor ein neuer Block produktiv geht, bitte auf den Test-VMs ausprobieren
(`docs/test-vms.md`). Ist ein Befehl für ein System unsicher: das Ziel weglassen und in
`docs/offene-punkte.md` eintragen.

## 9. Rezepte

Rezepte (`recipes/*.yaml`) verketten Blöcke mit einem eigenen, einfachen Formular:

```yaml
id: drucker_einrichten
name: Drucker einrichten
kategorie: Drucker
beschreibung: Prüft, ob der Drucker erreichbar ist, und richtet ihn ein.
schlagworte: [drucker, printer]
felder:                         # Formularfelder (gleiche Typen wie Parameter)
  - id: drucker_ip
    label: IP-Adresse des Druckers
    typ: ip_oder_hostname
    beispiel: 192.168.1.50
schritte:
  - block: ping
    parameter: {ziel: $drucker_ip, anzahl: 2, abbrechen: true}   # $feld = Formularwert
  - block: drucker_ip
    parameter: {name: Drucker-Empfang, ip: $drucker_ip}
  - block: setupdiag
    nur_fuer: [powershell]      # Schritt nur für diese Ziele
```

Ein wörtliches `$` am Anfang eines Werts schreibt man als `$$`.

**Bedingte Schritte:** `nur_wenn: {feld: wert}` nimmt einen Schritt nur auf, wenn das Formularfeld diesen
Wert hat (mehrere Werte als Liste, mehrere Felder = alle müssen passen; ja/nein als `true`/`false`):

```yaml
  - block: richtlinie_setzen
    parameter: {richtlinie: edge:msedge:HomepageLocation, zustand: aktiviert, e_homepagelocation: $startseite}
    nur_wenn: {browser: edge}
  - block: wiederherstellungspunkt
    parameter: {aktivieren: false}
    nur_wenn: {wiederherstellungspunkt: true}
```

Die Registry prüft beim Start, dass es das Feld gibt und der Wert zum Feld passt; die Rezeptseite zeigt
„nur wenn …“ an. Bei `richtlinie_setzen` mit fester Richtlinie dürfen die Optionen der Richtlinie (`e_…`)
wie normale Parameter belegt werden (IDs im Registry-Panel bzw. `GET /api/registry/richtlinie?id=…`).
