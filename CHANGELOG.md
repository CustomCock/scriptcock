# Changelog

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
