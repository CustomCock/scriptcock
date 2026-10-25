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
| `virenschutz_status`, `sicherheits_schnellcheck` | powershell | Auswertung von `productState` (SecurityCenter2) ist nicht offiziell dokumentiert (Byte 2 = aktiv, Byte 3 = Signaturen). Mit Defender **und** ESET prüfen. |
| `office_version` | powershell | Zuordnung Kanal-GUID → Name; je nach Installation steht der Kanal in `UpdateChannel` oder nur in `CDNBaseUrl`. |
| `teams_cache_leeren` | powershell | Cache-Pfad des neuen Teams (`MSTeams_8wekyb3d8bbwe`) auf aktuellem Client prüfen. |
| `onedrive_reset` | powershell | Prüft drei typische Installationspfade; Firmen-Installationen „pro Computer“ ggf. an anderem Ort. |
| `boot_dauer` | powershell | Startdauer aus `Properties[5]` von Ereignis 100 (Diagnostics-Performance) – Index prüfen. |
| `fehlgeschlagene_anmeldungen` | powershell/bash | Feld-Indizes von Ereignis 4625 (5 = Konto, 10 = Anmeldetyp, 19 = IP); Linux braucht persistentes Journal bzw. sshd-Meldungen im Journal. |
| `dism_sfc` | powershell/cmd | `sfc` schreibt umgeleitet UTF-16: PowerShell liest die Ausgabe dafür kurz als UTF-16, CMD führt den Schritt ohne Umleitung aus (Ausgabe dann nicht im Protokoll). Auf Win 11 prüfen. |
| `update_status` | powershell | Die COM-Suche nach Updates dauert mitunter Minuten und folgt WSUS, falls konfiguriert. |
| `winget_upgrade_alle` | powershell/cmd | winget ist im SYSTEM-Kontext (z. B. Fernwartung als Dienst) nicht verfügbar. |
| `support_infos` | cmd | Keine Seriennummer (wmic ist abgekündigt). AnyDesk-ID nur bei Standard-Installation unter `ProgramData`. |
| `bildschirm_sperren` | bash/zsh | `loginctl lock-session` funktioniert nur in einer grafischen Sitzung; macOS sperrt nur bei passender Einstellung. |
| `benutzer_deaktivieren`, `passwort_zuruecksetzen` | zsh | `pwpolicy -disableuser` bzw. `dscl . -passwd` auf aktuellem macOS prüfen (SecureToken/FileVault). |
| `energieplan` | powershell/cmd | Modern-Standby-Geräte haben nur „Ausbalanciert“ – `/setactive` schlägt dann fehl. |
| `smart_status` | zsh | Zeigt nur `disk0`. |
| `neustart_countdown` | bash | `shutdown -r +N` – Meldung erscheint nur in Terminal-Sitzungen (wall). |
| alle | cmd | Ausgaben eines Schritts erscheinen erst nach seinem Ende (Umleitung in eine Temp-Datei, weil CMD kein `tee` hat). Interaktive Blöcke (`interaktiv: true`) laufen ohne Umleitung und werden daher nicht vollständig protokolliert. |
| alle | powershell | Native Programme, die Fehler über stderr melden, aber Exit-Code 0 liefern, werden nicht als Fehler erkannt. |
| `ping` | cmd | `ping.exe` meldet „Zielhost nicht erreichbar“ (Antwort eines Routers) mit Exit-Code 0. PowerShell prüft daher zusätzlich auf `TTL=`; CMD wertet nur den Exit-Code aus. Die Laufzeit (`ms`) gibt es unter CMD nicht (Ausgabe sprachabhängig). |
| `dienst_status` | cmd | `laeuft` sucht `RUNNING` in der Ausgabe von `sc query` – prüfen, ob das auf deutschem Windows englisch bleibt. |
| `verschieben` | cmd | `move` verschiebt Ordner nur innerhalb desselben Laufwerks. |
| `loeschen`, `alte_dateien_loeschen` | cmd | Schutzliste in CMD nur Laufwerkswurzel, `%SystemRoot%`, `%ProgramFiles%`, `%USERPROFILE%` (PowerShell und bash/zsh schützen mehr). `del` meldet manche Fehler nicht über den Errorlevel. |
| `alte_dateien_loeschen` | cmd | `forfiles` liefert keine Anzahl (keine Rückgabe `anzahl` unter CMD). |
| `datei_backup` | cmd | Zeitstempel über einen kurzen PowerShell-Aufruf; Zielordner-Option gibt es unter CMD nicht. |
| `rechner_umbenennen` | powershell/cmd | In einer Domäne braucht `Rename-Computer` Domänen-Anmeldedaten – dann schlägt der Schritt mit Meldung fehl. |
| `zeit_sync` | bash | Nutzt `chronyc makestep`, sonst `timedatectl set-ntp` + Neustart von `systemd-timesyncd`; andere NTP-Dienste (ntpd) nicht abgedeckt. |
| `zeit_sync`, `zeitzone_setzen`, `rechner_umbenennen` | zsh | `sntp`, `systemsetup`, `scutil` nur mit Attrappen getestet. |
| `dns_abfrage` | powershell/cmd | `Resolve-DnsName` gibt es unter Linux nicht – nur Syntax geprüft. CMD (`nslookup`) liefert keinen Rückgabewert. |
| `http_check` | cmd | Nutzt `curl.exe` (ab Windows 10 1803); kein Statuscode als Rückgabe, nur „erreichbar“. Proxy-Einstellungen des Systems werden nicht übernommen. |
| `ports_pruefen` | cmd | Gibt es für CMD nicht (kein Bordmittel). |
| `wake_on_lan` | bash/zsh | Ohne `wakeonlan` wird python3 gebraucht (auf macOS nicht immer installiert). |
| `msi_installieren`, `exe_installieren`, `treiber_installieren`, `treiber_entfernen`, `drucker_server_verbinden` | powershell/cmd | Nur unter Windows ausführbar – unter Linux nur Text/Syntax geprüft. Exit-Codes (3010, 1641, 259) auf Win 11 bestätigen. |
| `exe_installieren` | powershell/cmd | Nur vier feste Silent-Profile; Installer mit eigenen Schaltern (z. B. Lizenzschlüssel) gehen bewusst nicht. CMD-Profil InstallShield (`/v"/qn …"`) auf echtem Setup prüfen. |
| `drucker_server_verbinden` | bash/zsh | Gibt es nur für Windows (CUPS/SMB-Drucker brauchen Anmeldedaten und Treiberwahl). Point-and-Print-Richtlinie kann die Treiberinstallation ohne Admin verhindern. |
| `software_version` | cmd | Gibt es für CMD nicht. macOS sucht nur unter `/Applications`; Windows nur Einträge mit DisplayVersion. |
| `eventlog_export` | cmd | Exportiert das ganze Protokoll (ohne Zeitraum) als `okm-ereignisse.evtx`. |
| `logdatei_ende` | powershell | Liest mit der Standard-Codierung von PowerShell 5.1 – UTF-8-Logs ohne BOM können Umlaute falsch zeigen. |
| `neustart_herunterfahren`, `neustart_abbrechen` | alle | Nur mit Attrappen getestet. macOS: `shutdown` kennt nur Minuten; Abbrechen beendet den wartenden `shutdown`-Prozess (`pkill`). Windows: `shutdown /a` hält von Windows Update geplante Neustarts nicht dauerhaft auf. |
| `wiederherstellungspunkt` | powershell/cmd | Auf Win 11 prüfen: Verhalten bei abgeschaltetem Computerschutz und bei der 24-Stunden-Sperre; Server-Windows hat keine Wiederherstellungspunkte. CMD liefert keine Rückgabe `erstellt`. |
| `chkdsk_planen` | powershell/cmd | `fsutil dirty set` auf Win 11 bestätigen (Prüfung läuft beim nächsten Start); kein `/r` (Sektorprüfung) möglich. |
| `kb_deinstallieren` | powershell/cmd | Kumulative Updates lassen sich mit `wusa` oft nicht entfernen (dann Fehlercode statt Erfolg). CMD: `wusa /kb:` mit Ziffern aus der `for`-Variablen – auf echtem Windows prüfen. |
| `verknuepfung_erstellen` | alle | Windows (`WScript.Shell`) nur Syntax geprüft. GNOME: Desktop-Verknüpfungen brauchen „Start erlauben“ (`gio set … metadata::trusted` wird versucht). macOS-Anmeldeobjekt per AppleScript braucht ggf. die Automation-Freigabe für „System Events“. |
| `bericht_html` | powershell/cmd | PowerShell liest das noch offene Transcript (FileShare ReadWrite), CMD das Protokoll per `Get-Content -Encoding UTF8` – beides auf Win 11 prüfen. Die Zusammenfassung am Scriptende fehlt im Bericht. |
| `ordner_oeffnen`, `datei_oeffnen` | bash | Braucht eine grafische Sitzung (`xdg-open`); in SSH-Sitzungen schlägt der Schritt fehl. |
| `pakete_installieren` | powershell/cmd | winget-Codes für „schon installiert“ (-1978335189, -1978335135) auf Win 11 bestätigen; CMD zählt diese Fälle als Fehler. Paketmanager-Auswahl gilt unter Windows nicht (immer winget). macOS: Formeln und Apps (--cask) lassen sich in einem Schritt nicht mischen. |
| `netzwerkadapter_neustarten` | alle | Nur mit Attrappen getestet. Linux braucht NetworkManager (`nmcli`); `networking off` trennt **alle** Verbindungen. macOS: `ifconfig down/up` – bei WLAN ggf. erneute Anmeldung nötig. |
| `office_schnellreparatur` | powershell | Nur Klick-und-Los-Office; Aufruf von `OfficeClickToRun.exe` (Parameter, Exit-Codes) auf Win 11 mit Microsoft 365 prüfen. Für CMD gibt es den Baustein nicht. |
| Rezept „Neuer Arbeitsplatz“ | zsh | Mischt einen root-Baustein (Umbenennen über sudo) mit Homebrew (nie root) – auf echtem macOS durchspielen. |
| Registry-Bausteine | powershell/cmd | Unter Linux nur Text/Syntax/PSSA und die reinen Hilfsfunktionen geprüft – echte Registry-Zugriffe laufen erst im Windows-CI-Job (Teil F). |
| Registry, Bereich „angemeldeter Benutzer“ | powershell/cmd | Mit UAC und **fremdem** Admin-Konto auf echter VM prüfen (Ziel: HKU\<SID> des Benutzers, nicht das Admin-Profil). RDP mit mehreren Sitzungen → Abbruch. `Software\Classes` des Benutzers liegt in `UsrClass.dat` (`HKU\<SID>_Classes`) und wird nicht abgedeckt. |
| Registry, „Alle Benutzerprofile“/„Standardprofil“ | powershell | Laden/Entladen nicht angemeldeter `NTUSER.DAT` nur auf echter VM prüfbar; Rückgängig-Dateien dieser Profile verweisen auf `HKU\OkmTemp_…` und gehen nur, wenn das Profil wieder so geladen ist. |
| Registry, CMD | cmd | Rückgängig-Datei nur für schon vorhandene Schlüssel (neu angelegte Schlüssel werden nicht vermerkt). `registry_pruefen` vergleicht per `findstr` – bei Daten mit Sonderzeichen/Umlauten unzuverlässiger als PowerShell. `registry_import` sichert Schlüssel mit Umlauten im Namen ggf. nicht (Umweg über `type`/`findstr`). „Nachfragen“ gibt es nur in PowerShell. |
| `richtlinie_setzen`, Konvention ohne Werte | powershell | Richtlinien nur mit `valueName` (ohne enabled/disabledValue) schreiben aktiviert = DWORD 1, deaktiviert = DWORD 0 – Verhalten des Gruppenrichtlinien-Editors, in [MS-GPREG] nicht ausdrücklich beschrieben. Auf Win 11 mit gpedit.msc gegenprüfen (Registry.pol nach dem Setzen vergleichen). |
| `richtlinie_setzen`, LGPO-Textformat | powershell | `MULTISZ:` mit `\0` als Trenner, `DELETEALLVALUES` und `EXSZ:` nach der LGPO-3.0-Doku umgesetzt, aber noch nicht mit `LGPO.exe /t` auf echter VM eingespielt und per `/parse` zurückgelesen. Schlüssel-Entfernen kennt Registry.pol nicht – „nicht konfiguriert“ lässt leere Schlüssel dort stehen. |
| `richtlinie_setzen`, Benutzer-Richtlinien | powershell | Kein gpupdate (liefe im Admin-Profil) – nur Hinweis „neu anmelden“. Ob Edge/Chrome Benutzer-Richtlinien aus HKU\<SID> ohne Neuanmeldung übernehmen, auf echter VM prüfen. Methode „Lokale Gruppenrichtlinie“ + Bereich ≠ angemeldeter Benutzer schreibt in die Benutzer-Registry.pol (gilt dann für **alle** Benutzer ohne Admin-Ausnahme) – Hinweis in der Oberfläche fehlt noch (Teil C). |
| `admin_werkzeug_bereitstellen` | powershell | Download (TLS 1.2, Proxy des Systems), Hash-Prüfung, Entpacken (msiexec /a, expand.exe, Office-EXE /extract), `revision`-Vergleich und Central Store nur unter Linux auf Text/PSSA geprüft. Office-Vorlagen: die EXE wird mit `/quiet /extract:` ausgeführt – sie ist vorher per SHA-256 geprüft. LGPO-Sicherung liegt in `%TEMP%` (kann von der Datenträgerbereinigung entfernt werden). |
| Vorlagen-Pakete OneDrive, Adobe Reader, Zoom | – | Kein verifizierbarer offizieller Direkt-Download → `format: manuell`, nicht im Katalog. Vorlagen von Hand ablegen (siehe `docs/richtlinien-katalog.md`). |
| alle Datei-Bausteine aus Paket 1 | powershell/cmd | Unter Linux nur Syntax/Lint geprüft (Windows-Pfade), auf Win 11 ausführen. |
| alle | powershell/cmd | Ausführen-Checkliste (`docs/test-vms.md`, Abschnitt 4): alle Windows-Zellen (Doppelklick/„Mit PowerShell ausführen“, UAC angefordert/abgelehnt, Konsole UTF-8, Fenster bleibt offen) sind noch **nicht** auf Win 11 geprüft. |
| alle | bash/zsh | Checkliste bisher nur im Linux-Container mit Attrappen (`ping`, `sudo`); auf Debian 12 und echtem macOS (Terminal.app, echtes sudo) wiederholen. |

