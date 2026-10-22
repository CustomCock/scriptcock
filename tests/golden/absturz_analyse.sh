#!/usr/bin/env bash
# ======================================================================
# Titel:             Absturz-Analyse
# Beschreibung:      Sucht Bluescreens, unerwartete Neustarts und abstürzende Programme bzw. Kernel- und Systemfehler.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. Kernel-/Hardware-Meldungen (dmesg) [Risiko: gruen]
#    2. Systemlog: letzte Fehler anzeigen [Risiko: gruen]
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
# Schritt 1/2: Kernel-/Hardware-Meldungen (dmesg) (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/2 (Kernel-/Hardware-Meldungen (dmesg))'
printf '%s\n' '[1/2] Kernel-Meldungen werden gelesen …'
journalctl -k -b -p warning --no-pager || dmesg --level=err,warn
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/2: Systemlog: letzte Fehler anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/2 (Systemlog: letzte Fehler anzeigen)'
printf '%s\n' '[2/2] Fehler der letzten 24 Stunden werden gelesen …'
journalctl --no-pager -p err -n 200 --since=-24h
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
