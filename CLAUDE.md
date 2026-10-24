# CLAUDE.md – okm Script-Baukasten

Webanwendung fürs okm-Intranet: Mitarbeiter stellen sich aus geprüften Bausteinen Scripte
zusammen (PowerShell 5.1, CMD, Bash, zsh) und laden sie herunter. **Die Anwendung führt
nichts selbst aus.** Oberfläche, Fehlermeldungen, Bezeichner und Doku sind deutsch.

## Befehle

```bash
pip install -e ".[dev]"                    # Abhängigkeiten
AUTH_DISABLED=true uvicorn app.main:app --reload   # lokal starten → http://127.0.0.1:8000
pytest -q -rs                              # alle Tests (zeigt übersprungene Syntax-Checks)
UPDATE_GOLDEN=1 pytest tests/test_golden.py   # Golden-Files nach gewollter Änderung neu erzeugen
ruff check . && ruff format --check .      # Lint + Format
mypy app                                   # Typprüfung (strict)
python tools/katalog_pruefen.py            # Paket-IDs des Software-Katalogs online prüfen (braucht Netz)
python tools/screenshots.py [katalog rezepte]   # Screenshots in 4 Breiten nach docs/screenshots/
python tools/checkliste_scripte.py checkliste/  # Test-Scripte für die VM-Checkliste (docs/test-vms.md)
```

Syntax-Checks in den Tests brauchen `bash`, `zsh`, `shellcheck`, `pwsh` (+ Modul
`PSScriptAnalyzer`), der Test der Katalog-Suche braucht `node`. Fehlt ein Werkzeug, wird der
Test mit Hinweis übersprungen; die GitHub-CI hat alle.

## Architektur / Datenfluss

```
UI-Formular / JSON ──► ScriptRequest ──► validation.py ──► ScriptIR ──► Generator[ziel] ──► GeneratedScript
(unsicher)             models/request    Whitelist pro      nur geprüfte    escaping.py        Bytes + SHA-256
                                         Parametertyp       Werte                              → DB (db.py)
```

| Datei | Aufgabe |
|---|---|
| `app/escaping.py` | **Sicherheitskritisch.** Literal pro Zielsprache, `Escaped`-Markertyp, echo-/Kommentar-Escaping |
| `app/validation.py` | Parametertypen (Whitelist) → `ParamValue`; ganzer Request → `ScriptIR` |
| `app/ir.py` | Zielunabhängige IR. Schritte = Baum über Diskriminator `art`: `block`, `wenn_fehler`, `wiederhole` |
| `app/codeenv.py` | Jinja-Umgebung für Code: `finalize` lässt **nur** `Escaped` durch |
| `app/registry.py` | Lädt/prüft `blocks/**/*.yaml` und `recipes/*.yaml` beim Start, bricht bei Fehlern ab |
| `app/generators/base.py` | Fester Script-Aufbau (Kopf → Präambel → Schritte → Abschluss), Dry-Run-Logik |
| `app/generators/{powershell,cmd,bash}.py` | Sprachspezifische Bausteine (`bash.py` enthält auch zsh) |
| `app/export.py` | **Einzige Stelle** für Dateiformat: PS = UTF-8 mit BOM + CRLF, CMD = ohne BOM + CRLF + `chcp 65001`, bash/zsh = LF; Kopfzeile „Manuell bearbeitet“ |
| `app/routes/export.py` | `POST /api/script/export` (Text → Datei-Bytes, `X-Script-SHA256`) und `POST /api/script/pruefen` |
| `app/syntaxpruefung.py` | „Syntax prüfen“: dieselben Checks wie die Tests (`tests/syntax.py` importiert von hier), nur parsen |
| `app/service.py` | Rezept-Formular → Request, `generiere` (ohne Speichern) / `erzeuge` (mit Speichern) |
| `app/baukasten.py` | Listen-Modus: Formular lesen, Rezept aus Schrittliste; DB-Rezepte vorschlagen/freigeben/laden/YAML |
| `app/bibliothek.py` | Bibliothek: Rechte, Suche, Tags, Bewertungen, „Erneut öffnen“ aus der IR, Blockversionen |
| `app/routes/pages.py`, `baukasten.py`, `bibliothek.py`, `verwaltung.py`, `api.py` | HTML-Seiten je Bereich, JSON-API |
| `app/routes/blockly.py`, `static/js/blockly-modus.js` | Blockly-Modus: Katalog → Toolbox, Arbeitsfläche → JSON (kein Code!) |
| `static/js/app.js` | Gemeinsames JS (Zwischenablage, `OkmExport`, Listen-Modus: Sortable, Palette, Rezept-Filter) |
| `static/js/script-editor.js`, `_editor.html`, `_editor_kopf.html` | Script-Editor (CodeMirror 5) für alle Modi, siehe unten und `docs/editor.md` |
| `app/katalog.py`, `app/models/software.py` | Software-Katalog (`katalog/software-katalog.yaml`) laden/prüfen; Abbruch bei Fehlern |
| `app/routes/software.py`, `_katalog.html` | Seite `/software` und einklappbarer Katalog in Rezept/Baukasten/Blockly (Daten als eingebettetes JSON) |
| `static/js/katalog-suche.js`, `software-katalog.js` | Suche (rein, auch unter Node getestet) bzw. **eine** Katalog-Komponente `SoftwareKatalog.mount` |
| `tools/katalog_pruefen.py` | Prüft alle Paket-IDs online (monatlich per `.github/workflows/katalog-pruefen.yml`) |
| `app/auth.py` | OIDC (Keycloak), Rollen `nutzer`/`admin`, `AUTH_DISABLED` |

