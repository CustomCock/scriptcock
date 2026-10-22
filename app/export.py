"""Dateiformat der Scripte – die einzige Stelle mit den Regeln für Encoding und Zeilenenden.

Der Generator und der Export-Endpunkt (``POST /api/script/export``) nutzen beide
:func:`exportiere`, damit Download, Kopieren und Bibliothek byte-gleich sind:

* PowerShell: UTF-8 **mit** BOM, CRLF – PowerShell 5.1 liest UTF-8 ohne BOM als ANSI.
* CMD: UTF-8 **ohne** BOM (``ï»¿@echo`` wäre kein Befehl), CRLF, ``chcp 65001 >nul``.
* bash/zsh: UTF-8 ohne BOM, LF – ein CR ergäbe ``$'\\r': command not found``.
"""

from __future__ import annotations

from app.escaping import Ziel

BOM = b"\xef\xbb\xbf"
CHCP = "chcp 65001 >nul"


def _normalisiert(text: str) -> list[str]:
    text = text.removeprefix("﻿").replace("\r\n", "\n").replace("\r", "\n")
    zeilen = text.split("\n")
    if zeilen and zeilen[-1] == "":
        zeilen.pop()
    return zeilen


def _mit_chcp(zeilen: list[str]) -> list[str]:
    """``chcp 65001 >nul`` direkt nach ``@echo off`` sicherstellen (vorher wären Umlaute kaputt)."""
    if any(z.strip().lower() == CHCP for z in zeilen[:5]):
        return zeilen
    if zeilen and zeilen[0].strip().lower() == "@echo off":
        return [zeilen[0], CHCP, *zeilen[1:]]
    return [CHCP, *zeilen]


def zeilenende(ziel: Ziel) -> str:
    return "\n" if ziel in (Ziel.BASH, Ziel.ZSH) else "\r\n"


def text_fuer(text: str, ziel: Ziel) -> str:
    """Text mit den Zeilenenden des Ziels (ohne BOM), endet mit genau einem Zeilenende."""
    zeilen = _normalisiert(text)
    if ziel is Ziel.CMD:
        zeilen = _mit_chcp(zeilen)
    ende = zeilenende(ziel)
    return ende.join(zeilen) + ende


def exportiere(text: str, ziel: Ziel) -> bytes:
    """Exakter Dateiinhalt für ``ziel``."""
    inhalt = text_fuer(text, ziel).encode("utf-8")
    return BOM + inhalt if ziel is Ziel.POWERSHELL else inhalt
