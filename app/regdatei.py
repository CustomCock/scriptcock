"""Parser für .reg-Dateien (Export aus regedit) → Schritte der Registry-Bausteine.

Damit lässt sich eine Einstellung am Referenz-PC exportieren und in ein Script verwandeln. Der Parser
ist rein (Text → Einträge); jeder erzeugte Schritt läuft danach durch die normale Validierung
(Whitelist, Schutzliste, Bereich) – der .reg-Inhalt landet nie roh im Script.

Format (``Windows Registry Editor Version 5.00`` bzw. ``REGEDIT4``):
    [HKEY_LOCAL_MACHINE\\SOFTWARE\\Firma]      Schlüssel (anlegen)
    [-HKEY_LOCAL_MACHINE\\SOFTWARE\\Firma]     Schlüssel löschen
    "Name"="Text"          @="Standardwert"   "Name"=-  (Wert löschen)
    "Name"=dword:0000002a  "Name"=hex:0a,1b   hex(2): EXPAND_SZ, hex(7): MULTI_SZ, hex(b): QWORD
    Fortsetzungszeilen: „\\“ am Zeilenende; Kommentare mit „;“.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

KOPF_5 = "Windows Registry Editor Version 5.00"
KOPF_4 = "REGEDIT4"
MAX_TEXT = 1_000_000
MAX_SCHRITTE = 100

# Wurzel → (Bereich, Kurzform für den Pfad, Hinweis)
_WURZELN: dict[str, tuple[str, str, str]] = {
    "HKEY_LOCAL_MACHINE": ("computer", "HKLM", ""),
    "HKLM": ("computer", "HKLM", ""),
    "HKEY_CURRENT_USER": (
        "angemeldeter_benutzer",
        "",
        "HKEY_CURRENT_USER → Bereich „Angemeldeter Benutzer“ (nicht das Admin-Konto). Bei Bedarf im "
        "Schritt auf „Alle Benutzerprofile“ oder „Standardprofil“ ändern.",
    ),
    "HKCU": ("angemeldeter_benutzer", "", ""),
    "HKEY_CLASSES_ROOT": (
        "computer",
        "HKLM\\SOFTWARE\\Classes",
        "HKEY_CLASSES_ROOT → HKLM\\SOFTWARE\\Classes (gilt für alle Benutzer).",
    ),
    "HKCR": ("computer", "HKLM\\SOFTWARE\\Classes", ""),
}
_TYP_HEX = {
    "": "REG_BINARY",
    "0": None,  # REG_NONE – nicht unterstützt
    "1": "REG_SZ",
    "2": "REG_EXPAND_SZ",
    "3": "REG_BINARY",
    "4": "REG_DWORD",
    "7": "REG_MULTI_SZ",
    "b": "REG_QWORD",
}


class RegFehler(ValueError):
    pass


@dataclass
class RegEintrag:
    """Eine Operation aus der .reg-Datei (``zeile`` = Zeilennummer für Meldungen)."""

    art: str  # schluessel_anlegen | schluessel_loeschen | wert_setzen | wert_loeschen
    zeile: int
    bereich: str
    pfad: str
    wertname: str = ""
    typ: str = ""
    daten: str | int | list[str] | None = None


@dataclass
class RegErgebnis:
    eintraege: list[RegEintrag] = field(default_factory=list)
    fehler: list[str] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)


def dekodieren(roh: bytes) -> str:
    """regedit speichert UTF-16 LE mit BOM (Version 5.00); REGEDIT4 ist ANSI."""
    if roh.startswith(b"\xff\xfe") or roh.startswith(b"\xfe\xff"):
        return roh.decode("utf-16")
    if roh.startswith(b"\xef\xbb\xbf"):
        return roh[3:].decode("utf-8")
    try:
        return roh.decode("utf-8")
    except UnicodeDecodeError:
        return roh.decode("cp1252")


def _logische_zeilen(text: str) -> list[tuple[int, str]]:
    """Fortsetzungszeilen (``\\`` am Ende) zusammenfügen; Rückgabe (Zeilennummer, Inhalt)."""
    ergebnis: list[tuple[int, str]] = []
    puffer = ""
    start = 0
    for nr, zeile in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
        if not puffer:
            start = nr
            inhalt = zeile.strip()
        else:
            inhalt = zeile.strip()
        if inhalt.endswith("\\") and (puffer or "=" in inhalt) and not inhalt.startswith("["):
            puffer += inhalt[:-1]
            continue
        ergebnis.append((start, puffer + inhalt))
        puffer = ""
    if puffer:
        ergebnis.append((start, puffer))
    return ergebnis


def _zitat(text: str, pos: int) -> tuple[str, int]:
    """Liest ``"…"`` ab ``pos`` (mit ``\\\\`` und ``\\"``); Rückgabe (Text, Position nach dem Zitat)."""
    if pos >= len(text) or text[pos] != '"':
        raise RegFehler("Anführungszeichen erwartet.")
    teile: list[str] = []
    i = pos + 1
    while i < len(text):
        z = text[i]
        if z == "\\" and i + 1 < len(text):
            teile.append(text[i + 1])
            i += 2
            continue
        if z == '"':
            return "".join(teile), i + 1
        teile.append(z)
        i += 1
    raise RegFehler("Schließendes Anführungszeichen fehlt.")


def _hex_bytes(text: str) -> bytes:
    roh = text.replace(" ", "").replace("\t", "")
    if not roh:
        return b""
    teile = roh.split(",")
    try:
        werte = [int(t, 16) for t in teile]
    except ValueError:
        raise RegFehler("Ungültige Hex-Daten.") from None
    if any(not 0 <= w <= 255 or len(t) > 2 for w, t in zip(werte, teile, strict=True)):
        raise RegFehler("Ungültige Hex-Daten (Bytes 00–ff mit Komma getrennt).")
    return bytes(werte)


def _text_aus_bytes(daten: bytes, unicode: bool) -> str:
    if unicode:
        if len(daten) % 2:
            raise RegFehler("UTF-16-Daten mit ungerader Länge.")
        return daten.decode("utf-16-le")
    return daten.decode("cp1252")


def _wert(daten: str, unicode: bool) -> tuple[str, str | int | list[str]]:
    """Datenteil hinter ``=`` → (Typ, Daten)."""
    if daten.startswith('"'):
        text, ende = _zitat(daten, 0)
        if daten[ende:].strip():
            raise RegFehler("Unerwarteter Text nach dem Wert.")
        return "REG_SZ", text
    klein = daten.lower()
    if klein.startswith("dword:"):
        ziffern = daten[6:].strip()
        if not re.fullmatch(r"[0-9a-fA-F]{1,8}", ziffern):
            raise RegFehler("dword: braucht 1–8 Hex-Ziffern.")
        return "REG_DWORD", int(ziffern, 16)
    m = re.fullmatch(r"hex(?:\(([0-9a-fA-F]{1,8})\))?:(.*)", daten, re.S)
    if not m:
        raise RegFehler(f"Unbekanntes Datenformat „{daten[:20]}“.")
    kennung = (m[1] or "").lower().lstrip("0") if m[1] else ""
    if m[1] and not kennung:
        kennung = "0"
    typ = _TYP_HEX.get(kennung)
    if typ is None:
        raise RegFehler(f"Typ hex({m[1]}) wird nicht unterstützt.")
    roh = _hex_bytes(m[2])
    if typ == "REG_BINARY":
        return typ, " ".join(f"{b:02x}" for b in roh)
    if typ == "REG_DWORD":
        if len(roh) != 4:
            raise RegFehler("hex(4): braucht genau 4 Bytes.")
        return typ, int.from_bytes(roh, "little")
    if typ == "REG_QWORD":
        if len(roh) != 8:
            raise RegFehler("hex(b): braucht genau 8 Bytes.")
        return typ, int.from_bytes(roh, "little")
    text = _text_aus_bytes(roh, unicode)
    if typ == "REG_MULTI_SZ":
        return typ, [t for t in text.split("\0") if t]
    return typ, text.split("\0", 1)[0]  # SZ/EXPAND_SZ: abschließende Null weg


def _schluessel(text: str) -> tuple[str, str, str]:
    """Schlüsselname → (Bereich, Pfad wie im Baustein, Hinweis)."""
    wurzel, _, rest = text.partition("\\")
    eintrag = _WURZELN.get(wurzel.upper())
    if eintrag is None:
        if wurzel.upper() in ("HKEY_USERS", "HKU"):
            raise RegFehler(
                "HKEY_USERS wird nicht übernommen (SIDs gelten nur am Referenz-PC) – als HKEY_CURRENT_USER "
                "exportieren und den Bereich im Schritt wählen."
            )
        raise RegFehler(f"Wurzel „{wurzel}“ wird nicht unterstützt (nur HKLM, HKCU, HKCR).")
    bereich, kurz, hinweis = eintrag
    rest = rest.strip("\\")
    if not rest:
        raise RegFehler("Nur die Wurzel – bitte einen Schlüssel darunter exportieren.")
    pfad = f"{kurz}\\{rest}" if kurz else rest
    return bereich, pfad, hinweis


def parsen(text: str) -> RegErgebnis:
    """.reg-Text → Einträge. Fehlerhafte Zeilen landen in ``fehler`` (mit Zeilennummer), der Rest wird
    trotzdem gelesen."""
    erg = RegErgebnis()
    if len(text) > MAX_TEXT:
        erg.fehler.append("Der Inhalt ist zu groß (höchstens 1 MB).")
        return erg
    text = text.lstrip("﻿")
    zeilen = _logische_zeilen(text)
    inhalt = [(nr, z) for nr, z in zeilen if z and not z.startswith(";")]
    if not inhalt:
        erg.fehler.append("Kein Inhalt.")
        return erg
    kopf = inhalt[0][1]
    if kopf == KOPF_5:
        unicode = True
        inhalt = inhalt[1:]
    elif kopf == KOPF_4:
        unicode = False
        inhalt = inhalt[1:]
    else:
        unicode = True
        erg.hinweise.append(f"Kopfzeile „{KOPF_5}“ fehlt – der Inhalt wird trotzdem gelesen.")
    aktuell: tuple[str, str] | None = None  # (Bereich, Pfad) des offenen Schlüssels
    mit_werten = False
    gesehen_hinweise: set[str] = set()

    def schluessel_abschliessen() -> None:
        # Schlüssel ohne Werte → anlegen (bei Werten legt „Wert setzen“ ihn ohnehin an)
        if aktuell is not None and not mit_werten:
            erg.eintraege.append(RegEintrag("schluessel_anlegen", start_nr, aktuell[0], aktuell[1]))

    start_nr = 0
    for nr, zeile in inhalt:
        if zeile.startswith("["):
            schluessel_abschliessen()
            aktuell, mit_werten = None, False
            if not zeile.endswith("]"):
                erg.fehler.append(f"Zeile {nr}: „]“ fehlt.")
                continue
            name = zeile[1:-1].strip()
            loeschen = name.startswith("-")
            try:
                bereich, pfad, hinweis = _schluessel(name.lstrip("-").strip())
            except RegFehler as e:
                erg.fehler.append(f"Zeile {nr}: {e}")
                continue
            if hinweis and hinweis not in gesehen_hinweise:
                gesehen_hinweise.add(hinweis)
                erg.hinweise.append(hinweis)
            if loeschen:
                erg.eintraege.append(RegEintrag("schluessel_loeschen", nr, bereich, pfad))
            else:
                aktuell, start_nr = (bereich, pfad), nr
            continue
        if aktuell is None:
            erg.fehler.append(f"Zeile {nr}: Wert ohne gültigen Schlüssel davor – übersprungen.")
            continue
        try:
            if zeile.startswith("@"):
                name, rest = "", zeile[1:].lstrip()
            else:
                name, ende = _zitat(zeile, 0)
                rest = zeile[ende:].lstrip()
            if not rest.startswith("="):
                raise RegFehler("„=“ fehlt.")
            daten = rest[1:].strip()
            mit_werten = True
            if daten == "-":
                erg.eintraege.append(RegEintrag("wert_loeschen", nr, aktuell[0], aktuell[1], name))
                continue
            typ, wert = _wert(daten, unicode)
            erg.eintraege.append(RegEintrag("wert_setzen", nr, aktuell[0], aktuell[1], name, typ, wert))
        except RegFehler as e:
            erg.fehler.append(f"Zeile {nr}: {e}")
    schluessel_abschliessen()
    if len(erg.eintraege) > MAX_SCHRITTE:
        erg.fehler.append(f"Mehr als {MAX_SCHRITTE} Einträge – nur die ersten {MAX_SCHRITTE} zählen.")
        del erg.eintraege[MAX_SCHRITTE:]
    return erg


def schritt(e: RegEintrag) -> dict[str, Any]:
    """Eintrag → Schritt im Request-Format (``block_id`` + ``parameter``)."""
    basis: dict[str, Any] = {"bereich": e.bereich, "pfad": e.pfad}
    if e.art == "schluessel_anlegen":
        return {"block_id": "registry_schluessel_anlegen", "parameter": basis}
    if e.art == "schluessel_loeschen":
        return {"block_id": "registry_schluessel_loeschen", "parameter": basis}
    if e.art == "wert_loeschen":
        return {"block_id": "registry_wert_loeschen", "parameter": {**basis, "wertname": e.wertname}}
    daten: Any = e.daten
    if isinstance(daten, int):
        daten = str(daten)
    return {
        "block_id": "registry_wert_setzen",
        "parameter": {**basis, "wertname": e.wertname, "typ": e.typ, "daten": daten},
    }