## Konventionen

- **Nie** Benutzereingaben roh in Code. Templates bekommen nur `Escaped`; Platzhalter stehen
  **nie** in Quotes (`-Name {{ dienst }}`, nicht `'{{ dienst }}'`) – die Registry prüft das.
- Neue Parametertypen: Whitelist in `validation.py` + Tests in `tests/test_validation.py`.
  Werte dürfen nicht mit `-` beginnen (Option-Injection).
- Neue Blöcke: nur YAML (`docs/neuen-block-anlegen.md`). Jeder Pflichtparameter braucht `beispiel`/`standard`.
- **Rechte** pro Ziel im Block: `rechte: {powershell: admin, bash: root, zsh: nie_root, …}` mit
  `admin` (nur Windows), `root` (nur bash/zsh), `benutzer` (Standard), `nie_root`. Das alte
  `admin_noetig` wird abgelehnt. Windows-Scripte starten sich per UAC selbst neu; bash/zsh holen
  einmal `sudo -v` + Keepalive. Root-Blöcke schreiben `{{ sudo }}` vor privilegierte Befehle
  (wird `okm_sudo `; bash = Funktion, zsh = Alias) – nie `sudo` direkt. `nie_root` bricht als root ab.
- **Rückgabewerte**: `rueckgabe: [{id, typ: zahl|ja_nein, beschreibung, ziele?}]`; im Template
  `{{ rueckgabe_<id> }}` als Zuweisungsziel (Namen `OkmS<n>_<id>`/`okm_s<n>_<id>`/`OKM_S<n>_<ID>` nur
  vom Generator). Generator belegt vor Schritt 1 mit „unbekannt“ vor und normalisiert nach jedem
  Schritt. Parametertyp `variable` (+ `variable_typ`) verweist mit `"<schritt>.<id>"` auf einen
  früheren Schritt; `_BaumPruefer.verweis_pruefen` prüft Reihenfolge, Typ, Ziel und „Versuche“-Grenzen.
- Ausgaben in Templates nur über die Helfer (`okm_info`/`okm_ok`/`okm_warn`/`okm_fehler`,
  `Write-OkmInfo`/`Write-OkmOk`/`Write-OkmWarnung`/`Write-OkmFehler`) – keine Farbcodes. `tipp:` im
  Block erscheint beim Fehler. Erwartete negative Ergebnisse (Ping ohne Antwort, Dienst gestoppt …)
  melden statt abbrechen.
- Jedes Script endet mit Zusammenfassung (bash/zsh `trap okm_ende EXIT`, PS `trap`/`Exit-OkmScript`,
  CMD Sprungmarken) und hält das Fenster offen, außer mit `--nopause`/`-NoPause`/`/nopause`.
