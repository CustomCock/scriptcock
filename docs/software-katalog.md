# Software-Katalog

Der Software-Katalog listet Paket-IDs für **winget** (Windows), **Homebrew** (macOS) sowie
**apt** und **Flatpak** (Linux). Mitarbeiter finden ihn

- als eigene Seite unter **Software** (`/software`) – zum Nachschlagen und Kopieren,
- in **Rezepten**, im **Baukasten** und in **Blockly** als einklappbarer Abschnitt rechts direkt
  unter der Vorschau (auf schmalen Bildschirmen unter der Vorschau). Er klappt von selbst auf,
  sobald ein Feld „Paketname“ fokussiert oder ein Schritt „Paket installieren“ hinzugefügt bzw.
  (Blockly) ausgewählt wird. Dort übernimmt **＋** eine ID ins Script.

Technisch ist es **eine** Komponente: das Partial `app/templates/_katalog.html` und
`SoftwareKatalog.mount(element, optionen)` in `static/js/software-katalog.js`. Kleine Adapter
am Ende der Datei verbinden sie mit der jeweiligen Seite (`data-modus` = `seite`, `rezept`,
`baukasten`, `blockly`).

Einzige Datenquelle ist [`katalog/software-katalog.yaml`](../katalog/software-katalog.yaml).
Die Oberfläche wird komplett daraus erzeugt; ist die Datei fehlerhaft, startet die Anwendung
nicht und nennt Eintrag und Feld (wie bei Bausteinen).

> Die Datei liegt bewusst unter `katalog/` und nicht unter `data/`: `data/` ist der
> Datenbank-Ordner (in `.gitignore`, im Docker-Betrieb ein Volume, das die Datei verdecken würde).

## Bedienung

| Aktion | So geht's |
|---|---|
| Suchen | Tippen genügt (Name, Beschreibung, Kategorie, Suchbegriffe **und** alle Paket-IDs). Mehrere Wörter müssen alle vorkommen. Groß-/Kleinschreibung, Umlaute (`loeschen` = `löschen`) sowie `- . _` und Leerzeichen sind egal (`7zip` findet „7-Zip“). |
| Plattform | Windows · macOS · Linux · Alle. Im Baukasten/Rezept folgt der Filter dem Zielsystem. |
| Kategorien | Aufklappen und Chips anklicken (Mehrfachauswahl). Auswahl und Plattform merkt sich der Browser. |
| ⧉ | kopiert **nur die ID** (funktioniert auch über HTTP – dann mit Fallback; klappt gar nichts, wird die ID markiert: Strg+C). |
| ▾ | kopiert den kompletten Installationsbefehl (z. B. `winget install --id … -e --source winget …`). |
| ＋ | Baukasten: hängt einen Schritt „Paket/Software installieren“ mit ID und passendem Paketmanager an. War vorher ein Feld „Paketname“ aktiv, wird nur dieses Feld befüllt. Rezept: befüllt das Feld „Paketname“. Blockly: ist ein „Paket installieren“-Baustein ausgewählt, bekommt er die ID; sonst wird ein neuer Baustein unter dem ausgewählten (bzw. am Ende des Scripts) angelegt. |
| Checkboxen | Baukasten: mehrere Programme wählen → „Ausgewählte installieren (n)“ legt je einen Schritt an – das eigene „Standardsoftware-Paket“. |
| Tastatur | `/` klappt den Katalog auf und fokussiert die Suche · `↑` `↓` wählen einen Treffer · `Enter` kopiert dessen ID · `Esc` leert die Suche. |

## Eintrag ergänzen

Neue Software kann jeder per Pull-Request ergänzen:

```yaml
  - name: "7-Zip"
    kategorie: "Packprogramme"          # vorhandene Kategorie nehmen, wenn möglich
    beschreibung: "Packprogramm für zip, 7z, rar"
    suchbegriffe: ["zip", "archiv", "entpacken"]
    winget: "7zip.7zip"                 # Windows
    brew: "sevenzip"                    # macOS, Homebrew-Formel  → brew install sevenzip
    brew_cask: ""                       # macOS, Homebrew-Cask    → brew install --cask <id>
    apt: "7zip"                         # Debian/Ubuntu (geprüft gegen Ubuntu 24.04 main+universe)
    flatpak: ""                         # Flathub
    hinweis: ""                         # optional, z. B. „Lizenz nötig“
    hersteller_url: ""                  # optional, für Software ohne Paket-ID
    intern: ""                          # optional, UNC-Pfad zum Installer auf dem okm-Fileserver
```

Regeln (prüft die Anwendung beim Start und `pytest`):

- `name`, `kategorie`, `beschreibung` sind Pflicht; leere Felder dürfen fehlen.
- Mindestens eine Paket-ID **oder** `hersteller_url`/`intern`.
- Keine ID doppelt pro Plattform (winget ohne Rücksicht auf Groß-/Kleinschreibung).
- IDs: Buchstaben, Ziffern und `. _ + @ -`, beginnend mit Buchstabe/Ziffer (max. 128 Zeichen).
- Software aus Fremdquellen (Docker CE, VS Code, Azure CLI, VirtualBox …) **nicht** als apt-Paket
  eintragen – dafür muss erst ein Hersteller-Repository eingebunden werden.
- Gibt es ein Paket nur unter Ubuntu oder heißt es unter Debian anders: `hinweis` setzen.

### Die richtige ID finden

| Plattform | Befehl | Feld |
|---|---|---|
| Windows | `winget search firefox` → Spalte **ID** | `winget` |
| macOS | `brew search firefox` → unter „Formulae“ = `brew`, unter „Casks“ = `brew_cask` | `brew` / `brew_cask` |
| Linux | `apt search firefox` bzw. `apt show <name>` (Ubuntu 24.04) | `apt` |
| Linux | `flatpak search firefox` → Spalte **Application ID** | `flatpak` |

Alternativ im Browser: winget.run bzw. github.com/microsoft/winget-pkgs, formulae.brew.sh,
packages.ubuntu.com, flathub.org.

## IDs regelmäßig prüfen

Paket-IDs ändern sich (Umbenennungen, Pakete verschwinden, Flathub-Apps werden abgekündigt).

```bash
python tools/katalog_pruefen.py                  # alle Quellen (braucht Netz und git)
python tools/katalog_pruefen.py --nur winget,brew
python tools/katalog_pruefen.py --aktualisieren  # bei Erfolg geprueft_am auf heute setzen → committen
```

Das Script prüft gegen den Verzeichnisbaum von `microsoft/winget-pkgs`, `Homebrew/homebrew-core`
und `homebrew-cask` (blobless Clone, nur `git ls-tree`), den `Packages`-Index von Ubuntu 24.04
und Debian Stable sowie die Flathub-API (ersatzweise die Repositories unter `github.com/flathub`).
Ungültige IDs werden mit ähnlichen Treffern bzw. der Homebrew-Umbenennung gemeldet,
abgekündigte Flathub-Apps als „EOL“. Exit-Code 1 = ungültige IDs, 2 = Quelle nicht erreichbar.

Der GitHub-Workflow [`katalog-pruefen.yml`](../.github/workflows/katalog-pruefen.yml) läuft am
1. jedes Monats (und per Hand) und legt bei Fehlern ein Issue an bzw. ergänzt das offene.
Im normalen CI läuft nur die Offline-Prüfung (`tests/test_katalog.py`: Schema, Duplikate,
Validierung und Escaping aller IDs, Syntax-Checks der damit erzeugten Scripte).
