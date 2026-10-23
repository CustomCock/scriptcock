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
# Im Editor geänderte Scripte tragen diese Zeile im Kopf (19 Zeichen breites Feld wie die übrigen).
MANUELL_ZEILE = "Manuell bearbeitet: ja (nicht vom Baukasten geprüft)"


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


def _mit_markierung(zeilen: list[str], ziel: Ziel) -> list[str]:
    """``MANUELL_ZEILE`` nach „Benötigte Rechte:“ einfügen – fehlt der Kopf, nach Shebang/@echo off/chcp."""
    if any(MANUELL_ZEILE in z for z in zeilen):
        return zeilen
    kommentar = "rem " if ziel is Ziel.CMD else "# "
    for i, z in enumerate(zeilen[:60]):
        if "Benötigte Rechte:" in z and z.lstrip().lower().startswith(("#", "rem")):
            praefix = z[: z.index("Benötigte Rechte:")]
            return [*zeilen[: i + 1], praefix + MANUELL_ZEILE, *zeilen[i + 1 :]]
    pos = 0
    while pos < len(zeilen) and pos < 3:
        z = zeilen[pos].strip().lower()
        if (pos == 0 and z.startswith(("#!", "#requires", "@echo off"))) or z == CHCP:
            pos += 1
        else:
            break
    return [*zeilen[:pos], kommentar + MANUELL_ZEILE, *zeilen[pos:]]


def zeilenende(ziel: Ziel) -> str:
    return "\n" if ziel in (Ziel.BASH, Ziel.ZSH) else "\r\n"


def text_fuer(text: str, ziel: Ziel, *, manuell_bearbeitet: bool = False) -> str:
    """Text mit den Zeilenenden des Ziels (ohne BOM), endet mit genau einem Zeilenende."""
    zeilen = _normalisiert(text)
    if ziel is Ziel.CMD:
        zeilen = _mit_chcp(zeilen)
    if manuell_bearbeitet:
        zeilen = _mit_markierung(zeilen, ziel)
    ende = zeilenende(ziel)
    return ende.join(zeilen) + ende


def exportiere(text: str, ziel: Ziel, *, manuell_bearbeitet: bool = False) -> bytes:
    """Exakter Dateiinhalt für ``ziel``; ``manuell_bearbeitet`` ergänzt die Kopfzeile (idempotent)."""
    inhalt = text_fuer(text, ziel, manuell_bearbeitet=manuell_bearbeitet).encode("utf-8")
    return BOM + inhalt if ziel is Ziel.POWERSHELL else inhalt
