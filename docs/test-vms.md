# Manuelle Prüfung auf Proxmox-Test-VMs

Die automatischen Tests prüfen Syntax, Escaping und – für bash/zsh/pwsh unter Linux – den
Ablauf. Ob ein Befehl auf dem echten Zielsystem das Richtige tut, zeigt nur ein Lauf auf
einer echten Maschine. Diese Anleitung beschreibt den Ablauf auf Proxmox.

## 1. VMs vorbereiten (einmalig)

| VM | Vorlage | Hinweise |
|---|---|---|
| `bk-win11` | Windows 11 Pro (deutsch), VirtIO-Treiber | lokales Admin-Konto **und** Standardkonto anlegen; Drucker-/Netzlaufwerk-Tests brauchen Zugriff aufs Test-VLAN |
| `bk-debian` | Debian 12 (Cloud-Image oder Netinst) | Benutzer mit `sudo`; `cups` und `traceroute` für die entsprechenden Blöcke installieren |
| `bk-macos` | nur falls lizenzrechtlich zulässig (Apple-Hardware) – sonst auf einem echten Test-Mac | Standardbenutzer + Admin |

Nach der Grundinstallation jeweils einen **Snapshot `sauber`** anlegen:

```bash
qm snapshot <vmid> sauber --description "Grundinstallation für Script-Baukasten-Tests"
```

## 2. Testlauf

1. VM auf den Snapshot zurücksetzen: `qm rollback <vmid> sauber`, dann starten.
2. Im Baukasten das Script erzeugen – **zuerst mit „Nur simulieren“**, dann normal.
3. Script in die VM bringen (Download über den Browser in der VM oder per Proxmox-Konsole/SSH/`scp`).
4. SHA-256 vergleichen:
   - Windows: `Get-FileHash .\datei.ps1 -Algorithm SHA256`
   - Linux: `sha256sum datei.sh` · macOS: `shasum -a 256 datei.sh`
5. Ausführen wie in der UI beschrieben (`Set-ExecutionPolicy -Scope Process Bypass`; Linux/macOS `chmod +x`, **ohne** sudo – das Script fragt selbst).
6. Prüfen:
   - Fortschrittsausgaben `[n/m]` erscheinen, am Ende „Fertig: X von X Schritten erfolgreich.“
   - Das Protokoll existiert am ausgegebenen Pfad und enthält alle Ausgaben.
   - Rote Schritte fragen nach „JA“; jede andere Eingabe bricht ab.
   - Rechte: ohne Adminrechte starten → Erklärung + UAC-Abfrage bzw. sudo-Passwort; abgelehnt → verständlicher Abbruch vor Schritt 1.
   - Fehlerfall: einen Block absichtlich fehlschlagen lassen (z. B. Datei kopieren mit falscher Quelle) → „FEHLER  Schritt …“ + Zusammenfassung.
   - Bei Windows: das Script einmal mit Windows PowerShell **5.1** (`powershell.exe`) und – falls vorhanden – mit PowerShell 7 starten.
   - Umlaute in Ausgabe und Protokoll sind korrekt (BOM / `chcp 65001`).
7. Ergebnis im Abschnitt „Protokoll der Prüfungen“ unten eintragen. Gefundene Probleme in
   `docs/offene-punkte.md` aufnehmen bzw. dort abhaken.

## 3. Was pro Block mindestens zu prüfen ist

- Jedes Rezept für jedes angebotene Zielsystem einmal komplett.
- Alle Blöcke mit Einträgen in `docs/offene-punkte.md`.
- Neue oder geänderte Blöcke (`version` erhöht) vor dem Merge.

## 4. Ausführen-Checkliste (Fehlerbehebung Runde 1)

Test-Scripte erzeugen – je Zielsystem ein Script mit Umlauten, einem Admin-/root-Block
(„Druckwarteschlange leeren“), einem Ping auf die nicht erreichbare IP `192.0.2.1` und einem
absichtlich fehlschlagenden Block („Datei kopieren“ mit fehlender Quelle), dazu je eine im Editor
„manuell bearbeitete“ Fassung:

