#!/usr/bin/env bash
# ======================================================================
# Titel:             Update-Status prüfen
# Beschreibung:      Zeigt die zuletzt installierten und die noch ausstehenden Updates.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. Update-Status anzeigen [Risiko: gruen]
#    2. Letzter Neustart und ausstehender Neustart [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

set -Eeuo pipefail

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=2
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
# Schritt 1/2: Update-Status anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/2 (Update-Status anzeigen)'
printf '%s\n' '[1/2] Update-Status wird ermittelt …'
if command -v apt >/dev/null 2>&1; then
  apt list --upgradable 2>/dev/null
elif command -v dnf >/dev/null 2>&1; then
  dnf -q check-update || [ $? -eq 100 ]
else
  printf '%s\n' 'Kein unterstützter Paketmanager (apt, dnf) gefunden.'
fi
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/2: Letzter Neustart und ausstehender Neustart (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/2 (Letzter Neustart und ausstehender Neustart)'
printf '%s\n' '[2/2] Startzeit und ausstehende Neustarts werden geprüft …'
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

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
