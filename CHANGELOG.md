# Changelog

## Fehlerbehebung Runde 1

### 8. Rezept-Übersicht als Karten-Raster

- **Vorher:** schlichte Kartenliste mit Kategorie-Dropdown, Serversuche ohne Umlaut-Toleranz;
  Rezepte für andere Zielsysteme fehlten ganz, ohne Hinweis.
- **Lösung:**
  - Karten gruppiert nach Kategorie mit Zwischenüberschriften; die Gruppen fließen als Spalten,
    damit Kategorien mit ein bis drei Rezepten keinen Leerraum hinterlassen.
  - Pro Karte: Kategorie-Icon (eigene Inline-SVGs), Titel, Beschreibung (zwei Zeilen),
    Zielsysteme als Badges (nicht verfügbare durchgestrichen), Risiko als Farbpunkt mit Text
    („nur lesen“, „ändert etwas“, „kritisch“), Anzahl der Schritte, „braucht Admin/sudo“.
  - Live-Suche mit derselben Normalisierung wie der Software-Katalog (Umlaute, Satzzeichen)
    und Kategorie-Chips mit dem eindeutigen aktiven Zustand aus Punkt 4; ohne JavaScript filtert
    weiter der Server (`?q=`).
  - Nicht verfügbare Rezepte stehen unten, abgeschwächt, mit „Nicht für macOS verfügbar“.
  - „Zuletzt benutzt“: die letzten vier Rezepte, aus denen der Benutzer Scripte erzeugt hat.
  - Kategorie „Windows Update“ in „Updates“ aufgegangen.
- **Tests:** Server-Rendering (Gruppen, Badges, Risiko, Schritte, Rechte, Sortierung, Zuletzt
  benutzt), Playwright (Live-Suche inkl. Umlaute, Chips, Leer-Hinweis, sichtbarer Tastaturfokus).
- Screenshots: `docs/screenshots/rezepte-{360,768,1280,1920}.png`.

### 6. + 7. Software-Katalog unter der Vorschau, eine Komponente, auch in Blockly

(Ein gemeinsamer Commit: Beide Punkte beruhen auf demselben Umbau der Katalog-Komponente.)

- **Vorher:** Der Katalog war eine Schublade über der Seite, im Baukasten über einen Knopf zu
  öffnen; in Blockly fehlte er ganz. Paneel-Code und Seitenlogik waren vermischt.
- **Lösung:**
  - **Eine Komponente:** Partial `_katalog.html` + `SoftwareKatalog.mount(el, {daten,
    zielPlattform, onUebernehmen, kannUebernehmen, onMehrfach})`; Adapter für `/software`,
    Rezept, Baukasten und Blockly. Keine Kopien.
  - **Platz:** rechte Spalte direkt unter der Vorschau (Rezept, Baukasten, Blockly), die Spalte
    ist `position: sticky`. Auf schmalen Bildschirmen Blöcke → Vorschau → Katalog untereinander.
  - Standardmäßig eingeklappt; klappt automatisch auf, wenn ein Schritt „Paket installieren“
    hinzugefügt (Liste) bzw. angelegt/ausgewählt (Blockly) oder ein Feld „Paketname“ fokussiert
    wird. Die Plattform folgt dem Zielsystem.
  - Blockly: ＋ legt einen „Paket installieren“-Baustein mit ID und Paketmanager an – unter dem
    ausgewählten Baustein, sonst am Ende des Scripts; ist ein solcher Baustein ausgewählt, wird
    nur dessen ID gesetzt.
- **Tests (Playwright):** Position/sticky/eingeklappt, Aufklappen beim Hinzufügen bzw. Fokus,
  ＋ füllt das fokussierte Feld, Reihenfolge auf 600 px, Blockly (neuer Baustein im Script,
  danach ID ersetzen, Vorschau zeigt `brew install --cask 'vlc'`), dieselbe Komponente auf allen
  vier Seiten.

### 5. Software-Katalog: Zeilenumbrüche

