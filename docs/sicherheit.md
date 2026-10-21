# Sicherheitskonzept

Der Script-Baukasten erzeugt Code, den Mitarbeiter auf ihren Rechnern – oft mit
Administratorrechten – ausführen. Ein einziger Fehler beim Einbauen von Eingaben
würde aus einem harmlosen Formular ein Werkzeug für Code-Injection machen. Deshalb gilt:
**Benutzereingaben landen niemals roh in einem Script.**

## 1. Zwei Verteidigungslinien

1. **Whitelist-Validierung** (`app/validation.py`): Jeder Parameter hat einen Typ
   (`ipv4`, `dienstname`, `pfad_windows`, …). Nur Werte, die genau zu diesem Typ passen,
   werden angenommen und normalisiert. Ein Dienstname kann z. B. gar kein `;` oder
   Leerzeichen enthalten. Zusätzlich gilt für alle Typen:
   - Steuerzeichen, Zeilenumbrüche, NUL, Unicode-Zeilentrenner und Bidi-Steuerzeichen
     („Trojan Source“) werden abgelehnt.
   - Werte dürfen nicht mit `-` beginnen – sonst könnten Programme sie als Option lesen
     (Option-Injection, z. B. ein „Dateiname“ `-rf`), obwohl sie korrekt gequotet sind.
2. **Escaping pro Zielsprache** (`app/escaping.py`): Auch ein gültiger Wert wird immer als
   vollständiges, sicheres Literal der Zielsprache eingesetzt.

Beide Linien sind unabhängig voneinander getestet: Die Escaping-Tests verwenden
Injection-Payloads, die die Validierung nie durchlassen würde.

## 2. Escaping je Zielsprache

| Ziel | Form | Regel |
|---|---|---|
| PowerShell | `'wert'` | Jedes Single-Quote-Zeichen wird verdoppelt – **auch** die Unicode-Varianten `‘ ’ ‚ ‛`, die PowerShell ebenfalls als Quote behandelt. Nie Double Quotes (dort würde `$()` expandiert). |
| bash / zsh | `'wert'` | `'` → `'\''`. In Single Quotes ist sonst nichts besonders. Kein `eval`, keine Backticks. |
| CMD | `"wert"` | Innerhalb von `"…"` sind `^ & \| < > ( )` wörtlich. `%` → `%%`. `!` ist wörtlich, weil jedes Script `DisableDelayedExpansion` setzt. **`"` wird abgelehnt** – es gibt kein sicheres Escaping. Abschließende `\` werden verdoppelt (sonst würde `"C:\"` bei vielen Programmen das Quote escapen). |

Zahlen (`zahl`, `port`) werden nach der Validierung als reine Ziffernfolge eingesetzt,
`ja_nein` als Sprach-Bool (`$true`, `1`, `true`).

Fortschrittsmeldungen und Simulationsausgaben enthalten Eingaben und werden darum als
Ganzes für den Ausgabekontext escaped (`Write-Host '…'`, `printf '%s\n' '…'`, bzw. in
CMD `echo(` mit `^` vor jedem Sonderzeichen). Der Kopfkommentar verwendet nur
Zeilenkommentare; in CMD werden Sonderzeichen in `rem`-Zeilen ersetzt, weil `%`-Expansion
und ein `^` am Zeilenende dort sonst greifen würden.

## 3. Warum Eingaben nie roh in Templates landen können

Block-Templates sind Jinja2-Templates, aber in einer **eigenen** Umgebung
(`app/codeenv.py`):

