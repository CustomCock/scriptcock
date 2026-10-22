#!/bin/zsh
# ======================================================================
# Titel:             PC ist langsam
# Beschreibung:      Sucht die typischen Bremsen – CPU- und Speicherlast, volle Festplatte, lange Laufzeit, Autostart-Programme und Festplatten-Gesundheit.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. „PC ist langsam“-Check [Risiko: gruen]
#    2. Top-Ressourcenverbraucher [Risiko: gruen]
#    3. Festplattenbelegung anzeigen [Risiko: gruen]
#    4. Autostart-Einträge anzeigen [Risiko: gruen]
#    5. Festplatten-Gesundheit (SMART) [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

setopt ERR_EXIT NO_UNSET PIPE_FAIL

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=5
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
# Schritt 1/5: „PC ist langsam“-Check (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/5 („PC ist langsam“-Check)'
printf '%s\n' '[1/5] Rechner wird auf typische Bremsen geprüft …'
printf 'Last (1/5/15 min): %s   CPU-Kerne: %s\n' "$(sysctl -n vm.loadavg)" "$(sysctl -n hw.ncpu)"
memory_pressure | tail -n 1 || true
df -h /
uptime
printf '\n%s\n' 'Größte Verbraucher:'
ps -Ao pid,%cpu,%mem,comm -m | awk 'NR <= 6'
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/5: Top-Ressourcenverbraucher (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/5 (Top-Ressourcenverbraucher)'
printf '%s\n' '[2/5] Prozesse werden nach Last sortiert …'
printf '%s\n' 'Nach CPU:'
ps -Ao pid,user,%cpu,%mem,comm -r | awk 'NR <= 11'
printf '\n%s\n' 'Nach Arbeitsspeicher:'
ps -Ao pid,user,%cpu,%mem,comm -m | awk 'NR <= 11'
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 3/5: Festplattenbelegung anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/5 (Festplattenbelegung anzeigen)'
printf '%s\n' '[3/5] Festplattenbelegung wird ermittelt …'
df -h -l
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 4/5: Autostart-Einträge anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='4/5 (Autostart-Einträge anzeigen)'
printf '%s\n' '[4/5] Autostart-Einträge werden gelesen …'
for okm_ordner in /Library/LaunchAgents /Library/LaunchDaemons "$HOME/Library/LaunchAgents"; do
  printf '\n%s:\n' "$okm_ordner"
  ls -1 "$okm_ordner" 2>/dev/null || true
done
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 5/5: Festplatten-Gesundheit (SMART) (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='5/5 (Festplatten-Gesundheit (SMART))'
printf '%s\n' '[5/5] Festplatten-Gesundheit wird geprüft …'
diskutil info disk0 | grep -E 'Device / Media Name|SMART Status|Solid State' || true
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
