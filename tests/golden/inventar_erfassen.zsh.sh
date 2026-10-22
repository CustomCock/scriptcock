#!/bin/zsh
# ======================================================================
# Titel:             Seriennummer und Inventar erfassen
# Beschreibung:      Sammelt Seriennummer, Hardware, Betriebssystem, Lizenzstatus und installierte Programme für die Inventarisierung.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. Seriennummer und Modell [Risiko: gruen]
#    2. Systeminfo anzeigen [Risiko: gruen]
#    3. Letzter Neustart und ausstehender Neustart [Risiko: gruen]
#    4. Installierte Software auflisten [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

setopt ERR_EXIT NO_UNSET PIPE_FAIL

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=4
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
# Schritt 1/4: Seriennummer und Modell (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/4 (Seriennummer und Modell)'
printf '%s\n' '[1/4] Hardware-Daten werden gelesen …'
printf 'Modell:         %s\n' "$(sysctl -n hw.model)"
printf 'Seriennummer:   %s\n' "$(ioreg -c IOPlatformExpertDevice -d 2 | awk -F'"' '/IOPlatformSerialNumber/ {print $4}')"
printf 'Prozessor:      %s\n' "$(sysctl -n machdep.cpu.brand_string)"
sw_vers
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/4: Systeminfo anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/4 (Systeminfo anzeigen)'
printf '%s\n' '[2/4] Systeminformationen werden gesammelt …'
printf 'Rechnername:    %s\n' "$(scutil --get ComputerName 2>/dev/null || hostname)"
sw_vers
printf 'Prozessor:      %s\n' "$(sysctl -n machdep.cpu.brand_string)"
printf 'RAM gesamt:     %s GB\n' "$(( $(sysctl -n hw.memsize) / 1073741824 ))"
printf 'Laufzeit:      %s\n' "$(uptime)"
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 3/4: Letzter Neustart und ausstehender Neustart (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/4 (Letzter Neustart und ausstehender Neustart)'
printf '%s\n' '[3/4] Startzeit und ausstehende Neustarts werden geprüft …'
printf 'Letzter Start: %s\n' "$(sysctl -n kern.boottime)"
uptime
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 4/4: Installierte Software auflisten (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='4/4 (Installierte Software auflisten)'
printf '%s\n' '[4/4] Installierte Software wird gelesen …'
for okm_app in /Applications/*.app; do
  okm_version="$(defaults read "$okm_app/Contents/Info" CFBundleShortVersionString 2>/dev/null || printf '%s' '?')"
  printf '%-45s %s\n' "$(basename "$okm_app" .app)" "$okm_version"
done
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
