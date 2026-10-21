#!/bin/zsh
# ======================================================================
# Titel:             Drucker einrichten
# Beschreibung:      Prüft, ob der Drucker im Netzwerk erreichbar ist, und richtet ihn anschließend über seine IP-Adresse ein.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. Ping auf Ziel [Risiko: gruen]
#    2. Drucker per IP hinzufügen [Risiko: gelb, Admin]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

setopt ERR_EXIT NO_UNSET PIPE_FAIL

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=2
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

# Prüfung: root-Rechte
if [ "$(id -u)" -ne 0 ]; then
  printf '%s\n' 'Dieses Script braucht Administratorrechte (root).'
  printf '%s\n' 'Bitte so starten: sudo zsh ./script.sh'
  printf 'Protokoll: %s\n' "$OKM_LOG"
  exit 1
fi

# --------------------------------------------------------------------
# Schritt 1/2: Ping auf Ziel (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/2 (Ping auf Ziel)'
printf '%s\n' '[1/2] Ping auf 192.168.1.50 (2x) …'
ping -c 2 '192.168.1.50'
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/2: Drucker per IP hinzufügen (Risiko: gelb)
# --------------------------------------------------------------------
OKM_SCHRITT='2/2 (Drucker per IP hinzufügen)'
printf '%s\n' '[2/2] Drucker Drucker-Empfang (192.168.1.50) wird eingerichtet …'
lpadmin -p 'Drucker-Empfang' -E -v ipp://'192.168.1.50'/ipp/print -m everywhere
# Prüfung
lpstat -p 'Drucker-Empfang'
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
