#!/bin/zsh
# ======================================================================
# Titel:             Druckwarteschlange neu starten
# Beschreibung:      Startet den Druckdienst neu, wenn Druckaufträge hängen bleiben.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. Dienst neu starten [Risiko: gelb, Admin]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

setopt ERR_EXIT NO_UNSET PIPE_FAIL

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=1
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

# Prüfung: root-Rechte
if [ "$(id -u)" -ne 0 ]; then
  printf '%s\n' 'Dieses Script braucht Administratorrechte (root).'
  printf '%s\n' 'Bitte so starten: sudo zsh ./script.sh'
  printf 'Protokoll: %s\n' "$OKM_LOG"
  exit 1
fi

# --------------------------------------------------------------------
# Schritt 1/1: Dienst neu starten (Risiko: gelb)
# --------------------------------------------------------------------
OKM_SCHRITT='1/1 (Dienst neu starten)'
printf '%s\n' '[1/1] Dienst org.cups.cupsd wird neu gestartet …'
launchctl kickstart -k system/'org.cups.cupsd'
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
