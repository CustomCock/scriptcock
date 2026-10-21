# Offene Punkte

Befehle, die noch nicht auf echten Systemen verifiziert sind, und bewusste Lücken.
Vor dem produktiven Einsatz auf den Test-VMs prüfen (`docs/test-vms.md`).

## Auf echten Systemen zu verifizieren

| Block | Ziel | Punkt |
|---|---|---|
| `systeminfo` | cmd | `systeminfo \| findstr` filtert nach deutschen **und** englischen Feldnamen. Auf deutschem Windows 11 prüfen, ob „Verfügbarer physischer Speicher“ (Suchwort `Verf`) unter `chcp 65001` gefunden wird. |
| `drucker_ip` | powershell | Standardtreiber „Microsoft IPP Class Driver“ zusammen mit einem Standard-TCP/IP-Port prüfen. Für Drucker ohne IPP ggf. „Microsoft PCL6 Class Driver“ als Auswahl anbieten. |
| `drucker_ip` | bash/zsh | `lpadmin -m everywhere` braucht einen IPP-Everywhere-fähigen Drucker unter `ipp://<ip>/ipp/print`. Bei älteren Druckern schlägt das fehl. |
| `dienst_status` | zsh | `launchctl print system/<label>` – prüfen, ob ohne root genug Informationen kommen und ob das grep-Muster auf aktuellem macOS passt. |
| `dienst_neustarten` | zsh | Keine `pruefung` hinterlegt (unklar, wie zuverlässig der Status nach `kickstart` gelesen werden kann). |
| `benutzer_anlegen` | cmd | Administratorgruppe heißt je nach Sprache „Administratoren“/„Administrators“; andere Sprachen werden nicht abgedeckt. PowerShell nutzt die sprachunabhängige SID. |
| `benutzer_anlegen` | zsh | `sysadminctl` liefert teils Exit-Code 0 trotz Fehler; daher folgt `id <name>` als Kontrolle. SecureToken/FileVault-Freischaltung ist nicht abgedeckt. |
| `festplattenbelegung` | cmd | `fsutil volume diskfree` braucht Adminrechte; Netzlaufwerke/CD-Laufwerke liefern Fehler, die ignoriert werden. |
| `windows_update_reset` | cmd | Fehler einzelner `net stop`/`ren`-Befehle werden nicht einzeln ausgewertet; Erfolg wird am Ende nur am umbenannten SoftwareDistribution-Ordner festgemacht. |
| `prozess_beenden` | bash | `pkill -x` vergleicht mit dem Prozessnamen, der unter Linux auf 15 Zeichen gekürzt ist. |
| `paket_installieren` | powershell/cmd | winget meldet „bereits installiert“ mit einem Fehlercode – der Schritt gilt dann als fehlgeschlagen. Ggf. `winget list --id` vorschalten. |
| `traceroute` | bash | Weder `traceroute` noch `tracepath` sind auf Debian standardmäßig installiert; der Block meldet das nur. |
| `temp_aufraeumen` | cmd | `forfiles` meldet „keine Dateien gefunden“ als Fehler; der Block setzt den Fehlercode daher immer auf 0 und kann echte Fehler nicht erkennen. |
| alle | cmd | Ausgaben eines Schritts erscheinen erst nach seinem Ende (Umleitung in eine Temp-Datei, weil CMD kein `tee` hat). Interaktive Blöcke (`interaktiv: true`) laufen ohne Umleitung und werden daher nicht vollständig protokolliert. |
| alle | powershell | Native Programme, die Fehler über stderr melden, aber Exit-Code 0 liefern, werden nicht als Fehler erkannt. |

## Bewusst nicht umgesetzt

- **Port erreichbar prüfen** und **Drucker per IP** gibt es für CMD nicht (kein Bordmittel ohne PowerShell).
- **Netzlaufwerk** gibt es für Linux nicht (abhängig von Desktop/fstab/cifs-utils).
- Die macOS-Blöcke sind ohne Mac-Testgerät nur per `zsh -n` geprüft.

## Freier Baukasten

- SortableJS setzt beim Ziehen ein leeres `style`-Attribut, das die CSP (`style-src 'self'`)
  blockiert. Das erzeugt nur eine Konsolenmeldung, die Funktion ist nicht betroffen.
- Rezepte aus „Als Rezept speichern“ liegen nur in der Datenbank. Zum dauerhaften Übernehmen
  ins Repository den YAML-Export unter `recipes/` ablegen (dann den DB-Eintrag löschen, sonst
  existiert das Rezept doppelt mit unterschiedlicher ID).
- Gespeicherte Rezepte können gelöscht, aber nicht bearbeitet werden (Workaround: im Baukasten
  neu zusammenstellen und erneut speichern).
- Der Browser-Test (`tests/test_browser.py`) läuft in der CI nicht, weil Playwright keine
  Projektabhängigkeit ist.

## Bibliothek & Verwaltung

- Freigegebene DB-Rezepte liegen im Speicher der Registry. Mit mehreren uvicorn-Workern
  (`--workers N`) sähen andere Prozesse eine Freigabe erst nach einem Neustart. Die mitgelieferte
  systemd-Unit startet daher genau einen Prozess.
- Titel/Beschreibung in der Bibliothek sind reine Metadaten; der Kopfkommentar des Scripts
  behält den Titel von der Erzeugung.
- Es gibt keine Datenbank-Migrationen (Alembic). Neue Tabellen legt die App selbst an; neue
  Spalten in bestehenden Tabellen bräuchten künftig eine Migration.

## Phasen

- Phase 4 (Blockly) ist noch nicht umgesetzt (siehe `CHANGELOG.md`).
