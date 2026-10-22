# Vorlagen – Umsetzungsstand

Abgleich der Ideensammlung („Script-Vorlagen“, 25 Kategorien) mit dem, was im Baukasten
steckt. **Bausteine** (`blocks/`) sind einzeln im Baukasten/Blockly nutzbar, **Rezepte**
(`recipes/`) sind fertige Abläufe mit Formular. Ungeprüfte Befehle: [offene-punkte.md](offene-punkte.md).

Stand: 140 Bausteine, 21 Rezepte.

## Umgesetzt (MVP-Kategorien und Kombi-Vorlagen)

| Kat. | Thema | Bausteine | Rezepte |
|---|---|---|---|
| 1 | Systeminfo & Inventar | `systeminfo` (inkl. CPU/Build), `seriennummer`, `software_liste`, `windows_lizenz`, `windows_version`, `uptime_neustart`, `angemeldete_benutzer`, `akku_bericht`, `windows11_check`, `treiberliste`, `geraete_fehler` | Seriennummer und Inventar erfassen, Windows-11-Tauglichkeit |
| 2 | Netzwerk-Diagnose | `ping`, `traceroute`, `port_pruefen`, `gateway_ping`, `dns_test`, `oeffentliche_ip`, `mtu_test`, `netzwerkadapter`, `wlan_info`, `wlan_profile`, `wlan_report`, `offene_verbindungen`, `lauschende_ports`, `arp_tabelle`, `routing_tabelle`, `proxy_anzeigen` | Netzwerkproblem diagnostizieren (erweitert: Router, Internet, DNS) |
| 3 | Netzwerk-Reparatur (★) | `dns_cache_leeren`, `ip_erneuern`, `firewall_status` | – |
| 4 | Drucker | `drucker_ip`, `drucker_liste`, `druckwarteschlange_leeren`, `standarddrucker`, `drucker_entfernen`, `testseite`, `druckerport_pruefen`, `dienst_neustarten` | Drucker einrichten, Druckwarteschlange neu starten, Drucker-Problem diagnostizieren |
| 5 | Dateien & Freigaben | `netzlaufwerk_verbinden`/`_trennen`, `netzlaufwerke_anzeigen`, `ordner_anlegen`, `kopieren`, `ordner_spiegeln`, `grosse_dateien`, `ordnergroessen`, `alte_dateien_finden`, `freigaben_auflisten`, `ntfs_rechte`, `zip_erstellen` | Netzlaufwerk verbinden |
| 6 | Benutzer (lokal) | `lokale_benutzer`, `lokale_admins`, `benutzer_anlegen`, `benutzer_zu_gruppe`, `passwort_zuruecksetzen`, `benutzer_deaktivieren`, `profilgroessen` | – |
| 8 | Dienste & Prozesse | `dienst_status`, `dienst_neustarten`, `dienst_starten_stoppen`, `dienst_starttyp`, `gestoppte_autodienste`, `prozess_suchen`, `prozess_beenden`, `top_prozesse`, `autostart_anzeigen`, `geplante_aufgaben` | – |
| 9 | Updates | `update_status`, `windows_update_reset`, `setupdiag`, `update_log_export`, `dism_sfc`, `linux_upgrade`, `macos_updates` | Update-Status prüfen, Windows Update reparieren, Systemdateien reparieren |
| 10 | Software (★) | `paket_installieren`, `winget_upgrade_alle` | Software installieren |
| 11 | Speicher & Bereinigung | `festplattenbelegung`, `temp_aufraeumen`, `winsxs_bereinigen`, `papierkorb_leeren`, `browser_cache_leeren`, `teams_cache_leeren`, `journal_kuerzen`, `paket_cache_leeren`, `smart_status`, `laufwerk_optimieren`, `schattenkopien` | Speicherplatz freigeben |
| 12 | Datensicherung (★) | `benutzerdaten_sichern` | Benutzerdaten sichern |
| 13 | Sicherheit | `virenschutz_status`, `defender_schnellscan`, `defender_signaturen`, `bitlocker_status`, `filevault_status`, `gatekeeper_sip`, `sicherheits_schnellcheck`, `fehlgeschlagene_anmeldungen`, `smbv1_status`, `rdp_status`, `zertifikat_website`, `ssh_haertung`, `incident_erstsicherung` | Sicherheits-Schnellprüfung, Incident-Erstsicherung (nur Windows) |
| 14 | Logs & Fehleranalyse | `diagnosepaket`, `ereignisanzeige_fehler`, `systemlog_fehler`, `bluescreen_analyse`, `unerwartete_neustarts`, `absturzende_programme`, `boot_dauer`, `kernel_fehler`, `ereignis_nach_id` | Diagnosepaket für den Support, Absturz-Analyse |
| 15 | Performance | `pc_langsam_check`, `energieplan`, `energiebericht`, `standby_verhinderer`, `ruhezustand_deaktivieren`, `schnellstart_deaktivieren`, `swap_nutzung` | PC ist langsam |
| 16 | Office | `office_version`, `office_update_erzwingen`, `outlook_abgesichert`, `dsregcmd_status`, `onedrive_reset` | Office-Probleme eingrenzen |
| 18 | Server (nur ★) | – | Server-Gesundheitscheck (Windows + Linux) |
| 19 | Linux-Server | `linux_gesundheitscheck`, `fehlgeschlagene_units`, `inodes`, `docker_uebersicht`, `raid_status` (inkl. ZFS) | (im Server-Gesundheitscheck) |
| 20 | macOS | `spotlight_neu`, `dock_zuruecksetzen`, `rosetta_installieren`, `profile_status` | – |
| 21 | Fernwartung & Support | `support_infos` (inkl. TeamViewer-/AnyDesk-ID), `meldung`, `bildschirm_sperren`, `neustart_countdown` | Support-Infos anzeigen |
| 25 | Kleine Helfer | `datei_hash`, `datei_download` (mit optionaler SHA-256-Prüfung), `dateien_durchsuchen`, `zeit_pruefen`, `sprache_region` | – |

