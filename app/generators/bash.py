"""Generatoren für Bash (Linux) und zsh (macOS) – ``.sh``, LF, UTF-8.

Beide teilen sich den Aufbau; Unterschiede sind Shebang, Fehlerbehandlung
(``set -Eeuo pipefail`` + ``trap ERR`` vs. ``setopt`` + ``TRAPZERR``) und die
Syntax von ``read``.
"""

from __future__ import annotations

from typing import ClassVar

from app.escaping import Ziel, sh_literal
from app.generators.base import Generator, SchrittInfo
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
            f"OKM_GESAMT={gesamt}",
            "OKM_OK=0",
            "OKM_SCHRITT='-'",
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

    @staticmethod
    def _fehler_ausgabe() -> list[str]:
        return [
            '  printf \'\\nFEHLER in Schritt %s (Exit-Code %s).\\n\' "$OKM_SCHRITT" "$okm_rc"',
            '  printf \'Erfolgreich bis dahin: %s von %s Schritten.\\n\' "$OKM_OK" "$OKM_GESAMT"',
            "  printf 'Protokoll: %s\\n' \"$OKM_LOG\"",
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
                "  printf 'Protokoll: %s\\n' \"$OKM_LOG\"",
                "  exit 2",
                "fi",
            ]
        zeilen += info.koerper
        if info.pruefung:
            zeilen += ["# Prüfung", *info.pruefung]
        zeilen += ["OKM_OK=$((OKM_OK + 1))", ""]
        return zeilen

    def abschluss(self, ir: ScriptIR) -> list[str]:
        return [
            'printf \'\\nFertig, %s von %s Schritten erfolgreich.\\n\' "$OKM_OK" "$OKM_GESAMT"',
            "printf 'Protokoll: %s\\n' \"$OKM_LOG\"",
        ]


class BashGenerator(ShGenerator):
    ziel: ClassVar[Ziel] = Ziel.BASH
    shebang: ClassVar[str] = "#!/usr/bin/env bash"
    sudo_hinweis: ClassVar[str] = "Bitte so starten: sudo bash ./script.sh"

    def fehlerbehandlung(self) -> list[str]:
        return ["set -Eeuo pipefail"]

    def fehler_handler(self) -> list[str]:
        return [
            "okm_fehler() {",
            "  local okm_rc=$?",
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

    def fehlerbehandlung(self) -> list[str]:
        return ["setopt ERR_EXIT NO_UNSET PIPE_FAIL"]

    def fehler_handler(self) -> list[str]:
        return [
            "TRAPZERR() {",
            "  local okm_rc=$?",
            *self._fehler_ausgabe(),
            "}",
        ]

    def lies_antwort(self, prompt: str) -> str:
        # zsh: "variable?Prompt"
        return f"read -r {_lit('okm_antwort?' + prompt)} || true"