- In CMD-Templates verboten: `%ERRORLEVEL%`, `goto`, `exit` (außer `cmd /c exit N`),
  `EnableDelayedExpansion`, `call` mit Platzhaltern, unausgeglichene Klammern.
  In bash/zsh: `eval`, Backticks, `exit`, `sudo`. In PowerShell: `Invoke-Expression`/`iex`, Here-Strings, `exit`.
- PowerShell-Code muss **5.1-kompatibel** sein (kein `??`, `?.`, Ternary, `-Parallel`).
- Interne Variablen in generierten Scripten: Präfix `Okm`/`OKM_`/`okm_`.
- Unsichere Befehle für ein Zielsystem lieber weglassen und in `docs/offene-punkte.md` notieren.
- Platzhalter-Implementierungen nur mit `TODO` + Eintrag in `docs/offene-punkte.md`.
- PSScriptAnalyzer-Ausnahmen stehen in `tests/syntax.py` (`PSSA_AUSNAHMEN`) mit Begründung.
- Nach jeder Phase: Tests grün, `CHANGELOG.md` ergänzen, Commit.

## Listen-Modus (Baukasten) – Formular-Konvention

Reihenfolge der Schritte = Reihenfolge im DOM. Jeder Schritt hat `schritt=<uid>:<block_id>`
(uid = 8 Hex-Zeichen), Parameter heißen `p.<uid>.<parameter_id>`. Checkboxen haben davor ein
verstecktes `false`; beim Lesen gewinnt der letzte Wert. Parameter, die das aktuelle Ziel nicht
nutzt, werden als versteckte Felder mitgeführt, damit Werte beim Zielwechsel erhalten bleiben.
Die Live-Vorschau (`/baukasten/vorschau`) speichert nichts; erst `/baukasten/erzeugen` speichert.

Optionaler Browser-Test: `pip install playwright` (Chromium-Pfad ggf. per `CHROMIUM_PFAD`),
sonst wird `tests/test_browser.py` übersprungen.

## Ablauf-Bausteine (Kontrollknoten) – Hinweise für Änderungen

- Neue Knotentypen: Klasse in `app/ir.py` + Eingabe in `app/models/request.py` (Tag im
  `Discriminator`) + Zweig in `validation._BaumPruefer` + `emit_<art>` in `generators/base.py`
  + sprachspezifische Methode in allen vier Generatoren + Blockly-Block in `blockly-modus.js`.
- `Feldfehler.schritt` = Position des Knotens in **Vorordnung über alle Knoten** (bei flachen
  Listen = Listenindex). Blockly baut dieselbe Reihenfolge in `serialisieren()` auf.
- Generator-Zustand während `erzeuge()`: `_nr` (Schrittnummer), `_id` (Container-ID für
  Labels/Variablen), `_versuche` (Stack offener „Versuche“), `mit_kontrolle`.
- bash/zsh: Fehler-Handler beachtet `OKM_SCHUTZ` (Rückgabe einer Versuche-Subshell) und
  `OKM_VERSUCH` (in der Subshell nur diese beenden). Roter Abbruch im Versuch = Exit 112.
- CMD: niemals Schritte in `for`/`( … )`-Blöcke packen – nur Sprungmarken.
- Flache Scripte müssen byte-gleich bleiben (Golden-Files).

## Script-Editor (alle Modi)

- Eine Instanz pro Seite (`#script-editor`, `window.OkmEditor`). Zustände `generiert` / `manuell`
  (Text ≠ letzte generierte Fassung) → Banner mit „Neu generieren“ und Diff, einmaliger
  Sicherheitshinweis (`localStorage`).
- Listen-Modus: Der Editor steht **außerhalb** von `#bk-vorschau`; das htmx-Fragment liefert den
  generierten Text in `textarea[data-editor-generiert]` (bzw. `[data-editor-leer]`). Im Zustand
  `manuell` bleibt der bearbeitete Text bei jeder Live-Vorschau stehen. Blockly ruft
  `ScriptEditor.fuer(el).setzeGeneriert(text, ziel, dateiname)`.
