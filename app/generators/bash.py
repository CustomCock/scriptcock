"""Generatoren für Bash (Linux) und zsh (macOS) – ``.sh``, LF, UTF-8.

Beide teilen sich den Aufbau; Unterschiede sind Shebang, Fehlerbehandlung
(``set -Eeuo pipefail`` + ``trap ERR`` vs. ``setopt`` + ``TRAPZERR``) und die
Syntax von ``read``.
"""

from __future__ import annotations

from typing import ClassVar

from app.escaping import Ziel, sh_literal
from app.generators.base import EINZUG, LINIE, Generator, SchrittInfo, einruecken
from app.ir import ScriptIR
from app.models.block import BlockDef

NIE_ROOT_TEXT = "Dieses Script darf nicht als root (mit sudo) gestartet werden: "
NIE_ROOT_HINWEIS = "Bitte ohne sudo starten – das Script fragt selbst, wenn es sudo braucht."
ABBRUCH_TEXT = " Abgebrochen durch Benutzer. Es wurde nichts weiter ausgeführt."


def _lit(text: str) -> str:
    return str(sh_literal(text))


class ShGenerator(Generator):
    zeilenende: ClassVar[str] = "\n"
    endung: ClassVar[str] = ".sh"
    shebang: ClassVar[str]
    errexit_aus: ClassVar[str]
    errexit_an: ClassVar[str]
    # Exit-Code, mit dem eine rote Abfrage einen „Versuche“-Block (Subshell) verlässt;
    # er wird nach außen weitergereicht und darf keine Ausweichschritte auslösen.
    ABBRUCH_CODE: ClassVar[int] = 112

    def ist_kommentar(self, zeile: str) -> bool:
        return zeile.lstrip().startswith("#")

    def kopf(self, ir: ScriptIR, defs: list[BlockDef]) -> list[str]:
        return [self.shebang, *[f"# {z}".rstrip() for z in self.kommentar_zeilen(ir, defs)], ""]

    def fehlerbehandlung(self) -> list[str]:
        raise NotImplementedError

    def lies_antwort(self, prompt: str) -> str:
        raise NotImplementedError

    def pause(self) -> list[str]:
        raise NotImplementedError

    def praeambel(self, ir: ScriptIR, gesamt: int, braucht_admin: bool) -> list[str]:
        zeilen = [
            *self.fehlerbehandlung(),
            "",
            "# --nopause: am Ende nicht auf Enter warten (Fernwartung/RMM)",
            "OKM_KEINE_PAUSE=0",
            'for okm_arg in "$@"; do',
            '  if [ "$okm_arg" = --nopause ]; then OKM_KEINE_PAUSE=1; fi',
            "done",
            'OKM_LOG="${TMPDIR:-/tmp}/okm-script-$(date +%Y%m%d-%H%M%S).log"',
            *([] if self.mit_kontrolle else [f"OKM_GESAMT={gesamt}"]),
            "OKM_OK=0",
            "OKM_NR=0",
            "OKM_SCHRITT='-'",
            "OKM_STATUS=laeuft",
            "OKM_TIPP=''",
            "OKM_SUDO_PID=''",
            "",
            "# Meldungen: Werte immer als Argumente übergeben, nie in den Formatstring einsetzen.",
            "# Keine Farben – die Ausgabe geht auch ins Protokoll.",
            "okm_info() { printf '%s\\n' \"$*\"; }",
            '# shellcheck disable=SC2120  # Text ist optional (Blöcke dürfen okm_ok "…" nutzen)',
            f"okm_ok() {{ if [ $# -gt 0 ]; then printf '{EINZUG}OK  %s\\n' \"$*\"; "
            f"else printf '%s\\n' '{EINZUG}OK'; fi; }}",
            f"okm_warn() {{ printf '{EINZUG}WARNUNG  %s\\n' \"$*\"; }}",
            f"okm_fehler() {{ printf '{EINZUG}FEHLER  %s\\n' \"$*\"; }}",
            *(
                ['okm_sudo() { if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo -- "$@"; fi; }']
                if self._admin_schritte
                else []
            ),
            *self._zusammenfassung(),
            "# Fenster/Terminal offen halten – nur wenn ein Mensch davor sitzt",
            "okm_pause() {",
            '  if [ "$OKM_KEINE_PAUSE" = 1 ] || [ ! -t 0 ]; then return 0; fi',
            *self.pause(),
            "}",
        ]
        if self.mit_kontrolle:
            zeilen += [
                "# Für „Versuche“-Blöcke (Subshells): Schutz-Flag, Tiefe, Zählerdatei",
                "OKM_SCHUTZ=0",
                "OKM_VERSUCH=0",
                'OKM_ZAEHLER="$(mktemp)"',
                "printf '0' > \"$OKM_ZAEHLER\"",
                "okm_geschafft() {",
                "  OKM_OK=$((OKM_OK + 1))",
                '  printf \'%s\' "$OKM_OK" > "$OKM_ZAEHLER"',
                "}",
            ]
        zeilen += [
            *self.fehler_handler(),
            "",
            "# Zusammenfassung bei JEDEM Ende – auch bei Fehlern, die kein ERR auslösen",
            "# (z. B. nicht gesetzte Variable) oder einem Abbruch ohne Meldung.",
            "okm_ende() {",
            "  local okm_rc=$?",
            '  if [ "$OKM_STATUS" = laeuft ]; then',
            '    if [ "$okm_rc" -eq 0 ]; then',
            "      OKM_STATUS=fertig",
            "    else",
            '      okm_fehler "Script unerwartet beendet in Schritt $OKM_SCHRITT (Exit-Code $okm_rc)."',
            "      OKM_STATUS=fehler",
            "    fi",
            "  fi",
            "  okm_zusammenfassung",
            '  if [ -n "$OKM_SUDO_PID" ]; then kill "$OKM_SUDO_PID" 2>/dev/null || true; fi',
            *(['  rm -f "$OKM_ZAEHLER"'] if self.mit_kontrolle else []),
            "  okm_pause",
            "  # Ausgabe schließen und kurz auf tee warten, sonst fehlen beim Schließen des Fensters",
            "  # die letzten Zeilen (höchstens 2 s – ein Hintergrundprozess darf nichts aufhalten)",
            "  exec 1>&- 2>&-",
            "  okm_i=0",
            '  while [ "$okm_i" -lt 20 ] && kill -0 "${OKM_TEE:-0}" 2>/dev/null; do',
            "    sleep 0.1",
            "    okm_i=$((okm_i + 1))",
            "  done",
            '  exit "$okm_rc"',
            "}",
            "trap okm_ende EXIT",
            "",
            "# Ausgabe zusätzlich ins Protokoll – über eine FIFO statt >(tee), damit das Script am Ende",
            "# auf tee warten kann (zsh verliert sonst die komplette Ausgabe, wenn das Fenster zugeht).",
            'OKM_TMPDIR="$(mktemp -d)"',
            'mkfifo -m 600 "$OKM_TMPDIR/ausgabe"',
            'tee -a "$OKM_LOG" < "$OKM_TMPDIR/ausgabe" &',
            "OKM_TEE=$!",
            'exec > "$OKM_TMPDIR/ausgabe" 2>&1',
            'rm -rf "$OKM_TMPDIR"',
            "",
            *[f"okm_info {_lit(z)}" for z in self.kopf_ausgabe(ir)],
            "",
        ]
        zeilen += self._rechte()
        return zeilen

    def _rechte(self) -> list[str]:
        """sudo einmal am Anfang statt Neustart als root (sonst kaputtes brew und ~ = /root)."""
        zeilen: list[str] = []
        if self._nie_root_schritte:
            liste = self.schritt_liste(self._nie_root_schritte)
            zeilen += [
                "# Schritte, die NICHT als root laufen dürfen (z. B. Homebrew verweigert root)",
                'if [ "$(id -u)" -eq 0 ]; then',
                f"  okm_fehler {_lit(NIE_ROOT_TEXT + liste + '.')}",
                f"  okm_info {_lit(EINZUG + NIE_ROOT_HINWEIS)}",
                "  OKM_STATUS=rechte",
                "  exit 1",
                "fi",
            ]
        if not self._admin_schritte:
            return [*zeilen, "okm_info 'Rechte: ohne erhöhte Rechte'", ""]
        return [
            *zeilen,
            f"# Rechte: sudo für {self.schritt_liste(self._admin_schritte)}",
            "okm_info 'Für diese Schritte werden Administratorrechte (sudo) gebraucht:'",
            *[f"okm_info {_lit(f'{EINZUG}Schritt {i} ({b.name})')}" for i, b in self._admin_schritte],
            'if [ "$(id -u)" -eq 0 ]; then',
            "  okm_info 'Rechte: als root gestartet'",
            "else",
            "  if ! command -v sudo >/dev/null 2>&1; then",
            "    okm_fehler 'sudo ist nicht installiert – bitte die IT fragen.'",
            "    OKM_STATUS=rechte",
            "    exit 1",
            "  fi",
            "  okm_info 'sudo fragt jetzt einmal nach deinem Passwort (die Eingabe bleibt unsichtbar).'",
            "  if ! sudo -v; then",
            "    okm_fehler 'sudo wurde abgelehnt oder das Passwort war falsch.'",
            "    OKM_STATUS=rechte",
            "    exit 1",
            "  fi",
            "  okm_info 'Rechte: sudo erfolgreich'",
            "  # sudo-Zeitstempel frisch halten, damit lange Scripte nicht noch einmal fragen",
            '  while true; do sudo -n true; sleep 50; kill -0 "$$" || exit; done >/dev/null 2>&1 &',
            "  OKM_SUDO_PID=$!",
            "fi",
            "",
        ]

    def _zusammenfassung(self) -> list[str]:
        if self.mit_kontrolle:
            fertig = "printf ' Fertig: %s Schritte erfolgreich ausgeführt.\\n' \"$OKM_OK\""
            fehler = "printf ' Abgebrochen bei Schritt %s.\\n' \"$OKM_NR\""
            bisher = "printf ' Erfolgreich bis dahin: %s Schritte.\\n' \"$OKM_OK\""
        else:
            fertig = 'printf \' Fertig: %s von %s Schritten erfolgreich.\\n\' "$OKM_OK" "$OKM_GESAMT"'
            fehler = 'printf \' Abgebrochen bei Schritt %s von %s.\\n\' "$OKM_NR" "$OKM_GESAMT"'
            bisher = 'printf \' Erfolgreich bis dahin: %s von %s Schritten.\\n\' "$OKM_OK" "$OKM_GESAMT"'
        return [
            "okm_zusammenfassung() {",
            f"  okm_info {_lit(LINIE)}",
            '  case "$OKM_STATUS" in',
            f"    fertig) {fertig} ;;",
            f"    abbruch) okm_info {_lit(ABBRUCH_TEXT)} ;;",
            f"    rechte) okm_info {_lit(' Abgebrochen: fehlende Rechte.')} ;;",
            f"    *) {fehler}; {bisher} ;;",
            "  esac",
            "  printf ' Protokoll: %s\\n' \"$OKM_LOG\"",
            f"  okm_info {_lit(LINIE)}",
            "}",
        ]

    def fehler_handler(self) -> list[str]:
        raise NotImplementedError

    def _fehler_pruefungen(self) -> list[str]:
        """Am Anfang des Fehler-Handlers: Sonderfälle der „Versuche“-Blöcke."""
        if not self.mit_kontrolle:
            return []
        return [
            "  # Rückgabewert eines „Versuche“-Blocks wertet das Script selbst aus",
            '  if [ "$OKM_SCHUTZ" = 1 ]; then return 0; fi',
            '  if [ "$OKM_VERSUCH" -gt 0 ]; then',
            '    okm_fehler "Schritt $OKM_SCHRITT ist fehlgeschlagen (Exit-Code $okm_rc)."',
            '    exit "$okm_rc"',
            "  fi",
        ]

    def _fehler_ausgabe(self) -> list[str]:
        """Abbruch des ganzen Scripts; die Zusammenfassung schreibt okm_ende (EXIT)."""
        return [
            '  okm_fehler "Schritt $OKM_SCHRITT: Befehl endete mit Exit-Code $okm_rc."',
            *self.fehler_ort(),
            '  if [ -n "$OKM_TIPP" ]; then okm_info "' + EINZUG + 'Tipp: $OKM_TIPP"; fi',
            "  OKM_STATUS=fehler",
            '  exit "$okm_rc"',
        ]

    def fehler_ort(self) -> list[str]:
        raise NotImplementedError

    def schritt(self, info: SchrittInfo) -> list[str]:
        b = info.block
        zeilen = [
            "# " + "-" * 68,
            f"# Schritt {info.bezeichnung}: {b.name} (Risiko: {b.risiko.value})",
            "# " + "-" * 68,
            f"OKM_NR={info.nr}",
            f"OKM_SCHRITT={_lit(f'{info.bezeichnung} ({b.name})')}",
            f"OKM_TIPP={_lit(b.tipp)}",
            f"okm_info {_lit(self.schritt_titel(info))}",
        ]
        if info.bestaetigen:
            zeilen += [
                f"okm_warn {_lit(f'ACHTUNG: Dieser Schritt ist destruktiv: {b.name}')}",
                'okm_antwort=""',
                self.lies_antwort("Zum Fortfahren JA eingeben (alles andere bricht ab): "),
                'if [ "$okm_antwort" != "JA" ]; then',
                *(
                    [f"  exit {self.ABBRUCH_CODE}"]
                    if self.im_versuch
                    else ["  OKM_STATUS=abbruch", "  exit 2"]
                ),
                "fi",
            ]
        zeilen += info.koerper
        if info.pruefung:
            zeilen += ["# Prüfung", *info.pruefung]
        zeilen += ["okm_geschafft" if self.mit_kontrolle else "OKM_OK=$((OKM_OK + 1))", "okm_ok", ""]
        return zeilen

    def wenn_fehler(self, nr: int, versuch: list[str], sonst: list[str]) -> list[str]:
        rc = f"okm_rc_{nr}"
        weiterreichen = (
            [f"  exit {self.ABBRUCH_CODE}"] if self.im_versuch else ["  OKM_STATUS=abbruch", "  exit 2"]
        )
        return [
            f"# ===== Versuche (Block {nr}) =====",
            "# Läuft in einer Subshell mit eigenem Fehlerabbruch; ein Fehler darin beendet",
            "# nur die Subshell, danach folgen die Ausweichschritte.",
            "OKM_SCHUTZ=1",
            self.errexit_aus,
            "(",
            "  OKM_SCHUTZ=0",
            "  OKM_VERSUCH=$((OKM_VERSUCH + 1))",
            f"  {self.errexit_an}",
            *einruecken(versuch, 2),
            ")",
            f"{rc}=$?",
            self.errexit_an,
            "OKM_SCHUTZ=0",
            'OKM_OK="$(cat "$OKM_ZAEHLER")"',
            f'if [ "${rc}" -eq {self.ABBRUCH_CODE} ]; then',
            *weiterreichen,
            "fi",
            f'if [ "${rc}" -ne 0 ]; then',
            f"  okm_warn {_lit(self.meldung_ausweichen(bool(sonst)))}",
            *einruecken(sonst, 2),
            "fi",
            f"# ===== Ende Versuche (Block {nr}) =====",
            "",
        ]

    def wiederhole(self, nr: int, anzahl: int, rumpf: list[str]) -> list[str]:
        var = f"okm_durchlauf_{nr}"
        return [
            f"# ===== Wiederhole {anzahl}-mal (Block {nr}) =====",
            f"for (({var} = 1; {var} <= {anzahl}; {var}++)); do",
            f'  okm_info "--- Durchlauf ${var} von {anzahl} ---"',
            *einruecken(rumpf, 2),
            "done",
            "",
        ]

    def abschluss(self, ir: ScriptIR) -> list[str]:
        # Zusammenfassung, Aufräumen und Pause übernimmt okm_ende (EXIT-Trap)
        return ["OKM_STATUS=fertig"]


