"""Generator für Windows-Batch (``.cmd``, CRLF, UTF-8 ohne BOM + ``chcp 65001``).

Delayed Expansion ist immer aus. Die Ausgabe jedes Schritts wird in eine
temporäre Datei umgeleitet und danach auf Konsole und ins Log geschrieben
(CMD hat kein ``tee``). Interaktive Blöcke laufen ohne Umleitung.
"""

from __future__ import annotations

from typing import ClassVar

from app.escaping import Ziel, echo_cmd, kommentar_text
from app.generators.base import EINZUG, LINIE, Generator, SchrittInfo
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
            'set "OKM_RC=0"',
            "rem /nopause: am Ende nicht auf eine Taste warten (Fernwartung/RMM)",
            'if /i "%~1"=="/nopause" set "OKM_KEINE_PAUSE=1"',
            'set "OKM_TIPP="',
            *[z for k in self.kopf_ausgabe(ir) for z in _echo_beides(k)],
            "",
        ]
        if braucht_admin:
            zeilen += [
                "rem Rechte: Administrator für "
                + kommentar_text(Ziel.CMD, self.schritt_liste(self._admin_schritte)),
                "net session >nul 2>&1",
                "if errorlevel 1 goto :okm_rechte_anfordern",
                *_echo_beides("Rechte: als Administrator gestartet"),
                "",
            ]
        else:
            zeilen += [*_echo_beides("Rechte: ohne erhöhte Rechte"), ""]
        return zeilen

    @property
    def _fehlerziel(self) -> str:
        """Sprungziel bei einem Fehler: Ausweichschritte des innersten „Versuche“-Blocks oder Abbruch."""
        return f":okm_sonst_{self._versuche[-1]}" if self.im_versuch else ":okm_fehler"

    def _gruppe(self, zeilen: list[str], interaktiv: bool) -> list[str]:
        ziel = self._fehlerziel
        # Exit-Code direkt sichern (auch negative Codes wie winget-HRESULTs), bevor "type" ihn ändert.
        # Im Generator erlaubt; in Block-Templates ist %ERRORLEVEL% verboten.
        if interaktiv:
            return [*zeilen, 'set "OKM_RC=%ERRORLEVEL%"', f'if not "%OKM_RC%"=="0" goto {ziel}']
        return [
            "(",
            *zeilen,
            f") >{TMP} 2>&1",
            'set "OKM_RC=%ERRORLEVEL%"',
            f"type {TMP}",
            f"type {TMP} >>{LOG}",
            f'if not "%OKM_RC%"=="0" goto {ziel}',
        ]

    def schritt(self, info: SchrittInfo) -> list[str]:
        b = info.block
        name = kommentar_text(Ziel.CMD, b.name)
        zeilen = [
            "rem " + "-" * 68,
            f"rem Schritt {info.bezeichnung}: {name} (Risiko: {b.risiko.value})",
            "rem " + "-" * 68,
            f'set "OKM_SCHRITT={info.nr}"',
            # Tipp ohne CMD-Sonderzeichen, weil er später per %OKM_TIPP% ausgegeben wird
            f'set "OKM_TIPP={kommentar_text(Ziel.CMD, b.tipp)}"' if b.tipp else 'set "OKM_TIPP="',
            *_echo_beides(self.schritt_titel(info)),
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
        zeilen += ["set /a OKM_OK+=1 >nul", *_echo_beides(EINZUG + "OK"), ""]
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
        if self.mit_kontrolle:
            fertig = " Fertig: %OKM_OK% Schritte erfolgreich ausgeführt."
            fehler = " Abgebrochen bei Schritt %OKM_SCHRITT%."
            bisher = " Erfolgreich bis dahin: %OKM_OK% Schritte."
        else:
            fertig = " Fertig: %OKM_OK% von %OKM_GESAMT% Schritten erfolgreich."
            fehler = " Abgebrochen bei Schritt %OKM_SCHRITT% von %OKM_GESAMT%."
            bisher = " Erfolgreich bis dahin: %OKM_OK% von %OKM_GESAMT% Schritten."

        def beides(text: str) -> list[str]:
            # Text mit %VARIABLEN% (vom Generator, keine Benutzerwerte) auf Konsole und ins Log
            return [f"echo({text}", f">>{LOG} echo({text}"]

        def fuss(*texte: str) -> list[str]:
            zeilen = [*_echo_beides(LINIE)]
            for text in texte:
                zeilen += beides(text)
            return [
                *zeilen,
                *beides(f" Protokoll: {LOG}"),
                *_echo_beides(LINIE),
                f"del {TMP} >nul 2>&1",
                "if not defined OKM_KEINE_PAUSE pause",
                "endlocal",
            ]

        rechte = (
            [
                ":okm_rechte_anfordern",
                *_echo_beides(
                    "Dieses Script braucht Administratorrechte für: "
                    + self.schritt_liste(self._admin_schritte)
                    + "."
                ),
                *_echo_beides(
                    "Es wird jetzt mit Administratorrechten neu gestartet (Windows fragt gleich nach)."
                ),
                # Pfad über eine Umgebungsvariable an PowerShell – so stören Leerzeichen und ' im Pfad nicht
                'set "OKM_SELBST=%~f0"',
                'powershell -NoProfile -Command "Start-Process -FilePath $env:OKM_SELBST -Verb RunAs"',
                "if errorlevel 1 goto :okm_rechte_abgelehnt",
                *_echo_beides("Läuft im neuen Fenster mit Administratorrechten weiter."),
                "endlocal",
                "exit /b 0",
                "",
                ":okm_rechte_abgelehnt",
                *beides(
                    EINZUG + "FEHLER  Die Administratorrechte wurden abgelehnt (Benutzerkontensteuerung)."
                ),
                *fuss(" Abgebrochen: fehlende Administratorrechte."),
                "exit /b 1",
            ]
            if self._admin_schritte
            else []
        )

        return [
            *fuss(fertig),
            "exit /b 0",
            "",
            ":okm_fehler",
            *beides(EINZUG + "FEHLER  Schritt %OKM_SCHRITT% endete mit Fehlercode %OKM_RC%."),
            f"if defined OKM_TIPP echo({EINZUG}Tipp: %OKM_TIPP%",
            f"if defined OKM_TIPP >>{LOG} echo({EINZUG}Tipp: %OKM_TIPP%",
            *fuss(fehler, bisher),
            "exit /b 1",
            "",
            ":okm_abbruch",
            *fuss(" Abgebrochen durch Benutzer. Es wurde nichts weiter ausgeführt."),
            "exit /b 2",
            "",
            *rechte,
        ]
