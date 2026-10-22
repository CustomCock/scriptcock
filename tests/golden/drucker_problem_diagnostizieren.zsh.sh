#!/bin/zsh
# ======================================================================
# Titel:             Drucker-Problem diagnostizieren
# Beschreibung:      Prüft, ob der Drucker im Netz erreichbar ist, ob der Druckdienst läuft und welche Drucker eingerichtet sind.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. Ping auf Ziel [Risiko: gruen]
#    2. Drucker-Erreichbarkeit prüfen [Risiko: gruen]
#    3. Installierte Drucker auflisten [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

setopt ERR_EXIT NO_UNSET PIPE_FAIL

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=3
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
# Schritt 1/3: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/3 (Ping auf Ziel)'
printf '%s\n' '[1/3] Ping auf 192.168.1.50 (2x) …'
ping -c 2 '192.168.1.50' || printf '%s\n' 'Hinweis: Das Ziel hat nicht (vollständig) geantwortet.'
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/3: Drucker-Erreichbarkeit prüfen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/3 (Drucker-Erreichbarkeit prüfen)'
printf '%s\n' '[2/3] Drucker 192.168.1.50 wird geprüft …'
okm_drucker='192.168.1.50'
if ping -c 2 "$okm_drucker" >/dev/null 2>&1; then printf '%s\n' 'Ping: antwortet'; else printf '%s\n' 'Ping: keine Antwort'; fi
for okm_port in 9100 631 515; do
  if nc -z -G 3 "$okm_drucker" "$okm_port" 2>/dev/null; then
    printf 'Port %s: offen\n' "$okm_port"
  else
    printf 'Port %s: geschlossen\n' "$okm_port"
  fi
done
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 3/3: Installierte Drucker auflisten (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/3 (Installierte Drucker auflisten)'
printf '%s\n' '[3/3] Drucker werden aufgelistet …'
lpstat -p -d || printf '%s\n' 'Keine Drucker eingerichtet.'
lpstat -v || true
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
