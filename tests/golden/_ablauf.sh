#!/usr/bin/env bash
# ======================================================================
# Titel:             Ablauf
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        Linux (Bash 4+)
# Enthaltene Schritte:
#    1. Meldung/Pause für den Benutzer [Risiko: gruen]
#   Versuche:
#       2. Ordner anlegen [Risiko: gelb]
#      Versuche:
#          3. Ping auf Ziel [Risiko: gruen]
#      Fehler darin übergehen.
#   Wenn das fehlschlägt:
#       4. Meldung/Pause für den Benutzer [Risiko: gruen]
#      Wiederhole 2-mal:
#          5. Prozess beenden [Risiko: rot]
#   Wiederhole 3-mal:
#       6. Meldung/Pause für den Benutzer [Risiko: gruen]
#      Versuche:
#          7. Dienst-Status prüfen [Risiko: gruen]
#      Fehler darin übergehen.
#    8. Meldung/Pause für den Benutzer [Risiko: gruen]
#
# Generiert mit dem okm Script-Baukasten
# ======================================================================

set -Eeuo pipefail

OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"
OKM_OK=0
OKM_SCHRITT='-'
# Für „Versuche“-Blöcke (Subshells): Schutz-Flag, Tiefe, Zählerdatei
OKM_SCHUTZ=0
OKM_VERSUCH=0
OKM_ZAEHLER="$(mktemp)"
printf '0' > "$OKM_ZAEHLER"
okm_geschafft() {
  OKM_OK=$((OKM_OK + 1))
  printf '%s' "$OKM_OK" > "$OKM_ZAEHLER"
}
exec > >(tee -a "$OKM_LOG") 2>&1

okm_fehler() {
  local okm_rc=$?
  # Rückgabewert eines „Versuche“-Blocks wertet das Script selbst aus
  if [ "$OKM_SCHUTZ" = 1 ]; then return 0; fi
  if [ "$OKM_VERSUCH" -gt 0 ]; then
    printf '\nSchritt %s ist fehlgeschlagen (Exit-Code %s).\n' "$OKM_SCHRITT" "$okm_rc"
    exit "$okm_rc"
  fi
  trap - ERR
  printf '\nFEHLER in Schritt %s (Exit-Code %s).\n' "$OKM_SCHRITT" "$okm_rc"
  printf 'Erfolgreich bis dahin: %s Schritte.\n' "$OKM_OK"
  printf 'Protokoll: %s\n' "$OKM_LOG"
  rm -f "$OKM_ZAEHLER"
  exit "$okm_rc"
}
trap okm_fehler ERR

# --------------------------------------------------------------------
# Schritt 1/8: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='1/8 (Meldung/Pause für den Benutzer)'
printf '%s\n' '[1/8] Hinweis für den Benutzer …'
printf '%s\n' 'Start'
okm_geschafft

# ===== Versuche (Block 1) =====
# Läuft in einer Subshell mit eigenem Fehlerabbruch; ein Fehler darin beendet
# nur die Subshell, danach folgen die Ausweichschritte.
OKM_SCHUTZ=1
set +e
(
  OKM_SCHUTZ=0
  OKM_VERSUCH=$((OKM_VERSUCH + 1))
  set -e
  # --------------------------------------------------------------------
  # Schritt 2/8: Ordner anlegen (Risiko: gelb)
  # --------------------------------------------------------------------
  OKM_SCHRITT='2/8 (Ordner anlegen)'
  printf '%s\n' '[2/8] Ordner /tmp/okm-test wird angelegt …'
  mkdir -p -- '/tmp/okm-test'
  okm_geschafft

  # ===== Versuche (Block 2) =====
  # Läuft in einer Subshell mit eigenem Fehlerabbruch; ein Fehler darin beendet
  # nur die Subshell, danach folgen die Ausweichschritte.
  OKM_SCHUTZ=1
  set +e
  (
    OKM_SCHUTZ=0
    OKM_VERSUCH=$((OKM_VERSUCH + 1))
    set -e
    # --------------------------------------------------------------------
    # Schritt 3/8: Ping auf Ziel (Risiko: gruen)
    # --------------------------------------------------------------------
    OKM_SCHRITT='3/8 (Ping auf Ziel)'
    printf '%s\n' '[3/8] Ping auf 10.0.0.1 (4x) …'
    ping -c 4 '10.0.0.1'
    okm_geschafft

  )
  okm_rc_2=$?
  set -e
  OKM_SCHUTZ=0
  OKM_OK="$(cat "$OKM_ZAEHLER")"
  if [ "$okm_rc_2" -eq 112 ]; then
    exit 112
  fi
  if [ "$okm_rc_2" -ne 0 ]; then
    printf '%s\n' 'Ein Schritt ist fehlgeschlagen - der Fehler wird wie vorgesehen übergangen.'
  fi
  # ===== Ende Versuche (Block 2) =====

)
okm_rc_1=$?
set -e
OKM_SCHUTZ=0
OKM_OK="$(cat "$OKM_ZAEHLER")"
if [ "$okm_rc_1" -eq 112 ]; then
  printf 'Protokoll: %s\n' "$OKM_LOG"
  rm -f "$OKM_ZAEHLER"
  exit 2
