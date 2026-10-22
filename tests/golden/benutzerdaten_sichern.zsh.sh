#!/bin/zsh
# ======================================================================
# Titel:             Benutzerdaten sichern
# Beschreibung:      Kopiert Desktop, Dokumente, Bilder, Downloads usw. des angemeldeten Benutzers in einen Ordner – z. B. vor einer Neuinstallation.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. Benutzerdaten sichern [Risiko: gelb]
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
# Schritt 1/1: Benutzerdaten sichern (Risiko: gelb)
# --------------------------------------------------------------------
OKM_SCHRITT='1/1 (Benutzerdaten sichern)'
printf '%s\n' '[1/1] Benutzerdaten werden nach /media/usb/Sicherung gesichert …'
okm_ziel='/media/usb/Sicherung'
okm_ziel="$okm_ziel/$(id -un)_$(date +%Y-%m-%d_%H%M)"
mkdir -p "$okm_ziel"
for okm_ordner in Desktop Documents Pictures; do
  if [ -d "$HOME/$okm_ordner" ]; then
    printf 'Sichere %s …\n' "$okm_ordner"
    cp -a "$HOME/$okm_ordner" "$okm_ziel/"
  fi
done
printf 'Gesichert nach: %s\n' "$okm_ziel"
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
