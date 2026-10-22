#!/bin/zsh
# ======================================================================
# Titel:             Update-Status prüfen
# Beschreibung:      Zeigt die zuletzt installierten und die noch ausstehenden Updates.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. Update-Status anzeigen [Risiko: gruen]
#    2. Letzter Neustart und ausstehender Neustart [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

setopt ERR_EXIT NO_UNSET PIPE_FAIL

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=2
OKM_OK=0
OKM_SCHRITT='-'
exec > >(tee -a "$OKM_LOG") 2>&1

TRAPZERR() {
  local okm_rc=$?
  printf '\nFEHLER in Schritt %s (Exit-Code %s).\n' "$OKM_SCHRITT" "$okm_rc"
  printf 'Erfolgreich bis dahin: %s von %s Schritten.\n' "$OKM_OK" "$OKM_GESAMT"
  printf 'Protokoll: %s\n' "$OKM_LOG"
  exit "$okm_rc"
}

# --------------------------------------------------------------------
# Schritt 1/2: Update-Status anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/2 (Update-Status anzeigen)'
printf '%s\n' '[1/2] Update-Status wird ermittelt …'
softwareupdate --list 2>&1 || true
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/2: Letzter Neustart und ausstehender Neustart (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/2 (Letzter Neustart und ausstehender Neustart)'
printf '%s\n' '[2/2] Startzeit und ausstehende Neustarts werden geprüft …'
printf 'Letzter Start: %s\n' "$(sysctl -n kern.boottime)"
uptime
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
