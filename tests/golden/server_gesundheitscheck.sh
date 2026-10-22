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

OKM_LOG="${TMPDIR:-/tmp}/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=5
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
okm_info ' okm Script-Baukasten · Server-Gesundheitscheck'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# --------------------------------------------------------------------
# Schritt 1/5: Linux: Server-Gesundheitscheck (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/5 (Linux: Server-Gesundheitscheck)'
OKM_TIPP=''
okm_info '[1/5] Server-Gesundheit wird geprüft ...'
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
okm_ok

# --------------------------------------------------------------------
# Schritt 2/5: Linux: Fehlgeschlagene Dienste (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=2
OKM_SCHRITT='2/5 (Linux: Fehlgeschlagene Dienste)'
OKM_TIPP=''
okm_info '[2/5] Fehlgeschlagene Dienste werden gesucht ...'
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
okm_ok

# --------------------------------------------------------------------
# Schritt 3/5: Linux: RAID- und ZFS-Status (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=3
OKM_SCHRITT='3/5 (Linux: RAID- und ZFS-Status)'
OKM_TIPP=''
okm_info '[3/5] RAID-/ZFS-Status wird gelesen ...'
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
okm_ok

# --------------------------------------------------------------------
# Schritt 4/5: Kernel-/Hardware-Meldungen (dmesg) (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=4
OKM_SCHRITT='4/5 (Kernel-/Hardware-Meldungen (dmesg))'
OKM_TIPP=''
okm_info '[4/5] Kernel-Meldungen werden gelesen ...'
journalctl -k -b -p warning --no-pager || dmesg --level=err,warn
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 5/5: Update-Status anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=5
OKM_SCHRITT='5/5 (Update-Status anzeigen)'
OKM_TIPP=''
okm_info '[5/5] Update-Status wird ermittelt ...'
if command -v apt >/dev/null 2>&1; then
  apt list --upgradable 2>/dev/null
elif command -v dnf >/dev/null 2>&1; then
  dnf -q check-update || [ $? -eq 100 ]
else
  printf '%s\n' 'Kein unterstützter Paketmanager (apt, dnf) gefunden.'
fi
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
okm_zusammenfassung
