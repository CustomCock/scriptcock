"""ADMX/ADML-Parser für den Richtlinien-Katalog (Administrative Vorlagen).

Liest die Vorlagen eines oder mehrerer Pakete (``registry/quellen/<paket>/admx/``) und liefert pro
Richtlinie ein Dict mit Schlüssel, Wertname, Zuständen und Elementen – Grundlage für
``registry/katalog/<paket>.json`` (``tools/admx_katalog.py``) und den Baustein ``richtlinie_setzen``.

Herstellerdateien gelten als halb vertrauenswürdig: Schlüssel, Wertnamen und Daten laufen durch
dieselben Prüfungen wie Benutzereingaben (``app.validation``); was durchfällt, wird ausgelassen und
gezählt. ``xml.etree`` löst keine externen Entitäten auf (kein XXE).

Registry-Wert (``RegWert``): ``{"typ": "REG_DWORD", "daten": 1}`` · ``{"typ": "REG_QWORD", …}`` ·
``{"typ": "REG_SZ"|"REG_EXPAND_SZ", "daten": "…"}`` · ``{"loeschen": true}``.
Listeneintrag: ``{"schluessel": "…", "wertname": "…", "wert": RegWert}``.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.models.block import ParameterDef, ParamTyp
from app.validation import ValidierungsFehler, registry_daten, validiere_wert

_PFAD = ParameterDef(id="pfad", label="Schlüssel", typ=ParamTyp.REGISTRY_PFAD)
_NAME = ParameterDef(id="name", label="Wertname", typ=ParamTyp.REGISTRY_WERTNAME, pflicht=False)
_STRING = re.compile(r"^\$\((string|presentation)\.([^)]+)\)$")
KLASSEN = {"Machine": "machine", "User": "user", "Both": "both"}


class AdmxFehler(ValueError):
    """Konstrukt, das der Katalog nicht abbilden kann – die Richtlinie wird ausgelassen."""


def _lokal(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _kinder(el: ET.Element | None, name: str | None = None) -> list[ET.Element]:
    if el is None:
        return []
    return [k for k in el if name is None or _lokal(k) == name]


def _kind(el: ET.Element | None, name: str) -> ET.Element | None:
    gefunden = _kinder(el, name)
    return gefunden[0] if gefunden else None


_DEKLARATION = re.compile(r"^\s*<\?xml[^>]*\?>")


def _lesen(datei: Path) -> ET.Element:
    """XML lesen; Kodierung selbst bestimmen (manche ADMX deklarieren „unicode“, ADML oft UTF-16)."""
    roh = datei.read_bytes()
    if roh.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = roh.decode("utf-16")
    else:
        text = roh.decode("utf-8-sig", errors="replace")
    return ET.fromstring(_DEKLARATION.sub("", text, count=1))  # noqa: S314 – lokale Dateien, keine Entitäten


@dataclass
class Sprache:
    """Texte einer ADML-Datei (de-DE, sonst en-US)."""

    texte: dict[str, str] = field(default_factory=dict)
    praesentationen: dict[str, ET.Element] = field(default_factory=dict)
    sprache: str = "de"

    @classmethod
    def laden(cls, datei: Path | None, sprache: str) -> Sprache:
        if datei is None or not datei.exists():
            return cls(sprache="")
        wurzel = _lesen(datei)
        res = _kind(wurzel, "resources")
        texte = {
            s.get("id", ""): (s.text or "").strip() for s in _kinder(_kind(res, "stringTable"), "string")
        }
        praes = {p.get("id", ""): p for p in _kinder(_kind(res, "presentationTable"), "presentation")}
        return cls(texte, praes, sprache)

    def text(self, verweis: str | None) -> str | None:
        if not verweis:
            return None
        m = _STRING.match(verweis.strip())
        if not m:
            return verweis
        return self.texte.get(m.group(2))


@dataclass
class Datei:
    """Eine ADMX-Datei mit ihren Sprachen und Namensräumen."""

    pfad: Path
    paket: str
    wurzel: ET.Element
    de: Sprache
    en: Sprache
    namespace: str = ""
    praefixe: dict[str, str] = field(default_factory=dict)  # Präfix → Namespace

    def text(self, verweis: str | None) -> tuple[str | None, str]:
        """Text aus de-DE, sonst en-US. Rückgabe (Text, Sprache)."""
        wert = self.de.text(verweis)
        if wert is not None:
            return wert, "de"
        wert = self.en.text(verweis)
        return (wert, "en") if wert is not None else (None, "")

    def praesentation(self, verweis: str | None) -> ET.Element | None:
        if not verweis:
            return None
        m = _STRING.match(verweis.strip())
        if not m:
            return None
        praes = self.de.praesentationen.get(m.group(2))
        return praes if praes is not None else self.en.praesentationen.get(m.group(2))

    def global_id(self, ref: str) -> str:
        """``prefix:name`` bzw. ``name`` → ``<namespace>:<name>``."""
        praefix, _, name = ref.rpartition(":")
        ns = self.praefixe.get(praefix, praefix) if praefix else self.namespace
        return f"{ns}:{name}"


@dataclass
class Statistik:
    richtlinien: Counter[str] = field(default_factory=Counter)
    ohne_deutsch: Counter[str] = field(default_factory=Counter)
    ausgelassen: Counter[str] = field(default_factory=Counter)
    gruende: Counter[str] = field(default_factory=Counter)
    nicht_unterstuetzt: Counter[str] = field(default_factory=Counter)


def dateien_laden(paket: str, ordner: Path) -> list[Datei]:
    ergebnis = []
    for admx in sorted(ordner.glob("*.admx"), key=lambda p: p.name.lower()):
        adml = admx.stem + ".adml"
        de = _sprachdatei(ordner, ("de-DE", "de-de", "de"), adml)
        en = _sprachdatei(ordner, ("en-US", "en-us", "en"), adml)
        wurzel = _lesen(admx)
        datei = Datei(admx, paket, wurzel, Sprache.laden(de, "de"), Sprache.laden(en, "en"))
        ns = _kind(wurzel, "policyNamespaces")
        ziel = _kind(ns, "target")
        if ziel is not None:
            datei.namespace = ziel.get("namespace", "")
            datei.praefixe[ziel.get("prefix", "")] = datei.namespace
        for using in _kinder(ns, "using"):
            datei.praefixe[using.get("prefix", "")] = using.get("namespace", "")
        ergebnis.append(datei)
    return ergebnis


def _sprachdatei(ordner: Path, unterordner: tuple[str, ...], name: str) -> Path | None:
    for u in unterordner:
        for kandidat in (ordner / u).glob("*.adml") if (ordner / u).is_dir() else []:
            if kandidat.name.lower() == name.lower():
                return kandidat
    return None


# --- Kategorien und „Unterstützt auf“ (über alle Dateien aller Pakete) ------------------------------


@dataclass
class Gesamt:
    kategorien: dict[str, dict[str, Any]] = field(default_factory=dict)  # global_id → {name, eltern, paket}
    unterstuetzt: dict[str, str] = field(default_factory=dict)  # global_id → Text

    def aufnehmen(self, datei: Datei, stat: Statistik) -> None:
        for kat in _kinder(_kind(datei.wurzel, "categories"), "category"):
            name, _ = datei.text(kat.get("displayName"))
            eltern = _kind(kat, "parentCategory")
            gid = datei.global_id(kat.get("name", ""))
            self.kategorien[gid] = {
                "id": gid,
                "name": name or kat.get("name", ""),
                "eltern": datei.global_id(eltern.get("ref", "")) if eltern is not None else None,
                "paket": datei.paket,
            }
        definitionen = _kind(_kind(datei.wurzel, "supportedOn"), "definitions")
        for d in _kinder(definitionen, "definition"):
            text, _ = datei.text(d.get("displayName"))
            if text:
                self.unterstuetzt[datei.global_id(d.get("name", ""))] = text

    def pfad(self, gid: str | None) -> list[str]:
        namen: list[str] = []
        gesehen: set[str] = set()
        while gid and gid in self.kategorien and gid not in gesehen:
            gesehen.add(gid)
            namen.append(self.kategorien[gid]["name"])
            gid = self.kategorien[gid]["eltern"]
        return list(reversed(namen))


# --- Werte -----------------------------------------------------------------------------------------


def _pruefen_pfad(schluessel: str) -> str:
    try:
        wert = validiere_wert(_PFAD, schluessel).wert
    except ValidierungsFehler as e:
        raise AdmxFehler(f"Schlüssel: {e}") from None
    if not isinstance(wert, str) or wert.split("\\", 1)[0] in ("HKLM", "HKCU", "HKU", "HKCR", "HKCC"):
        raise AdmxFehler("Schlüssel mit Wurzel")
    return wert


def _pruefen_name(name: str | None) -> str:
    if not name:
        return ""
    try:
        wert = validiere_wert(_NAME, name).wert
    except ValidierungsFehler as e:
        raise AdmxFehler(f"Wertname: {e}") from None
    return wert if isinstance(wert, str) else ""


def regwert(el: ET.Element | None) -> dict[str, Any] | None:
    """``<decimal value="1"/>`` | ``<longDecimal …/>`` | ``<string>…</string>`` | ``<delete/>``."""
    if el is None:
        return None
    kind = el if _lokal(el) in ("decimal", "longDecimal", "string", "delete") else next(iter(el), None)
    if kind is None:
        return None
    art = _lokal(kind)
    try:
        if art == "decimal":
            return {"typ": "REG_DWORD", "daten": registry_daten(kind.get("value", ""), "REG_DWORD")}
        if art == "longDecimal":
            return {"typ": "REG_QWORD", "daten": registry_daten(kind.get("value", ""), "REG_QWORD")}
        if art == "string":
            text = kind.text or ""
            return {"typ": "REG_SZ", "daten": registry_daten(text, "REG_SZ") if text.strip() else ""}
    except ValidierungsFehler as e:
        raise AdmxFehler(f"Wert: {e}") from None
    if art == "delete":
        return {"loeschen": True}
    raise AdmxFehler(f"unbekannter Wert <{art}>")


def regliste(el: ET.Element | None, schluessel: str) -> list[dict[str, Any]]:
    if el is None:
        return []
    standard = el.get("defaultKey") or schluessel
    eintraege = []
    for item in _kinder(el, "item"):
        wert = regwert(_kind(item, "value"))
        if wert is None:
            raise AdmxFehler("Listeneintrag ohne Wert")
        eintraege.append(
            {
                "schluessel": _pruefen_pfad(item.get("key") or standard),
                "wertname": _pruefen_name(item.get("valueName")),
                "wert": wert,
            }
        )
    return eintraege


# --- Elemente ---------------------------------------------------------------------------------------


def _beschriftungen(datei: Datei, praes: ET.Element | None) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Presentation → {refId: {label, art, standard…}} und Reihenfolge der refIds."""
    info: dict[str, dict[str, Any]] = {}
    reihenfolge: list[str] = []
    for teil in _kinder(praes):
        ref = teil.get("refId")
        art = _lokal(teil)
        if not ref:
            continue
        label_el = _kind(teil, "label")
        label = (label_el.text if label_el is not None else teil.text) or ""
        eintrag: dict[str, Any] = {"label": " ".join(label.split()), "steuerung": art}
        if art == "decimalTextBox" and teil.get("defaultValue"):
            eintrag["standard"] = int(teil.get("defaultValue", "0"))
        elif art == "checkBox":
            eintrag["standard"] = teil.get("defaultChecked", "false") == "true"
        elif art == "dropdownList" and teil.get("defaultItem"):
            eintrag["standard"] = int(teil.get("defaultItem", "0"))
        elif art in ("textBox", "comboBox"):
            std = _kind(teil, "defaultValue")
            if std is None:  # Element ohne Kinder ist „falsy“ – kein „or“
                std = _kind(teil, "default")
            if std is not None and std.text:
                eintrag["standard"] = std.text
        info[ref] = eintrag
        reihenfolge.append(ref)
    return info, reihenfolge