- **Ursachen (reproduziert per Playwright bei 360/768/1280/1920 px):**
  - IDs brachen mitten im Wort um (`overflow-wrap: anywhere` + `<wbr>` nach Punkten:
    „geeksoftwareGmbH.“ / „PDF24Creator“), Label/ID/Knöpfe flossen frei (Flexbox mit Umbruch).
  - Im Panel wurden bei vielen Treffern die Flex-Kinder gestaucht: Der Plattform-Umschalter
    schrumpfte, die Kategorien-Zeile lag darüber und fing Klicks ab.
- **Lösung:** Eintrag als CSS-Grid – Kopf: Name (darf umbrechen) | Kategorie (bricht nie);
  Beschreibung höchstens zwei Zeilen (voller Text als `title`); ID-Zeile
  `7rem | minmax(0, 1fr) | auto` mit `white-space: nowrap` + Ellipsis + `title`, Knöpfe mit
  fester Größe in derselben Zeile. Panel mindestens 340 px; schmaler (Container-Query) wechselt
  die Zeile ins Kartenlayout mit dem Label über der ID. `flex-shrink: 0` im Katalog.
- **Tests:** Playwright misst bei vier Breiten auf `/software` und im Panel: ID einzeilig,
  `title` = volle ID, kein `break-all`, Knöpfe ≥ 28 px und auf Höhe der ID.
- Screenshots: `docs/screenshots/katalog-seite-*.png`, `katalog-panel-*.png`.

### 4. Software-Katalog: aktiver Filter erkennbar

- **Ursache:** Aktive Kategorie-Chips waren nur dunkelsand hinterlegt (kaum Kontrast zu inaktiv),
  ohne zweites Merkmal – in Graustufen bzw. bei Farbsehschwäche nicht unterscheidbar.
- **Lösung:** Aktive Chips und Plattform-Umschalter gefüllt in okm-Rot, weiße fette Schrift und
  ✓ davor; inaktiv nur Umriss, Hover sandgelb. `aria-pressed` wie bisher. Neue Zeile über der
  Trefferliste: „Gefiltert: **PDF** ×, **Backup & Cloud** × · **Windows** × · Filter
  zurücksetzen“ – jeder Filter einzeln entfernbar.
- **Test:** Playwright prüft Hintergrund, Schriftfarbe/-stärke, ✓ (`::before`) aktiv vs. inaktiv,
  die Filterzeile, Entfernen einzelner Filter und „Filter zurücksetzen“.
- **Neu:** `tools/screenshots.py` legt Screenshots in vier Breiten unter `docs/screenshots/` ab.

### 3. Admin-/sudo-Rechte automatisch im Script

- **Vorher:** Fehlten Rechte, brach das Script mit „bitte als Administrator starten“ ab; die
  Anleitung empfahl unter Linux/macOS `sudo ./script.sh` – damit liefen auch Homebrew-Befehle
  als root (brew verweigert das) und `~` zeigte auf `/root`.
- **Lösung:**
  - Neues Schema `rechte:` pro Ziel (`admin` | `root` | `benutzer` | `nie_root`) statt
    `admin_noetig`; der alte Schlüssel wird mit klarer Meldung abgelehnt. Alle Blöcke migriert
    (`paket_installieren`/`paket_cache_leeren` unter macOS: `nie_root`).
  - PowerShell/CMD: erklären, für welche Schritte Adminrechte nötig sind, und starten sich per
    UAC neu (`Start-Process … -Verb RunAs`, Pfad mit Leerzeichen sicher). UAC abgelehnt →
    Meldung + Zusammenfassung + Pause.
  - bash/zsh: kein Neustart als root. Einmal `sudo -v` mit Erklärung, Keepalive im Hintergrund
    (wird am Ende beendet), privilegierte Befehle über `{{ sudo }}` → `okm_sudo` (die Registry
    erzwingt den Platzhalter in `root`-Blöcken und verbietet ihn sonst). Als root gestartet mit
    `nie_root`-Block → Abbruch mit Erklärung. Protokoll im Benutzerkontext.
  - Kopfkommentar `Benötigte Rechte: …`, Ausgabe/Protokoll `Rechte: als Administrator gestartet` /
    `sudo erfolgreich` / `ohne erhöhte Rechte`.
  - UI: Badge „Braucht Admin“/„Braucht sudo“ mit Schritten als Tooltip, Anleitung angepasst
    („Das Script fragt einmal nach deinem Passwort“, Start **ohne** sudo).