## Bewusst nicht umgesetzt

- **Port erreichbar prüfen** und **Drucker per IP** gibt es für CMD nicht (kein Bordmittel ohne PowerShell).
- **Netzlaufwerk** gibt es für Linux nicht (abhängig von Desktop/fstab/cifs-utils).
- Die macOS-Blöcke sind ohne Mac-Testgerät nur per `zsh -n` und mit zsh unter Linux geprüft
  (macOS-Befehle wie `launchctl`, `sysadminctl` nur als Attrappen).
- BitLocker-Wiederherstellungsschlüssel, Passwort-Generator, Office-Schnellreparatur, ESET-Status
  u. a.: siehe [vorlagen-status.md](vorlagen-status.md) („Bewusst nicht umgesetzt“).
- Der Neustart mit Vorwarnung fehlt für macOS (kein Countdown mit Meldung per Bordmittel).

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

## Software-Katalog

- Kopieren ist automatisch in Chromium getestet (Clipboard-API und Fallback). In **Edge und
  Firefox** über HTTPS **und** reines HTTP noch einmal von Hand prüfen.
- Die Spec verweist bei fehlendem Homebrew auf eine Vorlage „Homebrew installieren“ – die gibt
  es noch nicht (der Installer lädt ein Script aus dem Internet und ist interaktiv). Bis dahin
  meldet der Baustein „bitte an die IT wenden“.
