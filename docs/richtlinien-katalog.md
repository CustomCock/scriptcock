# Richtlinien-Katalog (Administrative Vorlagen / ADMX)

Der Baustein **„Richtlinie setzen“** (`richtlinie_setzen`) setzt Einstellungen aus den offiziellen
Administrativen Vorlagen von Windows, Office, Edge, Chrome und Firefox – mit Titel, Erklärung und
allen Optionen der Richtlinie, so wie sie im Gruppenrichtlinien-Editor (gpedit.msc) erscheinen.
Grundlage ist ein Katalog, der aus den Original-Vorlagen der Hersteller erzeugt und ins Git
eingecheckt wird. Die App lädt zur Laufzeit nichts aus dem Internet.

## Aktueller Stand

<!-- STATISTIK-START -->
| Paket | Version | Richtlinien | ohne deutsche Übersetzung | ausgelassen |
|---|---|---|---|---|
| Windows 11 | 25H2 (Sep 2025 Update) | 3621 | 0 | 0 |
| Microsoft 365 Apps / Office | 5568.1000 | 2420 | 0 | 0 |
| Microsoft Edge | 158.0.4344.0 | 913 | 0 | 0 |
| Google Chrome | Stand 23.10.2026 | 742 | 0 | 0 |
| Mozilla Firefox | 8.4 | 424 | 0 | 0 |

Nicht im Katalog (Vorlagen nicht abgelegt): Microsoft OneDrive, Adobe Acrobat Reader, Zoom Workplace.

Nicht unterstützte Konstrukte (Richtlinie trotzdem im Katalog): clientExtension (29), list mit valueName (3)
<!-- STATISTIK-ENDE -->

Die Tabelle schreibt `tools/admx_katalog.py` bei jedem Lauf neu.

## Aufbau

```
registry/admx-quellen.yaml      offizielle URLs + SHA-256 je Paket, dazu LGPO.exe
        │  tools/admx_holen.py  (Download, Hash-Prüfung, Entpacken)
        ▼
registry/quellen/<paket>/       Rohdaten – NICHT im Git (.gitignore)
        │  tools/admx_katalog.py (app/admx.py: Parser)
        ▼
registry/katalog/<paket>.jsonl  Katalog – im Git, eine Zeile pro Eintrag, sortiert
        │  App-Start (app/richtlinien.py)
        ▼
<data>/richtlinien-<hash>.sqlite  Suchindex (SQLite FTS5) neben der Datenbank, wird bei
                                  geändertem Katalog automatisch neu gebaut
```

- **Richtlinien-ID**: `<paket>:<admx-datei ohne Endung, klein>:<name>`, z. B.
  `edge:msedge:HomepageLocation`. IDs ändern sich nicht, solange der Hersteller den Namen behält –
  gespeicherte Scripte und Rezepte bleiben öffenbar.
- **Kategorien** werden paketübergreifend aufgelöst (`using`-Präfixe, z. B. Office-Kategorien unter
  „Microsoft Office 2016“).
- **Sprache**: Titel und Erklärung aus `de-DE`, sonst `en-US` (dann als „ohne deutsche Übersetzung“
  gezählt).
- **Suche**: klein, Umlaute → ae/oe/ue/ss, Akzente weg, Präfixsuche pro Wort, alle Wörter müssen
  vorkommen. Gewichtet: Titel > Wertname/Schlüssel > Kategoriepfad > Erklärung. Durchsucht werden
  auch die Schlüssel und Wertnamen der Elemente.

## Was der Parser übernimmt

Herstellerdateien gelten als **halb vertrauenswürdig**: Schlüssel, Wertnamen und Daten laufen durch
dieselben Prüfungen wie Benutzereingaben (`app.validation`). Was durchfällt (Steuerzeichen, Schlüssel
mit Wurzel, unbekannte Klasse …), wird ausgelassen und mit Grund in der Statistik gezählt. Beim
Erzeugen des Scripts werden alle Daten **noch einmal** geprüft und einzeln escaped.

| ADMX | im Baukasten |
|---|---|
| `enabledValue`/`disabledValue`, `enabledList`/`disabledList` | Zustand „aktiviert“/„deaktiviert“ |
| nur `valueName`, keine Werte | aktiviert = `REG_DWORD 1`, deaktiviert = `REG_DWORD 0` (*) |
| `boolean` (trueValue/falseValue/Listen) | Ja/Nein |
| `decimal`, `longDecimal` (min/max, `storeAsText`) | Zahl (`REG_DWORD`/`REG_QWORD`/`REG_SZ`) |
| `text` (`maxLength`, `expandable`) | Text (`REG_SZ`/`REG_EXPAND_SZ`) |
| `multiText` (`maxStrings`) | Zeilen (`REG_MULTI_SZ`) |
| `enum` (Wert + `valueList`) | Auswahl |
| `list` (`valuePrefix`, `additive`, `explicitValue`, `expandable`) | Zeilen; bei `explicitValue` als `Name=Wert` |
| `soft="true"` | nur setzen, wenn der Wert noch fehlt |
| Standardwerte aus der Presentation (checkBox, decimalTextBox, dropdownList, textBox) | Standard im Formular |

(*) Das ist das Verhalten des Gruppenrichtlinien-Editors bei Richtlinien ohne eigene Werte; in der
Protokollspezifikation [MS-GPREG] ist es nicht ausdrücklich beschrieben. Steht in `docs/offene-punkte.md`.

**Nicht unterstützt** (Richtlinie bleibt im Katalog, das Konstrukt wird ignoriert und gezählt):
`clientExtension` (eine Gruppenrichtlinien-Erweiterung müsste zusätzlich laufen) und `list` mit
eigenem `valueName`.

## Zustände

