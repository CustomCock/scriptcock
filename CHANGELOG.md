# Changelog

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
