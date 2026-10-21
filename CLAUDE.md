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
```

Syntax-Checks in den Tests brauchen `bash`, `zsh`, `shellcheck`, `pwsh` (+ Modul
`PSScriptAnalyzer`). Fehlt ein Werkzeug, wird der Test mit Hinweis übersprungen; die
GitHub-CI installiert alle.

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
| `app/service.py` | Rezept-Formular → Request, `generiere` (ohne Speichern) / `erzeuge` (mit Speichern) |
| `app/baukasten.py` | Listen-Modus: Formular lesen, Rezept aus Schrittliste; DB-Rezepte vorschlagen/freigeben/laden/YAML |
| `app/bibliothek.py` | Bibliothek: Rechte, Suche, Tags, Bewertungen, „Erneut öffnen“ aus der IR, Blockversionen |
| `app/routes/pages.py`, `baukasten.py`, `bibliothek.py`, `verwaltung.py`, `api.py` | HTML-Seiten je Bereich, JSON-API |
| `app/routes/blockly.py`, `static/js/blockly-modus.js` | Blockly-Modus: Katalog → Toolbox, Arbeitsfläche → JSON (kein Code!) |
| `static/js/app.js` | Gemeinsames JS (Highlighting, Zwischenablage, Listen-Modus: Sortable, Palette) |
| `app/auth.py` | OIDC (Keycloak), Rollen `nutzer`/`admin`, `AUTH_DISABLED` |

## Konventionen

- **Nie** Benutzereingaben roh in Code. Templates bekommen nur `Escaped`; Platzhalter stehen
  **nie** in Quotes (`-Name {{ dienst }}`, nicht `'{{ dienst }}'`) – die Registry prüft das.
- Neue Parametertypen: Whitelist in `validation.py` + Tests in `tests/test_validation.py`.
  Werte dürfen nicht mit `-` beginnen (Option-Injection).
- Neue Blöcke: nur YAML (`docs/neuen-block-anlegen.md`). Jeder Pflichtparameter braucht `beispiel`/`standard`.
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

## Sicherheit (Kurzfassung, Details in `docs/sicherheit.md`)

- PowerShell `'…'` (alle Unicode-Single-Quotes verdoppelt), bash/zsh `'…'` mit `'\''`,
  CMD `"…"` mit `%%`, `"` wird abgelehnt, Delayed Expansion immer aus.
- Steuerzeichen/Zeilenumbrüche/Bidi-Zeichen werden immer abgelehnt.
- CSRF: ändernde Requests brauchen `HX-Request: true` oder `X-Okm-Request: 1`.
- CSP ohne Inline-Scripte → JS nur in `static/js/app.js`.
- Alle Frontend-Bibliotheken liegen unter `static/vendor/` (keine CDNs).
