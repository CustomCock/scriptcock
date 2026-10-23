# Script-Editor

In allen drei Modi (Rezept, Listen-Modus, Blockly) ist die Vorschau ein **bearbeitbarer Editor**.
Komponente: `static/js/script-editor.js`, Markup `app/templates/_editor.html`, Dateien in
`_editor_kopf.html`. Pro Seite gibt es genau eine Instanz (`#script-editor`, global `window.OkmEditor`).

## Zustände

| Zustand | Bedeutung | Anzeige |
|---|---|---|
| `generiert` | Text = letzte Fassung des Baukastens | Marke „generiert“ |
| `manuell` | Text weicht von der generierten Fassung ab | gelbe Marke, gelber Rahmen, Banner |

Der Zustand ergibt sich aus dem Vergleich mit der generierten Fassung: Wer alle Änderungen per
Strg+Z zurücknimmt, ist wieder bei `generiert`.

- **Banner** „Manuell bearbeitet – nicht vom Baukasten geprüft“ mit
  - **Neu generieren**: ersetzt den Text durch die aktuelle Fassung des Baukastens (der
    Undo-Verlauf bleibt, Strg+Z holt die eigenen Änderungen zurück),
  - **Änderungen anzeigen**: Zeilen-Diff (LCS) gegenüber der generierten Fassung.
- Im Listen- und Blockly-Modus aktualisiert jede Änderung an den Bausteinen die generierte
  Fassung. Im Zustand `generiert` folgt der Editor sofort; im Zustand `manuell` bleibt der
  bearbeitete Text stehen (nur Diff und Banner werden aktualisiert). Wechselt das Zielsystem,
  sagt das Banner, für welches Ziel der Text noch geschrieben ist.
- **Einmaliger Sicherheitshinweis** bei der ersten Änderung („Verstanden“ merkt sich der Browser
  in `localStorage`, Schlüssel `okm-editor-hinweis-gelesen`).
- **Rückgängig/Wiederholen**: Knöpfe ↶ ↷ sowie Strg+Z / Strg+Y. Suchen mit Strg+F, Gehe zu Zeile mit Alt+G.

## Download, Kopieren, Bibliothek

- Download und Kopieren laufen immer über `POST /api/script/export` (gleiche Encoding-Regeln wie
  der Generator, siehe `app/export.py`). Ist der Text bearbeitet, setzt der Editor
  `manuell_bearbeitet: true`: Der Export fügt im Kopf unter „Benötigte Rechte“ die Zeile
  `Manuell bearbeitet: ja (nicht vom Baukasten geprüft)` ein (idempotent; fehlt der Kopf, direkt
  nach Shebang / `@echo off` + `chcp`). Der SHA-256 (`X-Script-SHA256`) gilt für die fertige Datei
  und wird unter dem Editor angezeigt.
- Download-/Kopier-Knöpfe im Ergebnisbereich (`data-editor-bezug`) nutzen den Editor-Inhalt,
  sobald er bearbeitet ist.
- „In Bibliothek speichern“ schickt den bearbeiteten Text mit (`editor_text`). Gespeichert werden
  IR, Editor-Text und `manuell_bearbeitet`; `inhalt`/`sha256` werden zur bearbeiteten Datei.
  „Erneut öffnen“ baut die Bausteine aus der IR auf und startet den Editor mit dem bearbeiteten
  Text im Zustand `manuell` (eingebettet als `#editor-vorbelegung`).
- Bestehende Datenbanken bekommen die Spalten `editor_text` und `manuell_bearbeitet` beim Start
  per `ALTER TABLE` (`Datenbank._migrieren`).

## Syntax prüfen

`POST /api/script/pruefen` (`app/syntaxpruefung.py`) nutzt **dieselben Checks wie die Tests**
(`tests/syntax.py` importiert Befehle, PSSA-Ausnahmen und CMD-Regeln von dort):

| Ziel | Werkzeuge |
|---|---|
| bash | `bash -n`, shellcheck |
| zsh | `zsh -n` |
| PowerShell | PowerShell-Parser (`pwsh`), PSScriptAnalyzer (wenn installiert) |
| CMD | Baukasten-Regeln (kein echter Parser unter Linux) |

- Befunde haben eine Zeilennummer, die sich auf den Editor-Text bezieht; die Zeilen werden im
  Editor rot hinterlegt, „Zeile n“ springt hin.
- Fehlt ein Werkzeug, steht das als Hinweis im Ergebnis; ohne irgendein gelaufenes Werkzeug
  heißt das Ergebnis „Nicht geprüft“ (nie „OK“).
- Es wird **nur geparst, nie ausgeführt**. Text höchstens 500 000 Zeichen, 60 s pro Werkzeug,
  höchstens 4 Prüfungen gleichzeitig (sonst 429), temporäres Verzeichnis pro Prüfung.

## Warum CodeMirror 5?

- Läuft als klassische Script-Dateien ohne Build-Schritt und ohne Modul-Loader – passt zu
  „alles unter `static/vendor/`, keine CDNs“ und zur CSP ohne Inline-Scripte (CodeMirror setzt
  Styles nur per CSSOM, das erlaubt `style-src 'self'`).
- Fertige Modi für PowerShell und Shell; für Batch reicht ein kleiner Simple-Mode
  (`okm-batch` in `script-editor.js`).
- CodeMirror 6 bräuchte einen Bundler (ES-Module, viele Pakete), Monaco ist mehrere MB groß und
  lädt Worker – beides unverhältnismäßig für einen Script-Editor.
- Version und Lizenz: `static/vendor/VERSIONS.txt` (CodeMirror 5.65.18, MIT). Geprüft gegen die
  sha512-Integrity des npm-Registers.
- Fehlt CodeMirror (z. B. Datei nicht ausgeliefert), bleibt ein normales Textfeld mit allen
  Funktionen außer Hervorhebung und Undo-Knöpfen.
