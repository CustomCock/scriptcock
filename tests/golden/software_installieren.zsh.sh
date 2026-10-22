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

TRAPZERR() {
  local okm_rc=$?
  okm_fehler "Schritt $OKM_SCHRITT: Befehl endete mit Exit-Code $okm_rc."
  if [ -n "$OKM_TIPP" ]; then okm_info "      Tipp: $OKM_TIPP"; fi
  OKM_STATUS=fehler
  okm_zusammenfassung
  exit "$okm_rc"
}

okm_info '=============================================='
okm_info ' okm Script-Baukasten · Software installieren'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# --------------------------------------------------------------------
# Schritt 1/1: Paket/Software installieren (Risiko: gelb)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/1 (Paket/Software installieren)'
OKM_TIPP='Paket-ID im Software-Katalog prüfen. Ist das Programm schon installiert, meldet der Paketmanager ebenfalls einen Fehler.'
okm_info '[1/1] Mozilla.Firefox wird installiert ...'
if ! command -v brew >/dev/null 2>&1; then
  printf '%s\n' 'Homebrew ist nicht installiert (siehe https://brew.sh). Bitte an die IT wenden.'
  false
fi
brew install 'Mozilla.Firefox'
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
okm_zusammenfassung