def element(datei: Datei, el: ET.Element, policy_key: str, stat: Statistik) -> dict[str, Any]:
    art = _lokal(el)
    eid = el.get("id", "")
    schluessel = _pruefen_pfad(el.get("key") or policy_key)
    e: dict[str, Any] = {
        "id": eid,
        "art": art,
        "schluessel": schluessel,
        "wertname": _pruefen_name(el.get("valueName")),
        "pflicht": el.get("required", "false") == "true",
    }
    if el.get("soft") == "true":
        stat.nicht_unterstuetzt["soft (nur setzen, wenn nicht vorhanden)"] += 1
        e["nur_wenn_fehlt"] = True
    if el.get("clientExtension"):
        stat.nicht_unterstuetzt["clientExtension"] += 1
    if art == "boolean":
        wahr, falsch = _kind(el, "trueValue"), _kind(el, "falseValue")
        e["wahr"] = {
            "wert": regwert(wahr) or {"typ": "REG_DWORD", "daten": 1},
            "liste": regliste(_kind(el, "trueList"), schluessel),
        }
        e["falsch"] = {
            "wert": regwert(falsch) or {"typ": "REG_DWORD", "daten": 0},
            "liste": regliste(_kind(el, "falseList"), schluessel),
        }
        if not e["wertname"]:
            e["wahr"]["wert"] = e["falsch"]["wert"] = None
    elif art in ("decimal", "longDecimal"):
        grenze = 0xFFFFFFFF if art == "decimal" else 0xFFFFFFFFFFFFFFFF
        e["min"] = int(el.get("minValue", "0"))
        e["max"] = min(int(el.get("maxValue", str(9999 if art == "decimal" else grenze))), grenze)
        e["als_text"] = el.get("storeAsText", "false") == "true"
    elif art == "text":
        e["max_laenge"] = min(int(el.get("maxLength", "1023")), 4096)
        e["erweiterbar"] = el.get("expandable", "false") == "true"
    elif art == "multiText":
        e["max_laenge"] = min(int(el.get("maxLength", "1023")), 4096)
        e["max_eintraege"] = int(el.get("maxStrings", "0")) or None
    elif art == "enum":
        optionen = []
        for nr, item in enumerate(_kinder(el, "item")):
            label, _ = datei.text(item.get("displayName"))
            wert = regwert(_kind(item, "value"))
            if wert is None:
                raise AdmxFehler("Auswahl ohne Wert")
            optionen.append(
                {
                    "nr": nr,
                    "label": label or str(nr),
                    "wert": wert,
                    "liste": regliste(_kind(item, "valueList"), schluessel),
                }
            )
        if not optionen:
            raise AdmxFehler("Auswahl ohne Einträge")
        e["optionen"] = optionen
    elif art == "list":
        e["praefix"] = el.get("valuePrefix") or ""
        e["additiv"] = el.get("additive", "false") == "true"
        e["expliziter_wert"] = el.get("explicitValue", "false") == "true"
        e["erweiterbar"] = el.get("expandable", "false") == "true"
        if e["wertname"]:
            stat.nicht_unterstuetzt["list mit valueName"] += 1
    else:
        raise AdmxFehler(f"unbekanntes Element <{art}>")
    return e