| Zustand | Wirkung |
|---|---|
| aktiviert | enabledValue/enabledList + alle Elemente. Nicht-additive Listen werden vorher geleert (wie `**delvals.` in Registry.pol). |
| deaktiviert | disabledValue/disabledList; Elementwerte und Werte der enabledList werden gelöscht. |
| nicht konfiguriert | alle Werte, die die Richtlinie schreiben kann, löschen; danach leere Schlüssel entfernen (tiefste zuerst). |

Elementwerte werden nur im Zustand „aktiviert“ geprüft.

## Methoden

- **Registry direkt** (Standard): `Set-OkmRegistryWert` usw. mit Sicherung als `.reg` (Rückgängig-Ordner).
  Wirkt sofort, ist aber in gpedit.msc nicht sichtbar. Eine Domänen-Gruppenrichtlinie überschreibt den Wert.
- **Lokale Gruppenrichtlinie**: schreibt über `LGPO.exe /t` in die lokale Richtlinie (sichtbar in
  gpedit.msc). Davor muss **„Admin-Werkzeug bereitstellen“ (LGPO)** stehen. Vor der ersten Änderung
  wird die lokale Richtlinie mit `LGPO.exe /b` gesichert; der Pfad steht in der Zusammenfassung.

**Benutzer-Richtlinien**: Bereich wie bei den Registry-Bausteinen (angemeldeter Benutzer, alle
Benutzer, Standardprofil). Computer-Richtlinien gelten immer für den Computer; ein falscher Bereich ist
ein Validierungsfehler.

**Anwenden**: Bei Computer-Richtlinien läuft am Script-Ende einmal `gpupdate /target:computer`.
Bei Benutzer-Richtlinien nicht – das Script läuft als Administrator, gpupdate träfe dessen Profil.
Stattdessen meldet die Zusammenfassung „neu anmelden“.

**Risiko**: Der Baustein ist gelb. Der Teil `Policies` der Schutzliste (`registry/schutz.yaml`) zählt
hier nicht als Rot-Grund – das ist der Normalfall jeder Richtlinie. Schreibt eine Richtlinie nach
`HKLM\SYSTEM`, Winlogon oder `…\Lsa`, wird der Schritt rot; gesperrte Bereiche bleiben gesperrt.

## Admin-Werkzeug bereitstellen

`admin_werkzeug_bereitstellen` lädt **LGPO.exe**, die **Vorlagen** eines Pakets (damit die
Einstellungen in gpedit.msc erscheinen) oder installiert die **Software**, falls sie fehlt (winget).

- Jede Datei wird gegen den SHA-256 aus `registry/admx-quellen.yaml` geprüft; bei LGPO zusätzlich die
  `LGPO.exe` im ZIP. Weicht ein Hash ab, bricht der Schritt ab – nichts Ungeprüftes wird ausgeführt.
- **Quelle Intranet**: Die App liefert unter `GET /werkzeuge/<id>/<datei>` genau die Original-Dateien
  aus (gleiche Namen, gleicher Hash), abgelegt von `tools/admx_holen.py` in
  `registry/quellen/<id>/download/`. Ausgeliefert wird nur, was in der YAML steht. Die Adresse, unter der
  Windows-Rechner die App erreichen, kommt aus `OKM_WERKZEUG_URL`; fehlt sie, ist „Intranet“ ein
  Validierungsfehler.
- **Quelle Hersteller**: offizielle Download-URL aus der YAML.
- Werkzeuge landen unter `C:\ProgramData\okm\werkzeuge\<Name>\<Version>\`; ist die richtige Version
  schon da, wird nichts geladen.
- Vorlagen gehen nach `C:\Windows\PolicyDefinitions`. Vorhandene **neuere** Vorlagen (Attribut
  `revision`) bleiben, ältere werden vorher gesichert.
- **Central Store** (`\\<Domäne>\SYSVOL\<Domäne>\Policies\PolicyDefinitions`) wirkt auf alle Rechner der
  Domäne → roter Schritt.

## Aktualisieren (monatlich oder bei neuer Version)

1. Herstellerseite (`seite` in `registry/admx-quellen.yaml`) öffnen, neue Version suchen.
   Bei Edge liefert die offizielle Produktliste `https://edgeupdates.microsoft.com/api/products?view=enterprise`
   URL **und** SHA-256 der Policy-CAB.
2. `version`, `url` eintragen, `sha256` leeren und `python tools/admx_holen.py <paket> --erster-download`
   ausführen – das Script zeigt den berechneten Hash. Nur übernehmen, wenn die URL von der offiziellen
   Seite stammt (bei Edge: Hash mit der Produktliste vergleichen).
3. `python tools/admx_holen.py` (alle Pakete, prüft alle Hashes) und `python tools/admx_katalog.py`.
4. `git diff registry/katalog/` ansehen: weggefallene IDs betreffen gespeicherte Scripte/Rezepte
   (die Validierung meldet dann „gibt es im Katalog nicht (mehr)“).
5. `pytest -q`, CHANGELOG ergänzen, committen.

Ohne Netz oder bei Paketen mit `format: manuell` (OneDrive, Adobe Reader, Zoom): die Dateien von Hand
nach `registry/quellen/<id>/admx/` (ADML in `de-DE/` bzw. `en-US/`) legen und Schritt 3 ausführen.

Werkzeuge zum Entpacken: `msiextract` (msitools) für Windows, `cabextract` für Edge und Office,
sonst `7z`. Fehlt eins, meldet `admx_holen.py` das.

## Tests

`tests/test_richtlinien.py` arbeitet nur mit eigenen Vorlagen aus `tests/daten/admx/` (alle
Element-Arten, UTF-16, paketübergreifende Kategorie, ungültige Einträge) – keine Herstellerdateien.
