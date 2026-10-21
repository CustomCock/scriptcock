# Changelog

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
