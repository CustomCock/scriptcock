#!/usr/bin/env bash
# ======================================================================
# Titel:             Drucker-Problem diagnostizieren
# Beschreibung:      Prüft, ob der Drucker im Netz erreichbar ist, ob der Druckdienst läuft und welche Drucker eingerichtet sind.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. Ping auf Ziel [Risiko: gruen]
#    2. Drucker-Erreichbarkeit prüfen [Risiko: gruen]
#    3. Dienst-Status prüfen [Risiko: gruen]
#    4. Installierte Drucker auflisten [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

set -Eeuo pipefail

OKM_LOG="${TMPDIR:-/tmp}/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=4
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
okm_info ' okm Script-Baukasten · Drucker-Problem diagnostizieren'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# --------------------------------------------------------------------
# Schritt 1/4: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/4 (Ping auf Ziel)'
OKM_TIPP='Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping.'
okm_info '[1/4] Ping auf 192.168.1.50 (2x) ...'
ping -c 2 '192.168.1.50' || printf '%s\n' 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.'
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
systemctl --no-pager status 'cups' || [ $? -eq 3 ]
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
okm_zusammenfassung