- **Tests (`tests/test_rechte.py`):** Schema/Registry-Regeln, alle Kombinationen im Generator,
  bash-Ausführung als `nobody` mit sudo-Attrappe (erfolgreich / abgelehnt, Protokoll gehört dem
  Benutzer), root + `nie_root` → Abbruch, Badge und Anleitung.
- **Golden-Files** neu erzeugt (Rechte-Zeile im Kopf, sudo/UAC-Logik – gewollt).

### 2. Scripte beenden sich ohne Meldung

- **Ursachen (reproduziert):**
  - bash: `set -u` (nicht gesetzte Variable) löst **kein** ERR-Trap aus – das Script endete ohne
    Fehlermeldung und ohne Zusammenfassung.
  - zsh: Mit `NO_UNSET` beendet sich zsh bei einer nicht gesetzten Variable sofort – nicht einmal
    ein EXIT-Trap läuft.
  - zsh: `exec > >(tee …)` – schließt sich das Terminal mit dem Scriptende (Doppelklick unter
    macOS), geht die **gesamte** Ausgabe verloren (mit `script(1)` nachgestellt).
  - Prüf-Blöcke brachen bei negativem Ergebnis ab: `dienst_status` bei unbekanntem Dienst,
    `zertifikat_website` bei nicht erreichbarem Server; `dns_test` (zsh) meldete gar nichts,
    weil `dscacheutil` auch ohne Treffer 0 liefert.
  - PowerShell: Fehler außerhalb der Schritte hatten kein Netz; das Fenster von „Mit PowerShell
    ausführen“ schloss sich sofort.
- **Lösung:**
  - bash/zsh: Zusammenfassung über `trap okm_ende EXIT` bei **jedem** Ende (Erfolg, Fehler,
    Abbruch, unerwartetes Ende → „Script unerwartet beendet in Schritt …“). ERR-Trap mit Zeile
    (`$LINENO`) und in bash dem Befehl (`$BASH_COMMAND`); zsh als String-Trap `ZERR`, weil
    `$LINENO` in `TRAPZERR()` immer 0 ist. zsh ohne `NO_UNSET`.
  - Protokoll über FIFO + Hintergrund-`tee`; am Ende wartet das Script höchstens 2 s auf `tee`.
  - PowerShell: Fehlermeldung mit Zeile, globales `trap { … }` als Netz.
  - Fenster offen halten: PowerShell (außer `-NoPause`, `-NonInteractive`, umgeleiteter Eingabe),
    CMD (außer `/nopause`), bash/zsh nur wenn `[ -t 0 ]` und ohne `--nopause`.
  - `dienst_status`, `zertifikat_website`, `dns_test` werten das Ergebnis aus und melden es mit
    `okm_warn`/`Write-OkmWarnung` statt abzubrechen (Ansatz „Befehl im `if`“ statt eines neuen
    YAML-Felds – so bleibt die Logik pro Ziel sichtbar und testbar). Doku in
    `docs/neuen-block-anlegen.md`.
- **Tests (`tests/test_abbruch.py`):** nicht gesetzte Variable, Fehler mit Schritt/Zeile/Befehl und
  Zusammenfassung in Ausgabe **und** Protokoll, PowerShell mit Zeile + Trap, Ping ohne Antwort
  läuft weiter (Attrappe im PATH), Dienst unbekannt/gestoppt, Zertifikat nicht erreichbar,
  Pause nur im Terminal (`script(1)`) und nicht mit `--nopause`, CMD `/nopause`.