- Download/Kopieren immer über `POST /api/script/export` (`manuell_bearbeitet: true` → Kopfzeile
  „Manuell bearbeitet: ja (nicht vom Baukasten geprüft)“). Knöpfe im Ergebnisbereich tragen
  `data-editor-bezug="herunterladen|kopieren"` und nehmen den Editor-Inhalt, wenn er bearbeitet ist.
- Bibliothek: `input[name=editor_text][data-editor-text]` im Speichern-Formular; DB-Spalten
  `editor_text`, `manuell_bearbeitet` (Mini-Migration in `Datenbank._migrieren`). „Erneut öffnen“
  bettet `#editor-vorbelegung` ein.
- „Syntax prüfen“: `POST /api/script/pruefen` – parst nur, meldet fehlende Werkzeuge ehrlich.

## Software-Katalog

- Einzige Datenquelle ist `katalog/software-katalog.yaml` (nicht `data/` – das ist DB/Volume).
  Nichts davon im Frontend hart codieren; Details und Pflege: `docs/software-katalog.md`.
- Alle IDs müssen den Typ `paketname` bestehen (`^[A-Za-z0-9][A-Za-z0-9._+@-]{0,127}$`).
- Eine Komponente: `_katalog.html` mit `katalog_modus` (`seite`, `rezept`, `baukasten`, `blockly`),
  JS `SoftwareKatalog.mount(el, {daten, zielPlattform, onUebernehmen, kannUebernehmen, onMehrfach})`
  mit Adaptern je `data-modus`. Außer auf `/software` steht er eingeklappt unter der Vorschau.
- „＋“ im Listen-Modus ruft `GET /baukasten/schritt?block=paket_installieren&p.paket=…&p.paketmanager=…`
  auf; im Blockly-Modus setzt es die ID im ausgewählten Paket-Block oder legt einen an.
  Paketmanager-Werte = Katalogfelder (`winget`, `brew`, `brew_cask`, `apt`, `flatpak`).
- Daten nur über Textknoten ins DOM (kein `innerHTML`), JSON per `tojson` eingebettet.

## Rechte

| Aktion | nutzer | admin |
|---|---|---|
| Scripte erzeugen, eigene in Bibliothek speichern, „Hat funktioniert“ | ✓ | ✓ |
| Bibliotheks-Scripte ansehen/herunterladen/erneut öffnen | ✓ | ✓ |
| Fremde private Scripte sehen, fremde Einträge entfernen | – | ✓ |
| Rezept vorschlagen / direkt speichern | vorschlagen | speichern |
| Verwaltung: Vorschläge freigeben, DB-Rezepte löschen | – | ✓ |
| Rote Bausteine ohne Checkbox | – | ✓ |

Rezeptfelder heißen im HTML-Formular `f.<feld_id>` (Kollisionsschutz mit `ziel`, `titel` …).

## Oberfläche

- Nur dunkles Design. Farben/Abstände ausschließlich über die Tokens in `:root` von
  `static/css/app.css`; Komponenten-Klassen sind deutsch (`knopf`, `knopf-primaer`, `panel`,
  `hinweis`, `fehlerbox`, `marke`, `risiko-*`, `seitenkopf`, `raster-zwei`, `raster-arbeit`).
- Icons: `{% import "_icons.html" as i %}` und `{{ i.icon("download") }}` (Inline-SVG, CSP-konform).
- Aktiver Menüpunkt wird in `base.html` aus dem URL-Pfad bestimmt.

## Sicherheit (Kurzfassung, Details in `docs/sicherheit.md`)

- PowerShell `'…'` (alle Unicode-Single-Quotes verdoppelt), bash/zsh `'…'` mit `'\''`,
  CMD `"…"` mit `%%`, `"` wird abgelehnt, Delayed Expansion immer aus.
- Steuerzeichen/Zeilenumbrüche/Bidi-Zeichen werden immer abgelehnt.
- CSRF: ändernde Requests brauchen `HX-Request: true` oder `X-Okm-Request: 1`.
- CSP ohne Inline-Scripte → JS nur in `static/js/app.js`.
- Alle Frontend-Bibliotheken liegen unter `static/vendor/` (keine CDNs).
