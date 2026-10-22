#!/usr/bin/env bash
# ======================================================================
# Titel:             PC ist langsam
# Beschreibung:      Sucht die typischen Bremsen – CPU- und Speicherlast, volle Festplatte, lange Laufzeit, Autostart-Programme und Festplatten-Gesundheit.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. „PC ist langsam“-Check [Risiko: gruen]
#    2. Top-Ressourcenverbraucher [Risiko: gruen]
#    3. Festplattenbelegung anzeigen [Risiko: gruen]
#    4. Autostart-Einträge anzeigen [Risiko: gruen]
#    5. Festplatten-Gesundheit (SMART) [Risiko: gruen, Admin]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

set -Eeuo pipefail

OKM_LOG="${TMPDIR:-/tmp}/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=5
OKM_OK=0
OKM_NR=0
OKM_SCHRITT='-'
OKM_STATUS=laeuft
OKM_TIPP=''

# Meldungen: Werte immer als Argumente übergeben, nie in den Formatstring einsetzen.
# Keine Farben – die Ausgabe geht auch ins Protokoll.
okm_info() { printf '%s\n' "$*"; }
# shellcheck disable=SC2120  # Text ist optional (Blöcke dürfen okm_ok "…" nutzen)
okm_ok() { if [ $# -gt 0 ]; then printf '      OK  %s\n' "$*"; else printf '%s\n' '      OK'; fi; }
okm_warn() { printf '      WARNUNG  %s\n' "$*"; }
okm_fehler() { printf '      FEHLER  %s\n' "$*"; }
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
exec > >(tee -a "$OKM_LOG") 2>&1

okm_bei_fehler() {
  local okm_rc=$?
  trap - ERR
  okm_fehler "Schritt $OKM_SCHRITT: Befehl endete mit Exit-Code $okm_rc."
  if [ -n "$OKM_TIPP" ]; then okm_info "      Tipp: $OKM_TIPP"; fi
  OKM_STATUS=fehler
  okm_zusammenfassung
  exit "$okm_rc"
}
trap okm_bei_fehler ERR

okm_info '=============================================='
okm_info ' okm Script-Baukasten · PC ist langsam'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# Prüfung: root-Rechte
if [ "$(id -u)" -ne 0 ]; then
  okm_fehler 'Dieses Script braucht Administratorrechte (root).'
  okm_info '      Bitte so starten: sudo bash ./script.sh'
  OKM_STATUS=rechte
  okm_zusammenfassung
  exit 1
fi

# --------------------------------------------------------------------
# Schritt 1/5: „PC ist langsam“-Check (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/5 („PC ist langsam“-Check)'
OKM_TIPP=''
okm_info '[1/5] Rechner wird auf typische Bremsen geprüft ...'
printf 'Last (1/5/15 min): %s   CPU-Kerne: %s\n' "$(cut -d ' ' -f 1-3 /proc/loadavg)" "$(nproc)"
free -h
df -h /
uptime -p 2>/dev/null || uptime
printf '\n%s\n' 'Größte Verbraucher:'
ps -eo pid,%cpu,%mem,comm --sort=-%mem | awk 'NR <= 6'
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 2/5: Top-Ressourcenverbraucher (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=2
OKM_SCHRITT='2/5 (Top-Ressourcenverbraucher)'
OKM_TIPP=''
okm_info '[2/5] Prozesse werden nach Last sortiert ...'
printf '%s\n' 'Nach CPU:'
ps -eo pid,user,%cpu,%mem,comm --sort=-%cpu | awk 'NR <= 11'
printf '\n%s\n' 'Nach Arbeitsspeicher:'
ps -eo pid,user,%cpu,%mem,comm --sort=-%mem | awk 'NR <= 11'
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 3/5: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=3
OKM_SCHRITT='3/5 (Festplattenbelegung anzeigen)'
OKM_TIPP=''
okm_info '[3/5] Festplattenbelegung wird ermittelt ...'
df -h -x tmpfs -x devtmpfs -x squashfs -x overlay
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 4/5: Autostart-Einträge anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=4
OKM_SCHRITT='4/5 (Autostart-Einträge anzeigen)'
OKM_TIPP=''
okm_info '[4/5] Autostart-Einträge werden gelesen ...'
printf '%s\n' 'Aktivierte Systemdienste:'
systemctl list-unit-files --type=service --state=enabled --no-pager
printf '\n%s\n' 'Desktop-Autostart:'
ls -1 /etc/xdg/autostart "$HOME/.config/autostart" 2>/dev/null || true
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 5/5: Festplatten-Gesundheit (SMART) (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=5
OKM_SCHRITT='5/5 (Festplatten-Gesundheit (SMART))'
OKM_TIPP=''
okm_info '[5/5] Festplatten-Gesundheit wird geprüft ...'
lsblk -d -o NAME,MODEL,SIZE,ROTA,TYPE
if command -v smartctl >/dev/null 2>&1; then
  for okm_disk in /dev/sd? /dev/nvme?n1; do
    if [ -e "$okm_disk" ]; then
      printf '\n%s:\n' "$okm_disk"
      smartctl -H "$okm_disk" || true
    fi
  done
else
  printf '\n%s\n' 'smartctl ist nicht installiert (Paket smartmontools) – nur Basisinfos angezeigt.'
fi
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
okm_zusammenfassung
