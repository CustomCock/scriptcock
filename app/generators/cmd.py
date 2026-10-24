"""Generator für Windows-Batch (``.cmd``, CRLF, UTF-8 ohne BOM + ``chcp 65001``).

Delayed Expansion ist immer aus. Die Ausgabe jedes Schritts wird in eine
temporäre Datei umgeleitet und danach auf Konsole und ins Log geschrieben
(CMD hat kein ``tee``). Interaktive Blöcke laufen ohne Umleitung.
"""

from __future__ import annotations

from typing import ClassVar

from app.escaping import Escaped, Ziel, echo_cmd, kommentar_text
from app.generators.base import EINZUG, LINIE, PLANMAESSIG, Generator, SchrittInfo
from app.ir import ScriptIR, Vergleich
from app.models.block import BlockDef, RueckgabeDef, RueckgabeTyp

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
        zeilen += info.nachher
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

    def ausgabe_zeilen(self, text: str) -> list[str]:
        return _echo_beides(text)

    @staticmethod
    def _beides(text: str) -> list[str]:
        # Text mit %VARIABLEN% (vom Generator, keine Benutzerwerte) auf Konsole und ins Log
        return [f"echo({text}", f">>{LOG} echo({text}"]

    def _fuss(self, *texte: str, vorher: list[str] | None = None) -> list[str]:
        """Zusammenfassung + Aufräumen; ``vorher`` = bereits escapte Zeilen direkt unter der Linie."""
        zeilen = [*_echo_beides(LINIE), *(vorher or [])]
        for text in texte:
            zeilen += self._beides(text)
        return [
            *zeilen,
            *self._beides(f" Protokoll: {LOG}"),
            *_echo_beides(LINIE),
            f"del {TMP} >nul 2>&1",
            "if not defined OKM_KEINE_PAUSE pause",
            "endlocal",
        ]

    def _bisher(self) -> str:
        if self.mit_kontrolle:
            return " Erfolgreich bis dahin: %OKM_OK% Schritte."
        return " Erfolgreich bis dahin: %OKM_OK% von %OKM_GESAMT% Schritten."

    def abschluss(self, ir: ScriptIR) -> list[str]:
        if self.mit_kontrolle:
            fertig = " Fertig: %OKM_OK% Schritte erfolgreich ausgeführt."
            fehler = " Abgebrochen bei Schritt %OKM_SCHRITT%."
        else:
            fertig = " Fertig: %OKM_OK% von %OKM_GESAMT% Schritten erfolgreich."
            fehler = " Abgebrochen bei Schritt %OKM_SCHRITT% von %OKM_GESAMT%."
        bisher = self._bisher()
        beides = self._beides
        fuss = self._fuss

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

    def rueckgaben_vorbelegen(self, rueckgaben: list[tuple[Escaped, RueckgabeDef]]) -> list[str]:
        return [
            "rem Rückgabewerte der Schritte (Namen vergibt der Baukasten; leer = unbekannt)",
            *(f'set "{name}="' for name, _ in rueckgaben),
            "",
        ]

    def rueckgabe_normalisieren(self, name: Escaped, r: RueckgabeDef) -> list[str]:
        if r.typ is RueckgabeTyp.ZAHL:
            # Bleibt nach Entfernen von Ziffern und "-" etwas übrig, ist es keine Zahl.
            return [f'if defined {name} for /f "delims=-0123456789" %%z in ("%{name}%") do set "{name}="']
        return [f'if defined {name} if not "%{name}%"=="1" set "{name}=0"']

    _OPERATOR: ClassVar[dict[Vergleich, str]] = {
        Vergleich.GLEICH: "EQU",
        Vergleich.UNGLEICH: "NEQ",
        Vergleich.KLEINER: "LSS",
        Vergleich.GROESSER: "GTR",
        Vergleich.KLEINER_GLEICH: "LEQ",
        Vergleich.GROESSER_GLEICH: "GEQ",
    }

    def wenn(
        self,
        nr: int,
        name: str,
        typ: RueckgabeTyp,
        vergleich: Vergleich,
        zahl: int | None,
        text: str,
        dann: list[str],
        sonst: list[str],
    ) -> list[str]:
        # Nur Sprungmarken, keine ( … )-Blöcke. %NAME% ist normalisiert (Ziffern bzw. 0/1).
        sonst_label = f":okm_wenn_sonst_{nr}"
        if vergleich is Vergleich.UNBEKANNT:
            sprung = [f"if defined {name} goto {sonst_label}"]
        elif vergleich is Vergleich.JA:
            sprung = [f'if not "%{name}%"=="1" goto {sonst_label}']
        elif vergleich is Vergleich.NEIN:
            sprung = [f'if not "%{name}%"=="0" goto {sonst_label}']
        else:
            sprung = [
                f"if not defined {name} goto {sonst_label}",
                f"if not %{name}% {self._OPERATOR[vergleich]} {int(zahl or 0)} goto {sonst_label}",
            ]
        return [
            f"rem ===== Wenn {kommentar_text(Ziel.CMD, text)} (Block {nr}) =====",
            *sprung,
            *_echo_beides("Bedingung erfüllt: " + text),
            *dann,
            f"goto :okm_wenn_ende_{nr}",
            sonst_label,
            *_echo_beides("Bedingung nicht erfüllt: " + text),
            *sonst,
            f":okm_wenn_ende_{nr}",
            f"rem ===== Ende Wenn (Block {nr}) =====",
            "",
        ]

    def abbrechen(self, meldung: str, code: int) -> list[str]:
        return [
            f"rem ===== Beenden (Exit-Code {code}) =====",
            *self._fuss(self._bisher(), vorher=_echo_beides(PLANMAESSIG + meldung)),
            f"exit /b {int(code)}",
            "",
        ]

    def warten(self, sekunden: int, text: str) -> list[str]:
        # "timeout" scheitert bei umgeleiteter Eingabe (Fernwartung) – ping auf localhost wartet zuverlässig
        return [*_echo_beides(text), f"ping -n {int(sekunden) + 1} 127.0.0.1 >nul", ""]

    def bestaetigung(self, meldung: str) -> list[str]:
        return [
            *_echo_beides(meldung),
            'set "OKM_ANTWORT="',
            'set /p "OKM_ANTWORT=Zum Fortfahren JA eingeben (alles andere bricht ab): "',
            "if not defined OKM_ANTWORT goto :okm_abbruch",
            'set "OKM_ANTWORT=%OKM_ANTWORT:"=%"',
            'if not "%OKM_ANTWORT%"=="JA" goto :okm_abbruch',
            "",
        ]

    def kommentar(self, text: str) -> str:
        return f"rem Notiz: {text}"
