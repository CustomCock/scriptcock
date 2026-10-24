"""Escaping von Werten pro Zielsprache – sicherheitskritisch.

Grundregeln (siehe docs/sicherheit.md):

* Jeder Wert wird zu einem *vollständigen* Literal der Zielsprache, inklusive
  der umschließenden Anführungszeichen. Templates setzen Platzhalter daher nie
  selbst in Quotes.
* Steuerzeichen (Zeilenumbrüche, NUL, Tabs, Bidi-Steuerzeichen, …) werden
  grundsätzlich abgelehnt, nicht escaped.
* Wo ein Zeichen in einer Zielsprache nicht sicher darstellbar ist (z. B. ``"``
  in CMD), wird der Wert abgelehnt.
* Das Ergebnis ist immer ein :class:`Escaped`. Die Code-Template-Umgebung
  (``app/codeenv.py``) gibt ausschließlich ``Escaped``-Objekte aus.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import Any


class Ziel(StrEnum):
    POWERSHELL = "powershell"
    CMD = "cmd"
    BASH = "bash"
    ZSH = "zsh"


class UnsicherError(ValueError):
    """Ein Wert kann für die Zielsprache nicht sicher dargestellt werden."""


class Escaped(str):
    """Markiert einen String als fertig escapten Code-Baustein.

    ``wert`` enthält den ursprünglichen (validierten) Wert. Er darf in
    Template-Bedingungen verwendet werden (``{% if x.wert == 'apt' %}``), wird
    aber nie ausgegeben – die Code-Umgebung lehnt alles ab, was kein
    ``Escaped`` ist.
    """

    __slots__ = ("_wahr", "wert")
    wert: Any
    _wahr: bool | None

    def __new__(cls, code: str, wert: Any = None, wahr: bool | None = None) -> Escaped:
        obj = super().__new__(cls, code)
        obj.wert = wert
        obj._wahr = wahr
        return obj

    def __bool__(self) -> bool:
        if self._wahr is not None:
            return self._wahr
        return len(self) > 0


# Unicode-Zeichen, die PowerShell innerhalb von Single-Quote-Strings als
# Anführungszeichen behandelt (siehe PowerShell CharExtensions.IsSingleQuote).
_PS_SINGLE_QUOTES = frozenset("'‘’‚‛")


def pruefe_zeichen(wert: str) -> None:
    """Lehnt Steuer- und Formatzeichen ab (Zeilenumbrüche, NUL, Bidi, …)."""
    for zeichen in wert:
        kategorie = unicodedata.category(zeichen)
        if kategorie in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"):
            raise UnsicherError(
                "Die Eingabe enthält unsichtbare Steuerzeichen oder Zeilenumbrüche. "
                "Bitte nur eine einzelne Zeile normalen Text eingeben."
            )


def powershell_literal(wert: str) -> Escaped:
    """Single-quoted PowerShell-String; jedes Single-Quote-Zeichen wird verdoppelt."""
    pruefe_zeichen(wert)
    innen = "".join(z + z if z in _PS_SINGLE_QUOTES else z for z in wert)
    return Escaped(f"'{innen}'", wert)


def sh_literal(wert: str) -> Escaped:
    """Single-quoted POSIX-String (bash und zsh): ``'`` → ``'\\''``."""
    pruefe_zeichen(wert)
    return Escaped("'" + wert.replace("'", "'\\''") + "'", wert)


def cmd_literal(wert: str) -> Escaped:
    """Double-quoted Batch-Argument.

    Innerhalb von ``"…"`` sind ``^ & | < > ( )`` wörtlich. ``%`` wird zu ``%%``.
    ``!`` ist wörtlich, weil jedes Script mit ``DisableDelayedExpansion`` läuft.
    ``"`` kann nicht sicher escaped werden und wird abgelehnt.
    """
    pruefe_zeichen(wert)
    if '"' in wert:
        raise UnsicherError('Anführungszeichen (") sind in Windows-CMD-Scripten nicht erlaubt.')
    innen = wert.replace("%", "%%")
    # Ein abschließender Backslash würde bei Programmen mit MSVCRT-Argument-
    # parsing das schließende Quote escapen ("C:\" → C:"). Verdoppeln.
    nachlauf = len(innen) - len(innen.rstrip("\\"))
    innen += "\\" * nachlauf
    return Escaped('"' + innen + '"', wert)


def literal(ziel: Ziel, wert: str) -> Escaped:
    if ziel is Ziel.POWERSHELL:
        return powershell_literal(wert)
    if ziel is Ziel.CMD:
        return cmd_literal(wert)
    return sh_literal(wert)


def zahl(wert: int) -> Escaped:
    """Ganzzahl ohne Quotes. ``bool`` ist ausdrücklich ausgeschlossen."""
    if isinstance(wert, bool) or not isinstance(wert, int):
        raise UnsicherError("Interner Fehler: Zahl erwartet.")
    return Escaped(str(wert), wert)


def wahrheitswert(ziel: Ziel, wert: bool) -> Escaped:
    """Bool-Literal; im Template als Bedingung nutzbar (``{% if x %}``)."""
    if ziel is Ziel.POWERSHELL:
        code = "$true" if wert else "$false"
    elif ziel is Ziel.CMD:
        code = "1" if wert else "0"
    else:
        code = "true" if wert else "false"
    return Escaped(code, wert, wahr=wert)


def liste(ziel: Ziel, werte: list[str | int]) -> Escaped:
    """Mehrere Werte, jeder einzeln escaped.

    PowerShell: ``@('a', 'b')`` · bash/zsh: ``'a' 'b'`` (für ``arr=({{ x }})``) ·
    CMD: ``"a" "b"`` (für ``for %%x in ({{ x }}) do …``). Zahlen ohne Quotes.
    """
    teile = [
        zahl(w) if isinstance(w, int) and not isinstance(w, bool) else literal(ziel, str(w)) for w in werte
    ]
    if ziel is Ziel.POWERSHELL:
        return Escaped("@(" + ", ".join(teile) + ")", list(werte))
    return Escaped(" ".join(teile), list(werte))


def leer() -> Escaped:
    """Platzhalter für einen nicht ausgefüllten optionalen Parameter."""
    return Escaped("", None, wahr=False)


def vertraut(code: str) -> Escaped:
    """Vom Generator selbst erzeugter Code (z. B. `` -WhatIf``) – nie für Eingaben!"""
    return Escaped(code)


# --- Rückgabewerte (Variablen, deren Namen nur der Generator vergibt) ----------

_RUECKGABE_ID = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


def variablen_name(ziel: Ziel, nr: int, rid: str) -> str:
    """``OkmS3_frei_prozent`` / ``okm_s3_frei_prozent`` / ``OKM_S3_FREI_PROZENT``."""
    if not (isinstance(nr, int) and nr > 0 and _RUECKGABE_ID.match(rid)):
        raise UnsicherError(f"Ungültiger Rückgabewert: {nr}.{rid}")
    if ziel is Ziel.POWERSHELL:
        return f"OkmS{nr}_{rid}"
    if ziel is Ziel.CMD:
        return f"OKM_S{nr}_{rid.upper()}"
    return f"okm_s{nr}_{rid}"


def variable_setzen(ziel: Ziel, nr: int, rid: str) -> Escaped:
    """Ziel einer Zuweisung im Block-Template (``{{ rueckgabe_x }} = …``)."""
    name = variablen_name(ziel, nr, rid)
    return Escaped("$script:" + name if ziel is Ziel.POWERSHELL else name)


def variable_lesen(ziel: Ziel, nr: int, rid: str) -> Escaped:
    """Vollständiger Ausdruck, der den Wert liest (wie ein Literal: Templates quoten nicht selbst).

    Die Werte sind vom Generator normalisiert (Ziffern, 0/1 bzw. leer) – auch ``%…%`` in CMD
    kann daher keine Sonderzeichen einschleusen.
    """
    name = variablen_name(ziel, nr, rid)
    if ziel is Ziel.POWERSHELL:
        return Escaped("$script:" + name, f"{nr}.{rid}")
    if ziel is Ziel.CMD:
        return Escaped(f'"%{name}%"', f"{nr}.{rid}")
    return Escaped(f'"${name}"', f"{nr}.{rid}")


# --- Ausgabe von beliebigem Text (Fortschrittsmeldungen, Simulation) ---------


def echo_powershell(text: str) -> str:
    return "Write-Host " + powershell_literal(text)


def echo_sh(text: str) -> str:
    return "printf '%s\\n' " + sh_literal(text)


_CMD_ECHO_SONDER = frozenset('^&|<>()"')


def echo_cmd(text: str) -> str:
    """``echo(`` mit Caret-Escaping aller Sonderzeichen.

    Weil auch ``"`` mit ``^`` escaped wird, wechselt der Parser nie in den
    Quote-Modus – jedes ``^`` wirkt also. ``%`` wird verdoppelt.
    """
    pruefe_zeichen(text)
    teile = []
    for z in text:
        if z in _CMD_ECHO_SONDER:
            teile.append("^" + z)
        elif z == "%":
            teile.append("%%")
        else:
            teile.append(z)
    return "echo(" + "".join(teile)


def echo(ziel: Ziel, text: str) -> str:
    if ziel is Ziel.POWERSHELL:
        return echo_powershell(text)
    if ziel is Ziel.CMD:
        return echo_cmd(text)
    return echo_sh(text)


def kommentar_text(ziel: Ziel, text: str) -> str:
    """Text für Kommentarzeilen. Zeilenumbrüche werden vorher entfernt.

    CMD-Kommentare (``rem``) sind tückisch (``%``-Expansion, ``^`` am
    Zeilenende verlängert den Kommentar), daher werden dort alle
    Sonderzeichen ersetzt.
    """
    sauber = "".join(
        " " if unicodedata.category(z) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp") else z for z in text
    )
    if ziel is Ziel.CMD:
        sauber = "".join("_" if z in '%^&|<>"!' else z for z in sauber)
    return sauber.strip()