- `autoescape=False` – HTML-Escaping wäre für Shell-Code falsch und gefährlich
  (es würde nur `<>&"'` behandeln, nicht `$`, `` ` ``, `%`).
- Ein `finalize`-Hook lässt in `{{ … }}` **ausschließlich** Objekte vom Typ `Escaped`
  durch. Diese erzeugt nur `escaping.py`. Ein roher String, eine Zahl, eine Konstante,
  das Ergebnis eines Filters oder einer Verkettung (`{{ x ~ 'a' }}`) führt sofort zu
  einem Fehler. Ein vergessenes Escaping ist damit kein stiller Fehler, sondern
  unmöglich.
- Der Rohwert ist als `x.wert` nur für Bedingungen nutzbar (`{% if x.wert == 'apt' %}`),
  er kann nicht ausgegeben werden.
- Sandbox, `StrictUndefined`, keine Filter.

Die Registry prüft beim Start zusätzlich jedes Template:

- nur deklarierte Platzhalter,
- kein Platzhalter innerhalb von Anführungszeichen (sonst würde das Quoting doppelt bzw. aufgebrochen),
- sprachspezifische Verbote: `eval`, Backticks, `Invoke-Expression`, `%ERRORLEVEL%`,
  `EnableDelayedExpansion`, `call` mit Platzhaltern (würde `%` erneut expandieren),
  `goto`/`exit` (der Generator steuert den Ablauf), unausgeglichene Klammern in CMD.

Generatoren arbeiten nur auf der IR, die ausschließlich aus validierten Werten besteht.
Auch eine aus der Datenbank geladene IR (Phase 3) oder eine LLM-Ausgabe (Phase 5) läuft
erneut durch dieselbe Validierung.

## 4. Risikostufen

| Stufe | Bedeutung | Verhalten |
|---|---|---|
| `gruen` | nur lesen | normal |
| `gelb` | ändert etwas | Hinweis in der UI |
| `rot` | löscht / destruktiv | UI-Checkbox „Ich weiß, was dieses Script tut“ (Admins ausgenommen) **und** im Script vor dem Schritt eine Abfrage, bei der „JA“ (Großbuchstaben) getippt werden muss. Alles andere bricht ab (Exit-Code 2). |

## 5. Weitere Schutzmaßnahmen im Script

- **Admin-Prüfung** am Anfang, wenn ein Block Adminrechte braucht – das Script bricht
  verständlich ab, statt halb durchzulaufen.
- **Fehlerabbruch**: `set -Eeuo pipefail` + `trap ERR` (bash), `ERR_EXIT NO_UNSET PIPE_FAIL`
  (zsh), `$ErrorActionPreference='Stop'` + `try/catch` je Schritt + `$LASTEXITCODE` (PowerShell),
  `if errorlevel 1` / `if not errorlevel 0` je Schritt (CMD).
- **Dry-Run**: PowerShell nutzt `-WhatIf`, wo das Template es vorsieht; sonst wird jede Zeile
  eines gelben/roten Blocks zu einer Ausgabe „[SIMULATION] würde ausführen: …“.
- **Protokoll** jedes Laufs (`%TEMP%` bzw. `/tmp`), Pfad wird am Ende ausgegeben.
- **SHA-256** jedes erzeugten Scripts wird gespeichert und angezeigt.

## 6. Webanwendung

- Login per OIDC (Keycloak), optional auf eine Gruppe beschränkt. `AUTH_DISABLED=true`
  nur für die Entwicklung – die UI zeigt dann ein rotes Banner.
- CSRF-Schutz: ändernde Requests müssen den Header `HX-Request: true` (htmx) oder
  `X-Okm-Request: 1` (fetch) tragen; fremde Seiten können diese ohne CORS-Freigabe nicht setzen.
  Zusätzlich `SameSite=Lax`-Cookies.
- Content-Security-Policy ohne Inline-Scripte, `frame-ancestors 'none'`.
- Downloads nur für den Ersteller (bzw. Admins / freigegebene Bibliotheks-Scripte).
- Keine CDNs: alle Bibliotheken liegen unter `static/vendor/`.

## 7. Blockly-Modus

Blockly erzeugt **keinen** Code. Die Arbeitsfläche wird nur in die Schrittliste (JSON) übersetzt,
die das Backend genauso validiert, escaped und generiert wie in den anderen Modi. Die einzige
Ausnahme von der strengen CSP: Auf `/blockly` ist `style-src 'unsafe-inline'` erlaubt, weil
Blockly seine SVG-Darstellung mit Inline-Styles aufbaut. `script-src` bleibt `'self'`; die
Seitendaten liegen in einem `<script type="application/json">`-Block (wird nicht ausgeführt).

## 8. Tests

- `tests/test_escaping.py`: Injection-Payloads (`test"; Remove-Item C:\ -Recurse; "`,
  `$(rm -rf ~)`, `` `whoami` ``, `a & del /q *`, `%PATH%`, `'; drop`, Unicode-Quotes, …).
  bash, zsh und PowerShell werden **echt ausgeführt**: Das Literal muss exakt den Payload
  ausgeben, und eine Kanarien-Datei darf nicht entstehen. CMD wird gegen ein Modell der
  Batch-Verarbeitung geprüft.
- `tests/test_codeenv.py`: Rohwerte, Konstanten, Filter, Verkettungen werden abgelehnt.
- `tests/test_ausfuehrung.py`: Erzeugte bash-/zsh-Scripte werden mit Payloads in Pfaden
  ausgeführt – die Verzeichnisse entstehen mit wörtlichem Namen, nichts wird ausgeführt.
