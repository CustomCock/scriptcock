# Registry-Bausteine

Kategorie **Registry** im Baukasten, in Blockly und in den Rezepten. Alles hier gilt für PowerShell und
CMD; was nur PowerShell kann, steht dabei. Die Richtlinien aus den Administrativen Vorlagen
(„Richtlinie setzen“) beschreibt [`richtlinien-katalog.md`](richtlinien-katalog.md).

## Bausteine

| Baustein | Risiko | Ziele | Wozu |
|---|---|---|---|
| Registry-Wert lesen | grün | PS, CMD | Wert anzeigen; Rückgabe `vorhanden` |
| Registry-Schlüssel anzeigen | grün | PS, CMD | alle Werte und Unterschlüssel eines Schlüssels |
| Registry-Wert prüfen (Soll/Ist) | grün | PS, CMD | ein Wert gegen Typ + Daten; bei Abweichung melden oder abbrechen; Rückgabe `stimmt` |
| Registry-Werte prüfen (Soll/Ist-Liste) | grün | PS | viele Zeilen `Pfad ; Wertname ; Typ ; Soll` auf einmal, Rückgabe `abweichungen` |
| Registry-Rechte anzeigen | grün | PS | Besitzer und Berechtigungen eines Schlüssels |
| Registry-Schlüssel exportieren | grün | PS, CMD | `.reg`-Datei schreiben (Standard: `%TEMP%`) |
| Registry-Wert setzen | gelb | PS, CMD | alle Typen, mit Sicherung, Zurücklesen und „wenn vorhanden“ |
| Registry-Schlüssel anlegen | gelb | PS, CMD | leeren Schlüssel anlegen (vorhandener Inhalt bleibt) |
| Registry-Wert löschen | rot | PS, CMD | Wert löschen, vorher sichern |
| Registry-Schlüssel löschen | rot | PS, CMD | Schlüssel samt Unterschlüsseln löschen, vorher sichern und anzeigen |
| .reg-Datei importieren | rot | PS, CMD | Datei zuerst zeigen und prüfen, betroffene Schlüssel sichern, dann `reg import` |
| Explorer neu starten | gelb | PS, CMD | damit Explorer-Einstellungen sofort wirken |

Pfade gibt man in der Kurzform `HKLM\SOFTWARE\…` oder lang (`HKEY_LOCAL_MACHINE\…`) an; sie werden auf die
Kurzform gebracht. Typen: `REG_SZ`, `REG_EXPAND_SZ`, `REG_DWORD`, `REG_QWORD`, `REG_MULTI_SZ`, `REG_BINARY`.
`REG_DWORD` nimmt 0 bis 4294967295 (dezimal oder `0x…`, Werte über `0x7FFFFFFF` werden richtig als
vorzeichenlos geschrieben), `REG_EXPAND_SZ` wird **nicht** aufgelöst (`%SystemRoot%` bleibt stehen),
`REG_MULTI_SZ` nimmt eine Zeile pro Eintrag, `REG_BINARY` Hex-Bytes (`0a 1b` oder `0a1b`).
Ein leerer Wertname ist der Standardwert `(Standard)`.

**Ansicht 64/32 Bit**: Standard ist die 64-Bit-Registry. Läuft ein PowerShell-Script als 32-Bit-Prozess
(z. B. aus einem 32-Bit-Softwareverteiler), startet es sich als 64-Bit-PowerShell neu; sonst würde
`HKLM\SOFTWARE` stillschweigend nach `WOW6432Node` umgeleitet. CMD gibt `/reg:64` bzw. `/reg:32` immer mit.

## Bereich – und die HKCU-Falle

Windows-Scripte starten sich per UAC als Administrator neu. Meldet sich dabei ein **anderes** Konto an
(typisch: der Benutzer arbeitet ohne Adminrechte, der Helpdesk gibt sein Admin-Konto ein), ist `HKCU`
im neuen Prozess das Profil des **Admin-Kontos**. Ein Script, das „HKCU\Software\…“ setzt, ändert dann
nicht die Einstellung des Benutzers, sondern die des Helpdesk-Kontos – und meldet trotzdem Erfolg.

Deshalb benutzt kein erzeugtes Script je `HKCU`. Benutzer-Einstellungen laufen über den **Bereich**:

