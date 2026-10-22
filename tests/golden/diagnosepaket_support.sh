#!/usr/bin/env bash
# ======================================================================
# Titel:             Diagnosepaket für den Support erstellen
# Beschreibung:      Sammelt Systeminformationen, Netzwerkeinstellungen und Protokolle in einer Datei, die du an den Support schicken kannst.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. Systeminfo anzeigen [Risiko: gruen]
#    2. Diagnosepaket erstellen [Risiko: gelb]
#    3. Meldung/Pause für den Benutzer [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

set -Eeuo pipefail

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
printf 'Rechnername:    %s\n' "$(hostname)"
printf 'Betriebssystem: %s\n' "$(grep -m1 '^PRETTY_NAME=' /etc/os-release | cut -d= -f2- | tr -d '"')"
printf 'Kernel:         %s\n' "$(uname -r)"
printf 'Prozessor:     %s (%s Threads)\n' "$(awk -F: '/model name/ {print $2; exit}' /proc/cpuinfo)" "$(nproc)"
printf 'Laufzeit:       %s\n' "$(uptime -p)"
free -h
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
{ uname -a; cat /etc/os-release; uptime; free -h; df -h; } > "$okm_arbeit/system.txt" 2>&1 || true
{ ip address; ip route; cat /etc/resolv.conf; } > "$okm_arbeit/netzwerk.txt" 2>&1 || true
journalctl --no-pager -p warning -n 1000 > "$okm_arbeit/journal.txt" 2>&1 || true
ps aux > "$okm_arbeit/prozesse.txt" 2>&1 || true
okm_paket="$HOME/okm-diagnose-$(hostname)-$okm_stempel.tar.gz"
tar -czf "$okm_paket" -C "$okm_arbeit" .
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
read -r -p 'Weiter mit Enter ... ' _ || true
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
okm_zusammenfassung
