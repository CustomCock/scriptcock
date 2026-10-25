"""Abstrakte Generator-Klasse.

``erzeuge()`` legt den Aufbau jedes Scripts fest (Kopf → Präambel → Schritte
→ Abschluss). Die Unterklassen liefern nur sprachspezifische Bausteine.
Generatoren arbeiten ausschließlich auf der IR.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar
from urllib.parse import quote

from app import escaping
from app.escaping import Escaped, UnsicherError, Ziel
from app.export import exportiere, text_fuer
from app.ir import (
    Abbrechen,
    Bestaetigung,
    BlockSchritt,
    FuerJeden,
    Knoten,
    Kommentar,
    ParamValue,
    ScriptIR,
    Vergleich,
    Warten,
    Wenn,
    WennFehler,
    Wiederhole,
    alle_knoten,
)
from app.models.block import (
    RUECKGABE_PRAEFIX,
    WINDOWS,
    BlockDef,
    ParamTyp,
    Recht,
    Risiko,
    RueckgabeDef,
    RueckgabeTyp,
)
from app.registry import Registry
from app.regschutz import lade_schutz
from app.validation import ValidierungsFehler, pruefe_wert_fuer_ziel, registry_ps_form, verweis_teile


class GenerierungsFehler(ValueError):
    pass


@dataclass
class GeneratedScript:
    ziel: Ziel
    text: str  # mit Zielzeilenenden, ohne BOM
    inhalt: bytes  # exakt der Dateiinhalt (inkl. BOM)
    sha256: str
    dateiname: str
    warnungen: list[str] = field(default_factory=list)


@dataclass
class SchrittInfo:
    nr: int
    gesamt: int
    block: BlockDef
    fortschritt: str
    koerper: list[str]
    pruefung: list[str]
    bestaetigen: bool  # rote Bestätigung im Script
    risiko: Risiko  # Risiko des Schritts (kann höher sein als das des Blocks)
    # Läuft vor der JA-Abfrage (nur bei bestaetigen; darf nichts ändern)
    vorschau: list[str] = field(default_factory=list)
    # Nach erfolgreichem Schritt: Rückgabewerte normalisieren (außerhalb jeder Umleitung/Gruppe)
    nachher: list[str] = field(default_factory=list)

    @property
    def bezeichnung(self) -> str:
        return f"{self.nr}/{self.gesamt}"


ZIEL_ANZEIGE = {
    Ziel.POWERSHELL: "Windows PowerShell 5.1",
    Ziel.CMD: "Windows Eingabeaufforderung (CMD)",
    Ziel.BASH: "Linux (Bash 4+)",
    Ziel.ZSH: "macOS (zsh)",
}

SIMULATION_PREFIX = "[SIMULATION] würde ausführen: "

# Registry „wirkung“: je höher, desto mehr ist nötig, damit Änderungen greifen („unbekannt“ extra)
WIRKUNG_RANG = {
    "sofort": 0,
    "explorer_neustart": 1,
    "gpupdate": 2,
    "abmelden": 3,
    "neustart": 4,
}
# CMD, Bereich „angemeldeter Benutzer“: SID des einen angemeldeten Benutzers (Besitzer von explorer.exe)
# zur Laufzeit ermitteln (hilfen/registry_benutzer.cmd). Kein/mehrere Benutzer oder keine Ausgabe →
# Errorlevel 9 – Templates unterscheiden so „Benutzer nicht ermittelbar“ von „Wert fehlt“ (1).
CMD_BENUTZER_ANFANG = (
    (Path(__file__).parent / "hilfen" / "registry_benutzer.cmd").read_text(encoding="utf-8").rstrip("\n")
)

# Einheitliches Ausgabeformat aller Ziele (siehe docs/sicherheit.md bzw. CHANGELOG)
LINIE_DOPPELT = "=" * 46
LINIE = "-" * 46
EINZUG = " " * 6


def unc_zu_smb_url(unc: str) -> str:
    """``\\\\server\\freigabe\\ordner`` → ``smb://server/freigabe/ordner`` (Segmente URL-kodiert)."""
    teile = unc.lstrip("\\").split("\\")
    return "smb://" + "/".join(quote(t, safe="") for t in teile)