## Zurückgestellt (laut Priorisierung)

- **Kat. 7 (AD), 17 (DATEV/Branchensoftware), 18 (Server-Rollen, außer Gesundheitscheck), 22
  (Onboarding/Offboarding):** brauchen echte Kundenumgebungen → erst nach Abstimmung im Team.
  Dienstnamen, Pfade und CLI-Befehle (DATEV, ESET, Securepoint) werden dann als Parameter
  angelegt, nicht fest eingebaut.
- **Kat. 24 (Monitoring/JSON):** erst mit dem Monitoring-Projekt. Vorbereitung: Die Ausgabe
  liegt pro Baustein im Template; für JSON entstehen eigene Bausteine (PowerShell
  `ConvertTo-Json`, bash/zsh mit `printf`, ohne Abhängigkeit von `jq`).

## Bewusst (noch) nicht umgesetzt

| Vorlage | Grund |
|---|---|
| BitLocker-Wiederherstellungsschlüssel anzeigen, Passwort-Generator | Die Ausgabe landet im Script-Protokoll (Transcript/Logdatei). Braucht erst eine Generator-Funktion „Schritt nicht protokollieren“. |
| WLAN-Profil hinzufügen, lokales Admin-Konto mit Passwort aus Parameter | Passwörter würden im Script stehen – widerspricht dem Sicherheitskonzept. Nur mit interaktiver Abfrage denkbar. |
| Office-Schnellreparatur | `OfficeClickToRun.exe scenario=Repair …` braucht Plattform/Sprache passend zur Installation – erst auf Test-VMs klären. |
| ESET-Status | Pfad/CLI (`ermm.exe`?) muss gegen die echte Umgebung geprüft werden; der allgemeine `virenschutz_status` zeigt ESET bereits über das Sicherheitscenter. |
| Statische IP, Hosts-Datei, Firewall-Regeln, Proxy setzen, Netzwerk-Stack-Reset | Adapter-/Profilnamen sind je Rechner verschieden; braucht sorgfältige Parametrisierung und Tests (nächste Runde). |
| Dauerping, Ping-Sweep, Bandbreitentest, Performance-Messung | Lang laufende Schleifen – sinnvoll erst mit Abbruch-/Zeitlimit-Konzept im Generator. |
| Alles andere ohne ★ in den Kategorien 3, 5, 6, 10, 12, 16, 20, 23, 25 | Nächste Ausbaustufe; jeweils nur YAML (`docs/neuen-block-anlegen.md`). |
