#!/usr/bin/env bash
# ======================================================================
# Titel:             Server-Gesundheitscheck
# Beschreibung:      Überblick über Laufzeit, Speicherplatz, Dienste, Fehler im Ereignisprotokoll bzw. Journal, RAID und Updates.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. Linux: Server-Gesundheitscheck [Risiko: gruen]
#    2. Linux: Fehlgeschlagene Dienste [Risiko: gruen]
#    3. Linux: RAID- und ZFS-Status [Risiko: gruen]
#    4. Kernel-/Hardware-Meldungen (dmesg) [Risiko: gruen]
#    5. Update-Status anzeigen [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

set -Eeuo pipefail

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=5
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
# Schritt 1/5: Linux: Server-Gesundheitscheck (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/5 (Linux: Server-Gesundheitscheck)'
printf '%s\n' '[1/5] Server-Gesundheit wird geprüft …'
printf '== %s ==\n' "$(hostname -f 2>/dev/null || hostname)"
uptime
printf '\n%s\n' '-- Arbeitsspeicher --'
free -h
printf '\n%s\n' '-- Speicherplatz --'
df -hP -x tmpfs -x devtmpfs -x squashfs -x overlay
printf '\n%s\n' '-- Inodes --'
df -iP -x tmpfs -x devtmpfs -x squashfs -x overlay
printf '\n%s\n' '-- Fehlgeschlagene Dienste --'
systemctl --failed --no-pager --no-legend || true
if [ -f /var/run/reboot-required ]; then
  printf '\n%s\n' 'Neustart ausstehend (Updates).'
fi
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/5: Linux: Fehlgeschlagene Dienste (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/5 (Linux: Fehlgeschlagene Dienste)'
printf '%s\n' '[2/5] Fehlgeschlagene Dienste werden gesucht …'
okm_units="$(systemctl --failed --no-legend --plain | awk '{print $1}')"
if [ -z "$okm_units" ]; then
  printf '%s\n' 'Keine fehlgeschlagenen Dienste.'
else
  for okm_unit in $okm_units; do
    printf '\n== %s ==\n' "$okm_unit"
    journalctl -u "$okm_unit" -n 10 --no-pager || true
  done
fi
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 3/5: Linux: RAID- und ZFS-Status (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/5 (Linux: RAID- und ZFS-Status)'
printf '%s\n' '[3/5] RAID-/ZFS-Status wird gelesen …'
if [ -r /proc/mdstat ]; then
  printf '%s\n' '-- Software-RAID (mdstat) --'
  cat /proc/mdstat
fi
if command -v zpool >/dev/null 2>&1; then
  printf '\n%s\n' '-- ZFS --'
  zpool status -x
  zpool list
fi
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 4/5: Kernel-/Hardware-Meldungen (dmesg) (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='4/5 (Kernel-/Hardware-Meldungen (dmesg))'
printf '%s\n' '[4/5] Kernel-Meldungen werden gelesen …'
journalctl -k -b -p warning --no-pager || dmesg --level=err,warn
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 5/5: Update-Status anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='5/5 (Update-Status anzeigen)'
printf '%s\n' '[5/5] Update-Status wird ermittelt …'
if command -v apt >/dev/null 2>&1; then
  apt list --upgradable 2>/dev/null
elif command -v dnf >/dev/null 2>&1; then
  dnf -q check-update || [ $? -eq 100 ]
else
  printf '%s\n' 'Kein unterstützter Paketmanager (apt, dnf) gefunden.'
fi
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