| Bereich | Wohin | PS | CMD |
|---|---|---|---|
| Computer (HKLM) | `HKLM\…` | ✓ | ✓ |
| Angemeldeter Benutzer | `HKU\<SID>\…` des Benutzers an der Konsole (Besitzer von `explorer.exe`) | ✓ | ✓ |
| Alle Benutzerprofile | jedes Profil aus `ProfileList`; angemeldete über `HKU\<SID>`, die anderen über ihre geladene `NTUSER.DAT` | ✓ | – |
| Standardprofil | `C:\Users\Default\NTUSER.DAT` – gilt für Benutzer, die sich zum ersten Mal anmelden | ✓ | – |
| Alle Benutzer + Standardprofil | beides | ✓ | – |

- Bei Benutzer-Bereichen gibt man den Pfad **ohne Wurzel** an (`Software\Firma\App`); `HKCU\…` wird
  angenommen und umgeschrieben. Für „Computer“ ist nur `HKLM` erlaubt (lesend auch `HKCR`, `HKCC`, `HKU`).
- „Angemeldeter Benutzer“ bricht ab, wenn niemand oder mehr als ein Benutzer angemeldet ist (Terminalserver).
- Geladene Profile (`reg load HKU\OkmTemp_…`) werden **immer** wieder entladen, auch nach einem Fehler –
  sonst bliebe die `NTUSER.DAT` gesperrt und der Benutzer könnte sich nicht anmelden. Lässt sich ein Profil
  nicht laden (meist: gerade in Benutzung, ohne dass `HKU\<SID>` sichtbar ist), bricht der Schritt mit
  dieser Meldung ab. Profile ohne `NTUSER.DAT` werden mit Warnung übersprungen.

## Wert setzen: `wenn_vorhanden`

| Einstellung | Wert existiert schon |
|---|---|
| überschreiben (Standard) | neuer Wert wird geschrieben; Typwechsel wird gewarnt und durchgeführt |
| nur wenn fehlt | bleibt unverändert („bereits vorhanden, nicht geändert“) |
| abbrechen | Schritt schlägt fehl, das Script bricht ab |
| nachfragen (nur PowerShell) | `überschreiben? (J/N)` |

Unabhängig davon: Hat der Wert schon genau Typ und Daten, wird nichts geschrieben („bereits richtig
gesetzt“). Vorher- und Nachher-Wert stehen im Protokoll. Nach dem Schreiben liest das Script den Wert
zurück und vergleicht – weicht er ab (z. B. weil eine Richtlinie ihn sofort zurücksetzt), ist der Schritt
fehlgeschlagen.

Fehlende Elternschlüssel werden angelegt, **ohne** vorhandene Schlüssel anzufassen: PowerShell nutzt
`RegistryKey.CreateSubKey` (statt `New-Item -Force`, das einen vorhandenen Schlüssel samt Inhalt neu
anlegt), CMD `reg add`. Der Windows-CI-Job prüft genau das mit einem Nachbarwert.

Geschützte Schlüssel (Besitzer TrustedInstaller, Zugriff verweigert): das Script meldet das und bricht ab.
Es übernimmt **nie** den Besitz.

## Rückgängig-Dateien

