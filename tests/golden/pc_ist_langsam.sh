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

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=5
OKM_OK=0
OKM_SCHRITT='-'
exec > >(tee -a "$OKM_LOG") 2>&1

okm_fehler() {
  local okm_rc=$?
  trap - ERR
  printf '\nFEHLER in Schritt %s (Exit-Code %s).\n' "$OKM_SCHRITT" "$okm_rc"
  printf 'Erfolgreich bis dahin: %s von %s Schritten.\n' "$OKM_OK" "$OKM_GESAMT"
  printf 'Protokoll: %s\n' "$OKM_LOG"
  exit "$okm_rc"
}
trap okm_fehler ERR

# Prüfung: root-Rechte
if [ "$(id -u)" -ne 0 ]; then
  printf '%s\n' 'Dieses Script braucht Administratorrechte (root).'
  printf '%s\n' 'Bitte so starten: sudo bash ./script.sh'
  printf 'Protokoll: %s\n' "$OKM_LOG"
  exit 1
fi

# --------------------------------------------------------------------
# Schritt 1/5: „PC ist langsam“-Check (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/5 („PC ist langsam“-Check)'
printf '%s\n' '[1/5] Rechner wird auf typische Bremsen geprüft …'
printf 'Last (1/5/15 min): %s   CPU-Kerne: %s\n' "$(cut -d ' ' -f 1-3 /proc/loadavg)" "$(nproc)"
free -h
df -h /
uptime -p 2>/dev/null || uptime
printf '\n%s\n' 'Größte Verbraucher:'
ps -eo pid,%cpu,%mem,comm --sort=-%mem | awk 'NR <= 6'
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/5: Top-Ressourcenverbraucher (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/5 (Top-Ressourcenverbraucher)'
printf '%s\n' '[2/5] Prozesse werden nach Last sortiert …'
printf '%s\n' 'Nach CPU:'
ps -eo pid,user,%cpu,%mem,comm --sort=-%cpu | awk 'NR <= 11'
printf '\n%s\n' 'Nach Arbeitsspeicher:'
ps -eo pid,user,%cpu,%mem,comm --sort=-%mem | awk 'NR <= 11'
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 3/5: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/5 (Festplattenbelegung anzeigen)'
printf '%s\n' '[3/5] Festplattenbelegung wird ermittelt …'
df -h -x tmpfs -x devtmpfs -x squashfs -x overlay
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 4/5: Autostart-Einträge anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='4/5 (Autostart-Einträge anzeigen)'
printf '%s\n' '[4/5] Autostart-Einträge werden gelesen …'
printf '%s\n' 'Aktivierte Systemdienste:'
systemctl list-unit-files --type=service --state=enabled --no-pager
printf '\n%s\n' 'Desktop-Autostart:'
ls -1 /etc/xdg/autostart "$HOME/.config/autostart" 2>/dev/null || true
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 5/5: Festplatten-Gesundheit (SMART) (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='5/5 (Festplatten-Gesundheit (SMART))'
printf '%s\n' '[5/5] Festplatten-Gesundheit wird geprüft …'
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

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
