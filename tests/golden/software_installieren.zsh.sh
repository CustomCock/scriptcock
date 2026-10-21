#!/bin/zsh
# ======================================================================
# Titel:             Software installieren
# Beschreibung:      Installiert ein Programm über den Paketmanager des Betriebssystems.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. Paket/Software installieren [Risiko: gelb]
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

# --------------------------------------------------------------------
# Schritt 1/1: Paket/Software installieren (Risiko: gelb)
# --------------------------------------------------------------------
OKM_SCHRITT='1/1 (Paket/Software installieren)'
printf '%s\n' '[1/1] Mozilla.Firefox wird installiert …'
if ! command -v brew >/dev/null 2>&1; then
  printf '%s\n' 'Homebrew ist nicht installiert (siehe https://brew.sh). Bitte an die IT wenden.'
  false
fi
brew install 'Mozilla.Firefox'
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
