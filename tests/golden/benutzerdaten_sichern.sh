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

OKM_LOG="${TMPDIR:-/tmp}/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=1
OKM_OK=0
OKM_NR=0
OKM_SCHRITT='-'
OKM_STATUS=laeuft
OKM_TIPP=''

# Meldungen: Werte immer als Argumente übergeben, nie in den Formatstring einsetzen.
# Keine Farben – die Ausgabe geht auch ins Protokoll.
okm_info() { printf '%s\n' "$*"; }
# shellcheck disable=SC2120  # Text ist optional (Blöcke dürfen okm_ok "…" nutzen)
okm_ok() { if [ $# -gt 0 ]; then printf '      OK  %s\n' "$*"; else printf '%s\n' '      OK'; fi; }
okm_warn() { printf '      WARNUNG  %s\n' "$*"; }
okm_fehler() { printf '      FEHLER  %s\n' "$*"; }
okm_zusammenfassung() {
  okm_info '----------------------------------------------'
  case "$OKM_STATUS" in
    fertig) printf ' Fertig: %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT" ;;
    abbruch) okm_info ' Abgebrochen durch Benutzer. Es wurde nichts weiter ausgeführt.' ;;
    rechte) okm_info ' Abgebrochen: fehlende Rechte.' ;;
    *) printf ' Abgebrochen bei Schritt %s von %s.\n' "$OKM_NR" "$OKM_GESAMT"; printf ' Erfolgreich bis dahin: %s von %s Schritten.\n' "$OKM_OK" "$OKM_GESAMT" ;;
  esac
  printf ' Protokoll: %s\n' "$OKM_LOG"
  okm_info '----------------------------------------------'
}
exec > >(tee -a "$OKM_LOG") 2>&1

okm_bei_fehler() {
  local okm_rc=$?
  trap - ERR
  okm_fehler "Schritt $OKM_SCHRITT: Befehl endete mit Exit-Code $okm_rc."
  if [ -n "$OKM_TIPP" ]; then okm_info "      Tipp: $OKM_TIPP"; fi
  OKM_STATUS=fehler
  okm_zusammenfassung
  exit "$okm_rc"
}
trap okm_bei_fehler ERR

okm_info '=============================================='
okm_info ' okm Script-Baukasten · Benutzerdaten sichern'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# --------------------------------------------------------------------
# Schritt 1/1: Benutzerdaten sichern (Risiko: gelb)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/1 (Benutzerdaten sichern)'
OKM_TIPP=''
okm_info '[1/1] Benutzerdaten werden nach /media/usb/Sicherung gesichert ...'
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
okm_ok

OKM_STATUS=fertig
okm_zusammenfassung
