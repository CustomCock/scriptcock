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

OKM_LOG="${TMPDIR:-/tmp}/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=3
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
okm_info ' okm Script-Baukasten · Sicherheits-Schnellprüfung'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# Prüfung: root-Rechte
if [ "$(id -u)" -ne 0 ]; then
  okm_fehler 'Dieses Script braucht Administratorrechte (root).'
  okm_info '      Bitte so starten: sudo bash ./script.sh'
  OKM_STATUS=rechte
  okm_zusammenfassung
  exit 1
fi

# --------------------------------------------------------------------
# Schritt 1/3: Firewall-Status anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/3 (Firewall-Status anzeigen)'
OKM_TIPP=''
okm_info '[1/3] Firewall-Status wird gelesen ...'
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
okm_ok

# --------------------------------------------------------------------
# Schritt 2/3: Linux: SSH-Konfiguration prüfen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=2
OKM_SCHRITT='2/3 (Linux: SSH-Konfiguration prüfen)'
OKM_TIPP=''
okm_info '[2/3] SSH-Konfiguration wird gelesen ...'
if ! command -v sshd >/dev/null 2>&1; then
  printf '%s\n' 'Kein SSH-Server installiert.'
else
  sshd -T 2>/dev/null | grep -Ei '^(port|permitrootlogin|passwordauthentication|pubkeyauthentication|permitemptypasswords|x11forwarding|maxauthtries) ' || true
fi
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 3/3: Lokale Administratoren anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=3
OKM_SCHRITT='3/3 (Lokale Administratoren anzeigen)'
OKM_TIPP=''
okm_info '[3/3] Lokale Administratoren werden aufgelistet ...'
getent group sudo wheel || printf '%s\n' 'Keine Gruppe sudo/wheel gefunden.'
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
okm_zusammenfassung