# --- Richtlinien ------------------------------------------------------------------------------------


def richtlinie(datei: Datei, pol: ET.Element, gesamt: Gesamt, stat: Statistik) -> dict[str, Any]:
    name = pol.get("name", "")
    klasse = KLASSEN.get(pol.get("class", ""))
    if klasse is None:
        raise AdmxFehler(f"unbekannte class {pol.get('class')}")
    schluessel = _pruefen_pfad(pol.get("key", ""))
    titel, sprache_t = datei.text(pol.get("displayName"))
    erklaerung, sprache_e = datei.text(pol.get("explainText"))
    eltern = _kind(pol, "parentCategory")
    kategorie = datei.global_id(eltern.get("ref", "")) if eltern is not None else None
    unterstuetzt_el = _kind(pol, "supportedOn")
    unterstuetzt = None
    if unterstuetzt_el is not None:
        unterstuetzt = gesamt.unterstuetzt.get(datei.global_id(unterstuetzt_el.get("ref", "")))
    beschr, reihenfolge = _beschriftungen(datei, datei.praesentation(pol.get("presentation")))
    elemente = [element(datei, el, schluessel, stat) for el in _kinder(_kind(pol, "elements"))]
    rang = {ref: i for i, ref in enumerate(reihenfolge)}
    for e in elemente:
        e.update(beschr.get(e["id"], {"label": e["id"]}))
    elemente.sort(key=lambda e: rang.get(e["id"], len(rang)))
    wertname = _pruefen_name(pol.get("valueName"))
    aktiviert = {
        "wert": regwert(_kind(pol, "enabledValue")),
        "liste": regliste(_kind(pol, "enabledList"), schluessel),
    }
    deaktiviert = {
        "wert": regwert(_kind(pol, "disabledValue")),
        "liste": regliste(_kind(pol, "disabledList"), schluessel),
    }
    if wertname and aktiviert["wert"] is None and deaktiviert["wert"] is None:
        # Konvention des Gruppenrichtlinien-Editors: aktiviert = DWORD 1, deaktiviert = DWORD 0
        aktiviert["wert"] = {"typ": "REG_DWORD", "daten": 1}
        deaktiviert["wert"] = {"typ": "REG_DWORD", "daten": 0}
    sprache = "de" if sprache_t == "de" and sprache_e in ("de", "") else "en"
    return {
        "id": f"{datei.paket}:{datei.pfad.stem.lower()}:{name}",
        "paket": datei.paket,
        "datei": datei.pfad.name,
        "name": name,
        "klasse": klasse,
        "kategorie": kategorie,
        "kategorie_pfad": gesamt.pfad(kategorie),
        "titel": titel or name,
        "erklaerung": erklaerung or "",
        "sprache": sprache,
        "unterstuetzt": unterstuetzt or "",
        "schluessel": schluessel,
        "wertname": wertname,
        "aktiviert": aktiviert,
        "deaktiviert": deaktiviert,
        "elemente": elemente,
    }


