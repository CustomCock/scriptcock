"""Generator für Windows-Batch (``.cmd``, CRLF, UTF-8 ohne BOM + ``chcp 65001``).

Delayed Expansion ist immer aus. Die Ausgabe jedes Schritts wird in eine
temporäre Datei umgeleitet und danach auf Konsole und ins Log geschrieben
(CMD hat kein ``tee``). Interaktive Blöcke laufen ohne Umleitung.
"""

from __future__ import annotations

from typing import ClassVar

from app.escaping import Ziel, echo_cmd, kommentar_text
from app.generators.base import Generator, SchrittInfo
from app.ir import ScriptIR
from app.models.block import BlockDef

LOG = '"%OKM_LOG%"'
TMP = '"%OKM_TMP%"'


def _echo_beides(text: str) -> list[str]:
    """Text auf Konsole und ins Log (Umleitung vorne, damit z. B. „…2“ nicht als ``2>`` gilt)."""
    zeile = echo_cmd(text)
    return [zeile, f">>{LOG} {zeile}"]


class CmdGenerator(Generator):
    ziel: ClassVar[Ziel] = Ziel.CMD
    endung: ClassVar[str] = ".cmd"
    zeilenende: ClassVar[str] = "\r\n"

    def ist_kommentar(self, zeile: str) -> bool:
        z = zeile.lstrip().lower()
        return z.startswith(("rem ", "::")) or z == "rem"

    def kopf(self, ir: ScriptIR, defs: list[BlockDef]) -> list[str]:
        return [
            "@echo off",
            "chcp 65001 >nul",
            "setlocal EnableExtensions DisableDelayedExpansion",
            *[f"rem {z}".rstrip() for z in self.kommentar_zeilen(ir, defs)],
            "",
        ]

    def praeambel(self, ir: ScriptIR, gesamt: int, braucht_admin: bool) -> list[str]:
        zeilen = [
            'set "OKM_TS="',
            'for /f "delims=" %%T in (\'powershell -NoProfile -NonInteractive -Command '
            '"Get-Date -Format yyyyMMdd-HHmmss"\') do set "OKM_TS=%%T"',
            'if not defined OKM_TS set "OKM_TS=%RANDOM%"',
            'set "OKM_LOG=%TEMP%\\okm-script-%OKM_TS%.log"',
            'set "OKM_TMP=%TEMP%\\okm-script-%OKM_TS%.tmp"',
            f'set "OKM_GESAMT={gesamt}"',
            'set "OKM_OK=0"',
            'set "OKM_SCHRITT=0"',
            *_echo_beides("okm Script-Baukasten: " + ir.meta.titel),
            "",
        ]
        if ir.optionen.dry_run:
            zeilen += [*_echo_beides("NUR SIMULATION: Es wird nichts verändert."), ""]
        if braucht_admin:
            zeilen += [
                "rem Prüfung: Administratorrechte",
                "net session >nul 2>&1",
                "if errorlevel 1 goto :okm_kein_admin",
                "",
            ]
        return zeilen

    @property
    def _fehlerziel(self) -> str:
        """Sprungziel bei einem Fehler: Ausweichschritte des innersten „Versuche“-Blocks oder Abbruch."""
        return f":okm_sonst_{self._versuche[-1]}" if self.im_versuch else ":okm_fehler"

    def _gruppe(self, zeilen: list[str], interaktiv: bool) -> list[str]:
        ziel = self._fehlerziel
        if interaktiv:
            # "if errorlevel 1" heißt ">= 1"; negative Codes (z. B. winget-HRESULTs)
            # fängt erst "if not errorlevel 0" ab.
            return [*zeilen, f"if errorlevel 1 goto {ziel}", f"if not errorlevel 0 goto {ziel}"]
        return [
            "(",
            *zeilen,
            f") >{TMP} 2>&1",
            'if errorlevel 1 (set "OKM_RC=1") else if not errorlevel 0 (set "OKM_RC=1") '
            'else (set "OKM_RC=0")',
            f"type {TMP}",
            f"type {TMP} >>{LOG}",
            f'if "%OKM_RC%"=="1" goto {ziel}',
        ]

    def schritt(self, info: SchrittInfo) -> list[str]:
        b = info.block
        name = kommentar_text(Ziel.CMD, b.name)
        zeilen = [
            "rem " + "-" * 68,
            f"rem Schritt {info.bezeichnung}: {name} (Risiko: {b.risiko.value})",
            "rem " + "-" * 68,
            f'set "OKM_SCHRITT={info.nr}"',
            *_echo_beides(f"[{info.bezeichnung}] {info.fortschritt} ..."),
        ]
        if info.bestaetigen:
            zeilen += [
                echo_cmd(f"ACHTUNG: Dieser Schritt ist destruktiv: {b.name}"),
                'set "OKM_ANTWORT="',
                'set /p "OKM_ANTWORT=Zum Fortfahren JA eingeben (alles andere bricht ab): "',
                "if not defined OKM_ANTWORT goto :okm_abbruch",
                'set "OKM_ANTWORT=%OKM_ANTWORT:"=%"',
                'if not "%OKM_ANTWORT%"=="JA" goto :okm_abbruch',
            ]
        # Errorlevel zurücksetzen: viele interne Befehle (echo, set, pause …)
        # ändern ihn nicht, ein alter Wert würde sonst als Fehler gelten.
        zeilen += ["(call )", *self._gruppe(info.koerper, b.interaktiv)]
        if info.pruefung:
            zeilen += ["rem Prüfung", "(call )", *self._gruppe(info.pruefung, b.interaktiv)]
        zeilen += ["set /a OKM_OK+=1 >nul", ""]
        return zeilen

    def wenn_fehler(self, nr: int, versuch: list[str], sonst: list[str]) -> list[str]:
        # Kein "for"/"( … )"-Block: dort würden %VARIABLEN% nur einmal expandiert und
        # goto bräche den Block ab. Stattdessen lineare Sprungmarken.
        meldung = "echo(Schritt %OKM_SCHRITT% ist fehlgeschlagen. " + (
            "Es geht mit den Ausweichschritten weiter."
            if sonst
            else "Der Fehler wird wie vorgesehen übergangen."
        )
        return [
            f"rem ===== Versuche (Block {nr}) =====",
            *versuch,
            f"goto :okm_ende_{nr}",
            f":okm_sonst_{nr}",
            meldung,
            f">>{LOG} {meldung}",
            *sonst,
            f":okm_ende_{nr}",
            f"rem ===== Ende Versuche (Block {nr}) =====",
            "",
        ]

    def wiederhole(self, nr: int, anzahl: int, rumpf: list[str]) -> list[str]:
        var = f"OKM_DURCHLAUF_{nr}"
        return [
            f"rem ===== Wiederhole {anzahl}-mal (Block {nr}) =====",
            f'set "{var}=0"',
            f":okm_schleife_{nr}",
            f"set /a {var}+=1 >nul",
            f"echo(--- Durchlauf %{var}% von {anzahl} ---",
            f">>{LOG} echo(--- Durchlauf %{var}% von {anzahl} ---",
            *rumpf,
            f"if %{var}% LSS {anzahl} goto :okm_schleife_{nr}",
            "",
        ]

    def abschluss(self, ir: ScriptIR) -> list[str]:
        schluss = self.schluss_text().format(ok="%OKM_OK%", gesamt="%OKM_GESAMT%")
        ende = [
            f"del {TMP} >nul 2>&1",
            "if not defined OKM_KEINE_PAUSE pause",
            "endlocal",
        ]
        return [
            "echo(",
            f"echo({schluss}",
            f">>{LOG} echo({schluss}",
            f"echo(Protokoll: {LOG}",
            *ende,
            "exit /b 0",
            "",
            ":okm_fehler",
            "echo(",
            "echo(FEHLER in Schritt %OKM_SCHRITT% von %OKM_GESAMT%. Details siehe Ausgabe oben.",
            f">>{LOG} echo(FEHLER in Schritt %OKM_SCHRITT% von %OKM_GESAMT%.",
            "echo(Erfolgreich bis dahin: %OKM_OK% Schritte.",
            f"echo(Protokoll: {LOG}",
            *ende,
            "exit /b 1",
            "",
            ":okm_abbruch",
            "echo(Abgebrochen. Es wurde nichts weiter ausgeführt.",
            f">>{LOG} echo(Abgebrochen durch Benutzer.",
            f"echo(Protokoll: {LOG}",
            *ende,
            "exit /b 2",
            "",
            ":okm_kein_admin",
            "echo(Dieses Script braucht Administratorrechte.",
            'echo(Bitte die Eingabeaufforderung mit Rechtsklick ^> "Als Administrator ausführen" öffnen',
            "echo(und das Script erneut starten.",
            *ende,
            "exit /b 1",
        ]