- **Golden-Files** neu erzeugt (EXIT-Trap, FIFO, Pause – gewollt).

### 1. Unlesbare Ausgabe („Wirrwarr“)

- **Ursache (reproduziert):** Jeder PowerShell-Schritt leitet seine Ausgabe durch `| Out-Host`,
  damit sie im Transcript landet. PowerShell 5.1 dekodiert die Ausgabe externer Programme dabei
  mit der OEM-Codepage (850). winget, DISM & Co. schreiben UTF-8 → aus „Größe“ wurde
  „Gr├Â├ƒe“ (Test mit pwsh und Codepage 850). `sfc` schreibt umgeleitet sogar UTF-16.
- **Nicht die Ursache:** Der Download baute nie per JS-`Blob` aus dem Vorschautext; er kam schon
  immer als Bytes vom Server (BOM/CRLF korrekt). Kopieren lieferte aber Text ohne BOM – wer ihn
  in Notepad einfügt und speichert, bekommt in PowerShell 5.1 kaputte Umlaute.
- **Lösung:**
  - PowerShell setzt am Anfang `[Console]::OutputEncoding` und `$OutputEncoding` auf UTF-8
    (ohne BOM); `dism_sfc` liest die sfc-Ausgabe kurz als UTF-16, in CMD läuft sfc ohne Umleitung.
  - Neuer Endpunkt `POST /api/script/export` (Text + Ziel → Bytes, `application/octet-stream`).
    Die Regeln (PS: UTF-8 mit BOM + CRLF, CMD: ohne BOM + CRLF + `chcp 65001`, bash/zsh: LF)
    stehen nur noch in `app/export.py`; Generator und Endpunkt nutzen dieselbe Funktion.
  - „In Zwischenablage kopieren“ läuft über den Export; bei PowerShell steht ein Hinweis zu
    „UTF-8 mit BOM“.
  - Einheitliches Ausgabeformat für alle Ziele: Kopfkasten (Titel, Datum, Autor), `[n/m] … ...`,
    eingerückt `OK` / `FEHLER  …` / `Tipp: …`, Schlusskasten mit Ergebnis und Protokollpfad.
    Meldungen über Hilfsfunktionen (`okm_info`/`okm_ok`/`okm_warn`/`okm_fehler`, in PowerShell
    `Write-OkmInfo`/`-Ok`/`-Warnung`/`-Fehler`), Werte immer als Argumente.
  - Neues Block-Feld `tipp` (für die häufigsten Fehlerfälle gesetzt).
  - Keine ANSI-Farbcodes: PowerShell nur `Write-Host -ForegroundColor`, CMD und bash/zsh ohne
    Farben (die Ausgabe geht auch ins Protokoll). bash/zsh-Protokoll unter `${TMPDIR:-/tmp}`.
  - Jinja-Code-Umgebung mit `keep_trailing_newline=True` (trim/lstrip waren schon an).
- **Tests:** Byte-Tests des Exports (BOM einmal/keinmal, nur CRLF bzw. nur LF, `chcp`), Endpunkt
  inkl. CSRF und Größenlimit, Generator = Export, keine `\x1b`, Ausgabeformat in bash/zsh/pwsh/CMD,
  pwsh mit Codepage 850, Golden-Files `_umlaute.*` (Büro, Größe, Löschen) für alle Ziele.
- **Golden-Files** neu erzeugt: neues Ausgabeformat (gewollt).

## Software-Katalog

- **Katalog mit 259 Programmen** (`katalog/software-katalog.yaml`) – einzige Datenquelle,
  Pydantic-Schema `SoftwarePaket`/`SoftwareKatalog`, wird beim Start geprüft (Pflichtfelder,
  mindestens eine Paket-ID bzw. Herstellerlink, keine doppelten IDs pro Plattform, alle IDs
  bestehen `paketname`). Vorgesehene Zusatzfelder: `hinweis`, `hersteller_url`, `intern`.
