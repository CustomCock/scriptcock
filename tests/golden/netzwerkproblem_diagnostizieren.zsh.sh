#!/bin/zsh
# ======================================================================
# Titel:             Netzwerkproblem diagnostizieren
# Beschreibung:      Prüft Schritt für Schritt Netzwerkeinstellungen, Router, Internet, Namensauflösung und ob ein bestimmter Server erreichbar ist (Ping, Traceroute, Port).
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. IP-Konfiguration anzeigen [Risiko: gruen]
#    2. Standard-Gateway anpingen [Risiko: gruen]
#    3. Ping auf Ziel [Risiko: gruen]
#    4. Namensauflösung (DNS) testen [Risiko: gruen]
#    5. Ping auf Ziel [Risiko: gruen]
#    6. Traceroute [Risiko: gruen]
#    7. Port erreichbar prüfen [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

setopt ERR_EXIT NO_UNSET PIPE_FAIL

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=7
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
# Schritt 1/7: IP-Konfiguration anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/7 (IP-Konfiguration anzeigen)'
printf '%s\n' '[1/7] IP-Konfiguration wird angezeigt …'
ifconfig | grep -E '^[a-z0-9]+:|inet ' || true
printf '\nStandard-Gateway:\n'
route -n get default 2>/dev/null | grep -E 'gateway|interface' || true
printf '\nDNS-Server:\n'
scutil --dns | grep 'nameserver\[' | sort -u || true
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/7: Standard-Gateway anpingen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/7 (Standard-Gateway anpingen)'
printf '%s\n' '[2/7] Standard-Gateway wird geprüft …'
okm_gateway="$(route -n get default 2>/dev/null | awk '/gateway:/ {print $2}')"
if [ -z "$okm_gateway" ]; then
  printf '%s\n' 'Kein Standard-Gateway gefunden – keine Netzwerkverbindung?'
else
  printf 'Standard-Gateway: %s\n' "$okm_gateway"
  ping -c 4 "$okm_gateway" || printf '%s\n' 'Hinweis: Das Gateway antwortet nicht.'
fi
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 3/7: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/7 (Ping auf Ziel)'
printf '%s\n' '[3/7] Ping auf 1.1.1.1 (2x) …'
ping -c 2 '1.1.1.1' || printf '%s\n' 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.'
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 4/7: Namensauflösung (DNS) testen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='4/7 (Namensauflösung (DNS) testen)'
printf '%s\n' '[4/7] DNS-Auflösung von www.microsoft.com wird geprüft …'
dscacheutil -q host -a name 'www.microsoft.com'
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 5/7: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='5/7 (Ping auf Ziel)'
printf '%s\n' '[5/7] Ping auf intranet.okm.local (4x) …'
ping -c 4 'intranet.okm.local' || printf '%s\n' 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.'
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 6/7: Traceroute (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='6/7 (Traceroute)'
printf '%s\n' '[6/7] Traceroute zu intranet.okm.local …'
traceroute -n 'intranet.okm.local' || true
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 7/7: Port erreichbar prüfen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='7/7 (Port erreichbar prüfen)'
printf '%s\n' '[7/7] Port 443 auf intranet.okm.local wird geprüft …'
if nc -z -G 5 'intranet.okm.local' 443 2>/dev/null; then
  printf '%s\n' 'Der Port ist erreichbar.'
else
  printf '%s\n' 'Der Port ist NICHT erreichbar.'
fi
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