- Im **Blockly-Modus** setzt „＋“ die ID in den ausgewählten Paket-Block, sonst entsteht ein neuer
  Block am Ende des Scripts. Mehrfachauswahl („Ausgewählte installieren“) gibt es dort nicht.
- Die Auswahlliste „Paketmanager“ zeigt unter Linux/macOS alle Werte. Ein unpassender Wert
  (z. B. `brew_cask` unter Linux) erzeugt eine klare Fehlermeldung im Script statt eines
  falschen Befehls; unter Windows wird das Feld ausgeblendet (immer winget).
- „＋“ füllt das zuletzt fokussierte Paketfeld. Safari fokussiert Knöpfe beim Klicken nicht – das
  Verhalten dort einmal prüfen.
- Gemerkte Plattform: Im Baukasten/Rezept gewinnt immer das Zielsystem; die gemerkte Wahl gilt
  nur auf der Seite „Software“.

## Bibliothek & Verwaltung

- Freigegebene DB-Rezepte liegen im Speicher der Registry. Mit mehreren uvicorn-Workern
  (`--workers N`) sähen andere Prozesse eine Freigabe erst nach einem Neustart. Die mitgelieferte
  systemd-Unit startet daher genau einen Prozess.
- Titel/Beschreibung in der Bibliothek sind reine Metadaten; der Kopfkommentar des Scripts
  behält den Titel von der Erzeugung.
