#!/bin/zsh
# ======================================================================
# Titel:             Ablauf
# Erstellt von:      pytest
# Erstellt am:       15.01.2026 09:30:00
# Baukasten-Version: 0.1.0
# Zielsystem:        macOS (zsh)
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

setopt ERR_EXIT PIPE_FAIL

# --nopause: am Ende nicht auf Enter warten (Fernwartung/RMM)
OKM_KEINE_PAUSE=0
for okm_arg in "$@"; do
  if [ "$okm_arg" = --nopause ]; then OKM_KEINE_PAUSE=1; fi
done
OKM_LOG="${TMPDIR:-/tmp}/okm-script-$(date +%Y%m%d-%H%M%S).log"
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
    fertig) printf ' Fertig: %s Schritte erfolgreich ausgeführt.\n' "$OKM_OK" ;;
    abbruch) okm_info ' Abgebrochen durch Benutzer. Es wurde nichts weiter ausgeführt.' ;;
    rechte) okm_info ' Abgebrochen: fehlende Rechte.' ;;
    *) printf ' Abgebrochen bei Schritt %s.\n' "$OKM_NR"; printf ' Erfolgreich bis dahin: %s Schritte.\n' "$OKM_OK" ;;
  esac
  printf ' Protokoll: %s\n' "$OKM_LOG"
  okm_info '----------------------------------------------'
}
# Fenster/Terminal offen halten – nur wenn ein Mensch davor sitzt
okm_pause() {
  if [ "$OKM_KEINE_PAUSE" = 1 ] || [ ! -t 0 ]; then return 0; fi
  read -r 'okm_weiter?Drücke Enter zum Schließen …' || true
}
# Für „Versuche“-Blöcke (Subshells): Schutz-Flag, Tiefe, Zählerdatei
OKM_SCHUTZ=0
OKM_VERSUCH=0
OKM_ZAEHLER="$(mktemp)"
printf '0' > "$OKM_ZAEHLER"
okm_geschafft() {
  OKM_OK=$((OKM_OK + 1))
  printf '%s' "$OKM_OK" > "$OKM_ZAEHLER"
}
okm_bei_fehler() {
  local okm_rc=$1 okm_zeile=$2
  # Rückgabewert eines „Versuche“-Blocks wertet das Script selbst aus
  if [ "$OKM_SCHUTZ" = 1 ]; then return 0; fi
  if [ "$OKM_VERSUCH" -gt 0 ]; then
    okm_fehler "Schritt $OKM_SCHRITT ist fehlgeschlagen (Exit-Code $okm_rc)."
    exit "$okm_rc"
  fi
  okm_fehler "Schritt $OKM_SCHRITT: Befehl endete mit Exit-Code $okm_rc."
  okm_info "      Zeile $okm_zeile"
  if [ -n "$OKM_TIPP" ]; then okm_info "      Tipp: $OKM_TIPP"; fi
  OKM_STATUS=fehler
  exit "$okm_rc"
}
trap 'okm_bei_fehler $? $LINENO' ZERR

# Zusammenfassung bei JEDEM Ende – auch bei Fehlern, die kein ERR auslösen
# (z. B. nicht gesetzte Variable) oder einem Abbruch ohne Meldung.
okm_ende() {
  local okm_rc=$?
  if [ "$OKM_STATUS" = laeuft ]; then
    if [ "$okm_rc" -eq 0 ]; then
      OKM_STATUS=fertig
    else
      okm_fehler "Script unerwartet beendet in Schritt $OKM_SCHRITT (Exit-Code $okm_rc)."
      OKM_STATUS=fehler
    fi
  fi
  okm_zusammenfassung
  rm -f "$OKM_ZAEHLER"
  okm_pause
  # Ausgabe schließen und kurz auf tee warten, sonst fehlen beim Schließen des Fensters
  # die letzten Zeilen (höchstens 2 s – ein Hintergrundprozess darf nichts aufhalten)
  exec 1>&- 2>&-
  okm_i=0
  while [ "$okm_i" -lt 20 ] && kill -0 "${OKM_TEE:-0}" 2>/dev/null; do
    sleep 0.1
    okm_i=$((okm_i + 1))
  done
  exit "$okm_rc"
}
trap okm_ende EXIT