- **Oberfläche:** eigene Seite `/software` (neuer Menüpunkt „Software“) und ausklappbares Panel
  im Baukasten und in Rezepten (auf dem Handy Vollbild). Live-Suche im Browser über Name,
  Beschreibung, Kategorie, Suchbegriffe und alle IDs mit Umlaut-/Satzzeichen-Normalisierung,
  Ranking und Hervorhebung; Plattform-Umschalter (folgt dem Zielsystem), Kategorie-Chips,
  Tastatur (`/`, `↑`/`↓`, `Enter`, `Esc`).
- **Kopieren** der ID (Clipboard-API, Fallback für HTTP, sonst Markieren + „Strg+C“) und des
  kompletten Installationsbefehls.
- **Ins Script übernehmen:** „＋“ legt einen Schritt „Paket/Software installieren“ an bzw.
  befüllt das aktive Paketfeld; Mehrfachauswahl „Ausgewählte installieren (n)“.
- `paket_installieren` (Version 2) kennt die Paketmanager `winget`, `apt`, `dnf`, `flatpak`,
  `brew`, `brew_cask`; winget immer mit `--id … -e --source winget`; Flatpak/Homebrew prüfen,
  ob das Werkzeug installiert ist. Das Rezept „Software installieren“ zieht mit.
- Parametertyp `paketname`: neue Whitelist `^[A-Za-z0-9][A-Za-z0-9._+@-]{0,127}$`
  (`/` ist nicht mehr erlaubt).
- **`tools/katalog_pruefen.py`** prüft alle IDs gegen winget-pkgs, Homebrew, Ubuntu 24.04/Debian
  und Flathub; monatlicher GitHub-Workflow legt bei Fehlern ein Issue an.
- Katalog-Korrekturen aus der ersten Prüfung: `python3` (apt) war bei Python 3.12 und 3.13
  doppelt → nur noch bei 3.12; Flathub-Paket von PyCharm Community ist abgekündigt (EOL) →
  entfernt; `dnsutils` → `bind9-dnsutils` (gibt es unter Ubuntu und Debian); Hinweise für
  apt-Pakete, die es nur unter Ubuntu gibt.
- Tests: Schema/Fehlermeldungen, Validierung + Escaping aller IDs für alle Ziele (inkl.
  Ausführung in bash/zsh/pwsh), Syntax-Checks der Scripte mit allen IDs, Suche unter Node,
  Browser-Test (Playwright).

## Vorlagen – 116 neue Bausteine, 13 neue Rezepte

- **Bausteine (jetzt 140)** aus der Ideensammlung, zuerst die ★-Vorlagen der Kategorien
  1, 2, 4, 5, 8, 9, 11, 13, 14, 21: Inventar (Seriennummer, Software, Lizenz, Windows-11-Check,
  Akku, Treiber …), Netzwerk (Gateway, DNS, öffentliche IP, MTU, WLAN, Ports, Proxy …),
  Drucker, Dateien & Freigaben, Dienste & Prozesse, Updates (Status, DISM+SFC, winget, apt/dnf,
  macOS), Speicher & Bereinigung, Sicherheit (Virenschutz, BitLocker/FileVault, Ampel-Check,
  Zertifikate, Incident-Erstsicherung …), Fehleranalyse (Bluescreens, Abstürze, Startdauer),
  Performance, Office/Entra ID, Support-Infos, lokale Benutzer, Linux-Server, macOS.
- **Neue Rezepte:** PC ist langsam, Support-Infos, Inventar erfassen, Windows-11-Tauglichkeit,
  Drucker-Problem diagnostizieren, Sicherheits-Schnellprüfung, Update-Status, Systemdateien
  reparieren, Benutzerdaten sichern, Server-Gesundheitscheck, Incident-Erstsicherung,
  Absturz-Analyse, Office-Probleme. „Netzwerkproblem diagnostizieren“ prüft jetzt zusätzlich
  Router, Internet und DNS.
