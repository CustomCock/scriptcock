#!/bin/zsh
# ======================================================================
# Titel:             Sicherheits-Schnellprüfung
# Beschreibung:      Prüft die wichtigsten Schutzmechanismen (Firewall, Virenschutz, Verschlüsselung, Admin-Konten) und zeigt Auffälligkeiten.
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
# Enthaltene Schritte:
#    1. Firewall-Status anzeigen [Risiko: gruen]
#    2. macOS: FileVault-Status [Risiko: gruen]
#    3. macOS: Gatekeeper und Systemintegritätsschutz [Risiko: gruen]
#    4. Lokale Administratoren anzeigen [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

setopt ERR_EXIT NO_UNSET PIPE_FAIL

OKM_LOG="${TMPDIR:-/tmp}/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_GESAMT=4
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

TRAPZERR() {
  local okm_rc=$?
  okm_fehler "Schritt $OKM_SCHRITT: Befehl endete mit Exit-Code $okm_rc."
  if [ -n "$OKM_TIPP" ]; then okm_info "      Tipp: $OKM_TIPP"; fi
  OKM_STATUS=fehler
  okm_zusammenfassung
  exit "$okm_rc"
}

okm_info '=============================================='
okm_info ' okm Script-Baukasten · Sicherheits-Schnellprüfung'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# --------------------------------------------------------------------
# Schritt 1/4: Firewall-Status anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/4 (Firewall-Status anzeigen)'
OKM_TIPP=''
okm_info '[1/4] Firewall-Status wird gelesen ...'
/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
/usr/libexec/ApplicationFirewall/socketfilterfw --getstealthmode
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 2/4: macOS: FileVault-Status (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=2
OKM_SCHRITT='2/4 (macOS: FileVault-Status)'
OKM_TIPP=''
okm_info '[2/4] FileVault-Status wird gelesen ...'
fdesetup status
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 3/4: macOS: Gatekeeper und Systemintegritätsschutz (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=3
OKM_SCHRITT='3/4 (macOS: Gatekeeper und Systemintegritätsschutz)'
OKM_TIPP=''
okm_info '[3/4] Gatekeeper und SIP werden geprüft ...'
spctl --status || true
csrutil status
OKM_OK=$((OKM_OK + 1))
okm_ok

# --------------------------------------------------------------------
# Schritt 4/4: Lokale Administratoren anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=4
OKM_SCHRITT='4/4 (Lokale Administratoren anzeigen)'
OKM_TIPP=''
okm_info '[4/4] Lokale Administratoren werden aufgelistet ...'
dscl . -read /Groups/admin GroupMembership
OKM_OK=$((OKM_OK + 1))
okm_ok

OKM_STATUS=fertig
okm_zusammenfassung
