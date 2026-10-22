#!/bin/zsh
# ======================================================================
# Titel:             Diagnosepaket für den Support erstellen
# Beschreibung:      Sammelt Systeminformationen, Netzwerkeinstellungen und Protokolle in einer Datei, die du an den Support schicken kannst.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. Systeminfo anzeigen [Risiko: gruen]
#    2. Diagnosepaket erstellen [Risiko: gelb]
#    3. Meldung/Pause für den Benutzer [Risiko: gruen]
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
# Schritt 1/3: Systeminfo anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/3 (Systeminfo anzeigen)'
printf '%s\n' '[1/3] Systeminformationen werden gesammelt …'
printf 'Rechnername:    %s\n' "$(scutil --get ComputerName 2>/dev/null || hostname)"
sw_vers
printf 'Prozessor:      %s\n' "$(sysctl -n machdep.cpu.brand_string)"
printf 'RAM gesamt:     %s GB\n' "$(( $(sysctl -n hw.memsize) / 1073741824 ))"
printf 'Laufzeit:      %s\n' "$(uptime)"
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/3: Diagnosepaket erstellen (Risiko: gelb)
# --------------------------------------------------------------------
OKM_SCHRITT='2/3 (Diagnosepaket erstellen)'
printf '%s\n' '[2/3] Diagnosepaket wird erstellt (das kann etwas dauern) …'
okm_stempel="$(date +%Y%m%d-%H%M%S)"
okm_arbeit="$(mktemp -d)"
{ sw_vers; uname -a; uptime; df -h; } > "$okm_arbeit/system.txt" 2>&1 || true
system_profiler SPHardwareDataType SPSoftwareDataType >> "$okm_arbeit/system.txt" 2>&1 || true
{ ifconfig; netstat -rn; scutil --dns; } > "$okm_arbeit/netzwerk.txt" 2>&1 || true
log show --last 24h --predicate 'messageType == error' --style compact > "$okm_arbeit/log.txt" 2>&1 || true
ps aux > "$okm_arbeit/prozesse.txt" 2>&1 || true
okm_paket="$HOME/Desktop/okm-diagnose-$(hostname -s)-$okm_stempel.zip"
ditto -c -k "$okm_arbeit" "$okm_paket"
rm -rf -- "$okm_arbeit"
printf 'Diagnosepaket erstellt: %s\n' "$okm_paket"
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 3/3: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/3 (Meldung/Pause für den Benutzer)'
printf '%s\n' '[3/3] Hinweis für den Benutzer …'
printf '%s\n' 'Fertig! Bitte die erstellte Datei an den Support schicken (Pfad siehe oben).'
read -r 'okm_weiter?Weiter mit Enter ... ' || true
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