fi
if [ "$okm_rc_1" -ne 0 ]; then
  printf '%s\n' 'Ein Schritt ist fehlgeschlagen - es geht mit den Ausweichschritten weiter.'
  # --------------------------------------------------------------------
  # Schritt 4/8: Meldung/Pause für den Benutzer (Risiko: gruen)
  # --------------------------------------------------------------------
  OKM_SCHRITT='4/8 (Meldung/Pause für den Benutzer)'
  printf '%s\n' '[4/8] Hinweis für den Benutzer …'
  printf '%s\n' 'Ausweichen'
  okm_geschafft

  # ===== Wiederhole 2-mal (Block 3) =====
  for ((okm_durchlauf_3 = 1; okm_durchlauf_3 <= 2; okm_durchlauf_3++)); do
    printf '%s\n' "--- Durchlauf $okm_durchlauf_3 von 2 ---"
    # --------------------------------------------------------------------
    # Schritt 5/8: Prozess beenden (Risiko: rot)
    # --------------------------------------------------------------------
    OKM_SCHRITT='5/8 (Prozess beenden)'
    printf '%s\n' '[5/8] Prozess notepad wird beendet …'
    printf '%s\n' 'ACHTUNG: Dieser Schritt ist destruktiv: Prozess beenden'
    okm_antwort=""
    read -r -p 'Zum Fortfahren JA eingeben (alles andere bricht ab): ' okm_antwort || true
    if [ "$okm_antwort" != "JA" ]; then
      printf '%s\n' 'Abgebrochen. Es wurde nichts weiter ausgeführt.'
      printf 'Protokoll: %s\n' "$OKM_LOG"
      exit 2
    fi
    if pkill -x -- 'notepad'; then
      printf '%s\n' 'Prozess beendet.'
    else
      printf '%s\n' 'Kein passender Prozess gefunden - nichts zu tun.'
    fi
    okm_geschafft

  done

fi
# ===== Ende Versuche (Block 1) =====

# ===== Wiederhole 3-mal (Block 4) =====
for ((okm_durchlauf_4 = 1; okm_durchlauf_4 <= 3; okm_durchlauf_4++)); do
  printf '%s\n' "--- Durchlauf $okm_durchlauf_4 von 3 ---"
  # --------------------------------------------------------------------
  # Schritt 6/8: Meldung/Pause für den Benutzer (Risiko: gruen)
  # --------------------------------------------------------------------
  OKM_SCHRITT='6/8 (Meldung/Pause für den Benutzer)'
  printf '%s\n' '[6/8] Hinweis für den Benutzer …'
  printf '%s\n' 'Schleife'
  okm_geschafft

  # ===== Versuche (Block 5) =====
  # Läuft in einer Subshell mit eigenem Fehlerabbruch; ein Fehler darin beendet
  # nur die Subshell, danach folgen die Ausweichschritte.
  OKM_SCHUTZ=1
  set +e
  (
    OKM_SCHUTZ=0
    OKM_VERSUCH=$((OKM_VERSUCH + 1))
    set -e
    # --------------------------------------------------------------------
    # Schritt 7/8: Dienst-Status prüfen (Risiko: gruen)
    # --------------------------------------------------------------------
    OKM_SCHRITT='7/8 (Dienst-Status prüfen)'
    printf '%s\n' '[7/8] Status von Dienst Spooler wird abgefragt …'
    systemctl --no-pager status 'Spooler' || [ $? -eq 3 ]
    okm_geschafft

  )
  okm_rc_5=$?
  set -e
  OKM_SCHUTZ=0
  OKM_OK="$(cat "$OKM_ZAEHLER")"
  if [ "$okm_rc_5" -eq 112 ]; then
    printf 'Protokoll: %s\n' "$OKM_LOG"
    rm -f "$OKM_ZAEHLER"
    exit 2
  fi
  if [ "$okm_rc_5" -ne 0 ]; then
    printf '%s\n' 'Ein Schritt ist fehlgeschlagen - der Fehler wird wie vorgesehen übergangen.'
  fi
  # ===== Ende Versuche (Block 5) =====

done

# --------------------------------------------------------------------
# Schritt 8/8: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
OKM_SCHRITT='8/8 (Meldung/Pause für den Benutzer)'
printf '%s\n' '[8/8] Hinweis für den Benutzer …'
printf '%s\n' 'Ende'
okm_geschafft

printf '\nFertig, %s Schritte erfolgreich ausgeführt.\n' "$OKM_OK"
printf 'Protokoll: %s\n' "$OKM_LOG"
rm -f "$OKM_ZAEHLER"
