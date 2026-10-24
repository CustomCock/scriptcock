#!/usr/bin/env bash
# ======================================================================
# Titel:             Neuer Arbeitsplatz einrichten
# Beschreibung:      Gibt einem neuen Rechner seinen Namen, stellt die Uhrzeit richtig und installiert die Standardsoftware. Danach einmal neu starten.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Benötigte Rechte:  sudo (Schritt 1, 2, 3)
# Enthaltene Schritte:
#    1. Rechner umbenennen [Risiko: gelb, sudo]
#    2. Uhrzeit synchronisieren [Risiko: gelb, sudo]
#    3. Mehrere Pakete installieren [Risiko: gelb, sudo]
#    4. Meldung/Pause für den Benutzer [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

set -Eeuo pipefail

# --nopause: am Ende nicht auf Enter warten (Fernwartung/RMM)
OKM_KEINE_PAUSE=0
for okm_arg in "$@"; do
  if [ "$okm_arg" = --nopause ]; then OKM_KEINE_PAUSE=1; fi
done
OKM_LOG="${TMPDIR:-/tmp}/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=4
OKM_OK=0
OKM_NR=0
OKM_SCHRITT='-'
OKM_STATUS=laeuft
OKM_TIPP=''
OKM_SUDO_PID=''

# Meldungen: Werte immer als Argumente übergeben, nie in den Formatstring einsetzen.
# Keine Farben – die Ausgabe geht auch ins Protokoll.
okm_info() { printf '%s\n' "$*"; }
# shellcheck disable=SC2120  # Text ist optional (Blöcke dürfen okm_ok "…" nutzen)
okm_ok() { if [ $# -gt 0 ]; then printf '      OK  %s\n' "$*"; else printf '%s\n' '      OK'; fi; }
okm_warn() { printf '      WARNUNG  %s\n' "$*"; }
okm_fehler() { printf '      FEHLER  %s\n' "$*"; }
# Exit-Code nur weiterreichen: der Fehler-Handler meldet so die Zeile des Schritts
# (nicht die dieser Funktion) und den Befehl aus OKM_SUDO_BEFEHL.
okm_sudo() {
  local okm_rc=0; OKM_SUDO_BEFEHL="okm_sudo $*"
  if [ "$(id -u)" -eq 0 ]; then "$@" || okm_rc=$?; else sudo -- "$@" || okm_rc=$?; fi
  return "$okm_rc"
}
okm_zusammenfassung() {
  okm_info '----------------------------------------------'
  case "$OKM_STATUS" in
    fertig) printf ' Fertig: %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT" ;;
    abbruch) okm_info ' Abgebrochen durch Benutzer. Es wurde nichts weiter ausgeführt.' ;;
    rechte) okm_info ' Abgebrochen: fehlende Rechte.' ;;
    *) printf ' Abgebrochen bei Schritt %s von %s.\n' "$OKM_NR" "$OKM_GESAMT"; printf ' Erfolgreich bis dahin: %s von %s Schritten.\n' "$OKM_OK" "$OKM_GESAMT" ;;
  esac
  printf ' Protokoll: %s\n' "$OKM_LOG"
  okm_info '----------------------------------------------'
}
# Fenster/Terminal offen halten – nur wenn ein Mensch davor sitzt
okm_pause() {
  if [ "$OKM_KEINE_PAUSE" = 1 ] || [ ! -t 0 ]; then return 0; fi
  read -r -p 'Drücke Enter zum Schließen …' _ || true
}
okm_bei_fehler() {
  local okm_rc=$1 okm_zeile=$2 okm_befehl=$3
  case $okm_befehl in 'return "$okm_rc"') okm_befehl=$OKM_SUDO_BEFEHL ;; esac
  trap - ERR
  okm_fehler "Schritt $OKM_SCHRITT: Befehl endete mit Exit-Code $okm_rc."
  okm_info "      Zeile $okm_zeile, Befehl: $okm_befehl"
  if [ -n "$OKM_TIPP" ]; then okm_info "      Tipp: $OKM_TIPP"; fi
  OKM_STATUS=fehler
  exit "$okm_rc"
}
trap 'okm_bei_fehler $? $LINENO "$BASH_COMMAND"' ERR

# Zusammenfassung bei JEDEM Ende – auch bei Fehlern, die kein ERR auslösen
# (z. B. nicht gesetzte Variable) oder einem Abbruch ohne Meldung.
okm_ende() {
  local okm_rc=$?
  if [ "$OKM_STATUS" = laeuft ]; then
    if [ "$okm_rc" -eq 0 ]; then
      OKM_STATUS=fertig
    else
      okm_fehler "Script unerwartet beendet in Schritt $OKM_SCHRITT (Exit-Code $okm_rc)."
      OKM_STATUS=fehler
    fi
  fi
  okm_zusammenfassung
  if [ -n "$OKM_SUDO_PID" ]; then kill "$OKM_SUDO_PID" 2>/dev/null || true; fi
  okm_pause
  # Ausgabe schließen und kurz auf tee warten, sonst fehlen beim Schließen des Fensters
  # die letzten Zeilen (höchstens 2 s – ein Hintergrundprozess darf nichts aufhalten)
  exec 1>&- 2>&-
  okm_i=0
  while [ "$okm_i" -lt 20 ] && kill -0 "${OKM_TEE:-0}" 2>/dev/null; do
    sleep 0.1
    okm_i=$((okm_i + 1))
  done
  exit "$okm_rc"
}
trap okm_ende EXIT

