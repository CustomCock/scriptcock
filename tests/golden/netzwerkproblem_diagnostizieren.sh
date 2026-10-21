#!/usr/bin/env bash
# ======================================================================
# Titel:             Netzwerkproblem diagnostizieren
# Beschreibung:      Zeigt die Netzwerkeinstellungen und prüft Schritt für Schritt, ob ein Server erreichbar ist (Ping, Traceroute, Port).
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. IP-Konfiguration anzeigen [Risiko: gruen]
#    2. Ping auf Ziel [Risiko: gruen]
#    3. Traceroute [Risiko: gruen]
#    4. Port erreichbar prüfen [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

set -Eeuo pipefail

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=4
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
# Schritt 1/4: IP-Konfiguration anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/4 (IP-Konfiguration anzeigen)'
printf '%s\n' '[1/4] IP-Konfiguration wird angezeigt …'
ip -brief address
printf '\nStandard-Gateway:\n'
ip route show default
printf '\nDNS-Server:\n'
if command -v resolvectl >/dev/null 2>&1 && systemctl is-active --quiet systemd-resolved; then
  resolvectl dns
else
  grep '^nameserver' /etc/resolv.conf || true
fi
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/4: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/4 (Ping auf Ziel)'
printf '%s\n' '[2/4] Ping auf intranet.okm.local (4x) …'
ping -c 4 'intranet.okm.local' || printf '%s\n' 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.'
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 3/4: Traceroute (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/4 (Traceroute)'
printf '%s\n' '[3/4] Traceroute zu intranet.okm.local …'
if command -v traceroute >/dev/null 2>&1; then
  traceroute -n 'intranet.okm.local' || true
elif command -v tracepath >/dev/null 2>&1; then
  tracepath -n 'intranet.okm.local' || true
else
  printf '%s\n' 'Weder traceroute noch tracepath ist installiert (Debian/Ubuntu: apt install traceroute).'
fi
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 4/4: Port erreichbar prüfen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='4/4 (Port erreichbar prüfen)'
printf '%s\n' '[4/4] Port 443 auf intranet.okm.local wird geprüft …'
if timeout 5 bash -c 'exec 3<>"/dev/tcp/$1/$2"' okm 'intranet.okm.local' 443 2>/dev/null; then
  printf '%s\n' 'Der Port ist erreichbar.'
else
  printf '%s\n' 'Der Port ist NICHT erreichbar.'
fi
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
