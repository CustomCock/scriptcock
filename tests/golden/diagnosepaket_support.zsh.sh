#!/bin/zsh
# ======================================================================
# Titel:             Diagnosepaket für den Support erstellen
# Beschreibung:      Sammelt Systeminformationen, Netzwerkeinstellungen und Protokolle in einer Datei, die du an den Support schicken kannst.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. Systeminfo anzeigen [Risiko: gruen]
#    2. Diagnosepaket erstellen [Risiko: gelb]
#    3. Meldung/Pause für den Benutzer [Risiko: gruen]
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
okm_info ' okm Script-Baukasten · Diagnosepaket für den Support erstellen'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# --------------------------------------------------------------------
# Schritt 1/3: Systeminfo anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/3 (Systeminfo anzeigen)'
OKM_TIPP=''
okm_info '[1/3] Systeminformationen werden gesammelt ...'
printf 'Rechnername:    %s\n' "$(scutil --get ComputerName 2>/dev/null || hostname)"
sw_vers
printf 'Prozessor:      %s\n' "$(sysctl -n machdep.cpu.brand_string)"
printf 'RAM gesamt:     %s GB\n' "$(( $(sysctl -n hw.memsize) / 1073741824 ))"
printf 'Laufzeit:      %s\n' "$(uptime)"
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 2/3: Diagnosepaket erstellen (Risiko: gelb)
# --------------------------------------------------------------------
OKM_NR=2
OKM_SCHRITT='2/3 (Diagnosepaket erstellen)'
OKM_TIPP=''
okm_info '[2/3] Diagnosepaket wird erstellt (das kann etwas dauern) ...'
okm_stempel="$(date +%Y%m%d-%H%M%S)"
okm_arbeit="$(mktemp -d)"
{ sw_vers; uname -a; uptime; df -h; } > "$okm_arbeit/system.txt" 2>&1 || true
system_profiler SPHardwareDataType SPSoftwareDataType >> "$okm_arbeit/system.txt" 2>&1 || true
{ ifconfig; netstat -rn; scutil --dns; } > "$okm_arbeit/netzwerk.txt" 2>&1 || true
log show --last 24h --predicate 'messageType == error' --style compact > "$okm_arbeit/log.txt" 2>&1 || true
ps aux > "$okm_arbeit/prozesse.txt" 2>&1 || true
okm_paket="$HOME/Desktop/okm-diagnose-$(hostname -s)-$okm_stempel.zip"
ditto -c -k "$okm_arbeit" "$okm_paket"
rm -rf -- "$okm_arbeit"
printf 'Diagnosepaket erstellt: %s\n' "$okm_paket"
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 3/3: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=3
OKM_SCHRITT='3/3 (Meldung/Pause für den Benutzer)'
OKM_TIPP=''
okm_info '[3/3] Hinweis für den Benutzer ...'
printf '%s\n' 'Fertig! Bitte die erstellte Datei an den Support schicken (Pfad siehe oben).'
read -r 'okm_weiter?Weiter mit Enter ... ' || true
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
