"""Lädt und prüft alle Block- und Rezept-YAMLs beim Start.

Ist eine Datei fehlerhaft, bricht der Start mit einer Meldung ab, die Datei,
Feld und Problem nennt. Geprüft wird u. a.:

* Schema (Pydantic, unbekannte Felder sind Fehler)
* Template-Syntax je Ziel, nur deklarierte Platzhalter
* Platzhalter stehen nicht innerhalb von Anführungszeichen
* sprachspezifische Verbote (``eval``, ``Invoke-Expression``, ``%ERRORLEVEL%`` …)
* Beispiel- und Standardwerte bestehen ihre eigene Validierung
* Rezepte verweisen nur auf existierende Blöcke, Parameter und Felder
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Template, TemplateSyntaxError, meta
from pydantic import ValidationError

from app.codeenv import code_umgebung, text_umgebung
from app.escaping import Ziel
from app.models.block import EINGEBAUTE_VARIABLEN, RUECKGABE_PRAEFIX, BlockDef, ParameterDef, ParamTyp, Recht
from app.models.recipe import RezeptDef, RezeptSchritt, feld_verweis, konstante
from app.validation import ValidierungsFehler, pruefe_wert_fuer_ziel, validiere_wert

PROJEKT = Path(__file__).resolve().parent.parent
BLOCK_VERZEICHNIS = PROJEKT / "blocks"
REZEPT_VERZEICHNIS = PROJEKT / "recipes"


class RegistryFehler(Exception):
    def __init__(self, fehler: list[str]) -> None:
        self.fehler = fehler
        super().__init__(
            "Block-/Rezept-Definitionen sind fehlerhaft:\n" + "\n".join(f"  - {f}" for f in fehler)
        )


# Verbotene Konstrukte in Code-Templates (pro Ziel).
_VERBOTE: dict[Ziel, list[tuple[re.Pattern[str], str]]] = {
    Ziel.POWERSHELL: [
        (re.compile(r"\b(Invoke-Expression|iex)\b", re.I), "Invoke-Expression ist verboten"),
        (re.compile(r"@['\"]\s*$", re.M), "Here-Strings sind verboten (Einrückung zerstört sie)"),
        (re.compile(r"^\s*exit\b", re.I | re.M), "'exit' ist verboten – der Generator steuert den Ablauf"),
    ],
    Ziel.CMD: [
        (re.compile(r"%ERRORLEVEL%", re.I), "%ERRORLEVEL% ist verboten, 'if errorlevel N' verwenden"),
        (re.compile(r"EnableDelayedExpansion", re.I), "Delayed Expansion ist verboten"),
        (re.compile(r"\bgoto\b", re.I), "'goto' ist verboten – der Generator steuert den Ablauf"),
        (re.compile(r"(?<!cmd /c )\bexit\b", re.I), "'exit' ist verboten ('cmd /c exit N' ist erlaubt)"),
        (re.compile(r"^\s*call\b.*\{\{", re.I | re.M), "'call' mit Platzhaltern ist verboten"),
    ],
    Ziel.BASH: [
        (re.compile(r"\beval\b"), "'eval' ist verboten"),
        (re.compile(r"`"), "Backticks sind verboten, $(…) verwenden"),
        (re.compile(r"^\s*exit\b", re.M), "'exit' ist verboten – der Generator steuert den Ablauf"),
        (
            re.compile(r"(^|[;&|(]\s*)sudo\b", re.M),
            "'sudo' im Template ist verboten – 'rechte: root' setzen und {{ sudo }} voranstellen",
        ),
    ],
}
_VERBOTE[Ziel.ZSH] = _VERBOTE[Ziel.BASH]


def platzhalter_in_quotes(quelle: str, ziel: Ziel) -> list[int]:
    """Zeilennummern (1-basiert), in denen ``{{`` innerhalb von Quotes steht."""
    quotes = {'"'} if ziel is Ziel.CMD else {'"', "'"}
    treffer: list[int] = []
    for nr, zeile in enumerate(quelle.splitlines(), start=1):
        stripped = zeile.strip()
        if ziel is Ziel.CMD and re.match(r"(?i)^(rem\b|::)", stripped):
            continue
        zustand: str | None = None
        i = 0
        while i < len(zeile):
            z = zeile[i]
            if zeile.startswith("{%", i) or zeile.startswith("{#", i):
                ende = zeile.find("%}" if z + zeile[i + 1] == "{%" else "#}", i)
                i = len(zeile) if ende < 0 else ende + 2
                continue
            if zeile.startswith("{{", i) and zustand is not None:
                treffer.append(nr)
                break
            if zustand is None and z == "#" and ziel is not Ziel.CMD and (i == 0 or zeile[i - 1].isspace()):
                break
            if z in quotes:
                if zustand is None:
                    zustand = z
                elif zustand == z:
                    zustand = None
            i += 1
    return treffer


def cmd_klammern_ok(quelle: str) -> bool:
    """Klammern außerhalb von Quotes müssen ausgeglichen sein (Schritt-Gruppierung)."""
    tiefe = 0
    for zeile in quelle.splitlines():
        if re.match(r"(?i)^\s*(rem\b|::)", zeile):
            continue
        in_quote = False
        vorher = ""
        for i, z in enumerate(zeile):
            if z == '"':
                in_quote = not in_quote
            elif not in_quote and vorher != "^":
                # "echo(" ist die sichere echo-Schreibweise, keine Blockklammer.
                if z == "(" and zeile[:i].lower().endswith("echo"):
                    pass
                elif z == "(":
                    tiefe += 1
                elif z == ")":
                    tiefe -= 1
                    if tiefe < 0:
                        return False
            vorher = z
    return tiefe == 0


@dataclass
class Registry:
    bloecke: dict[str, BlockDef] = field(default_factory=dict)
    rezepte: dict[str, RezeptDef] = field(default_factory=dict)
    # (block_id, art, ziel) -> kompiliertes Template; art in {"ziele", "pruefung", "dry_run"}
    vorlagen: dict[tuple[str, str, Ziel], Template] = field(default_factory=dict)
    variablen: dict[tuple[str, str, Ziel], frozenset[str]] = field(default_factory=dict)
    fortschritt: dict[str, Template] = field(default_factory=dict)

    def kategorien(self) -> list[str]:
        return sorted({b.kategorie for b in self.bloecke.values()})

    def benutzte_parameter(self, block: BlockDef, ziel: Ziel) -> set[str]:
        """Parameter-IDs, die die Templates des Blocks für ``ziel`` tatsächlich verwenden."""
        if not block.verfuegbar(ziel):
            return set()
        variablen: set[str] = set()
        for art in ("ziele", "pruefung", "dry_run"):
            variablen |= self.variablen.get((block.id, art, ziel), frozenset())
        abgeleitet = block.abgeleitete_variablen()
        return {abgeleitet.get(v, v) for v in variablen}

    def rezept_ziele(self, rezept: RezeptDef) -> list[Ziel]:
        """Ziele, für die alle aktiven Schritte eines Rezepts verfügbar sind.

        Feste Werte müssen zum Ziel passen (z. B. ein Windows-Pfad nicht unter Linux).
        """
        ergebnis = []
        for ziel in Ziel:
            schritte = rezept.schritte_fuer(ziel)
            if schritte and all(self._schritt_passt(s, ziel) for s in schritte):
                ergebnis.append(ziel)
        return ergebnis

    def _schritt_passt(self, schritt: RezeptSchritt, ziel: Ziel) -> bool:
        block = self.bloecke.get(schritt.block)
        if block is None or not block.verfuegbar(ziel):
            return False
        for pid, wert in schritt.parameter.items():
            param = block.param(pid)
            if param is None or feld_verweis(wert) is not None:
                continue
            try:
                pruefe_wert_fuer_ziel(validiere_wert(param, konstante(wert)), ziel)
            except ValidierungsFehler:
                return False
        return True

    def rezept_pruefen(self, rezept: RezeptDef) -> list[str]:
        """Prüft ein Rezept gegen die geladenen Blöcke, ohne es aufzunehmen."""
        fehler: list[str] = []
        if rezept.id in self.rezepte:
            fehler.append(f"{rezept.quelle}: Rezept-ID '{rezept.id}' ist bereits vergeben")
        _pruefe_rezept(rezept, self, fehler)
        return fehler

    def rezept_hinzufuegen(self, rezept: RezeptDef) -> None:
        """Fügt ein Rezept zur Laufzeit hinzu (z. B. aus der Datenbank) – mit voller Prüfung."""
        fehler = self.rezept_pruefen(rezept)
        if fehler:
            raise RegistryFehler(fehler)
        self.rezepte[rezept.id] = rezept

    def rezept_entfernen(self, rezept_id: str) -> None:
        self.rezepte.pop(rezept_id, None)


def _yaml_laden(pfad: Path) -> Any:
    with pfad.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _pydantic_fehler(rel: str, e: ValidationError) -> list[str]:
    meldungen = []
    for fehler in e.errors():
        ort = ".".join(str(t) for t in fehler["loc"]) or "(Datei)"
        meldungen.append(f"{rel}: {ort}: {fehler['msg']}")
    return meldungen


def _pruefe_block(block: BlockDef, reg: Registry, fehler: list[str]) -> None:
    rel = block.quelle
    env = code_umgebung()
    param_ids = {p.id for p in block.parameter} | set(block.abgeleitete_variablen())

    for p in block.parameter:
        # Verweise auf Rückgabewerte hängen vom Script ab – dafür gibt es kein festes Beispiel.
        if p.pflicht and p.beispiel is None and p.standard is None and p.typ is not ParamTyp.VARIABLE:
            fehler.append(f"{rel}: parameter.{p.id}: Pflichtparameter braucht 'beispiel' oder 'standard'")
        for name in ("beispiel", "standard"):
            wert = getattr(p, name)
            if wert is None:
                continue
            try:
                validiere_wert(p, wert)
            except ValidierungsFehler as e:
                fehler.append(f"{rel}: parameter.{p.id}.{name}: {e}")

    for art in ("ziele", "pruefung", "dry_run"):
        quellen: dict[Ziel, str] = getattr(block, art)
        for ziel, quelle in quellen.items():
            ort = f"{rel}: {art}.{ziel.value}"
            try:
                ast = env.parse(quelle)
            except TemplateSyntaxError as e:
                fehler.append(f"{ort}: Template-Syntaxfehler in Zeile {e.lineno}: {e.message}")
                continue
            variablen = meta.find_undeclared_variables(ast)
            rueckgaben = {RUECKGABE_PRAEFIX + r.id for r in block.rueckgaben(ziel)}
            unbekannt = variablen - param_ids - EINGEBAUTE_VARIABLEN - rueckgaben
            if unbekannt:
                fehler.append(f"{ort}: unbekannte Platzhalter: {', '.join(sorted(unbekannt))}")
            if "whatif" in variablen and ziel is not Ziel.POWERSHELL:
                fehler.append(f"{ort}: {{{{ whatif }}}} gibt es nur für PowerShell")
            if "sudo" in variablen and block.recht(ziel) is not Recht.ROOT:
                fehler.append(f"{ort}: {{{{ sudo }}}} nur in Blöcken mit 'rechte: {{{ziel.value}: root}}'")
            if art == "ziele" and block.recht(ziel) is Recht.ROOT and "sudo" not in variablen:
                fehler.append(
                    f"{ort}: Block braucht root – privilegierte Befehle mit {{{{ sudo }}}} beginnen"
                )
            for zeile in platzhalter_in_quotes(quelle, ziel):
                fehler.append(
                    f"{ort}: Zeile {zeile}: Platzhalter steht in Anführungszeichen – Werte werden "
                    "automatisch gequotet, bitte Quotes entfernen"
                )
            for muster, meldung in _VERBOTE[ziel]:
                if muster.search(quelle):
                    fehler.append(f"{ort}: {meldung}")
            if ziel is Ziel.CMD and not cmd_klammern_ok(quelle):
                fehler.append(f"{ort}: Klammern außerhalb von Anführungszeichen sind nicht ausgeglichen")
            reg.vorlagen[(block.id, art, ziel)] = env.from_string(quelle)
            reg.variablen[(block.id, art, ziel)] = frozenset(variablen)

    # Jeder Rückgabewert muss im Template seines Ziels gesetzt werden (sonst bliebe er „unbekannt“).
    for ziel in block.ziele:
        gesetzt = reg.variablen.get((block.id, "ziele", ziel), frozenset()) | reg.variablen.get(
            (block.id, "pruefung", ziel), frozenset()
        )
        for r in block.rueckgaben(ziel):
            if RUECKGABE_PRAEFIX + r.id not in gesetzt:
                fehler.append(
                    f"{rel}: ziele.{ziel.value}: Rückgabewert '{r.id}' wird nie gesetzt "
                    f"({{{{ {RUECKGABE_PRAEFIX}{r.id} }}}} fehlt) – sonst 'ziele' der Rückgabe einschränken"
                )

    if block.fortschritt is not None:
        try:
            tenv = text_umgebung()
            ast = tenv.parse(block.fortschritt)
            unbekannt = meta.find_undeclared_variables(ast) - {p.id for p in block.parameter}
            if unbekannt:
                fehler.append(f"{rel}: fortschritt: unbekannte Platzhalter: {', '.join(sorted(unbekannt))}")
            reg.fortschritt[block.id] = tenv.from_string(block.fortschritt)
        except TemplateSyntaxError as e:
            fehler.append(f"{rel}: fortschritt: Template-Syntaxfehler: {e.message}")


def _typ_kompatibel(feld: ParameterDef, param: ParameterDef) -> bool:
    if feld.typ != param.typ:
        return False
    if param.optionen:
        return {o.wert for o in feld.optionen} <= {o.wert for o in param.optionen}
    return True


def _pruefe_rezept(rezept: RezeptDef, reg: Registry, fehler: list[str]) -> None:
    rel = rezept.quelle
    felder = {f.id: f for f in rezept.felder}
    benutzt: set[str] = set()
    for p in rezept.felder:
        if p.pflicht and p.beispiel is None and p.standard is None:
            fehler.append(f"{rel}: felder.{p.id}: Pflichtfeld braucht 'beispiel' oder 'standard'")
        for name in ("beispiel", "standard"):
            wert = getattr(p, name)
            if wert is not None:
                try:
                    validiere_wert(p, wert)
                except ValidierungsFehler as e:
                    fehler.append(f"{rel}: felder.{p.id}.{name}: {e}")
    for i, schritt in enumerate(rezept.schritte):
        ort = f"{rel}: schritte.{i}"
        block = reg.bloecke.get(schritt.block)
        if block is None:
            fehler.append(f"{ort}: unbekannter Block '{schritt.block}'")
            continue
        for ziel in schritt.nur_fuer:
            if not block.verfuegbar(ziel):
                fehler.append(f"{ort}: Block '{block.id}' ist für {ziel.value} nicht verfügbar")
        for pid, wert in schritt.parameter.items():
            param = block.param(pid)
            if param is None:
                fehler.append(f"{ort}: Block '{block.id}' hat keinen Parameter '{pid}'")
                continue
            verweis = feld_verweis(wert)
            if verweis is not None:
                feld = felder.get(verweis)
                if feld is None:
                    fehler.append(f"{ort}.{pid}: Formularfeld '{verweis}' existiert nicht")
                elif not _typ_kompatibel(feld, param):
                    fehler.append(
                        f"{ort}.{pid}: Feld '{verweis}' hat Typ {feld.typ.value}, Parameter erwartet "
                        f"{param.typ.value} (bzw. passende Optionen)"
                    )
                benutzt.add(verweis)
            else:
                try:
                    validiere_wert(param, konstante(wert))
                except ValidierungsFehler as e:
                    fehler.append(f"{ort}.{pid}: {e}")
        for param in block.parameter:
            if param.pflicht and param.standard is None and param.id not in schritt.parameter:
                fehler.append(f"{ort}: Pflichtparameter '{param.id}' von Block '{block.id}' fehlt")
    for fid in felder.keys() - benutzt:
        fehler.append(f"{rel}: felder.{fid}: Feld wird in keinem Schritt verwendet")
    if not reg.rezept_ziele(rezept) and not any(f.startswith(rel) for f in fehler):
        fehler.append(f"{rel}: Rezept ist für kein Zielsystem vollständig verfügbar")


def lade_registry(
    block_verzeichnis: Path = BLOCK_VERZEICHNIS,
    rezept_verzeichnis: Path = REZEPT_VERZEICHNIS,
) -> Registry:
    reg = Registry()
    fehler: list[str] = []

    for pfad in sorted(block_verzeichnis.rglob("*.yaml")):
        rel = str(pfad.relative_to(block_verzeichnis.parent))
        try:
            daten = _yaml_laden(pfad)
        except yaml.YAMLError as e:
            fehler.append(f"{rel}: YAML-Syntaxfehler: {e}")
            continue
        if not isinstance(daten, dict):
            fehler.append(f"{rel}: Datei muss ein YAML-Objekt (Schlüssel: Wert) enthalten")
            continue
        try:
            block = BlockDef.model_validate({**daten, "quelle": rel})
        except ValidationError as e:
            fehler.extend(_pydantic_fehler(rel, e))
            continue
        if block.id in reg.bloecke:
            fehler.append(
                f"{rel}: Block-ID '{block.id}' ist bereits in {reg.bloecke[block.id].quelle} vergeben"
            )
            continue
        reg.bloecke[block.id] = block
        _pruefe_block(block, reg, fehler)

    for pfad in sorted(rezept_verzeichnis.rglob("*.yaml")) if rezept_verzeichnis.exists() else []:
        rel = str(pfad.relative_to(rezept_verzeichnis.parent))
        try:
            daten = _yaml_laden(pfad)
        except yaml.YAMLError as e:
            fehler.append(f"{rel}: YAML-Syntaxfehler: {e}")
            continue
        if not isinstance(daten, dict):
            fehler.append(f"{rel}: Datei muss ein YAML-Objekt enthalten")
            continue
        try:
            rezept = RezeptDef.model_validate({**daten, "quelle": rel})
        except ValidationError as e:
            fehler.extend(_pydantic_fehler(rel, e))
            continue
        if rezept.id in reg.rezepte:
            fehler.append(f"{rel}: Rezept-ID '{rezept.id}' ist doppelt")
            continue
        reg.rezepte[rezept.id] = rezept
        _pruefe_rezept(rezept, reg, fehler)

    if fehler:
        raise RegistryFehler(fehler)
    return reg