- `systeminfo` (Version 2) zeigt zusätzlich Prozessor, Kerne und Build.
- Neuer Parametertyp `sha256` (für die Hash-Prüfung beim Datei-Download).
- CMD-Regelprüfung erlaubt Umgebungsvariablen wie `%USERPROFILE%` in Anführungszeichen.
- Übersicht über umgesetzte, zurückgestellte und bewusst ausgelassene Vorlagen:
  `docs/vorlagen-status.md`; ungeprüfte Befehle in `docs/offene-punkte.md`.

## UI-Überarbeitung – Dark Theme & Übersicht

- **Komplett dunkles Design** in okm-Farben (Schwarz, Rot, Sandgelb) mit neuem Design-System
  (`static/css/app.css`): Farb-Tokens, einheitliche Knöpfe, Panels, Hinweise, Badges, Formulare,
  Tabellen; `color-scheme: dark` für native Bedienelemente; dunkles Blockly-Theme.
- **Navigation:** Icons (eigene Inline-SVGs, `_icons.html`), aktiver Menüpunkt markiert,
  kompakte Kopfzeile, auf dem Handy horizontal scrollbar.
- **Startseite als Einstieg:** die drei Wege (Rezepte, Baukasten, Blockly), zuletzt erstellte
  Scripte, Bibliothek – Admins sehen offene Rezept-Vorschläge. Die Betriebssystem-Wahl liegt
  jetzt unter `/rezepte`.
- **Weniger Text:** einheitliche Seitenköpfe (Titel + eine Zeile); Ausführungsanleitung,
  Bibliothek-Speichern und Optionen einklappbar.
- **Kompakter:** breiterer Inhaltsbereich; auf großen Bildschirmen Rezept-Formular und Vorschau
  nebeneinander, Baukasten dreispaltig (Bausteine | Schritte | Vorschau), Blockly mit Vorschau
  rechts; Schritt-Karten mit Rand in Risikofarbe.

## Phase 4 – Blockly-Modus + Ablauf-Bausteine

- **IR-Erweiterung** ohne Umbau: neue Knotentypen `wenn_fehler` („Versuche … / Wenn das
  fehlschlägt …“, leeres „sonst“ = Fehler übergehen) und `wiederhole` (1–50-mal) in der
  diskriminierten Union `Knoten`; `ir_version` 2, gespeicherte v1-IRs bleiben lesbar.
  Requests ohne `art` gelten weiter als Block (Rezept- und Listen-Modus unverändert).
- **Validierung** rekursiv mit Grenzen (Tiefe ≤ 4, ≤ 100 Bausteine insgesamt, Anzahl 1–50);
  Fehler tragen die Position des Knotens in Vorordnung (für Blockly).
- **Generatoren** für alle vier Ziele:
  - PowerShell: `try/catch`-Container, Schritte geben Fehler per `throw` weiter; `for`-Schleife.
  - CMD: lineare Sprungmarken (`:okm_sonst_N`, `:okm_ende_N`, `:okm_schleife_N`) statt
    `for`/Klammerblöcken, weil dort `%VAR%` nur einmal expandiert würde.
  - bash/zsh: „Versuche“ in einer Subshell mit eigenem errexit; Schutz-Flag für den Fehler-Handler,
    Zählerdatei für erfolgreiche Schritte, Exit-Code 112 reicht einen roten Abbruch nach außen
    durch (keine Ausweichschritte, Script endet mit 2).
  - Kopfkommentar zeigt die Struktur; Abschluss „Fertig, X Schritte erfolgreich ausgeführt.“
  - Scripte **ohne** Ablauf-Bausteine bleiben byte-gleich (Golden-Files unverändert).
