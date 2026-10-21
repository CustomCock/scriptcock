"""Generatoren für Bash (Linux) und zsh (macOS) – ``.sh``, LF, UTF-8.

Beide teilen sich den Aufbau; Unterschiede sind Shebang, Fehlerbehandlung
(``set -Eeuo pipefail`` + ``trap ERR`` vs. ``setopt`` + ``TRAPZERR``) und die
Syntax von ``read``.
"""

from __future__ import annotations

from typing import ClassVar

from app.escaping import Ziel, sh_literal
from app.generators.base import Generator, SchrittInfo, einruecken
from app.ir import ScriptIR
from app.models.block import BlockDef


def _lit(text: str) -> str:
    return str(sh_literal(text))


def _ausgabe(text: str) -> str:
    return f"printf '%s\\n' {_lit(text)}"


class ShGenerator(Generator):
    zeilenende: ClassVar[str] = "\n"
    endung: ClassVar[str] = ".sh"
    shebang: ClassVar[str]
    sudo_hinweis: ClassVar[str]
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

    def praeambel(self, ir: ScriptIR, gesamt: int, braucht_admin: bool) -> list[str]:
        zeilen = [
            *self.fehlerbehandlung(),
            "",
            'OKM_LOG="/tmp/okm-script-$(date +%Y%m%d-%H%M%S).log"',
            *([] if self.mit_kontrolle else [f"OKM_GESAMT={gesamt}"]),
            "OKM_OK=0",
            "OKM_SCHRITT='-'",
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
            'exec > >(tee -a "$OKM_LOG") 2>&1',
            "",
            *self.fehler_handler(),
            "",
        ]
        if ir.optionen.dry_run:
            zeilen += [_ausgabe("NUR SIMULATION: Es wird nichts verändert."), ""]
        if braucht_admin:
            zeilen += [
                "# Prüfung: root-Rechte",
                'if [ "$(id -u)" -ne 0 ]; then',
                f"  {_ausgabe('Dieses Script braucht Administratorrechte (root).')}",
                f"  {_ausgabe(self.sudo_hinweis)}",
                "  printf 'Protokoll: %s\\n' \"$OKM_LOG\"",
                "  exit 1",
                "fi",
                "",
            ]
        return zeilen

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
            '    printf \'\\nSchritt %s ist fehlgeschlagen (Exit-Code %s).\\n\' "$OKM_SCHRITT" "$okm_rc"',
            '    exit "$okm_rc"',
            "  fi",
        ]

    def _fehler_ausgabe(self) -> list[str]:
        """Abbruch des ganzen Scripts mit Zusammenfassung."""
        if not self.mit_kontrolle:
            return [
                '  printf \'\\nFEHLER in Schritt %s (Exit-Code %s).\\n\' "$OKM_SCHRITT" "$okm_rc"',
                '  printf \'Erfolgreich bis dahin: %s von %s Schritten.\\n\' "$OKM_OK" "$OKM_GESAMT"',
                "  printf 'Protokoll: %s\\n' \"$OKM_LOG\"",
                '  exit "$okm_rc"',
            ]
        return [
            '  printf \'\\nFEHLER in Schritt %s (Exit-Code %s).\\n\' "$OKM_SCHRITT" "$okm_rc"',
            "  printf 'Erfolgreich bis dahin: %s Schritte.\\n' \"$OKM_OK\"",
            "  printf 'Protokoll: %s\\n' \"$OKM_LOG\"",
            '  rm -f "$OKM_ZAEHLER"',
            '  exit "$okm_rc"',
        ]

    def schritt(self, info: SchrittInfo) -> list[str]:
        b = info.block
        zeilen = [
            "# " + "-" * 68,
            f"# Schritt {info.bezeichnung}: {b.name} (Risiko: {b.risiko.value})",
            "# " + "-" * 68,
            f"OKM_SCHRITT={_lit(f'{info.bezeichnung} ({b.name})')}",
            _ausgabe(f"[{info.bezeichnung}] {info.fortschritt} …"),
        ]
        if info.bestaetigen:
            zeilen += [
                _ausgabe(f"ACHTUNG: Dieser Schritt ist destruktiv: {b.name}"),
                'okm_antwort=""',
                self.lies_antwort("Zum Fortfahren JA eingeben (alles andere bricht ab): "),
                'if [ "$okm_antwort" != "JA" ]; then',
                f"  {_ausgabe('Abgebrochen. Es wurde nichts weiter ausgeführt.')}",
                *(
                    [f"  exit {self.ABBRUCH_CODE}"]
                    if self.im_versuch
                    else ["  printf 'Protokoll: %s\\n' \"$OKM_LOG\"", "  exit 2"]
                ),
                "fi",
            ]
        zeilen += info.koerper
        if info.pruefung:
            zeilen += ["# Prüfung", *info.pruefung]
        zeilen += ["okm_geschafft" if self.mit_kontrolle else "OKM_OK=$((OKM_OK + 1))", ""]
        return zeilen

    def wenn_fehler(self, nr: int, versuch: list[str], sonst: list[str]) -> list[str]:
        rc = f"okm_rc_{nr}"
        weiterreichen = (
            [f"  exit {self.ABBRUCH_CODE}"]
            if self.im_versuch
            else ["  printf 'Protokoll: %s\\n' \"$OKM_LOG\"", '  rm -f "$OKM_ZAEHLER"', "  exit 2"]
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
            f"  {_ausgabe(self.meldung_ausweichen(bool(sonst)))}",
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
            f"  printf '%s\\n' \"--- Durchlauf ${var} von {anzahl} ---\"",
            *einruecken(rumpf, 2),
            "done",
            "",
        ]

    def abschluss(self, ir: ScriptIR) -> list[str]:
        if self.mit_kontrolle:
            return [
                "printf '\\nFertig, %s Schritte erfolgreich ausgeführt.\\n' \"$OKM_OK\"",
                "printf 'Protokoll: %s\\n' \"$OKM_LOG\"",
                'rm -f "$OKM_ZAEHLER"',
            ]
        return [
            'printf \'\\nFertig, %s von %s Schritten erfolgreich.\\n\' "$OKM_OK" "$OKM_GESAMT"',
            "printf 'Protokoll: %s\\n' \"$OKM_LOG\"",
        ]


