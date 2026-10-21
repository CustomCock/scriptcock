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

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=3
OKM_OK=0
OKM_SCHRITT='-'
exec > >(tee -a "$OKM_LOG") 2>&1

okm_fehler() {
  local okm_rc=$?
  trap - ERR
  printf '\nFEHLER in Schritt %s (Exit-Code %s).\n' "$OKM_SCHRITT" "$okm_rc"
  printf 'Erfolgreich bis dahin: %s von %s Schritten.\n' "$OKM_OK" "$OKM_GESAMT"
  printf 'Protokoll: %s\n' "$OKM_LOG"
  exit "$okm_rc"
}
trap okm_fehler ERR

# --------------------------------------------------------------------
# Schritt 1/3: Systeminfo anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/3 (Systeminfo anzeigen)'
printf '%s\n' '[1/3] Systeminformationen werden gesammelt …'
printf 'Rechnername:    %s\n' "$(hostname)"
printf 'Betriebssystem: %s\n' "$(grep -m1 '^PRETTY_NAME=' /etc/os-release | cut -d= -f2- | tr -d '"')"
printf 'Kernel:         %s\n' "$(uname -r)"
printf 'Laufzeit:       %s\n' "$(uptime -p)"
free -h
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/3: Diagnosepaket erstellen (Risiko: gelb)
# --------------------------------------------------------------------
OKM_SCHRITT='2/3 (Diagnosepaket erstellen)'
printf '%s\n' '[2/3] Diagnosepaket wird erstellt (das kann etwas dauern) …'
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

# --------------------------------------------------------------------
# Schritt 3/3: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/3 (Meldung/Pause für den Benutzer)'
printf '%s\n' '[3/3] Hinweis für den Benutzer …'
printf '%s\n' 'Fertig! Bitte die erstellte Datei an den Support schicken (Pfad siehe oben).'
read -r -p 'Weiter mit Enter ... ' _ || true
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
