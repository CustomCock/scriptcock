#!/usr/bin/env bash
# ======================================================================
# Titel:             Netzwerkproblem diagnostizieren
# Beschreibung:      Prüft Schritt für Schritt Netzwerkeinstellungen, Router, Internet, Namensauflösung und ob ein bestimmter Server erreichbar ist (Ping, Traceroute, Port).
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
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

set -Eeuo pipefail

OKM_LOG="${TMPDIR:-/tmp}/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=7
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
okm_info ' okm Script-Baukasten · Netzwerkproblem diagnostizieren'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# --------------------------------------------------------------------
# Schritt 1/7: IP-Konfiguration anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/7 (IP-Konfiguration anzeigen)'
OKM_TIPP=''
okm_info '[1/7] IP-Konfiguration wird angezeigt ...'
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
okm_ok

# --------------------------------------------------------------------
# Schritt 2/7: Standard-Gateway anpingen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=2
OKM_SCHRITT='2/7 (Standard-Gateway anpingen)'
OKM_TIPP=''
okm_info '[2/7] Standard-Gateway wird geprüft ...'
okm_gateway="$(ip route show default | awk '{print $3; exit}')"
if [ -z "$okm_gateway" ]; then
  printf '%s\n' 'Kein Standard-Gateway gefunden – keine Netzwerkverbindung?'
else
  printf 'Standard-Gateway: %s\n' "$okm_gateway"
  ping -c 4 "$okm_gateway" || printf '%s\n' 'Hinweis: Das Gateway antwortet nicht.'
fi
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 3/7: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=3
OKM_SCHRITT='3/7 (Ping auf Ziel)'
OKM_TIPP='Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping.'
okm_info '[3/7] Ping auf 1.1.1.1 (2x) ...'
ping -c 2 '1.1.1.1' || printf '%s\n' 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.'
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 4/7: Namensauflösung (DNS) testen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=4
OKM_SCHRITT='4/7 (Namensauflösung (DNS) testen)'
OKM_TIPP=''
okm_info '[4/7] DNS-Auflösung von www.microsoft.com wird geprüft ...'
getent ahosts 'www.microsoft.com' || printf '%s\n' 'Der Name kann NICHT aufgelöst werden.'
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 5/7: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=5
OKM_SCHRITT='5/7 (Ping auf Ziel)'
OKM_TIPP='Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping.'
okm_info '[5/7] Ping auf intranet.okm.local (4x) ...'
ping -c 4 'intranet.okm.local' || printf '%s\n' 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.'
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 6/7: Traceroute (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=6
OKM_SCHRITT='6/7 (Traceroute)'
OKM_TIPP=''
okm_info '[6/7] Traceroute zu intranet.okm.local ...'
if command -v traceroute >/dev/null 2>&1; then
  traceroute -n 'intranet.okm.local' || true
elif command -v tracepath >/dev/null 2>&1; then
  tracepath -n 'intranet.okm.local' || true
else
  printf '%s\n' 'Weder traceroute noch tracepath ist installiert (Debian/Ubuntu: apt install traceroute).'
fi
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 7/7: Port erreichbar prüfen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=7
OKM_SCHRITT='7/7 (Port erreichbar prüfen)'
OKM_TIPP='Läuft der Dienst auf dem Zielrechner, und lässt die Firewall den Port durch?'
okm_info '[7/7] Port 443 auf intranet.okm.local wird geprüft ...'
if timeout 5 bash -c 'exec 3<>"/dev/tcp/$1/$2"' okm 'intranet.okm.local' 443 2>/dev/null; then
  printf '%s\n' 'Der Port ist erreichbar.'
else
  printf '%s\n' 'Der Port ist NICHT erreichbar.'
fi
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
okm_zusammenfassung