- **Blockly-Modus** (`/blockly`, vendored Blockly 11.2.1 mit deutschen Texten): Toolbox wird
  automatisch aus der Registry erzeugt (Kategorien = YAML-`kategorie`, Kategorie „Ablauf“),
  Parameter erscheinen passend zum Zielsystem, nicht verfügbare Bausteine sind in der Toolbox
  deaktiviert und auf der Fläche markiert. Blockly erzeugt **nur JSON** für `/api/v1/vorschau`
  (neu, speichert nicht) und `/api/v1/skripte`; Fehler des Servers erscheinen am jeweiligen
  Baustein. Entwurf wird im Browser zwischengespeichert, „Neu beginnen“ leert ihn.
- Bibliothek: Blockly-Scripte öffnen sich wieder im Blockly-Modus (aus der IR, inkl. Hinweise
  auf geänderte/entfernte Bausteine); der Listen-Modus lehnt Scripte mit Ablauf-Bausteinen ab.
- CSP: nur auf `/blockly` zusätzlich `style-src 'unsafe-inline'` (Blockly setzt Inline-Styles);
  Inline-Scripte bleiben überall verboten.
- Fix (CSS): `[hidden]` wird nicht mehr von `display:flex` überschrieben.
- Tests: IR/Validierung, Syntax aller Ziele (inkl. Simulation), CMD-Sprungmarken, Ausführung
  in bash/zsh/pwsh (Ausweichschritte, Fehler übergehen, Verschachtelung, Fehler in Ausweichschritten,
  roter Abbruch im Versuch, Schleifen), Golden-Files `_ablauf.*`, Blockly-Seite/API/Wiederöffnen,
  Browser-Test mit echtem Drag & Drop.

## Phase 3 – Bibliothek + Verwaltung

- **Bibliothek** (`/bibliothek`): erzeugte Scripte mit Titel, Beschreibung und Tags in die
  Bibliothek speichern (direkt nach dem Erzeugen oder auf der Detailseite). Suche über Titel,
  Beschreibung und Tags, Filter nach Zielsystem und Tag, Reiter „Meine Scripte“ (auch private),
  Seitenweise Anzeige. Sortierung nach „Hat funktioniert“-Stimmen.
- **Detailseite** (`/skripte/<id>`): Eckdaten, SHA-256, Code, enthaltene Bausteine mit
  Version beim Speichern vs. aktueller Version.
- **„Hat funktioniert ✓“**: eine Stimme pro Benutzer und Script (umschaltbar), Zähler in der Liste.
- **„Erneut öffnen und anpassen“**: lädt die gespeicherte IR (nicht den Script-Text) in den
  freien Baukasten – mit Hinweisen, wenn Bausteine seitdem geändert (Version), entfernt oder
  Parameter weggefallen sind.
- **Rollen**: Nutzer erzeugen, speichern und schlagen Rezepte vor; Admins geben Vorschläge in
  der **Verwaltung** (`/verwaltung`) frei, lehnen sie ab oder löschen DB-Rezepte (mit erneuter
  Prüfung gegen die aktuellen Bausteine, YAML-Export). Rote Bausteine ohne Zusatzbestätigung
  für Admins (seit Phase 1).
- Sichtbarkeit: private Scripte nur für Ersteller und Admins; Bibliotheks-Scripte für alle
  Angemeldeten; Ändern/Entfernen nur Ersteller und Admins.
- Neue Tabelle `bewertungen` (wird beim Start automatisch angelegt).
- **Fix:** Rezeptfelder heißen im Formular jetzt `f.<feld>`. Vorher kollidierte das Feld `ziel`
  des Rezepts „Netzwerkproblem diagnostizieren“ mit dem Zielsystem – das Rezept ließ sich im
  Browser nicht erzeugen.

## Phase 2 – Freier Baukasten (Listen-Modus)

- Neue Seite „Freier Baukasten“ (`/baukasten`): durchsuchbare Bausteinliste nach Kategorien,
  Hinzufügen per Drag & Drop (SortableJS, vendored) oder „+“-Knopf, Umsortieren per Griff
  oder ↑/↓, Entfernen, Parameter pro Schritt (serverseitig gerenderte Formularfelder).