# Ausgabe zusätzlich ins Protokoll – über eine FIFO statt >(tee), damit das Script am Ende
# auf tee warten kann (zsh verliert sonst die komplette Ausgabe, wenn das Fenster zugeht).
OKM_TMPDIR="$(mktemp -d)"
mkfifo -m 600 "$OKM_TMPDIR/ausgabe"
tee -a "$OKM_LOG" < "$OKM_TMPDIR/ausgabe" &
OKM_TEE=$!
exec > "$OKM_TMPDIR/ausgabe" 2>&1
rm -rf "$OKM_TMPDIR"

okm_info '=============================================='
okm_info ' okm Script-Baukasten · Ablauf'
okm_info ' Erstellt: 15.01.2026 09:30 · von pytest'
okm_info '=============================================='

# --------------------------------------------------------------------
# Schritt 1/8: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=1
OKM_SCHRITT='1/8 (Meldung/Pause für den Benutzer)'
OKM_TIPP=''
okm_info '[1/8] Hinweis für den Benutzer ...'
printf '%s\n' 'Start'
okm_geschafft
okm_ok

# ===== Versuche (Block 1) =====
# Läuft in einer Subshell mit eigenem Fehlerabbruch; ein Fehler darin beendet
# nur die Subshell, danach folgen die Ausweichschritte.
OKM_SCHUTZ=1
unsetopt ERR_EXIT
(
  OKM_SCHUTZ=0
  OKM_VERSUCH=$((OKM_VERSUCH + 1))
  setopt ERR_EXIT
  # --------------------------------------------------------------------
  # Schritt 2/8: Ordner anlegen (Risiko: gelb)
  # --------------------------------------------------------------------
  OKM_NR=2
  OKM_SCHRITT='2/8 (Ordner anlegen)'
  OKM_TIPP=''
  okm_info '[2/8] Ordner /tmp/okm-test wird angelegt ...'
  mkdir -p -- '/tmp/okm-test'
  okm_geschafft
  okm_ok

  # ===== Versuche (Block 2) =====
  # Läuft in einer Subshell mit eigenem Fehlerabbruch; ein Fehler darin beendet
  # nur die Subshell, danach folgen die Ausweichschritte.
  OKM_SCHUTZ=1
  unsetopt ERR_EXIT
  (
    OKM_SCHUTZ=0
    OKM_VERSUCH=$((OKM_VERSUCH + 1))
    setopt ERR_EXIT
    # --------------------------------------------------------------------
    # Schritt 3/8: Ping auf Ziel (Risiko: gruen)
    # --------------------------------------------------------------------
    OKM_NR=3
    OKM_SCHRITT='3/8 (Ping auf Ziel)'
    OKM_TIPP='Ist das Gerät eingeschaltet und im selben Netz? Manche Geräte und Firewalls antworten grundsätzlich nicht auf Ping.'
    okm_info '[3/8] Ping auf 10.0.0.1 (4x) ...'
    ping -c 4 '10.0.0.1'
    okm_geschafft
    okm_ok

  )
  okm_rc_2=$?
  setopt ERR_EXIT
  OKM_SCHUTZ=0
  OKM_OK="$(cat "$OKM_ZAEHLER")"
  if [ "$okm_rc_2" -eq 112 ]; then
    exit 112
  fi
  if [ "$okm_rc_2" -ne 0 ]; then
    okm_warn 'Ein Schritt ist fehlgeschlagen - der Fehler wird wie vorgesehen übergangen.'
  fi
  # ===== Ende Versuche (Block 2) =====

)
okm_rc_1=$?
setopt ERR_EXIT
OKM_SCHUTZ=0
OKM_OK="$(cat "$OKM_ZAEHLER")"
if [ "$okm_rc_1" -eq 112 ]; then
  OKM_STATUS=abbruch
  exit 2
