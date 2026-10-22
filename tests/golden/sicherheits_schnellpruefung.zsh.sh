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
# Schritt 1/4: Firewall-Status anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/4 (Firewall-Status anzeigen)'
printf '%s\n' '[1/4] Firewall-Status wird gelesen …'
/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
/usr/libexec/ApplicationFirewall/socketfilterfw --getstealthmode
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 2/4: macOS: FileVault-Status (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='2/4 (macOS: FileVault-Status)'
printf '%s\n' '[2/4] FileVault-Status wird gelesen …'
fdesetup status
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 3/4: macOS: Gatekeeper und Systemintegritätsschutz (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='3/4 (macOS: Gatekeeper und Systemintegritätsschutz)'
printf '%s\n' '[3/4] Gatekeeper und SIP werden geprüft …'
spctl --status || true
csrutil status
OKM_OK=$((OKM_OK + 1))

# --------------------------------------------------------------------
# Schritt 4/4: Lokale Administratoren anzeigen (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='4/4 (Lokale Administratoren anzeigen)'
printf '%s\n' '[4/4] Lokale Administratoren werden aufgelistet …'
dscl . -read /Groups/admin GroupMembership
OKM_OK=$((OKM_OK + 1))

printf '\nFertig, %s von %s Schritten erfolgreich.\n' "$OKM_OK" "$OKM_GESAMT"
printf 'Protokoll: %s\n' "$OKM_LOG"
