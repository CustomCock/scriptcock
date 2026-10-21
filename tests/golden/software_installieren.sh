#!/usr/bin/env bash
# ======================================================================
# Titel:             Software installieren
# Beschreibung:      Installiert ein Programm über den Paketmanager des Betriebssystems.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. Paket/Software installieren [Risiko: gelb, Admin]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

set -Eeuo pipefail

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=1
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
# Schritt 1/1: Paket/Software installieren (Risiko: gelb)
# --------------------------------------------------------------------
OKM_SCHRITT='1/1 (Paket/Software installieren)'
printf '%s\n' '[1/1] Mozilla.Firefox wird installiert …'
apt-get update
apt-get install -y 'Mozilla.Firefox'
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
