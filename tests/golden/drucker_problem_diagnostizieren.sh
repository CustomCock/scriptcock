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
# Schritt 1/4: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/4 (Ping auf Ziel)'
printf '%s\n' '[1/4] Ping auf 192.168.1.50 (2x) …'
ping -c 2 '192.168.1.50' || printf '%s\n' 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.'
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/4: Drucker-Erreichbarkeit prüfen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/4 (Drucker-Erreichbarkeit prüfen)'
printf '%s\n' '[2/4] Drucker 192.168.1.50 wird geprüft …'
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

# --------------------------------------------------------------------
# Schritt 3/4: Dienst-Status prüfen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/4 (Dienst-Status prüfen)'
printf '%s\n' '[3/4] Status von Dienst cups wird abgefragt …'
systemctl --no-pager status 'cups' || [ $? -eq 3 ]
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 4/4: Installierte Drucker auflisten (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='4/4 (Installierte Drucker auflisten)'
printf '%s\n' '[4/4] Drucker werden aufgelistet …'
lpstat -p -d || printf '%s\n' 'Keine Drucker eingerichtet (oder CUPS nicht installiert).'
lpstat -v || true
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