def dateiname(titel: str, endung: str) -> str:
    ersetzt = titel.lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        ersetzt = ersetzt.replace(alt, neu)
    ascii_text = unicodedata.normalize("NFKD", ersetzt).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:60].strip("-")
    return f"{slug or 'script'}{endung}"


class Generator(ABC):
    ziel: ClassVar[Ziel]
    endung: ClassVar[str]
    zeilenende: ClassVar[str]
    bom: ClassVar[bool] = False

    def __init__(self, registry: Registry) -> None:
        self.registry = registry

    # --- fester Ablauf ------------------------------------------------------

    def erzeuge(self, ir: ScriptIR) -> GeneratedScript:
        bloecke = list(ir.bloecke())
        defs: list[BlockDef] = []
        for schritt in bloecke:
            block = self.registry.bloecke.get(schritt.block_id)
            if block is None:
                raise GenerierungsFehler(f"Unbekannter Baustein „{schritt.block_id}“.")
            if not block.verfuegbar(self.ziel):
                raise GenerierungsFehler(
                    f"„{block.name}“ ist unter {ZIEL_ANZEIGE[self.ziel]} nicht verfügbar."
                )
            defs.append(block)
        # Schrittnummern (Vorordnung) der Blöcke mit besonderen Rechten
        self._admin_schritte = [(i, b) for i, b in enumerate(defs, 1) if b.braucht_admin(self.ziel)]
        self._nie_root_schritte = [
            (i, b) for i, b in enumerate(defs, 1) if b.recht(self.ziel) is Recht.NIE_ROOT
        ]
        braucht_admin = bool(self._admin_schritte)

        # Zustand für die rekursive Ausgabe
        self._ir = ir
        self._gesamt = len(bloecke)
        self._nr = 0  # laufende Schrittnummer (Pre-Order über Blöcke)
        self._id = 0  # eindeutige Nummer je Kontrollknoten (Labels, Variablen)
        self._versuche: list[int] = []  # offene "Versuche"-Blöcke (innerster zuletzt)
        self._durchlauf: list[int] = []  # Durchlauf-Index offener „Für jeden Wert“ (innerster zuletzt)
        self._defs = defs  # Block-Definitionen in Schrittnummer-Reihenfolge (für Verweise)
        # Ohne Verzweigung (Kommentar, Warten …) bleibt es bei „X von Y Schritten“.
        self.mit_kontrolle = ir.hat_verzweigung()
        self.hat_abbrechen = any(isinstance(k, Abbrechen) for k in alle_knoten(ir.schritte))
        # Registry-Bausteine: Hilfsfunktionen, 64-Bit-Neustart und Hinweise in der Zusammenfassung
        self.mit_registry = any(b.registry is not None or b.dynamisch is not None for b in defs)
        self.mit_richtlinien = any(b.dynamisch == "richtlinie" for b in defs)
        self.mit_dynamisch = any(b.dynamisch is not None for b in defs)

        zeilen: list[str] = []
        zeilen += self.kopf(ir, defs)
        zeilen += self.praeambel(ir, len(bloecke), braucht_admin)
        rueckgaben = [
            (escaping.variable_setzen(self.ziel, nr, r.id), r)
            for nr, b in enumerate(defs, 1)
            for r in b.rueckgaben(self.ziel)
        ]
        if rueckgaben:
            zeilen += self.rueckgaben_vorbelegen(rueckgaben)
        zeilen += self.emit_liste(ir.schritte)
        zeilen += self.abschluss(ir)

        roh = "\n".join(zeilen).rstrip("\n") + "\n"
        text = text_fuer(roh, self.ziel)
        inhalt = exportiere(roh, self.ziel)
        return GeneratedScript(
            ziel=self.ziel,
            text=text,
            inhalt=inhalt,
            sha256=hashlib.sha256(inhalt).hexdigest(),
            dateiname=dateiname(ir.meta.titel, self.endung),
        )

    @property
    def im_versuch(self) -> bool:
        """True, wenn der aktuelle Schritt in einem „Versuche“-Block steht (Fehler → Ausweichschritte)."""
        return bool(self._versuche)

    def emit_liste(self, knoten: list[Knoten]) -> list[str]:
        zeilen: list[str] = []
        for k in knoten:
            zeilen += self.emit_knoten(k)
        return zeilen

    def emit_knoten(self, knoten: Knoten) -> list[str]:
        methode: Callable[[Knoten], list[str]] = getattr(self, f"emit_{knoten.art}")
        return methode(knoten)

    def emit_block(self, schritt: BlockSchritt) -> list[str]:
        schritt = self.schleifenwert_einsetzen(schritt)
        self._nr += 1
        block = self.registry.bloecke[schritt.block_id]
        dry = self._ir.optionen.dry_run
        risiko = schritt.risiko or block.risiko
        kontext = self.kontext(block, schritt, dry)
        koerper = self.koerper(block, kontext, dry, risiko)
        vorschau: list[str] = []
        if risiko is Risiko.ROT and not dry and (block.id, "vorschau", self.ziel) in self.registry.vorlagen:
            vorschau = self.rendere(block, "vorschau", kontext)
        pruefung: list[str] = []
        if not dry and (block.id, "pruefung", self.ziel) in self.registry.vorlagen:
            pruefung = self.rendere(block, "pruefung", kontext)
        info = SchrittInfo(
            nr=self._nr,
            gesamt=self._gesamt,
            block=block,
            fortschritt=self.fortschrittstext(block, schritt),
            koerper=koerper,
            pruefung=pruefung,
            bestaetigen=risiko is Risiko.ROT and not dry,
            risiko=risiko,
            vorschau=vorschau,
            nachher=[
                z
                for r in block.rueckgaben(self.ziel)
                for z in self.rueckgabe_normalisieren(escaping.variable_setzen(self.ziel, self._nr, r.id), r)
            ],
        )
        return self.schritt(info)

    def emit_wenn_fehler(self, knoten: WennFehler) -> list[str]:
        self._id += 1
        nr = self._id
        self._versuche.append(nr)
        versuch = self.emit_liste(knoten.versuche)
        self._versuche.pop()
        sonst = self.emit_liste(knoten.sonst)
        return self.wenn_fehler(nr, versuch, sonst)

    def emit_wiederhole(self, knoten: Wiederhole) -> list[str]:
        self._id += 1
        nr = self._id
        return self.wiederhole(nr, knoten.anzahl, self.emit_liste(knoten.rumpf))

    def emit_fuer_jeden(self, knoten: FuerJeden) -> list[str]:
        """Rollt den Rumpf einmal pro Wert aus: jeder Durchlauf bekommt die geprüften Literale.

        Keine Laufzeitschleife – so gibt es keine Laufzeitvariablen mit Benutzerwerten (und unter CMD
        keine Schritte in ``for``-Blöcken). Schrittnummern sind wie bei „Wiederhole“ in jedem Durchlauf
        dieselben; Rückgabewerte eines Durchlaufs überschreiben die des vorherigen.
        """
        self._id += 1
        nr = self._id
        start = self._nr
        anzahl = len(knoten.werte)
        kopf = f"===== Für jeden Wert ({anzahl}) (Block {nr}): {', '.join(knoten.werte)} ====="
        zeilen = [self.kommentar(escaping.kommentar_text(self.ziel, kopf))]
        for i, wert in enumerate(knoten.werte):
            self._nr = start
            self._durchlauf.append(i)
            rumpf = self.emit_liste(knoten.rumpf)
            self._durchlauf.pop()
            zeilen += [*self.ausgabe_zeilen(f"--- Wert {i + 1} von {anzahl}: {wert} ---"), *rumpf]
        return [*zeilen, ""]

    def schleifenwert_einsetzen(self, schritt: BlockSchritt) -> BlockSchritt:
        """Parameter mit ``schleife`` → geprüfter Wert des aktuellen Durchlaufs (innerste Schleife)."""
        if not any(v.schleife for v in schritt.parameter.values()):
            return schritt
        if not self._durchlauf:
            raise GenerierungsFehler("Wert aus der Liste außerhalb von „Für jeden Wert“.")
        i = self._durchlauf[-1]
        parameter: dict[str, ParamValue] = {}
        for pid, v in schritt.parameter.items():
            if v.schleife and isinstance(v.wert, list):
                parameter[pid] = ParamValue(typ=v.typ, wert=v.wert[i])
            else:
                parameter[pid] = v
        return schritt.model_copy(update={"parameter": parameter})

    def ausgabe_zeilen(self, text: str) -> list[str]:
        """Meldung des Generators auf Konsole (und ins Protokoll, wo das nicht automatisch passiert)."""
        return [self.echo(text)]

    def emit_wenn(self, knoten: Wenn) -> list[str]:
        self._id += 1
        nr = self._id
        quelle_nr, rid = verweis_teile(knoten.wert)
        r = self._defs[quelle_nr - 1].rueckgabe_def(rid)
        if r is None:
            raise GenerierungsFehler(f"Schritt {quelle_nr} liefert keinen Wert „{rid}“.")
        name = escaping.variablen_name(self.ziel, quelle_nr, rid)
        text = bedingung_text(knoten)
        dann = self.emit_liste(knoten.dann)
        sonst = self.emit_liste(knoten.sonst)
        return self.wenn(nr, name, r.typ, knoten.vergleich, knoten.zahl, text, dann, sonst)

    def emit_abbrechen(self, knoten: Abbrechen) -> list[str]:
        return self.abbrechen(knoten.meldung, knoten.code)

    def emit_warten(self, knoten: Warten) -> list[str]:
        text = f"Warte {sekunden_text(knoten.sekunden)} …"
        if self._ir.optionen.dry_run:
            return [self.echo(SIMULATION_PREFIX + text)]
        return self.warten(knoten.sekunden, text)

    def emit_bestaetigung(self, knoten: Bestaetigung) -> list[str]:
        if self._ir.optionen.dry_run:
            return [self.echo(SIMULATION_PREFIX + "Rückfrage: " + knoten.meldung)]
        return self.bestaetigung(knoten.meldung)

    def emit_kommentar(self, knoten: Kommentar) -> list[str]:
        return [self.kommentar(escaping.kommentar_text(self.ziel, knoten.text))]

    def meldung_ausweichen(self, mit_sonst: bool) -> str:
        if mit_sonst:
            return "Ein Schritt ist fehlgeschlagen - es geht mit den Ausweichschritten weiter."
        return "Ein Schritt ist fehlgeschlagen - der Fehler wird wie vorgesehen übergangen."

    def kopf_ausgabe(self, ir: ScriptIR) -> list[str]:
        """Kasten am Scriptanfang (wird auf Konsole und ins Protokoll geschrieben)."""
        erstellt = ir.meta.erstellt_am.strftime("%d.%m.%Y %H:%M")
        zeilen = [
            LINIE_DOPPELT,
            f" okm Script-Baukasten · {ir.meta.titel}",
            f" Erstellt: {erstellt} · von {ir.meta.autor}",
        ]
        if ir.optionen.dry_run:
            zeilen.append(" NUR SIMULATION – es wird nichts verändert")
        return [*zeilen, LINIE_DOPPELT]

    def schritt_titel(self, info: SchrittInfo) -> str:
        return f"[{info.bezeichnung}] {info.fortschritt} ..."

    def schluss_text(self) -> str:
        """Text der Abschlussmeldung (mit Schleifen gibt es keine feste Gesamtzahl)."""
        if self.mit_kontrolle:
            return "Fertig, {ok} Schritte erfolgreich ausgeführt."
        return "Fertig, {ok} von {gesamt} Schritten erfolgreich."

    # --- Werte & Templates --------------------------------------------------

    def kontext(self, block: BlockDef, schritt: BlockSchritt, dry: bool) -> dict[str, Escaped]:
        kontext: dict[str, Escaped] = {}
        for p in block.parameter:
            wert = schritt.parameter.get(p.id)
            try:
                if wert is None or wert.wert is None:
                    kontext[p.id] = escaping.leer()
                    continue
                pruefe_wert_fuer_ziel(wert, self.ziel)
                if p.typ is ParamTyp.REGISTRY_DATEN:
                    regtyp = schritt.parameter.get(p.bezug or "typ")
                    if regtyp is None or not isinstance(regtyp.wert, str):
                        raise GenerierungsFehler(f"{block.name}: Registry-Typ fehlt.")
                    kontext[p.id] = escaping.registry_daten(self.ziel, regtyp.wert, wert.wert)
                elif p.typ is ParamTyp.VARIABLE and isinstance(wert.wert, str):
                    kontext[p.id] = escaping.variable_lesen(self.ziel, *verweis_teile(wert.wert))
                elif isinstance(wert.wert, list):
                    kontext[p.id] = escaping.liste(self.ziel, wert.wert)
                elif isinstance(wert.wert, bool):
                    kontext[p.id] = escaping.wahrheitswert(self.ziel, wert.wert)
                elif isinstance(wert.wert, int):
                    kontext[p.id] = escaping.zahl(wert.wert)
                else:
                    kontext[p.id] = escaping.literal(self.ziel, wert.wert)
            except (UnsicherError, ValidierungsFehler) as e:
                raise GenerierungsFehler(f"{block.name} – {p.label}: {e}") from None
        bereich = self._registry_bereich(block, schritt)
        for name, pid in block.abgeleitete_variablen().items():
            quelle = schritt.parameter.get(pid)
            if name.endswith("_abfrage"):
                kontext[name] = self._registry_abfrage(block, schritt, pid)
            elif quelle is None or not isinstance(quelle.wert, str):
                kontext[name] = escaping.leer()
            elif name.endswith("_reg") and self.ziel is Ziel.CMD and bereich == "angemeldeter_benutzer":
                kontext[name] = escaping.registry_pfad_benutzer_cmd(quelle.wert)
            elif name.endswith("_reg"):
                kontext[name] = escaping.literal(self.ziel, quelle.wert)
            elif name.endswith("_ps"):
                kontext[name] = escaping.literal(self.ziel, registry_ps_form(quelle.wert))
            else:
                kontext[name] = escaping.literal(self.ziel, unc_zu_smb_url(quelle.wert))
        for r in block.rueckgaben(self.ziel):
            kontext[RUECKGABE_PRAEFIX + r.id] = escaping.variable_setzen(self.ziel, self._nr, r.id)
        kontext.update(self._registry_kontext(block, schritt, bereich))
        kontext.update(self._dynamischer_kontext(block, schritt, dry))
        kontext["whatif"] = escaping.vertraut(" -WhatIf" if dry and self.ziel is Ziel.POWERSHELL else "")
        # Linux/macOS: privilegierte Befehle laufen über okm_sudo (root: direkt, sonst sudo)
        kontext["sudo"] = escaping.vertraut("okm_sudo " if block.recht(self.ziel) is Recht.ROOT else "")
        return kontext

    def _richtlinie_kopf(self, schritt: BlockSchritt) -> list[str]:
        rid = schritt.parameter.get("richtlinie")
        r = self.registry.richtlinien.richtlinie(str(rid.wert)) if rid is not None else None
        if r is None:
            return []
        paket = self.registry.richtlinien.paket(r["paket"]) or {}
        zustand = schritt.parameter.get("zustand")
        return [
            f"Richtlinie: {r['titel']} ({zustand.wert if zustand is not None else ''})",
            f"Paket: {paket.get('name', r['paket'])} {paket.get('version', '')}".rstrip(),
            f"Kategorie: {' > '.join(r['kategorie_pfad'])}",
        ]

    def _dynamischer_kontext(self, block: BlockDef, schritt: BlockSchritt, dry: bool) -> dict[str, Escaped]:
        """``richtlinie_code``/``werkzeug_code`` für dynamische Bausteine (nur PowerShell)."""
        kontext = {"richtlinie_code": escaping.leer(), "werkzeug_code": escaping.leer()}
        if block.dynamisch is None or self.ziel is not Ziel.POWERSHELL:
            return kontext
        from app.generators import richtlinie_ps

        try:
            if block.dynamisch == "richtlinie":
                zeilen = richtlinie_ps.richtlinie_code(self.registry, schritt, dry)
                kontext["richtlinie_code"] = escaping.vertraut("\n".join(zeilen))
            else:
                zeilen = richtlinie_ps.werkzeug_code(self.registry, schritt, dry)
                kontext["werkzeug_code"] = escaping.vertraut("\n".join(zeilen))
        except (richtlinie_ps.CodeFehler, UnsicherError) as e:
            raise GenerierungsFehler(f"{block.name}: {e}") from None
        return kontext

    @staticmethod
    def _registry_bereich(block: BlockDef, schritt: BlockSchritt) -> str | None:
        for p in block.parameter:
            if p.typ is ParamTyp.REGISTRY_BEREICH:
                wert = schritt.parameter.get(p.id)
                return wert.wert if wert is not None and isinstance(wert.wert, str) else None
        return None

    def _registry_abfrage(self, block: BlockDef, schritt: BlockSchritt, pid: str) -> Escaped:
        quelle = schritt.parameter.get(pid)
        param = block.param(pid)
        regtyp = schritt.parameter.get(param.bezug or "typ") if param is not None else None
        if quelle is None or quelle.wert is None or isinstance(quelle.wert, bool):
            return escaping.leer()
        if regtyp is None or not isinstance(regtyp.wert, str):
            return escaping.leer()
        return escaping.registry_abfrage(self.ziel, regtyp.wert, quelle.wert)

    def _registry_kontext(
        self, block: BlockDef, schritt: BlockSchritt, bereich: str | None
    ) -> dict[str, Escaped]:
        """Eingebaute Variablen für Registry-Bausteine (nur vom Generator erzeugter Code)."""
        anfang, ende = escaping.leer(), escaping.leer()
        if self.ziel is Ziel.CMD and block.registry is not None:
            if bereich == "angemeldeter_benutzer":
                anfang, ende = escaping.vertraut(CMD_BENUTZER_ANFANG), escaping.vertraut(")")
            else:
                anfang, ende = escaping.vertraut("("), escaping.vertraut(")")
        wirkung = schritt.parameter.get("wirkung")
        name = wirkung.wert if wirkung is not None and isinstance(wirkung.wert, str) else ""
        # findstr /l liest "\" als Escape → verdoppeln; Schlüssel selbst ("…]") und alles darunter ("…\")
        muster = " ".join(
            f'/c:"HKEY_LOCAL_MACHINE\\\\{rest}{ende}"'
            for teile in lade_schutz().gesperrt
            if teile and teile[0] == "hklm"
            for rest in ["\\\\".join(x.upper() for x in teile[1:])]
            for ende in ("]", "\\\\")
        )
        return {
            "benutzer_anfang": anfang,
            "benutzer_ende": ende,
            "wirkung_rang": escaping.zahl(WIRKUNG_RANG.get(name, 0)),
            "regschutz_cmd": escaping.vertraut(muster) if self.ziel is Ziel.CMD else escaping.leer(),
        }

    def rendere(self, block: BlockDef, art: str, kontext: dict[str, Escaped]) -> list[str]:
        vorlage = self.registry.vorlagen[(block.id, art, self.ziel)]
        code = vorlage.render(**kontext)
        return [z.rstrip() for z in code.strip("\n").splitlines()]

    def koerper(self, block: BlockDef, kontext: dict[str, Escaped], dry: bool, risiko: Risiko) -> list[str]:
        if not dry:
            return self.rendere(block, "ziele", kontext)
        if (block.id, "dry_run", self.ziel) in self.registry.vorlagen:
            return self.rendere(block, "dry_run", kontext)
        if risiko is Risiko.GRUEN:
            return self.rendere(block, "ziele", kontext)
        if "whatif" in self.registry.variablen[(block.id, "ziele", self.ziel)]:
            return self.rendere(block, "ziele", kontext)
        zeilen = self.rendere(block, "ziele", kontext)
        return [
            self.echo(SIMULATION_PREFIX + z.strip())
            for z in zeilen
            if z.strip() and not self.ist_kommentar(z)
        ]

    def fortschrittstext(self, block: BlockDef, schritt: BlockSchritt) -> str:
        vorlage = self.registry.fortschritt.get(block.id)
        if vorlage is None:
            return block.name
        werte = {p.id: als_text(schritt.parameter.get(p.id)) for p in block.parameter}
        for p in block.parameter:
            if p.typ is ParamTyp.VARIABLE and werte[p.id]:
                nr, rid = verweis_teile(werte[p.id])
                werte[p.id] = f"Wert {rid} aus Schritt {nr}"
        return " ".join(vorlage.render(**werte).split())

    def kommentar_zeilen(self, ir: ScriptIR, defs: list[BlockDef]) -> list[str]:
        """Inhalt des Kopfkommentars (ohne Kommentarzeichen)."""

        def k(text: str) -> str:
            return escaping.kommentar_text(self.ziel, text)

        zeilen = [
            "=" * 70,
            f"Titel:             {k(ir.meta.titel)}",
        ]
        beschreibung = [b for b in ir.meta.beschreibung.split("\n") if b.strip()]
        if beschreibung:
            zeilen.append(f"Beschreibung:      {k(beschreibung[0])}")
            zeilen += [f"                   {k(b)}" for b in beschreibung[1:]]
        zeilen += [
            f"Erstellt von:      {k(ir.meta.autor)}",
            f"Erstellt am:       {ir.meta.erstellt_am.strftime('%d.%m.%Y %H:%M:%S')}",
            f"Baukasten-Version: {k(ir.meta.baukasten_version)}",
            f"Zielsystem:        {ZIEL_ANZEIGE[self.ziel]}",
        ]
        zeilen.append(f"Benötigte Rechte:  {self.rechte_kopfzeile()}")
        if ir.optionen.dry_run:
            zeilen.append("Modus:             NUR SIMULATION - es wird nichts verändert")
        zeilen.append("Enthaltene Schritte:")
        zaehler = iter(range(1, len(defs) + 1))

        def liste(knoten: list[Knoten], einzug: int) -> None:
            for kn in knoten:
                if isinstance(kn, WennFehler):
                    zeilen.append(" " * einzug + "Versuche:")
                    liste(kn.versuche, einzug + 3)
                    zeilen.append(
                        " " * einzug + ("Wenn das fehlschlägt:" if kn.sonst else "Fehler darin übergehen.")
                    )
                    liste(kn.sonst, einzug + 3)
                elif isinstance(kn, Wiederhole):
                    zeilen.append(" " * einzug + f"Wiederhole {kn.anzahl}-mal:")
                    liste(kn.rumpf, einzug + 3)
                elif isinstance(kn, FuerJeden):
                    zeilen.append(" " * einzug + f"Für jeden Wert ({k(', '.join(kn.werte))}):")
                    liste(kn.rumpf, einzug + 3)
                elif isinstance(kn, Wenn):
                    zeilen.append(" " * einzug + f"Wenn {k(bedingung_text(kn))}:")
                    liste(kn.dann, einzug + 3)
                    if kn.sonst:
                        zeilen.append(" " * einzug + "Sonst:")
                        liste(kn.sonst, einzug + 3)
                elif isinstance(kn, Abbrechen):
                    zeilen.append(" " * einzug + f"Beenden (Exit-Code {kn.code}): {k(kn.meldung)}")
                elif isinstance(kn, Warten):
                    zeilen.append(" " * einzug + f"Warte {sekunden_text(kn.sekunden)}")
                elif isinstance(kn, Bestaetigung):
                    zeilen.append(" " * einzug + f"Bestätigung: {k(kn.meldung)}")
                elif isinstance(kn, Kommentar):
                    zeilen.append(" " * einzug + f"Notiz: {k(kn.text)}")
                else:
                    b = self.registry.bloecke[kn.block_id]
                    admin = f", {self.rechte_name}" if b.braucht_admin(self.ziel) else ""
                    zeilen.append(
                        " " * einzug
                        + f"{next(zaehler):>2}. {k(b.name)} [Risiko: {(kn.risiko or b.risiko).value}{admin}]"
                    )
                    if b.dynamisch == "richtlinie":
                        zeilen.extend(" " * (einzug + 4) + k(z) for z in self._richtlinie_kopf(kn))

        liste(ir.schritte, 2)
        zeilen += ["", "Generiert mit dem okm Script-Baukasten", "=" * 70]
        return zeilen

    # --- Rechte -----------------------------------------------------------------

    @property
    def rechte_name(self) -> str:
        return "Admin" if self.ziel in WINDOWS else "sudo"

    @staticmethod
    def schritt_liste(schritte: list[tuple[int, BlockDef]], mit_namen: bool = True) -> str:
        if mit_namen:
            return ", ".join(f"Schritt {i} ({b.name})" for i, b in schritte)
        return ", ".join(str(i) for i, _ in schritte)

    def rechte_kopfzeile(self) -> str:
        """``Administrator (Schritt 2, 4)`` / ``sudo (Schritt 1)`` / ``keine`` für den Kopfkommentar."""
        teile = []
        if self._admin_schritte:
            art = "Administrator" if self.ziel in WINDOWS else "sudo"
            teile.append(f"{art} (Schritt {self.schritt_liste(self._admin_schritte, False)})")
        if self._nie_root_schritte:
            teile.append(
                f"nicht als root starten (Schritt {self.schritt_liste(self._nie_root_schritte, False)})"
            )
        return "; ".join(teile) or "keine"

    def echo(self, text: str) -> str:
        return escaping.echo(self.ziel, text)

    # --- sprachspezifisch ---------------------------------------------------

    @abstractmethod
    def kopf(self, ir: ScriptIR, defs: list[BlockDef]) -> list[str]: ...

    @abstractmethod
    def praeambel(self, ir: ScriptIR, gesamt: int, braucht_admin: bool) -> list[str]: ...

    @abstractmethod
    def schritt(self, info: SchrittInfo) -> list[str]: ...

    @abstractmethod
    def abschluss(self, ir: ScriptIR) -> list[str]: ...

    @abstractmethod
    def wenn_fehler(self, nr: int, versuch: list[str], sonst: list[str]) -> list[str]: ...

    @abstractmethod
    def wiederhole(self, nr: int, anzahl: int, rumpf: list[str]) -> list[str]: ...

    @abstractmethod
    def ist_kommentar(self, zeile: str) -> bool: ...

    @abstractmethod
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
        """``name`` = Variablenname (ohne ``$``/``%``); unbekannt → alle Vergleiche falsch."""

    @abstractmethod
    def abbrechen(self, meldung: str, code: int) -> list[str]: ...

    @abstractmethod
    def warten(self, sekunden: int, text: str) -> list[str]: ...

    @abstractmethod
    def bestaetigung(self, meldung: str) -> list[str]: ...

    @abstractmethod
    def kommentar(self, text: str) -> str: ...

    @abstractmethod
    def rueckgaben_vorbelegen(self, rueckgaben: list[tuple[Escaped, RueckgabeDef]]) -> list[str]:
        """Alle Rückgabevariablen vor dem ersten Schritt auf „unbekannt“ setzen."""

    @abstractmethod
    def rueckgabe_normalisieren(self, name: Escaped, r: RueckgabeDef) -> list[str]:
        """Zahl → nur Ziffern (sonst unbekannt), ja/nein → fester Wahrheitswert."""


def als_text(v: object) -> str:
    """Wert für Fortschrittstexte (Listen mit Komma)."""
    wert = getattr(v, "wert", None)
    if wert is None:
        return ""
    if isinstance(wert, list):
        return ", ".join(str(w) for w in wert)
    return str(wert)


def sekunden_text(n: int) -> str:
    return "1 Sekunde" if n == 1 else f"{n} Sekunden"


def bedingung_text(k: Wenn) -> str:
    """``frei_prozent aus Schritt 3 < 10`` bzw. ``erreichbar aus Schritt 1 ist ja``."""
    nr, rid = verweis_teile(k.wert)
    zahl = f" {k.zahl}" if k.vergleich.mit_zahl else ""
    return f"{rid} aus Schritt {nr} {k.vergleich.text}{zahl}"


PLANMAESSIG = " Planmäßig beendet: "


def einruecken(zeilen: list[str], tiefe: int) -> list[str]:
    return [(" " * tiefe + z) if z else "" for z in zeilen]