- Es gibt keine Datenbank-Migrationen (Alembic). Neue Tabellen legt die App selbst an; neue
  Spalten ergänzt eine Mini-Migration per `ALTER TABLE` (`Datenbank._migrieren`, bisher nur
  `editor_text`/`manuell_bearbeitet`). Für Umbenennungen/Typänderungen braucht es Alembic.

## Script-Editor

- „Syntax prüfen“ nutzt auf dem Server dieselben Werkzeuge wie die Tests. Fehlen `shellcheck`,
  `zsh`, `pwsh` oder das Modul PSScriptAnalyzer, meldet die Prüfung das – für vollständige
  Prüfungen auf dem Server installieren.
- Für CMD gibt es keinen echten Parser, nur die Baukasten-Regeln.
- „Script erzeugen“ im Listen-/Blockly-Modus speichert die **generierte** Fassung; ein bearbeiteter
  Text landet erst mit „In Bibliothek speichern“ in der Datenbank (der Download-Knopf im Ergebnis
  liefert vorher schon den bearbeiteten Text).
- Listen-Modus: Wer den Titel tippt und sofort „Erzeugen“ klickt, löst beim Verlassen des Feldes
  noch eine Live-Vorschau aus, die das Ergebnis wieder leert.

## Rückgabewerte & Variablen

