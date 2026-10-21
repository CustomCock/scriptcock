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

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=3
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
# Schritt 1/3: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/3 (Festplattenbelegung anzeigen)'
printf '%s\n' '[1/3] Festplattenbelegung wird ermittelt …'
df -h -l
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/3: Temp-Ordner aufräumen (Risiko: rot)
# --------------------------------------------------------------------
OKM_SCHRITT='2/3 (Temp-Ordner aufräumen)'
printf '%s\n' '[2/3] Temporäre Dateien älter als 7 Tage werden gelöscht …'
printf '%s\n' 'ACHTUNG: Dieser Schritt ist destruktiv: Temp-Ordner aufräumen'
okm_antwort=""
read -r 'okm_antwort?Zum Fortfahren JA eingeben (alles andere bricht ab): ' || true
if [ "$okm_antwort" != "JA" ]; then
  printf '%s\n' 'Abgebrochen. Es wurde nichts weiter ausgeführt.'
  printf 'Protokoll: %s\n' "$OKM_LOG"
  exit 2
fi
find "${TMPDIR:-/tmp}" -mindepth 1 -type f -mtime +7 -delete 2>/dev/null || true
printf '%s\n' 'Aufräumen abgeschlossen.'
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 3/3: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/3 (Festplattenbelegung anzeigen)'
printf '%s\n' '[3/3] Festplattenbelegung wird ermittelt …'
df -h -l
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
