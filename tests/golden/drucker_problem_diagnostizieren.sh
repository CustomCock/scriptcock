#!/usr/bin/env bash
# ======================================================================
# Titel:             Drucker-Problem diagnostizieren
# Beschreibung:      Prüft, ob der Drucker im Netz erreichbar ist, ob der Druckdienst läuft und welche Drucker eingerichtet sind.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Benötigte Rechte:  keine
# Enthaltene Schritte:
#    1. Ping auf Ziel [Risiko: gruen]
#    2. Drucker-Erreichbarkeit prüfen [Risiko: gruen]
#    3. Dienst-Status prüfen [Risiko: gruen]
#    4. Installierte Drucker auflisten [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

set -Eeuo pipefail

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
  read -r -p 'Drücke Enter zum Schließen …' _ || true
}
okm_bei_fehler() {
  local okm_rc=$1 okm_zeile=$2 okm_befehl=$3
  trap - ERR
  okm_fehler "Schritt $OKM_SCHRITT: Befehl endete mit Exit-Code $okm_rc."
  okm_info "      Zeile $okm_zeile, Befehl: $okm_befehl"
  if [ -n "$OKM_TIPP" ]; then okm_info "      Tipp: $OKM_TIPP"; fi
  OKM_STATUS=fehler
  exit "$okm_rc"
}
trap 'okm_bei_fehler $? $LINENO "$BASH_COMMAND"' ERR

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
okm_info ' okm Script-Baukasten · Drucker-Problem diagnostizieren'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

okm_info 'Rechte: ohne erhöhte Rechte'

# Rückgabewerte der Schritte (Namen vergibt der Baukasten; leer = unbekannt)
okm_s1_erreichbar=''
okm_s1_ms=''
okm_s3_laeuft=''

# --------------------------------------------------------------------
# Schritt 1/4: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/4 (Ping auf Ziel)'
OKM_TIPP='Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping.'
okm_info '[1/4] Ping auf 192.168.1.50 (2x) ...'
okm_rc=0
okm_ausgabe=$(ping -c 2 '192.168.1.50' 2>&1) || okm_rc=$?
printf '%s\n' "$okm_ausgabe"
if [ "$okm_rc" -eq 0 ]; then
  okm_s1_erreichbar=1
  # "rtt min/avg/max/mdev = 11.1/12.6/…" (Linux) bzw. "round-trip min/avg/…" (macOS)
  okm_s1_ms=$(printf '%s\n' "$okm_ausgabe" | awk -F/ '/min\/avg/ { printf "%.0f", $5 }')
else
  okm_s1_erreichbar=0
  printf '%s\n' 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.'
fi
case "$okm_s1_erreichbar" in 1|true|ja) okm_s1_erreichbar=1 ;; '') ;; *) okm_s1_erreichbar=0 ;; esac
[[ $okm_s1_ms =~ ^-?[0-9]+$ ]] || okm_s1_ms=''
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 2/4: Drucker-Erreichbarkeit prüfen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=2
OKM_SCHRITT='2/4 (Drucker-Erreichbarkeit prüfen)'
OKM_TIPP=''
okm_info '[2/4] Drucker 192.168.1.50 wird geprüft ...'
okm_drucker='192.168.1.50'
if ping -c 2 "$okm_drucker" >/dev/null 2>&1; then printf '%s\n' 'Ping: antwortet'; else printf '%s\n' 'Ping: keine Antwort'; fi
for okm_port in 9100 631 515; do
  if timeout 3 bash -c 'exec 3<>"/dev/tcp/$1/$2"' okm "$okm_drucker" "$okm_port" 2>/dev/null; then
    printf 'Port %s: offen\n' "$okm_port"
  else
    printf 'Port %s: geschlossen\n' "$okm_port"
  fi
done
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 3/4: Dienst-Status prüfen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=3
OKM_SCHRITT='3/4 (Dienst-Status prüfen)'
OKM_TIPP=''
okm_info '[3/4] Status von Dienst cups wird abgefragt ...'
# Exit-Codes von systemctl status: 0 läuft, 3 gestoppt, 4 unbekannt – Ergebnis, kein Fehler
okm_rc=0
systemctl --no-pager status 'cups' || okm_rc=$?
okm_s3_laeuft=0
case "$okm_rc" in
  0) okm_s3_laeuft=1 ;;
  3) okm_warn 'Der Dienst ist vorhanden, läuft aber nicht.' ;;
  4) okm_warn 'Diesen Dienst gibt es nicht.' ;;
  *) okm_fehler "systemctl endete mit Exit-Code $okm_rc."; false ;;
esac
case "$okm_s3_laeuft" in 1|true|ja) okm_s3_laeuft=1 ;; '') ;; *) okm_s3_laeuft=0 ;; esac
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 4/4: Installierte Drucker auflisten (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=4
OKM_SCHRITT='4/4 (Installierte Drucker auflisten)'
OKM_TIPP=''
okm_info '[4/4] Drucker werden aufgelistet ...'
lpstat -p -d || printf '%s\n' 'Keine Drucker eingerichtet (oder CUPS nicht installiert).'
lpstat -v || true
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