- Der Parametertyp `variable` wird noch von **keinem Baustein** genutzt. Blockly zeigt dafür eine
  Auswahl der Werte davor; der Listen-Modus nur ein Textfeld (`3.frei_prozent`).
- „Wenn … dann … sonst“, „Abbrechen“, „Warten“, „Bestätigung“ und „Notiz“ gibt es nur in Blockly
  (Listen-Modus und Rezepte: Backlog P2).
- „Abbrechen“ ist innerhalb von „Versuche“ nicht erlaubt (in bash/zsh würde nur die Subshell enden).
- Blockly zeigt bei „Wenn“ alle Vergleiche; ob der Vergleich zum Werttyp passt (Zahl bzw. ja/nein),
  meldet erst die Prüfung im Backend.
- Rückgaben in Schleifen: Es gilt der Wert des letzten Durchlaufs.
- Rückgaben im Dry-Run bleiben „unbekannt“ (die Befehle laufen nicht).

## Blockly & Ablauf-Bausteine

- Leere Textfelder sind in Blockly sehr schmal (Blockly kennt keine Platzhalter in Feldern).
- Der Blockly-Entwurf liegt nur im `localStorage` des Browsers (pro Gerät, kein Server-Entwurf).
- „Hat funktioniert“-Zählung, Fortschritt `[n/m]`: `m` ist die Zahl der Bausteine im Text;
  in Schleifen wird derselbe Schritt mehrfach mit gleicher Nummer ausgegeben.
- CMD: Innerhalb von „Versuche“ wird ein roter Abbruch wie überall über `:okm_abbruch` beendet;
  die Ausgabe eines fehlgeschlagenen Schritts erscheint (wie generell in CMD) erst nach dem Schritt.
- Ablauf-Bausteine gibt es nur im Blockly-Modus (nicht im Listen-Modus und nicht in Rezepten).
- „Für jeden Wert“: In Blockly lässt sich `{wert}` nur in Textfeldern eintragen – nicht in Zahlen-,
  Auswahl- oder Ja/Nein-Feldern (die API nimmt den Schleifenwert auch für Zahlenfelder an). Der Rumpf
  wird pro Wert ausgerollt: 50 Werte × viele Schritte ergeben lange Scripte. Nur der Wert der innersten
  Schleife ist erreichbar.

## Phasen

- Phase 5 (LLM-Integration) ist zurückgestellt: `docs/llm-integration.md` fehlt noch.
