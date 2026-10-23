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

## 4. Protokoll der Prüfungen

| Datum | Prüfer | VM / System | Rezept/Block | Ergebnis |
|---|---|---|---|---|
| | | | | |