class BashGenerator(ShGenerator):
    ziel: ClassVar[Ziel] = Ziel.BASH
    shebang: ClassVar[str] = "#!/usr/bin/env bash"
    errexit_aus: ClassVar[str] = "set +e"
    errexit_an: ClassVar[str] = "set -e"

    def fehlerbehandlung(self) -> list[str]:
        return ["set -Eeuo pipefail"]

    def fehler_handler(self) -> list[str]:
        return [
            "okm_bei_fehler() {",
            "  local okm_rc=$1 okm_zeile=$2 okm_befehl=$3",
            *self._fehler_pruefungen(),
            "  trap - ERR",
            *self._fehler_ausgabe(),
            "}",
            "trap 'okm_bei_fehler $? $LINENO \"$BASH_COMMAND\"' ERR",
        ]

    def fehler_ort(self) -> list[str]:
        return [f'  okm_info "{EINZUG}Zeile $okm_zeile, Befehl: $okm_befehl"']

    def lies_antwort(self, prompt: str) -> str:
        return f"read -r -p {_lit(prompt)} okm_antwort || true"

    def pause(self) -> list[str]:
        return [f"  read -r -p {_lit('Drücke Enter zum Schließen …')} _ || true"]


class ZshGenerator(ShGenerator):
    ziel: ClassVar[Ziel] = Ziel.ZSH
    shebang: ClassVar[str] = "#!/bin/zsh"
    errexit_aus: ClassVar[str] = "unsetopt ERR_EXIT"
    errexit_an: ClassVar[str] = "setopt ERR_EXIT"

    def fehlerbehandlung(self) -> list[str]:
        # Kein NO_UNSET: zsh beendet sich bei einer nicht gesetzten Variable sofort – ohne EXIT-Trap,
        # also ohne jede Meldung. Leer ist hier das kleinere Übel.
        return ["setopt ERR_EXIT PIPE_FAIL"]

    def fehler_handler(self) -> list[str]:
        # String-Trap statt TRAPZERR(): nur so liefert $LINENO die Zeile des fehlgeschlagenen Befehls
        return [
            "okm_bei_fehler() {",
            "  local okm_rc=$1 okm_zeile=$2",
            *self._fehler_pruefungen(),
            *self._fehler_ausgabe(),
            "}",
            "trap 'okm_bei_fehler $? $LINENO' ZERR",
        ]

    def fehler_ort(self) -> list[str]:
        return [f'  okm_info "{EINZUG}Zeile $okm_zeile"']

    def pause(self) -> list[str]:
        return [f"  read -r {_lit('okm_weiter?Drücke Enter zum Schließen …')} || true"]

    def lies_antwort(self, prompt: str) -> str:
        # zsh: "variable?Prompt"
        return f"read -r {_lit('okm_antwort?' + prompt)} || true"
