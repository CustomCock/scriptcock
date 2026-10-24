#!/bin/zsh
# ======================================================================
# Titel:             Standardsoftware installieren
# Beschreibung:      Installiert mehrere Programme auf einmal – z. B. die übliche Ausstattung eines Arbeitsplatzes. Fehlgeschlagene Pakete werden am Ende aufgelistet.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Benötigte Rechte:  nicht als root starten (Schritt 1)
# Enthaltene Schritte:
#    1. Mehrere Pakete installieren [Risiko: gelb]
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
OKM_GESAMT=1
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
okm_info ' okm Script-Baukasten · Standardsoftware installieren'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# Schritte, die NICHT als root laufen dürfen (z. B. Homebrew verweigert root)
if [ "$(id -u)" -eq 0 ]; then
  okm_fehler 'Dieses Script darf nicht als root (mit sudo) gestartet werden: Schritt 1 (Mehrere Pakete installieren).'
  okm_info '      Bitte ohne sudo starten – das Script fragt selbst, wenn es sudo braucht.'
  OKM_STATUS=rechte
  exit 1
fi
okm_info 'Rechte: ohne erhöhte Rechte'

# Rückgabewerte der Schritte (Namen vergibt der Baukasten; leer = unbekannt)
okm_s1_fehlgeschlagen=''

# --------------------------------------------------------------------
# Schritt 1/1: Mehrere Pakete installieren (Risiko: gelb)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/1 (Mehrere Pakete installieren)'
OKM_TIPP='Die Paket-IDs im Software-Katalog prüfen; die nicht installierten stehen in der Meldung oben.'
okm_info '[1/1] Pakete werden installiert: Mozilla.Firefox, 7zip.7zip, VideoLAN.VLC ...'
okm_pakete=('Mozilla.Firefox' '7zip.7zip' 'VideoLAN.VLC')
okm_fehlt=()
if ! command -v brew >/dev/null 2>&1; then
  okm_fehlt=("${okm_pakete[@]}")
  okm_fehler 'Homebrew ist nicht installiert (siehe https://brew.sh) – bitte an die IT wenden.'
else
  for okm_p in "${okm_pakete[@]}"; do
    okm_info "--- $okm_p"
    brew install "$okm_p" || okm_fehlt+=("$okm_p")
  done
fi
set -- "${okm_fehlt[@]}"
okm_s1_fehlgeschlagen=$#
if [[ $# -gt 0 ]]; then
  okm_fehler "Nicht installiert: ${okm_fehlt[*]}"
  false
else
  okm_ok 'Alle Pakete installiert.'
fi
[[ $okm_s1_fehlgeschlagen =~ ^-?[0-9]+$ ]] || okm_s1_fehlgeschlagen=''
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
