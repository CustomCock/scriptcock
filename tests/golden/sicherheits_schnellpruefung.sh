#!/usr/bin/env bash
# ======================================================================
# Titel:             Sicherheits-Schnellprüfung
# Beschreibung:      Prüft die wichtigsten Schutzmechanismen (Firewall, Virenschutz, Verschlüsselung, Admin-Konten) und zeigt Auffälligkeiten.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. Firewall-Status anzeigen [Risiko: gruen, Admin]
#    2. Linux: SSH-Konfiguration prüfen [Risiko: gruen, Admin]
#    3. Lokale Administratoren anzeigen [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

set -Eeuo pipefail

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=3
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

# Prüfung: root-Rechte
if [ "$(id -u)" -ne 0 ]; then
  printf '%s\n' 'Dieses Script braucht Administratorrechte (root).'
  printf '%s\n' 'Bitte so starten: sudo bash ./script.sh'
  printf 'Protokoll: %s\n' "$OKM_LOG"
  exit 1
fi

# --------------------------------------------------------------------
# Schritt 1/3: Firewall-Status anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/3 (Firewall-Status anzeigen)'
printf '%s\n' '[1/3] Firewall-Status wird gelesen …'
if command -v ufw >/dev/null 2>&1; then
  ufw status verbose
elif command -v firewall-cmd >/dev/null 2>&1; then
  firewall-cmd --state || true
  firewall-cmd --list-all || true
elif command -v nft >/dev/null 2>&1; then
  nft list ruleset
else
  printf '%s\n' 'Keine bekannte Firewall-Verwaltung (ufw, firewalld, nftables) gefunden.'
fi
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/3: Linux: SSH-Konfiguration prüfen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/3 (Linux: SSH-Konfiguration prüfen)'
printf '%s\n' '[2/3] SSH-Konfiguration wird gelesen …'
if ! command -v sshd >/dev/null 2>&1; then
  printf '%s\n' 'Kein SSH-Server installiert.'
else
  sshd -T 2>/dev/null | grep -Ei '^(port|permitrootlogin|passwordauthentication|pubkeyauthentication|permitemptypasswords|x11forwarding|maxauthtries) ' || true
fi
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 3/3: Lokale Administratoren anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/3 (Lokale Administratoren anzeigen)'
printf '%s\n' '[3/3] Lokale Administratoren werden aufgelistet …'
getent group sudo wheel || printf '%s\n' 'Keine Gruppe sudo/wheel gefunden.'
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