# Ausgabe zusätzlich ins Protokoll – über eine FIFO statt >(tee), damit das Script am Ende
# auf tee warten kann (zsh verliert sonst die komplette Ausgabe, wenn das Fenster zugeht).
OKM_TMPDIR="$(mktemp -d)"
mkfifo -m 600 "$OKM_TMPDIR/ausgabe"
tee -a "$OKM_LOG" < "$OKM_TMPDIR/ausgabe" &
OKM_TEE=$!
exec > "$OKM_TMPDIR/ausgabe" 2>&1
rm -rf "$OKM_TMPDIR"

okm_info '=============================================='
okm_info ' okm Script-Baukasten · Neuer Arbeitsplatz einrichten'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# Rechte: sudo für Schritt 1 (Rechner umbenennen), Schritt 2 (Uhrzeit synchronisieren), Schritt 3 (Mehrere Pakete installieren)
okm_info 'Für diese Schritte werden Administratorrechte (sudo) gebraucht:'
okm_info '      Schritt 1 (Rechner umbenennen)'
okm_info '      Schritt 2 (Uhrzeit synchronisieren)'
okm_info '      Schritt 3 (Mehrere Pakete installieren)'
if [ "$(id -u)" -eq 0 ]; then
  okm_info 'Rechte: als root gestartet'
else
  if ! command -v sudo >/dev/null 2>&1; then
    okm_fehler 'sudo ist nicht installiert – bitte die IT fragen.'
    OKM_STATUS=rechte
    exit 1
  fi
  okm_info 'sudo fragt jetzt einmal nach deinem Passwort (die Eingabe bleibt unsichtbar).'
  if ! sudo -v; then
    okm_fehler 'sudo wurde abgelehnt oder das Passwort war falsch.'
    OKM_STATUS=rechte
    exit 1
  fi
  okm_info 'Rechte: sudo erfolgreich'
  # sudo-Zeitstempel frisch halten, damit lange Scripte nicht noch einmal fragen
  while true; do sudo -n true; sleep 50; kill -0 "$$" || exit; done >/dev/null 2>&1 &
  OKM_SUDO_PID=$!
fi

# Rückgabewerte der Schritte (Namen vergibt der Baukasten; leer = unbekannt)
okm_s3_fehlgeschlagen=''

# --------------------------------------------------------------------
# Schritt 1/4: Rechner umbenennen (Risiko: gelb)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/4 (Rechner umbenennen)'
OKM_TIPP='Ist der Rechner Mitglied einer Domäne? Dann muss die IT ihn umbenennen.'
okm_info '[1/4] Rechner wird in PC-EMPFANG-01 umbenannt ...'
okm_sudo hostnamectl set-hostname 'PC-EMPFANG-01'
printf 'Neuer Hostname: %s\n' "$(hostname)"
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 2/4: Uhrzeit synchronisieren (Risiko: gelb)
# --------------------------------------------------------------------
OKM_NR=2
OKM_SCHRITT='2/4 (Uhrzeit synchronisieren)'
OKM_TIPP='Ist der Zeitserver erreichbar (Firewall, UDP-Port 123)? In Domänen gibt der Domänencontroller die Zeit vor.'
okm_info '[2/4] Uhrzeit wird mit dem Zeitserver abgeglichen ...'
if command -v chronyc >/dev/null 2>&1; then
  okm_sudo chronyc makestep
else
  okm_sudo timedatectl set-ntp true
  okm_sudo systemctl restart systemd-timesyncd
fi
timedatectl status
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 3/4: Mehrere Pakete installieren (Risiko: gelb)
# --------------------------------------------------------------------
OKM_NR=3
OKM_SCHRITT='3/4 (Mehrere Pakete installieren)'
OKM_TIPP='Die Paket-IDs im Software-Katalog prüfen; die nicht installierten stehen in der Meldung oben.'
okm_info '[3/4] Pakete werden installiert: Mozilla.Firefox, 7zip.7zip ...'
okm_pakete=('Mozilla.Firefox' '7zip.7zip')
okm_fehlt=()
okm_sudo apt-get update || okm_warn 'Paketlisten konnten nicht aktualisiert werden.'
for okm_p in "${okm_pakete[@]}"; do
  okm_info "--- $okm_p"
  okm_sudo apt-get install -y "$okm_p" || okm_fehlt+=("$okm_p")
done
# Anzahl über $# (die Schreibweise mit Raute-Klammer kollidiert mit Jinja-Kommentaren)
set -- "${okm_fehlt[@]}"
okm_s3_fehlgeschlagen=$#
if [ $# -gt 0 ]; then
  okm_fehler "Nicht installiert: ${okm_fehlt[*]}"
  false
else
  okm_ok 'Alle Pakete installiert.'
fi
[[ $okm_s3_fehlgeschlagen =~ ^-?[0-9]+$ ]] || okm_s3_fehlgeschlagen=''
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 4/4: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=4
OKM_SCHRITT='4/4 (Meldung/Pause für den Benutzer)'
OKM_TIPP=''
okm_info '[4/4] Hinweis für den Benutzer ...'
printf '%s\n' 'Fertig. Bitte den Rechner jetzt neu starten, damit der neue Name gilt.'
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