class BashGenerator(ShGenerator):
    ziel: ClassVar[Ziel] = Ziel.BASH
    shebang: ClassVar[str] = "#!/usr/bin/env bash"
    sudo_hinweis: ClassVar[str] = "Bitte so starten: sudo bash ./script.sh"
    errexit_aus: ClassVar[str] = "set +e"
    errexit_an: ClassVar[str] = "set -e"

    def fehlerbehandlung(self) -> list[str]:
        return ["set -Eeuo pipefail"]

    def fehler_handler(self) -> list[str]:
        return [
            "okm_fehler() {",
            "  local okm_rc=$?",
            *self._fehler_pruefungen(),
            "  trap - ERR",
            *self._fehler_ausgabe(),
            "}",
            "trap okm_fehler ERR",
        ]

    def lies_antwort(self, prompt: str) -> str:
        return f"read -r -p {_lit(prompt)} okm_antwort || true"


class ZshGenerator(ShGenerator):
    ziel: ClassVar[Ziel] = Ziel.ZSH
    shebang: ClassVar[str] = "#!/bin/zsh"
    sudo_hinweis: ClassVar[str] = "Bitte so starten: sudo zsh ./script.sh"
    errexit_aus: ClassVar[str] = "unsetopt ERR_EXIT"
    errexit_an: ClassVar[str] = "setopt ERR_EXIT"

    def fehlerbehandlung(self) -> list[str]:
        return ["setopt ERR_EXIT NO_UNSET PIPE_FAIL"]

    def fehler_handler(self) -> list[str]:
        return [
            "TRAPZERR() {",
            "  local okm_rc=$?",
            *self._fehler_pruefungen(),
            *self._fehler_ausgabe(),
            "}",
        ]

    def lies_antwort(self, prompt: str) -> str:
        # zsh: "variable?Prompt"
        return f"read -r {_lit('okm_antwort?' + prompt)} || true"