def pakete_parsen(ordner: dict[str, Path]) -> tuple[dict[str, list[dict[str, Any]]], Gesamt, Statistik]:
    """Alle Pakete gemeinsam (Kategorien über Paketgrenzen). Rückgabe: Richtlinien je Paket."""
    stat = Statistik()
    gesamt = Gesamt()
    dateien = {paket: dateien_laden(paket, pfad) for paket, pfad in ordner.items()}
    for liste in dateien.values():
        for d in liste:
            gesamt.aufnehmen(d, stat)
    ergebnis: dict[str, list[dict[str, Any]]] = {}
    for paket, liste in dateien.items():
        richtlinien = []
        for d in liste:
            for pol in _kinder(_kind(d.wurzel, "policies"), "policy"):
                try:
                    r = richtlinie(d, pol, gesamt, stat)
                except (AdmxFehler, ValueError) as e:
                    stat.ausgelassen[paket] += 1
                    stat.gruende[str(e).split(":")[0]] += 1
                    continue
                richtlinien.append(r)
                stat.richtlinien[paket] += 1
                if r["sprache"] != "de":
                    stat.ohne_deutsch[paket] += 1
        richtlinien.sort(key=lambda r: r["id"].lower())
        ergebnis[paket] = richtlinien
    return ergebnis, gesamt, stat
