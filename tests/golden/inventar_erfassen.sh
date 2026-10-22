#!/usr/bin/env bash
# ======================================================================
# Titel:             Seriennummer und Inventar erfassen
# Beschreibung:      Sammelt Seriennummer, Hardware, Betriebssystem, Lizenzstatus und installierte Programme für die Inventarisierung.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. Seriennummer und Modell [Risiko: gruen]
#    2. Systeminfo anzeigen [Risiko: gruen]
#    3. Letzter Neustart und ausstehender Neustart [Risiko: gruen]
#    4. Installierte Software auflisten [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

set -Eeuo pipefail

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=4
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

# --------------------------------------------------------------------
# Schritt 1/4: Seriennummer und Modell (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/4 (Seriennummer und Modell)'
printf '%s\n' '[1/4] Hardware-Daten werden gelesen …'
for okm_feld in sys_vendor product_name product_serial bios_version bios_date; do
  okm_wert="$(cat "/sys/class/dmi/id/$okm_feld" 2>/dev/null || printf '%s' '(nur als root lesbar)')"
  printf '%-15s %s\n' "$okm_feld:" "$okm_wert"
done
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/4: Systeminfo anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/4 (Systeminfo anzeigen)'
printf '%s\n' '[2/4] Systeminformationen werden gesammelt …'
printf 'Rechnername:    %s\n' "$(hostname)"
printf 'Betriebssystem: %s\n' "$(grep -m1 '^PRETTY_NAME=' /etc/os-release | cut -d= -f2- | tr -d '"')"
printf 'Kernel:         %s\n' "$(uname -r)"
printf 'Prozessor:     %s (%s Threads)\n' "$(awk -F: '/model name/ {print $2; exit}' /proc/cpuinfo)" "$(nproc)"
printf 'Laufzeit:       %s\n' "$(uptime -p)"
free -h
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 3/4: Letzter Neustart und ausstehender Neustart (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/4 (Letzter Neustart und ausstehender Neustart)'
printf '%s\n' '[3/4] Startzeit und ausstehende Neustarts werden geprüft …'
printf 'Letzter Start: %s (%s)\n' "$(uptime -s)" "$(uptime -p)"
if [ -f /var/run/reboot-required ]; then
  printf '%s\n' 'Neustart ausstehend: JA'
  cat /var/run/reboot-required.pkgs 2>/dev/null || true
elif command -v needs-restarting >/dev/null 2>&1; then
  needs-restarting -r || true
else
  printf '%s\n' 'Neustart ausstehend: nein'
fi
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 4/4: Installierte Software auflisten (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='4/4 (Installierte Software auflisten)'
printf '%s\n' '[4/4] Installierte Software wird gelesen …'
if command -v dpkg-query >/dev/null 2>&1; then
  okm_liste="$(dpkg-query -W -f='${Package}\t${Version}\n')"
elif command -v rpm >/dev/null 2>&1; then
  okm_liste="$(rpm -qa --qf '%{NAME}\t%{VERSION}-%{RELEASE}\n' | sort)"
else
  okm_liste="$(printf '%s\n' 'Kein unterstützter Paketmanager gefunden.')"
fi
printf '%s\n' "$okm_liste"
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
