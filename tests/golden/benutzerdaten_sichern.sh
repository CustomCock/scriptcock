#!/usr/bin/env bash
# ======================================================================
# Titel:             Benutzerdaten sichern
# Beschreibung:      Kopiert Desktop, Dokumente, Bilder, Downloads usw. des angemeldeten Benutzers in einen Ordner – z. B. vor einer Neuinstallation.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. Benutzerdaten sichern [Risiko: gelb]
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

# --------------------------------------------------------------------
# Schritt 1/1: Benutzerdaten sichern (Risiko: gelb)
# --------------------------------------------------------------------
OKM_SCHRITT='1/1 (Benutzerdaten sichern)'
printf '%s\n' '[1/1] Benutzerdaten werden nach /media/usb/Sicherung gesichert …'
okm_ziel='/media/usb/Sicherung'
okm_ziel="$okm_ziel/$(id -un)_$(date +%Y-%m-%d_%H%M)"
mkdir -p -- "$okm_ziel"
for okm_typ in DESKTOP DOCUMENTS PICTURES; do
  okm_quelle="$(xdg-user-dir "$okm_typ" 2>/dev/null || true)"
  if [ -z "$okm_quelle" ] || [ "$okm_quelle" = "$HOME" ] || [ ! -d "$okm_quelle" ]; then continue; fi
  printf 'Sichere %s …\n' "$okm_quelle"
  cp -a -- "$okm_quelle" "$okm_ziel/"
done
printf 'Gesichert nach: %s\n' "$okm_ziel"
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
