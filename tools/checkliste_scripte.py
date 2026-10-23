#!/usr/bin/env python3
"""Test-Scripte für die Ausführen-Checkliste (``docs/test-vms.md``) erzeugen.

Ein Script pro Zielsystem mit Umlauten, einem Admin-/root-Block, einem Ping auf eine nicht
erreichbare IP (192.0.2.1, TEST-NET-1) und einem absichtlich fehlschlagenden Block – dazu je eine
„manuell bearbeitete“ Fassung, exportiert wie aus dem Editor.

Aufruf:  python tools/checkliste_scripte.py [zielordner]     (Standard: ./checkliste)
Die Dateien auf die Test-VMs kopieren und die Tabelle in docs/test-vms.md abarbeiten.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from app.escaping import Ziel  # noqa: E402
from app.export import exportiere  # noqa: E402
from app.generators import GeneratedScript, generator_fuer  # noqa: E402
from app.models.request import SchrittEingabe, ScriptRequest  # noqa: E402
from app.registry import Registry, lade_registry  # noqa: E402
from app.validation import validiere_request  # noqa: E402

UMLAUTE = "Umlaut-Test: äöü ÄÖÜ ß - Größe, Übergang, Öl"
NICHT_ERREICHBAR = "192.0.2.1"


def schritte(ziel: Ziel) -> list[tuple[str, dict[str, Any]]]:
    windows = ziel in (Ziel.POWERSHELL, Ziel.CMD)
    ordner = "C:\\okm-test" if windows else "/okm-test"
    trenner = "\\" if windows else "/"
    return [
        ("meldung", {"text": UMLAUTE, "pause": False}),
        ("druckwarteschlange_leeren", {}),  # braucht Admin bzw. sudo auf allen Zielen
        ("ping", {"ziel": NICHT_ERREICHBAR, "anzahl": 2, "abbrechen": False}),
        (
            "kopieren",  # Quelle gibt es nicht → schlägt absichtlich fehl
            {
                "art": "datei",
                "quelle": f"{ordner}{trenner}gibt-es-nicht.txt",
                "ziel": f"{ordner}{trenner}ziel.txt",
            },
        ),
    ]


def erzeuge(reg: Registry, ziel: Ziel) -> GeneratedScript:
    req = ScriptRequest(
        ziel=ziel,
        titel="Checkliste Größe Übergang",
        beschreibung="Test-Script für die Ausführen-Checkliste (docs/test-vms.md)",
        rot_bestaetigt=True,
        schritte=[SchrittEingabe(block_id=b, parameter=p) for b, p in schritte(ziel)],
    )
    return generator_fuer(ziel, reg).erzeuge(
        validiere_request(req, reg, autor="checkliste", jetzt=datetime.now())
    )


def bearbeitet(script: GeneratedScript) -> bytes:
    """Wie „Download“ aus dem Editor nach einer kleinen Änderung am Ende."""
    zusatz = {
        Ziel.POWERSHELL: "# Diese Zeile wurde im Editor ergänzt (äöü)",
        Ziel.CMD: "rem Diese Zeile wurde im Editor ergänzt (äöü)",
        Ziel.BASH: "# Diese Zeile wurde im Editor ergänzt (äöü)",
        Ziel.ZSH: "# Diese Zeile wurde im Editor ergänzt (äöü)",
    }[script.ziel]
    text = script.text.replace("\r\n", "\n") + zusatz + "\n"
    return exportiere(text, script.ziel, manuell_bearbeitet=True)


def main() -> None:
    zielordner = Path(sys.argv[1] if len(sys.argv) > 1 else "checkliste")
    zielordner.mkdir(parents=True, exist_ok=True)
    reg = lade_registry()
    for ziel in Ziel:
        s = erzeuge(reg, ziel)
        stamm, punkt, endung = s.dateiname.rpartition(".")
        if ziel is Ziel.ZSH:  # bash und zsh haben beide .sh
            stamm += "-zsh"
        name = f"{stamm}{punkt}{endung}"
        (zielordner / name).write_bytes(s.inhalt)
        (zielordner / f"{stamm}-bearbeitet{punkt}{endung}").write_bytes(bearbeitet(s))
        print(f"{ziel.value:<11} {zielordner / name}")


if __name__ == "__main__":
    main()