fi
if [ "$okm_rc_1" -ne 0 ]; then
  okm_warn 'Ein Schritt ist fehlgeschlagen - es geht mit den Ausweichschritten weiter.'
  # --------------------------------------------------------------------
  # Schritt 4/8: Meldung/Pause für den Benutzer (Risiko: gruen)
  # --------------------------------------------------------------------
  OKM_NR=4
  OKM_SCHRITT='4/8 (Meldung/Pause für den Benutzer)'
  OKM_TIPP=''
  okm_info '[4/8] Hinweis für den Benutzer ...'
  printf '%s\n' 'Ausweichen'
  okm_geschafft
  okm_ok

  # ===== Wiederhole 2-mal (Block 3) =====
  for ((okm_durchlauf_3 = 1; okm_durchlauf_3 <= 2; okm_durchlauf_3++)); do
    okm_info "--- Durchlauf $okm_durchlauf_3 von 2 ---"
    # --------------------------------------------------------------------
    # Schritt 5/8: Prozess beenden (Risiko: rot)
    # --------------------------------------------------------------------
    OKM_NR=5
    OKM_SCHRITT='5/8 (Prozess beenden)'
    OKM_TIPP=''
    okm_info '[5/8] Prozess notepad wird beendet ...'
    okm_warn 'ACHTUNG: Dieser Schritt ist destruktiv: Prozess beenden'
    okm_antwort=""
    read -r 'okm_antwort?Zum Fortfahren JA eingeben (alles andere bricht ab): ' || true
    if [ "$okm_antwort" != "JA" ]; then
      OKM_STATUS=abbruch
      exit 2
    fi
    if pkill -x 'notepad'; then
      printf '%s\n' 'Prozess beendet.'
    else
      printf '%s\n' 'Kein passender Prozess gefunden - nichts zu tun.'
    fi
    okm_geschafft
    okm_ok

  done

fi
# ===== Ende Versuche (Block 1) =====

# ===== Wiederhole 3-mal (Block 4) =====
for ((okm_durchlauf_4 = 1; okm_durchlauf_4 <= 3; okm_durchlauf_4++)); do
  okm_info "--- Durchlauf $okm_durchlauf_4 von 3 ---"
  # --------------------------------------------------------------------
  # Schritt 6/8: Meldung/Pause für den Benutzer (Risiko: gruen)
  # --------------------------------------------------------------------
  OKM_NR=6
  OKM_SCHRITT='6/8 (Meldung/Pause für den Benutzer)'
  OKM_TIPP=''
  okm_info '[6/8] Hinweis für den Benutzer ...'
  printf '%s\n' 'Schleife'
  okm_geschafft
  okm_ok

  # ===== Versuche (Block 5) =====
  # Läuft in einer Subshell mit eigenem Fehlerabbruch; ein Fehler darin beendet
  # nur die Subshell, danach folgen die Ausweichschritte.
  OKM_SCHUTZ=1
  unsetopt ERR_EXIT
  (
    OKM_SCHUTZ=0
    OKM_VERSUCH=$((OKM_VERSUCH + 1))
    setopt ERR_EXIT
    # --------------------------------------------------------------------
    # Schritt 7/8: Dienst-Status prüfen (Risiko: gruen)
    # --------------------------------------------------------------------
    OKM_NR=7
    OKM_SCHRITT='7/8 (Dienst-Status prüfen)'
    OKM_TIPP=''
    okm_info '[7/8] Status von Dienst Spooler wird abgefragt ...'
    okm_label='Spooler'
    if okm_launchd="$(launchctl print "system/$okm_label" 2>/dev/null)"; then
      printf '%s\n' "$okm_launchd" | grep -E '^\s*(state|pid|path) =' || true
    else
      okm_warn 'Diesen Dienst gibt es nicht (oder er ist nur für den angemeldeten Benutzer geladen).'
    fi
    okm_geschafft
    okm_ok

  )
  okm_rc_5=$?
  setopt ERR_EXIT
  OKM_SCHUTZ=0
  OKM_OK="$(cat "$OKM_ZAEHLER")"
  if [ "$okm_rc_5" -eq 112 ]; then
    OKM_STATUS=abbruch
    exit 2
  fi
  if [ "$okm_rc_5" -ne 0 ]; then
    okm_warn 'Ein Schritt ist fehlgeschlagen - der Fehler wird wie vorgesehen übergangen.'
  fi
  # ===== Ende Versuche (Block 5) =====

done

# --------------------------------------------------------------------
# Schritt 8/8: Meldung/Pause für den Benutzer (Risiko: gruen)
# --------------------------------------------------------------------
OKM_NR=8
OKM_SCHRITT='8/8 (Meldung/Pause für den Benutzer)'
OKM_TIPP=''
okm_info '[8/8] Hinweis für den Benutzer ...'
printf '%s\n' 'Ende'
okm_geschafft
okm_ok

OKM_STATUS=fertig