Vor jeder Änderung wird der betroffene Schlüssel als `.reg` gesichert, einmal pro Schlüssel und Lauf,
in `%TEMP%\okm-registry-backup-<Zeit>-<Kennung>\`. Die Zusammenfassung nennt den Ordner.

- **Zurückspielen:** die Dateien doppelklicken, **höchste Nummer zuerst** (PowerShell `001.reg`, `002.reg` …;
  CMD `<Schritt>.reg`). So steht am Ende der Zustand vor dem ersten Schritt.
- **PowerShell** schreibt zusätzlich Dateien, die neu angelegte Werte (`"Name"=-`) und neu angelegte
  Schlüssel (`[-HKEY_…]`) wieder entfernen.
- **CMD** kann das nicht: Werte und Schlüssel, die das Script neu angelegt hat, bleiben nach dem
  Zurückspielen stehen (steht in `offene-punkte.md`).
- Der Import einer `.reg`-Datei sichert vorher jeden Schlüssel, den die Datei berührt.

## Wirkung

Viele Einstellungen wirken nicht sofort. Jeder schreibende Baustein hat das Feld **Wirkung**
(`sofort`, `Explorer neu starten`, `abmelden`, `neu starten`, `gpupdate`, `unbekannt`); die
Zusammenfassung am Ende nennt die stärkste nötige Aktion **einmal** („Damit die Änderungen wirken:
Rechner neu starten“). Beim Setzen zählt sie unter PowerShell nur, wenn sich wirklich etwas geändert hat.
„Explorer neu starten“ gibt es auch als eigenen Baustein.

## Registry direkt oder lokale Gruppenrichtlinie

Für Richtlinien (`…\Policies\…`) gibt es zwei Wege, auswählbar im Baustein „Richtlinie setzen“:

| | Registry direkt | Lokale Gruppenrichtlinie (LGPO) |
|---|---|---|
| Schreibt | den Wert direkt | in `Registry.pol` der lokalen Richtlinie über `LGPO.exe /t` |
| Sichtbar in gpedit.msc | nein | ja |
| Wirkt | sofort (bzw. laut „Wirkung“) | nach `gpupdate` (läuft am Ende automatisch für Computer-Richtlinien) |
| Sicherung | `.reg`-Dateien wie oben | `LGPO.exe /b` der ganzen lokalen Richtlinie |
| Voraussetzung | – | Schritt „Admin-Werkzeug bereitstellen: LGPO“ davor |

Die einfachen Registry-Bausteine schreiben immer direkt.

## Domänen-Vorrang

Ist der Rechner in einer Domäne, gewinnt die **Domänen-Gruppenrichtlinie**: Beim nächsten
Hintergrund-Update (Standard 90 Minuten ± 30) oder bei `gpupdate` schreibt Windows alle Werte unter
`…\Policies\…`, die eine Domänen-GPO setzt, neu. Ein Script kann solche Werte also nur vorübergehend
ändern. Das gilt für beide Methoden – auch die lokale Gruppenrichtlinie hat den niedrigsten Rang
(lokal → Standort → Domäne → OU). Was dauerhaft gelten soll, gehört in die Domänen-GPO.
Werte **außerhalb** von `Policies` fasst die Gruppenrichtlinie nicht an (außer über
Gruppenrichtlinien-Einstellungen/Preferences, die ebenfalls regelmäßig neu angewendet werden).

## Schutzliste

`registry/schutz.yaml` wird bei der Validierung geprüft (`app/regschutz.py`), also bevor ein Script
überhaupt entsteht:

| Liste | Wirkung |
|---|---|
| `gesperrt` (`HKLM\SAM`, `HKLM\SECURITY`, `HKLM\BCD00000000`) | Schreiben, Löschen und Import nie – auch nicht für Admins |
| `rot` (`HKLM\SYSTEM`, Winlogon) | nur als roter Schritt (Bestätigung „JA“) |
| `rot_teile` (`Policies`, `Lsa`) | wie `rot`, wenn der Teil irgendwo im Pfad vorkommt (im Baustein „Richtlinie setzen“ zählt `Policies` nicht – das ist dort der Normalfall) |
| `loeschen_min_ebenen: 3` | Schlüssel erst ab drei Ebenen unter der Wurzel löschen (`HKCU\Software\Microsoft` bleibt) |

Die Prüfung vergleicht ohne Groß-/Kleinschreibung und Teil für Teil (`HKLM\SYSTEMX` ist nicht
`HKLM\SYSTEM`). Benutzer-Pfade werden als `HKCU\…` geprüft. Eine `.reg`-Datei kennt der Baukasten vorher nicht:
Das Script prüft beim Import **jeden** Schlüssel der Datei gegen `gesperrt` und bricht sonst ab; der
Import selbst ist immer ein roter Schritt.

## Häufige Einstellungen

`registry/haeufig.yaml` enthält fertige Einstellungen (SMBv1 aus, OneDrive-Anmeldung, Edge-Startseite …)
mit Beschreibung, Bereich, Wirkung, Risiko und **belegter Quelle** (Herstellervorlage oder Microsoft
Learn). Ohne offizielle Quelle kommt nichts hinein – siehe `offene-punkte.md`.

## Tests

- `tests/test_windows_registry.py`, `tests/golden/bausteine/` – erzeugter Code je Ziel.
- `tests/test_escaping.py`, `tests/test_validation.py` – Grenzwerte, Pfadformen, gesperrte Pfade.
- Job `windows` in `.github/workflows/ci.yml` – führt die Scripte unter Windows PowerShell 5.1 und CMD
  wirklich aus und prüft die Registry (`tools/windows_test.py`, `tests/windows/lauf.ps1`).
- Was nur auf einer echten VM geht (UAC mit fremdem Admin-Konto, nicht angemeldete Profile):
  [`test-vms.md`](test-vms.md).