```bash
python tools/checkliste_scripte.py checkliste/
```

Legende: **✓ auto** = am 23.10.2026 automatisch im Container geprüft (Ubuntu 24.04, bash 5.2,
zsh unter Linux, pwsh 7 unter Linux; `ping`/`cancel`/`sudo` als Attrappen im `PATH`, Start als
`root` und als `nobody`). **offen** = braucht die echte VM, noch nicht geprüft.

| Test | Win 11 PS 5.1 | Win 11 cmd | Debian | macOS |
|---|---|---|---|---|
| Rechtsklick „Mit PowerShell ausführen“ bzw. Doppelklick | offen | offen | – | – |
| Start im Terminal (`./script.sh`) | – | – | ✓ auto (Ubuntu statt Debian 12); VM offen | ✓ auto (zsh unter Linux); Mac offen |
| Umlaute korrekt in Konsole und Log | Datei ✓ auto (UTF-8 mit BOM, CRLF); Konsole offen | Datei ✓ auto (ohne BOM, CRLF, `chcp 65001`); Konsole offen | ✓ auto (Ausgabe + Protokoll) | ✓ auto (zsh/Linux); Terminal.app offen |
| Keine Steuerzeichen/Farbcodes als Text | Datei ✓ auto (kein ESC); Konsole offen | Datei ✓ auto; Konsole offen | ✓ auto (Ausgabe ohne ESC) | ✓ auto (zsh/Linux) |
| Admin/sudo wird erklärt und angefordert | offen (UAC nur unter Windows) | offen | ✓ auto (`nobody` + sudo-Attrappe) | ✓ auto (zsh, `nobody` + sudo-Attrappe); echtes sudo offen |
| UAC/sudo abgelehnt → verständliche Meldung | offen | offen | ✓ auto („sudo wurde abgelehnt …“, „Abgebrochen: fehlende Rechte.“) | ✓ auto (zsh/Linux) |
| Fehlschlagender Block → Schritt + Grund + Zusammenfassung | pwsh 7/Linux ✓ auto (`tests/test_abbruch.py`); 5.1 offen | offen | ✓ auto (Schritt 4/4, Exit-Code, Zeile, Befehl, Tipp, Zusammenfassung) | ✓ auto (zsh/Linux, mit Zeile) |
| Nicht erreichbarer Ping bricht nicht ab | offen | offen | ✓ auto (ping-Attrappe, kein ICMP im Container) | ✓ auto (zsh/Linux) |
| Fenster bleibt am Ende offen | offen | offen | – | – |
| Manuell bearbeitetes Script: Download korrekt, Kopfzeile vorhanden | Datei ✓ auto (BOM, CRLF, Kopfzeile, PowerShell-Parser ohne Fehler); Ausführung offen | Datei ✓ auto (CRLF, `chcp`, `rem`-Kopfzeile); Ausführung offen | ✓ auto (Kopfzeile, läuft); Browser-Download ✓ (`tests/test_browser.py`) | ✓ auto (Datei, Kopfzeile) |

**Gefunden und behoben beim Durchgehen (23.10.2026):** Schlug ein Befehl mit `{{ sudo }}` fehl,
nannte die Fehlermeldung unter bash die Zeile *in* der Hilfsfunktion und den Befehl `"$@"`, unter
zsh sogar `Zeile 0`/`Zeile 3`. Jetzt: Zeile des Schritts und der echte Befehl (siehe CHANGELOG).

**Noch offen:** alle Windows-Zellen sowie Debian 12 und macOS auf echten Maschinen – bitte mit
Datum und Prüfer in die Tabelle unten eintragen.

## 5. Protokoll der Prüfungen

| Datum | Prüfer | VM / System | Rezept/Block | Ergebnis |
|---|---|---|---|---|
| 23.10.2026 | Claude (automatisch) | Container Ubuntu 24.04 (bash 5.2, zsh, pwsh 7) | Checkliste-Scripte (`tools/checkliste_scripte.py`) | Linux-/zsh-Zeilen ✓, Dateiformate aller Ziele ✓; sudo-Fehlerzeile korrigiert; Windows/echte VMs offen |
| | | | | |
