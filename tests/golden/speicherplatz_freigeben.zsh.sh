#!/bin/zsh
# ======================================================================
# Titel:             Speicherplatz freigeben
# Beschreibung:      Zeigt die Festplattenbelegung, löscht alte temporäre Dateien und zeigt danach, wie viel Platz frei ist.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. Festplattenbelegung anzeigen [Risiko: gruen]
#    2. Temp-Ordner aufräumen [Risiko: rot]
#    3. Festplattenbelegung anzeigen [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

setopt ERR_EXIT NO_UNSET PIPE_FAIL

OKM_LOG="${TMPDIR:-/tmp}/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=3
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
okm_info ' okm Script-Baukasten · Speicherplatz freigeben'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# --------------------------------------------------------------------
# Schritt 1/3: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/3 (Festplattenbelegung anzeigen)'
OKM_TIPP=''
okm_info '[1/3] Festplattenbelegung wird ermittelt ...'
df -h -l
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 2/3: Temp-Ordner aufräumen (Risiko: rot)
# --------------------------------------------------------------------
OKM_NR=2
OKM_SCHRITT='2/3 (Temp-Ordner aufräumen)'
OKM_TIPP=''
okm_info '[2/3] Temporäre Dateien älter als 7 Tage werden gelöscht ...'
okm_warn 'ACHTUNG: Dieser Schritt ist destruktiv: Temp-Ordner aufräumen'
okm_antwort=""
read -r 'okm_antwort?Zum Fortfahren JA eingeben (alles andere bricht ab): ' || true
if [ "$okm_antwort" != "JA" ]; then
  OKM_STATUS=abbruch
  okm_zusammenfassung
  exit 2
fi
find "${TMPDIR:-/tmp}" -mindepth 1 -type f -mtime +7 -delete 2>/dev/null || true
printf '%s\n' 'Aufräumen abgeschlossen.'
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 3/3: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=3
OKM_SCHRITT='3/3 (Festplattenbelegung anzeigen)'
OKM_TIPP=''
okm_info '[3/3] Festplattenbelegung wird ermittelt ...'
df -h -l
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
okm_zusammenfassung