- Live-Vorschau mit Syntax-Highlighting bei jeder Änderung (wird nicht gespeichert);
  Fehler werden dem jeweiligen Schritt und Feld zugeordnet.
- Zielsystem jederzeit umschaltbar: Werte bleiben erhalten (auch für Parameter, die das
  neue Ziel nicht nutzt), nicht verfügbare Bausteine werden rot markiert bzw. in der
  Palette ausgegraut, der Download ist mit Erklärung gesperrt.
- Rote Bausteine: Bestätigung „Ich weiß, was dieses Script tut“ erscheint automatisch.
- „Als Rezept speichern“ für Admins: ausgefüllte Werte werden feste Rezeptwerte, leere
  Pflichtfelder werden Formularfelder. Rezepte liegen in der Datenbank (Tabelle `rezepte`),
  werden beim Start mit voller Registry-Prüfung geladen und lassen sich als YAML für
  `recipes/` exportieren.
- Rezepte mit festen Werten erscheinen nur für passende Zielsysteme (z. B. Windows-Pfad).
- Formularfeld-Vorlage `_feld.html` für Rezept- und Listen-Modus vereinheitlicht.
- Fix: In-Memory-SQLite nutzt einen `StaticPool` (sonst getrennte Datenbanken je Verbindung).
- Tests: Formular-Parser, Vorschau, Fehlerzuordnung, Zielwechsel, Reihenfolge, rote Bestätigung,
  Als-Rezept-Speichern inkl. Neustart und YAML-Export; optionaler Browser-Test (Playwright)
  für Drag & Drop, Zielwechsel und Download.

## Phase 1 – Kern + Rezept-Modus

- Kernarchitektur: Block-Schema (YAML, Pydantic), Registry mit Startprüfung (Schema,
  Template-Syntax, Platzhalter nicht in Quotes, verbotene Konstrukte je Sprache,
  Beispielwerte), zielunabhängige IR mit Baumstruktur für spätere Kontrollknoten.
- Generatoren für PowerShell 5.1 (CRLF, UTF-8 mit BOM), CMD (CRLF, `chcp 65001`,
  Delayed Expansion aus), Bash und zsh (LF): Kopfkommentar, Fehlerbehandlung, Protokoll,
  Fortschritt `[n/m]`, Admin-Prüfung, rote Bestätigung („JA“), Dry-Run, Zusammenfassung.
- Escaping pro Zielsprache inkl. Unicode-Quotes in PowerShell; eigene Jinja-Umgebung,
  die nur escapte Werte ausgibt. 20 Parametertypen mit deutschen Fehlermeldungen.
- Startbibliothek: 24 Blöcke, 8 Rezepte.
- Web-UI (Jinja2 + htmx, vendored highlight.js): Betriebssystem → Rezept (Suche, Kategorien)
  → Formular mit Live-Validierung → Vorschau mit SHA-256 → Download/Zwischenablage +
  Ausführungsanleitung. Login per OIDC/Keycloak, `AUTH_DISABLED` mit Warnbanner,
  CSRF-Schutz per Header, CSP. JSON-API `/api/v1/bloecke`, `/api/v1/skripte`.
- SQLite-Speicherung jedes erzeugten Scripts (Inhalt, Hash, IR).
- Betrieb: systemd-Unit, nginx-Konfiguration, Dockerfile + docker-compose.
- Tests: Escaping-Suite mit Injection-Payloads (Round-Trip in echter bash/zsh/pwsh),
  Validierung, Registry, Generatoren (jeder Block × jedes Ziel, normal und Simulation),
  Golden-Files aller Rezepte, Syntax-Checks (`bash -n`, `shellcheck`, `zsh -n`, pwsh-Parser,
  PSScriptAnalyzer, CMD-Lint), Ausführung echter Scripte, Web/Auth. GitHub-Actions-CI.
- Doku: README, CLAUDE.md, `docs/sicherheit.md`, `docs/neuen-block-anlegen.md`,
  `docs/test-vms.md`, `docs/offene-punkte.md`.
