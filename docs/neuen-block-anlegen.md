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
`smb://server/freigabe`-Adresse (für macOS).

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

## 6. Dry-Run (Simulation)

Im Modus „Nur simulieren“ gilt pro Block:

1. Gibt es `dry_run:` für das Ziel, wird dieser Code verwendet.
2. Sonst laufen grüne Blöcke normal (sie lesen nur).
3. PowerShell-Templates mit `{{ whatif }}` laufen mit `-WhatIf`. Setze `{{ whatif }}` an jedes
   Cmdlet, das `-WhatIf` unterstützt (direkt ans Ende, ohne Leerzeichen davor:
   `-Force{{ whatif }}`).
4. Sonst wird jede Zeile zu einer Ausgabe „[SIMULATION] würde ausführen: …“.

## 7. Testen

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

## 8. Rezepte

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
