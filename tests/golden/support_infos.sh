#!/usr/bin/env bash
# ======================================================================
# Titel:             Support-Infos anzeigen
# Beschreibung:      Zeigt Rechnername, Benutzer, IP-Adresse, Betriebssystem, Seriennummer und ggf. TeamViewer-/AnyDesk-ID – alles, was der Support am Telefon fragt.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. Support-Infos anzeigen [Risiko: gruen]
#    2. Meldung/Pause für den Benutzer [Risiko: gruen]
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
# Schritt 1/2: Support-Infos anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/2 (Support-Infos anzeigen)'
printf '%s\n' '[1/2] Support-Infos werden gesammelt …'
printf 'Rechnername:     %s\n' "$(hostname)"
printf 'Benutzer:        %s\n' "$(id -un)"
printf 'IP-Adresse(n):   %s\n' "$(hostname -I 2>/dev/null || true)"
if [ -r /etc/os-release ]; then
  printf 'Betriebssystem:  %s\n' "$(. /etc/os-release && printf '%s' "$PRETTY_NAME")"
fi
printf 'Kernel:          %s\n' "$(uname -r)"
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/2: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/2 (Meldung/Pause für den Benutzer)'
printf '%s\n' '[2/2] Hinweis für den Benutzer …'
printf '%s\n' 'Diese Angaben bitte dem Support durchgeben.'
read -r -p 'Weiter mit Enter ... ' _ || true
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
