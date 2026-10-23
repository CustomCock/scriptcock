#!/bin/zsh
# ======================================================================
# Titel:             Seriennummer und Inventar erfassen
# Beschreibung:      Sammelt Seriennummer, Hardware, Betriebssystem, Lizenzstatus und installierte Programme für die Inventarisierung.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Benötigte Rechte:  keine
# Enthaltene Schritte:
#    1. Seriennummer und Modell [Risiko: gruen]
#    2. Systeminfo anzeigen [Risiko: gruen]
#    3. Letzter Neustart und ausstehender Neustart [Risiko: gruen]
#    4. Installierte Software auflisten [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

setopt ERR_EXIT PIPE_FAIL

# --nopause: am Ende nicht auf Enter warten (Fernwartung/RMM)
OKM_KEINE_PAUSE=0
for okm_arg in "$@"; do
  if [ "$okm_arg" = --nopause ]; then OKM_KEINE_PAUSE=1; fi
done
OKM_LOG="${TMPDIR:-/tmp}/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=4
OKM_OK=0
OKM_NR=0
OKM_SCHRITT='-'
OKM_STATUS=laeuft
OKM_TIPP=''
OKM_SUDO_PID=''

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
# Fenster/Terminal offen halten – nur wenn ein Mensch davor sitzt
okm_pause() {
  if [ "$OKM_KEINE_PAUSE" = 1 ] || [ ! -t 0 ]; then return 0; fi
  read -r 'okm_weiter?Drücke Enter zum Schließen …' || true
}
okm_bei_fehler() {
  local okm_rc=$1 okm_zeile=$2
  okm_fehler "Schritt $OKM_SCHRITT: Befehl endete mit Exit-Code $okm_rc."
  okm_info "      Zeile $okm_zeile"
  if [ -n "$OKM_TIPP" ]; then okm_info "      Tipp: $OKM_TIPP"; fi
  OKM_STATUS=fehler
  exit "$okm_rc"
}
trap 'okm_bei_fehler $? $LINENO' ZERR

# Zusammenfassung bei JEDEM Ende – auch bei Fehlern, die kein ERR auslösen
# (z. B. nicht gesetzte Variable) oder einem Abbruch ohne Meldung.
okm_ende() {
  local okm_rc=$?
  if [ "$OKM_STATUS" = laeuft ]; then
    if [ "$okm_rc" -eq 0 ]; then
      OKM_STATUS=fertig
    else
      okm_fehler "Script unerwartet beendet in Schritt $OKM_SCHRITT (Exit-Code $okm_rc)."
      OKM_STATUS=fehler
    fi
  fi
  okm_zusammenfassung
  if [ -n "$OKM_SUDO_PID" ]; then kill "$OKM_SUDO_PID" 2>/dev/null || true; fi
  okm_pause
  # Ausgabe schließen und kurz auf tee warten, sonst fehlen beim Schließen des Fensters
  # die letzten Zeilen (höchstens 2 s – ein Hintergrundprozess darf nichts aufhalten)
  exec 1>&- 2>&-
  okm_i=0
  while [ "$okm_i" -lt 20 ] && kill -0 "${OKM_TEE:-0}" 2>/dev/null; do
    sleep 0.1
    okm_i=$((okm_i + 1))
  done
  exit "$okm_rc"
}
trap okm_ende EXIT

# Ausgabe zusätzlich ins Protokoll – über eine FIFO statt >(tee), damit das Script am Ende
# auf tee warten kann (zsh verliert sonst die komplette Ausgabe, wenn das Fenster zugeht).
OKM_TMPDIR="$(mktemp -d)"
mkfifo -m 600 "$OKM_TMPDIR/ausgabe"
tee -a "$OKM_LOG" < "$OKM_TMPDIR/ausgabe" &
OKM_TEE=$!
exec > "$OKM_TMPDIR/ausgabe" 2>&1
rm -rf "$OKM_TMPDIR"

okm_info '=============================================='
okm_info ' okm Script-Baukasten · Seriennummer und Inventar erfassen'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

okm_info 'Rechte: ohne erhöhte Rechte'

# --------------------------------------------------------------------
# Schritt 1/4: Seriennummer und Modell (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/4 (Seriennummer und Modell)'
OKM_TIPP=''
okm_info '[1/4] Hardware-Daten werden gelesen ...'
printf 'Modell:         %s\n' "$(sysctl -n hw.model)"
printf 'Seriennummer:   %s\n' "$(ioreg -c IOPlatformExpertDevice -d 2 | awk -F'"' '/IOPlatformSerialNumber/ {print $4}')"
printf 'Prozessor:      %s\n' "$(sysctl -n machdep.cpu.brand_string)"
sw_vers
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 2/4: Systeminfo anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=2
OKM_SCHRITT='2/4 (Systeminfo anzeigen)'
OKM_TIPP=''
okm_info '[2/4] Systeminformationen werden gesammelt ...'
printf 'Rechnername:    %s\n' "$(scutil --get ComputerName 2>/dev/null || hostname)"
sw_vers
printf 'Prozessor:      %s\n' "$(sysctl -n machdep.cpu.brand_string)"
printf 'RAM gesamt:     %s GB\n' "$(( $(sysctl -n hw.memsize) / 1073741824 ))"
printf 'Laufzeit:      %s\n' "$(uptime)"
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 3/4: Letzter Neustart und ausstehender Neustart (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=3
OKM_SCHRITT='3/4 (Letzter Neustart und ausstehender Neustart)'
OKM_TIPP=''
okm_info '[3/4] Startzeit und ausstehende Neustarts werden geprüft ...'
printf 'Letzter Start: %s\n' "$(sysctl -n kern.boottime)"
uptime
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 4/4: Installierte Software auflisten (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=4
OKM_SCHRITT='4/4 (Installierte Software auflisten)'
OKM_TIPP=''
okm_info '[4/4] Installierte Software wird gelesen ...'
for okm_app in /Applications/*.app; do
  okm_version="$(defaults read "$okm_app/Contents/Info" CFBundleShortVersionString 2>/dev/null || printf '%s' '?')"
  printf '%-45s %s\n' "$(basename "$okm_app" .app)" "$okm_version"
done
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
