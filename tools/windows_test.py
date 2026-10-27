#!/usr/bin/env python3
"""Testscripte + Manifest für den Windows-CI-Job (``.github/workflows/ci.yml``, Job ``windows``).

Erzeugt mit dem echten Generator PowerShell- und CMD-Scripte für die Registry-Bausteine (gegen
``HKLM\\SOFTWARE\\OkmTest\\<PS|CMD>`` und ``HKCU\\Software\\OkmTest\\<PS|CMD>`` über den Bereich
„Angemeldeter Benutzer“) sowie die Checkliste-Scripte (``tools/checkliste_scripte.py``). Dazu
``manifest.json`` mit Vorbedingungen (reg.exe-Aufrufe), erwarteten Exit-Codes und Prüfungen, die
``tests/windows/lauf.ps1`` auf dem Runner abarbeitet.

Aufruf:  python tools/windows_test.py [zielordner]
         (Standard: C:\\okm-ci unter Windows, sonst ./windows-test)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from app.escaping import Ziel  # noqa: E402
from app.generators import generator_fuer  # noqa: E402
from app.models.request import SchrittEingabe, ScriptRequest  # noqa: E402
from app.registry import Registry, lade_registry  # noqa: E402
from app.validation import validiere_request  # noqa: E402
from tools import checkliste_scripte  # noqa: E402

KURZ = {Ziel.POWERSHELL: "PS", Ziel.CMD: "CMD"}
UMLAUT = "Größe Übergang"


def setzen(bereich: str, pfad: str, name: str, typ: str, daten: Any, **kw: Any) -> tuple[str, dict[str, Any]]:
    return (
        "registry_wert_setzen",
        {"bereich": bereich, "pfad": pfad, "wertname": name, "typ": typ, "daten": daten, **kw},
    )


def wert(pfad: str, name: str, typ: str, daten: Any) -> dict[str, Any]:
    # Zahlen als Text: ConvertFrom-Json (PS 5.1) liest Werte über Int64 sonst ungenau
    return {
        "art": "wert",
        "pfad": pfad,
        "name": name,
        "typ": typ,
        "daten": str(daten) if isinstance(daten, int) else daten,
    }


def kein_wert(pfad: str, name: str) -> dict[str, Any]:
    return {"art": "kein_wert", "pfad": pfad, "name": name}


def reg_add(pfad: str, name: str, typ: str, daten: str) -> list[str]:
    return ["add", pfad, "/v", name, "/t", typ, "/d", daten, "/f", "/reg:64"]


def szenarien(ziel: Ziel, ordner: PureWindowsPath) -> list[dict[str, Any]]:
    """Ein Eintrag je Script: Schritte, Vorbedingungen, Erwartung, Prüfungen."""
    k = KURZ[ziel]
    hklm = f"HKLM\\SOFTWARE\\OkmTest\\{k}"
    hkcu = f"HKCU\\Software\\OkmTest\\{k}"
    multi = ["eins", "zwei drei"]
    liste: list[dict[str, Any]] = [
        {
            "name": "typen",
            "beschreibung": "Alle Typen, DWORD > 0x7FFFFFFF, EXPAND_SZ unaufgelöst, Standardwert, "
            "neuer Unterschlüssel; vorhandener Nachbarwert bleibt (New-Item-Falle)",
            "vorher": [reg_add(f"{hklm}\\Typen", "Nachbar", "REG_SZ", "bleibt")],
            "schritte": [
                setzen("computer", f"{hklm}\\Typen", "Gross", "REG_DWORD", "4294967295"),
                setzen("computer", f"{hklm}\\Typen", "Mitte", "REG_DWORD", "0x80000000"),
                setzen("computer", f"{hklm}\\Typen", "Q", "REG_QWORD", "0x8000000000000000"),
                setzen("computer", f"{hklm}\\Typen", "Text", "REG_SZ", f"C:\\Pfad {UMLAUT}\\"),
                setzen("computer", f"{hklm}\\Typen", "Exp", "REG_EXPAND_SZ", "%SystemRoot%\\okm"),
                setzen("computer", f"{hklm}\\Typen", "Multi", "REG_MULTI_SZ", "\n".join(multi)),
                setzen("computer", f"{hklm}\\Typen", "Bin", "REG_BINARY", "0a 1b ff"),
                setzen("computer", f"{hklm}\\Typen", "", "REG_SZ", "Standard"),
                setzen("computer", f"{hklm}\\Typen\\Neu\\Tief", "X", "REG_DWORD", "1"),
            ],
            "exit": 0,
            "pruefungen": [
                wert(f"{hklm}\\Typen", "Gross", "REG_DWORD", 4294967295),
                wert(f"{hklm}\\Typen", "Mitte", "REG_DWORD", 2147483648),
                wert(f"{hklm}\\Typen", "Q", "REG_QWORD", 9223372036854775808),
                wert(f"{hklm}\\Typen", "Text", "REG_SZ", f"C:\\Pfad {UMLAUT}\\"),
                wert(f"{hklm}\\Typen", "Exp", "REG_EXPAND_SZ", "%SystemRoot%\\okm"),
                wert(f"{hklm}\\Typen", "Multi", "REG_MULTI_SZ", multi),
                wert(f"{hklm}\\Typen", "Bin", "REG_BINARY", "0a1bff"),
                wert(f"{hklm}\\Typen", "", "REG_SZ", "Standard"),
                wert(f"{hklm}\\Typen", "Nachbar", "REG_SZ", "bleibt"),
                wert(f"{hklm}\\Typen\\Neu\\Tief", "X", "REG_DWORD", 1),
            ],
        },
        {
            "name": "nur_wenn_fehlt",
            "beschreibung": "„nur wenn fehlt“ lässt vorhandene Werte in Ruhe",
            "vorher": [reg_add(f"{hklm}\\Vorhanden", "Da", "REG_DWORD", "7")],
            "schritte": [
                setzen(
                    "computer", f"{hklm}\\Vorhanden", "Da", "REG_DWORD", "1", wenn_vorhanden="nur_wenn_fehlt"
                ),
                setzen(
                    "computer",
                    f"{hklm}\\Vorhanden",
                    "Fehlt",
                    "REG_DWORD",
                    "1",
                    wenn_vorhanden="nur_wenn_fehlt",
                ),
            ],
            "exit": 0,
            "pruefungen": [
                wert(f"{hklm}\\Vorhanden", "Da", "REG_DWORD", 7),
                wert(f"{hklm}\\Vorhanden", "Fehlt", "REG_DWORD", 1),
            ],
        },
        {
            "name": "abbrechen",
            "beschreibung": "„abbrechen“ bei vorhandenem Wert: Exit-Code ≠ 0, Wert unverändert",
            "vorher": [reg_add(f"{hklm}\\Abbruch", "Da", "REG_SZ", "alt")],
            "schritte": [
                setzen("computer", f"{hklm}\\Abbruch", "Da", "REG_SZ", "neu", wenn_vorhanden="abbrechen")
            ],
            "exit": "ungleich0",
            "pruefungen": [wert(f"{hklm}\\Abbruch", "Da", "REG_SZ", "alt")],
        },
        {
            "name": "rueckgaengig",
            "beschreibung": "Rückgängig-Dateien stellen den Ausgangszustand wieder her",
            "vorher": [reg_add(f"{hklm}\\Zurueck", "A", "REG_SZ", "alt")],
            "schritte": [
                setzen("computer", f"{hklm}\\Zurueck", "A", "REG_SZ", "neu"),
                setzen("computer", f"{hklm}\\Zurueck", "B", "REG_SZ", "neu"),
                setzen("computer", f"{hklm}\\ZurueckNeu\\Tief", "C", "REG_SZ", "neu"),
            ],
            "exit": 0,
            "pruefungen": [
                wert(f"{hklm}\\Zurueck", "A", "REG_SZ", "neu"),
                wert(f"{hklm}\\Zurueck", "B", "REG_SZ", "neu"),
                wert(f"{hklm}\\ZurueckNeu\\Tief", "C", "REG_SZ", "neu"),
            ],
            "rueckgaengig": [
                wert(f"{hklm}\\Zurueck", "A", "REG_SZ", "alt"),
                # CMD: neue Werte in vorhandenen Schlüsseln bleiben stehen (docs/offene-punkte.md),
                # neu angelegte Schlüssel kennt CMD nicht → nur PowerShell prüft beides
                *(
                    [
                        kein_wert(f"{hklm}\\Zurueck", "B"),
                        {"art": "kein_schluessel", "pfad": f"{hklm}\\ZurueckNeu"},
                    ]
                    if ziel is Ziel.POWERSHELL
                    else []
                ),
            ],
        },
        {
            "name": "loeschen",
            "beschreibung": "Wert und Schlüssel löschen (rote Schritte, JA über die Eingabe)",
            "vorher": [
                reg_add(f"{hklm}\\Loeschen", "Weg", "REG_SZ", "x"),
                reg_add(f"{hklm}\\Loeschen", "Bleibt", "REG_SZ", "y"),
                reg_add(f"{hklm}\\Loeschen\\Unter\\Tief", "Z", "REG_SZ", "z"),
            ],
            "schritte": [
                (
                    "registry_wert_loeschen",
                    {"bereich": "computer", "pfad": f"{hklm}\\Loeschen", "wertname": "Weg"},
                ),
                ("registry_schluessel_loeschen", {"bereich": "computer", "pfad": f"{hklm}\\Loeschen\\Unter"}),
            ],
            "ja": True,
            "exit": 0,
            "pruefungen": [
                kein_wert(f"{hklm}\\Loeschen", "Weg"),
                wert(f"{hklm}\\Loeschen", "Bleibt", "REG_SZ", "y"),
                {"art": "kein_schluessel", "pfad": f"{hklm}\\Loeschen\\Unter"},
            ],
        },
        {
            "name": "pruefen_export",
            "beschreibung": "Soll/Ist (ohne Abweichung) und Export in eine .reg-Datei",
            "vorher": [reg_add(f"{hklm}\\Pruefen", "Soll", "REG_DWORD", "5")],
            "schritte": [
                (
                    "registry_pruefen",
                    {
                        "bereich": "computer",
                        "pfad": f"{hklm}\\Pruefen",
                        "wertname": "Soll",
                        "typ": "REG_DWORD",
                        "daten": "5",
                        "abbrechen": True,
                    },
                ),
                (
                    "registry_export",
                    {
                        "bereich": "computer",
                        "pfad": f"{hklm}\\Pruefen",
                        "datei": str(ordner / f"export-{k}.reg"),
                    },
                ),
            ],
            "exit": 0,
            "pruefungen": [
                {"art": "datei_enthaelt", "datei": str(ordner / f"export-{k}.reg"), "text": "Soll"}
            ],
        },
        {
            "name": "pruefen_abweichung",
            "beschreibung": "Soll/Ist mit Abweichung und „abbrechen“: Exit-Code ≠ 0",
            "vorher": [reg_add(f"{hklm}\\Pruefen2", "Soll", "REG_DWORD", "5")],
            "schritte": [
                (
                    "registry_pruefen",
                    {
                        "bereich": "computer",
                        "pfad": f"{hklm}\\Pruefen2",
                        "wertname": "Soll",
                        "typ": "REG_DWORD",
                        "daten": "6",
                        "abbrechen": True,
                    },
                ),
            ],
            "exit": "ungleich0",
            "pruefungen": [wert(f"{hklm}\\Pruefen2", "Soll", "REG_DWORD", 5)],
        },
        {
            "name": "import",
            "beschreibung": ".reg-Datei importieren (mit Sicherung)",
            "vorher": [reg_add(f"{hklm}\\Import", "Alt", "REG_SZ", "vorher")],
            "reg_datei": {
                "datei": str(ordner / f"import-{k}.reg"),
                "zeilen": [
                    "Windows Registry Editor Version 5.00",
                    "",
                    f"[HKEY_LOCAL_MACHINE\\SOFTWARE\\OkmTest\\{k}\\Import]",
                    '"Neu"=dword:0000002a',
                    f'"Text"="{UMLAUT}"',
                    "",
                ],
            },
            "schritte": [("registry_import", {"datei": str(ordner / f"import-{k}.reg")})],
            "ja": True,
            "exit": 0,
            "pruefungen": [
                wert(f"{hklm}\\Import", "Neu", "REG_DWORD", 42),
                wert(f"{hklm}\\Import", "Text", "REG_SZ", UMLAUT),
                wert(f"{hklm}\\Import", "Alt", "REG_SZ", "vorher"),
            ],
        },
        {
            "name": "benutzer",
            "beschreibung": "Bereich „Angemeldeter Benutzer“ (HKCU des Konsolenbenutzers, "
            "nie das Admin-Profil)",
            "benutzer": True,
            "vorher": [],
            "schritte": [
                setzen("angemeldeter_benutzer", f"{hkcu}\\Benutzer", "Wert", "REG_SZ", f"für {UMLAUT}"),
                setzen("angemeldeter_benutzer", f"{hkcu}\\Benutzer", "Zahl", "REG_DWORD", "4294967295"),
            ],
            "exit": 0,
            "pruefungen": [
                wert(f"{hkcu}\\Benutzer", "Wert", "REG_SZ", f"für {UMLAUT}"),
                wert(f"{hkcu}\\Benutzer", "Zahl", "REG_DWORD", 4294967295),
            ],
        },
    ]
    if ziel is Ziel.POWERSHELL:
        liste.append(
            {
                "name": "soll_ist_liste",
                "beschreibung": "Soll/Ist-Liste (nur PowerShell): eine Abweichung → Rückgabe, kein Abbruch",
                "vorher": [
                    reg_add(f"{hklm}\\Liste", "A", "REG_DWORD", "1"),
                    reg_add(f"{hklm}\\Liste", "B", "REG_SZ", "x"),
                ],
                "schritte": [
                    (
                        "registry_soll_ist_liste",
                        {
                            "bereich": "computer",
                            "eintraege": f"{hklm}\\Liste ; A ; REG_DWORD ; 1\n{hklm}\\Liste ; B ; REG_SZ ; y",
                        },
                    )
                ],
                "exit": 0,
                "ausgabe": ["ABWEICHUNG", "Abweichungen: 1 von 2"],
                "pruefungen": [],
            }
        )
    return liste


def script(reg: Registry, ziel: Ziel, titel: str, schritte: list[tuple[str, dict[str, Any]]]) -> bytes:
    req = ScriptRequest(
        ziel=ziel,
        titel=titel,
        rot_bestaetigt=True,
        schritte=[SchrittEingabe(block_id=b, parameter=p) for b, p in schritte],
    )
    ir = validiere_request(req, reg, autor="windows-ci", jetzt=datetime.now())
    return generator_fuer(ziel, reg).erzeuge(ir).inhalt


def main() -> int:
    # Pfade in den Scripten sind immer Windows-Pfade (auf dem Runner = Ablageordner); unter Linux
    # entstehen die Dateien zum Ansehen/Syntax-Prüfen in ./windows-test, die Pfade zeigen auf C:\okm-ci.
    standard = "C:\\okm-ci" if os.name == "nt" else "windows-test"
    ordner = Path(sys.argv[1] if len(sys.argv) > 1 else standard).resolve()
    ordner.mkdir(parents=True, exist_ok=True)
    win = PureWindowsPath(str(ordner)) if os.name == "nt" else PureWindowsPath("C:\\okm-ci")
    reg = lade_registry()
    laeufe: list[dict[str, Any]] = []
    for ziel in (Ziel.POWERSHELL, Ziel.CMD):
        endung = ".ps1" if ziel is Ziel.POWERSHELL else ".cmd"
        for s in szenarien(ziel, win):
            datei = ordner / f"reg-{s['name']}-{KURZ[ziel]}{endung}"
            datei.write_bytes(script(reg, ziel, f"CI {s['name']}", s.pop("schritte")))
            if "reg_datei" in s:
                rd = s.pop("reg_datei")
                (ordner / PureWindowsPath(rd["datei"]).name).write_bytes(
                    b"\xff\xfe" + "\r\n".join(rd["zeilen"]).encode("utf-16-le")
                )
            laeufe.append({"datei": datei.name, "ziel": ziel.value, **s})
    # Checkliste: Umlaute, Admin-Block, Ping ohne Antwort, absichtlicher Fehler → Exit-Code 1
    for ziel in (Ziel.POWERSHELL, Ziel.CMD):
        g = checkliste_scripte.erzeuge(reg, ziel)
        endung = g.dateiname.rpartition(".")[2]
        for variante, inhalt in (("", g.inhalt), ("-bearbeitet", checkliste_scripte.bearbeitet(g))):
            datei = ordner / f"checkliste-{KURZ[ziel]}{variante}.{endung}"
            datei.write_bytes(inhalt)
            laeufe.append(
                {
                    "datei": datei.name,
                    "ziel": ziel.value,
                    "name": f"checkliste{variante}",
                    "beschreibung": "Checkliste: Umlaute, Fehlerbehandlung, Zusammenfassung, Exit-Code",
                    "vorher": [],
                    "exit": 1,
                    "ausgabe": [
                        checkliste_scripte.UMLAUTE,
                        "Abgebrochen bei Schritt 4 von 4",
                        "Erfolgreich bis dahin: 3 von 4",
                    ],
                    "pruefungen": [],
                }
            )
    manifest = {"erzeugt": datetime.now().isoformat(timespec="seconds"), "laeufe": laeufe}
    (ordner / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(laeufe)} Scripte + manifest.json in {ordner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
