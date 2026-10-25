"""Richtlinien-Katalog (ADMX) zur Laufzeit: Suchindex, Nachschlagen, dynamische Parameter, Operationen.

Quelle sind die Textdateien ``registry/katalog/<paket>.jsonl`` (erzeugt von ``tools/admx_katalog.py``).
Daraus entsteht beim ersten Zugriff ein SQLite-Suchindex mit FTS5 (``<cache>/richtlinien-<hash>.sqlite``);
er wird nur neu gebaut, wenn sich die Katalogdateien ändern, und danach nur gelesen.

``parameter_fuer`` macht aus den ADMX-Elementen einer Richtlinie normale ``ParameterDef`` (geprüft wie
jede andere Eingabe), ``operationen`` übersetzt Zustand + geprüfte Werte in Registry-Operationen, die der
Generator ausgibt.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.models.block import Option, ParameterDef, ParamTyp

PROJEKT = Path(__file__).resolve().parent.parent
KATALOG_ORDNER = PROJEKT / "registry" / "katalog"
HAEUFIG_YAML = PROJEKT / "registry" / "haeufig.yaml"
ZUSTAENDE = ("aktiviert", "deaktiviert", "nicht_konfiguriert")
ELEMENT_PRAEFIX = "e_"
_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def normalisiere(text: str) -> str:
    """Wie ``katalog-suche.js``: klein, Umlaute → ae/oe/ue/ss, Akzente weg; - . _ \\ trennen Wörter."""
    text = text.lower().translate(_UMLAUTE)
    text = "".join(z for z in unicodedata.normalize("NFD", text) if unicodedata.category(z) != "Mn")
    return re.sub(r"[-._\\/]+", " ", text)


@lru_cache(maxsize=2)
def haeufig(datei: Path = HAEUFIG_YAML) -> tuple[dict[str, Any], ...]:
    """Häufige Einstellungen (``registry/haeufig.yaml``) – Verweise auf Katalog-Richtlinien."""
    daten = yaml.safe_load(datei.read_text(encoding="utf-8")) or {}
    return tuple(dict(e) for e in daten.get("eintraege", []))


def _fts_anfrage(q: str) -> str | None:
    woerter = re.findall(r"\w+", normalisiere(q))
    if not woerter:
        return None
    return " AND ".join(f'"{w}"*' for w in woerter[:12])


@dataclass(frozen=True)
class Operation:
    """Eine Registry-Änderung einer Richtlinie (``pfad`` ohne Wurzel; die Wurzel ergibt die Klasse)."""

    art: str  # setzen | loeschen | leeren | leer_entfernen
    pfad: str
    name: str = ""
    typ: str = ""
    daten: str | int | tuple[str, ...] | None = None
    nur_wenn_fehlt: bool = False


class RichtlinienKatalog:
    def __init__(self, ordner: Path = KATALOG_ORDNER, cache: Path | None = None) -> None:
        self.ordner = ordner
        self.cache = cache or (PROJEKT / "data")

    # --- Index -----------------------------------------------------------------------------

    @cached_property
    def dateien(self) -> list[Path]:
        return sorted(self.ordner.glob("*.jsonl")) if self.ordner.is_dir() else []

    @cached_property
    def datenbank(self) -> Path:
        h = hashlib.sha256()
        for d in self.dateien:
            h.update(d.name.encode())
            h.update(d.read_bytes())
        ziel = self.cache / f"richtlinien-{h.hexdigest()[:16]}.sqlite"
        if not ziel.exists():
            self.cache.mkdir(parents=True, exist_ok=True)
            neu = ziel.with_suffix(".neu")
            neu.unlink(missing_ok=True)
            self._bauen(neu)
            neu.replace(ziel)
        return ziel

    def _bauen(self, ziel: Path) -> None:
        con = sqlite3.connect(ziel)
        con.executescript(
            """
            CREATE TABLE pakete (id TEXT PRIMARY KEY, name TEXT, version TEXT, seite TEXT, software TEXT,
                                 anzahl INTEGER DEFAULT 0);
            CREATE TABLE kategorien (id TEXT PRIMARY KEY, paket TEXT, name TEXT, eltern TEXT,
                                     anzahl INTEGER DEFAULT 0);
            CREATE TABLE richtlinien (id TEXT PRIMARY KEY, paket TEXT, titel TEXT, klasse TEXT,
                                      kategorie TEXT, pfad TEXT, schluessel TEXT, wertname TEXT,
                                      daten TEXT);
            CREATE VIRTUAL TABLE suche USING fts5(id UNINDEXED, titel, erklaerung, pfad, schluessel, wertname,
                                                  tokenize = 'unicode61 remove_diacritics 2');
            """
        )
        for datei in self.dateien:
            for zeile in datei.read_text(encoding="utf-8").splitlines():
                if not zeile.strip():
                    continue
                e = json.loads(zeile)
                if e["art"] == "paket":
                    con.execute(
                        "INSERT INTO pakete (id, name, version, seite, software) VALUES (?, ?, ?, ?, ?)",
                        (e["id"], e["name"], e.get("version", ""), e.get("seite", ""), e.get("software")),
                    )
                elif e["art"] == "kategorie":
                    con.execute(
                        "INSERT OR REPLACE INTO kategorien (id, paket, name, eltern) VALUES (?, ?, ?, ?)",
                        (e["id"], datei.stem, e["name"], e.get("eltern")),
                    )
                elif e["art"] == "richtlinie":
                    pfad = " > ".join(e["kategorie_pfad"])
                    con.execute(
                        "INSERT INTO richtlinien VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            e["id"],
                            e["paket"],
                            e["titel"],
                            e["klasse"],
                            e["kategorie"],
                            pfad,
                            e["schluessel"],
                            e["wertname"],
                            json.dumps(e, ensure_ascii=False),
                        ),
                    )
                    namen = " ".join([e["wertname"], *(el.get("wertname", "") for el in e["elemente"])])
                    alle = [e["schluessel"], *(el["schluessel"] for el in e["elemente"])]
                    schluessel = " ".join(dict.fromkeys(alle))
                    con.execute(
                        "INSERT INTO suche VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            e["id"],
                            normalisiere(e["titel"]),
                            normalisiere(e["erklaerung"]),
                            normalisiere(pfad),
                            normalisiere(schluessel),
                            normalisiere(namen) + " " + normalisiere(e["name"]),
                        ),
                    )
        # Anzahl je Kategorie inklusive aller Unterkategorien
        eltern = dict(con.execute("SELECT id, eltern FROM kategorien").fetchall())
        anzahl: dict[str, int] = {}
        for (kat,) in con.execute("SELECT kategorie FROM richtlinien"):
            gesehen = set()
            while kat and kat not in gesehen:
                gesehen.add(kat)
                anzahl[kat] = anzahl.get(kat, 0) + 1
                kat = eltern.get(kat)
        con.executemany("UPDATE kategorien SET anzahl = ? WHERE id = ?", [(n, k) for k, n in anzahl.items()])
        con.execute(
            "UPDATE pakete SET anzahl = (SELECT COUNT(*) FROM richtlinien r WHERE r.paket = pakete.id)"
        )
        con.commit()
        con.close()

    def _verbindung(self) -> sqlite3.Connection:
        con = sqlite3.connect(f"file:{self.datenbank}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con

    # --- Abfragen ---------------------------------------------------------------------------

    def pakete(self) -> list[dict[str, Any]]:
        with self._verbindung() as con:
            return [dict(z) for z in con.execute("SELECT * FROM pakete ORDER BY name")]

    def paket(self, pid: str) -> dict[str, Any] | None:
        with self._verbindung() as con:
            z = con.execute("SELECT * FROM pakete WHERE id = ?", (pid,)).fetchone()
            return dict(z) if z else None

    def richtlinie(self, rid: str) -> dict[str, Any] | None:
        if not isinstance(rid, str) or len(rid) > 300:
            return None
        with self._verbindung() as con:
            z = con.execute("SELECT daten FROM richtlinien WHERE id = ?", (rid,)).fetchone()
        return json.loads(z["daten"]) if z else None

    def admx_dateien(self, paket: str) -> list[str]:
        """Namen der ADMX-Dateien eines Pakets (für „Vorlagen bereitstellen“)."""
        with self._verbindung() as con:
            zeilen = con.execute(
                "SELECT DISTINCT json_extract(daten, '$.datei') FROM richtlinien WHERE paket = ? ORDER BY 1",
                (paket,),
            ).fetchall()
        return [str(z[0]) for z in zeilen if z[0]]

    def kategorien(self, eltern: str | None = None, paket: str | None = None) -> list[dict[str, Any]]:
        """Direkte Unterkategorien (``eltern`` leer = oberste Ebene, auch paketübergreifend)."""
        with self._verbindung() as con:
            if eltern:
                zeilen = con.execute(
                    "SELECT k.*, EXISTS(SELECT 1 FROM kategorien u WHERE u.eltern = k.id) AS hat_kinder "
                    "FROM kategorien k WHERE k.eltern = ? AND k.anzahl > 0 ORDER BY k.name",
                    (eltern,),
                ).fetchall()
            else:
                zeilen = con.execute(
                    "SELECT k.*, EXISTS(SELECT 1 FROM kategorien u WHERE u.eltern = k.id) AS hat_kinder "
                    "FROM kategorien k WHERE k.anzahl > 0 AND (k.eltern IS NULL OR k.eltern NOT IN "
                    "(SELECT id FROM kategorien)) AND (? IS NULL OR k.paket = ?) ORDER BY k.name",
                    (paket, paket),
                ).fetchall()
        return [dict(z) for z in zeilen]

    def suche(
        self,
        q: str = "",
        paket: str | None = None,
        klasse: str | None = None,
        kategorie: str | None = None,
        seite: int = 1,
        pro_seite: int = 25,
    ) -> dict[str, Any]:
        bedingungen, werte = [], []
        if paket:
            bedingungen.append("r.paket = ?")
            werte.append(paket)
        if klasse in ("machine", "user"):
            bedingungen.append("r.klasse IN (?, 'both')")
            werte.append(klasse)
        if kategorie:
            bedingungen.append("r.kategorie = ?")
            werte.append(kategorie)
        anfrage = _fts_anfrage(q) if q else None
        if q and anfrage is None:
            return {"treffer": [], "gesamt": 0, "seite": 1}
        quelle = "richtlinien r"
        reihenfolge = "r.titel"
        if anfrage:
            quelle = "suche s JOIN richtlinien r ON r.id = s.id"
            bedingungen.insert(0, "suche MATCH ?")
            werte.insert(0, anfrage)
            reihenfolge = "bm25(suche, 0, 10, 1, 3, 5, 5)"
        wo = ("WHERE " + " AND ".join(bedingungen)) if bedingungen else ""
        seite = max(1, seite)
        pro_seite = max(1, min(pro_seite, 100))
        with self._verbindung() as con:
            gesamt = con.execute(f"SELECT COUNT(*) FROM {quelle} {wo}", werte).fetchone()[0]  # noqa: S608
            zeilen = con.execute(
                f"SELECT r.id, r.paket, r.titel, r.klasse, r.pfad, r.schluessel, r.wertname "  # noqa: S608
                f"FROM {quelle} {wo} ORDER BY {reihenfolge} LIMIT ? OFFSET ?",
                [*werte, pro_seite, (seite - 1) * pro_seite],
            ).fetchall()
        return {"treffer": [dict(z) for z in zeilen], "gesamt": gesamt, "seite": seite}


# --- Dynamische Parameter -----------------------------------------------------------------------


def element_parameter_id(eid: str, vergeben: set[str]) -> str:
    basis = ELEMENT_PRAEFIX + (re.sub(r"[^a-z0-9_]+", "_", eid.lower()).strip("_") or "x")[:40]
    pid, n = basis, 2
    while pid in vergeben:
        pid, n = f"{basis}_{n}", n + 1
    vergeben.add(pid)
    return pid


def parameter_fuer(richtlinie: dict[str, Any]) -> list[tuple[ParameterDef, dict[str, Any]]]:
    """ADMX-Elemente → (ParameterDef, Element). Gelten nur im Zustand „aktiviert“."""
    ergebnis = []
    vergeben: set[str] = set()
    for e in richtlinie["elemente"]:
        pid = element_parameter_id(e["id"], vergeben)
        basis: dict[str, Any] = {"id": pid, "label": e.get("label") or e["id"], "pflicht": e["pflicht"]}
        art = e["art"]
        if art == "boolean":
            p = ParameterDef(
                **basis | {"typ": ParamTyp.JA_NEIN, "pflicht": False, "standard": e.get("standard", False)}
            )
        elif art in ("decimal", "longDecimal"):
            p = ParameterDef(
                **basis
                | {"typ": ParamTyp.ZAHL, "min": e["min"], "max": e["max"], "standard": e.get("standard")}
            )
        elif art == "text":
            p = ParameterDef(
                **basis | {"typ": ParamTyp.REGISTRY_TEXT, "max": None, "standard": e.get("standard")}
            )
        elif art == "enum":
            optionen = [Option(wert=str(o["nr"]), label=o["label"]) for o in e["optionen"]]
            std = e.get("standard")
            p = ParameterDef(
                **basis
                | {
                    "typ": ParamTyp.AUSWAHL,
                    "optionen": optionen,
                    "standard": str(std) if std is not None else None,
                }
            )
        elif art in ("multiText", "list"):
            hilfe = "Eine Zeile pro Eintrag"
            if art == "list" and e.get("expliziter_wert"):
                hilfe += " – Form: Name=Wert"
            p = ParameterDef(**basis | {"typ": ParamTyp.REGISTRY_ZEILEN, "hilfe": hilfe})
        else:
            continue
        ergebnis.append((p, e))
    return ergebnis


# --- Operationen ---------------------------------------------------------------------------------


def _wert_op(
    pfad: str, name: str, wert: dict[str, Any] | None, nur_wenn_fehlt: bool = False
) -> list[Operation]:
    if wert is None:
        return []
    if wert.get("loeschen"):
        return [Operation("loeschen", pfad, name)]
    return [Operation("setzen", pfad, name, wert["typ"], wert["daten"], nur_wenn_fehlt)]


def _liste_ops(liste: list[dict[str, Any]]) -> list[Operation]:
    ops: list[Operation] = []
    for item in liste:
        ops += _wert_op(item["schluessel"], item["wertname"], item["wert"])
    return ops


def _alle_werte(r: dict[str, Any]) -> list[Operation]:
    """Alles, was die Richtlinie schreiben kann – als Löschungen (nicht konfiguriert / deaktiviert)."""
    ops: list[Operation] = []
    if r["wertname"]:
        ops.append(Operation("loeschen", r["schluessel"], r["wertname"]))
    for zustand in ("aktiviert", "deaktiviert"):
        ops += [Operation("loeschen", i["schluessel"], i["wertname"]) for i in r[zustand]["liste"]]
    for e in r["elemente"]:
        if e["art"] == "list":
            ops.append(Operation("leeren", e["schluessel"]))
            continue
        if e["wertname"]:
            ops.append(Operation("loeschen", e["schluessel"], e["wertname"]))
        for teil in ("wahr", "falsch"):
            if teil in e:
                ops += [Operation("loeschen", i["schluessel"], i["wertname"]) for i in e[teil]["liste"]]
        for o in e.get("optionen", []):
            ops += [Operation("loeschen", i["schluessel"], i["wertname"]) for i in o["liste"]]
    return ops


def _eindeutig(ops: list[Operation]) -> list[Operation]:
    gesehen: set[tuple[str, str, str]] = set()
    ergebnis = []
    for op in ops:
        k = (op.art, op.pfad.lower(), op.name.lower())
        if k not in gesehen:
            gesehen.add(k)
            ergebnis.append(op)
    return ergebnis


def operationen(r: dict[str, Any], zustand: str, werte: dict[str, Any]) -> list[Operation]:
    """Zustand + geprüfte Elementwerte (Parameter-ID → Wert) → Registry-Operationen.

    ``nicht_konfiguriert``: alle Werte der Richtlinie löschen, danach leere Schlüssel entfernen.
    ``deaktiviert``: disabledValue/disabledList; Elementwerte werden gelöscht (wie der Gruppenrichtlinien-
    Editor). ``aktiviert``: enabledValue/enabledList und alle Elemente; Listen werden geleert und neu
    geschrieben (außer ``additive``).
    """
    if zustand == "nicht_konfiguriert":
        ops = _alle_werte(r)
        schluessel = sorted({op.pfad for op in ops}, key=lambda p: -p.count("\\"))
        return _eindeutig(ops + [Operation("leer_entfernen", p) for p in schluessel])
    if zustand == "deaktiviert":
        ops = _wert_op(r["schluessel"], r["wertname"], r["deaktiviert"]["wert"])
        ops += _liste_ops(r["deaktiviert"]["liste"])
        element_ops = [
            op
            for op in _alle_werte(r)
            if op.name.lower() != r["wertname"].lower() or op.pfad != r["schluessel"]
        ]
        return _eindeutig(ops + element_ops)
    ops = _wert_op(r["schluessel"], r["wertname"], r["aktiviert"]["wert"])
    ops += _liste_ops(r["aktiviert"]["liste"])
    for p, e in parameter_fuer(r):
        wert = werte.get(p.id)
        weich = bool(e.get("nur_wenn_fehlt"))
        art = e["art"]
        if art == "boolean":
            teil = e["wahr"] if wert else e["falsch"]
            ops += _wert_op(e["schluessel"], e["wertname"], teil["wert"], weich) if e["wertname"] else []
            ops += _liste_ops(teil["liste"])
        elif art in ("decimal", "longDecimal"):
            if wert is None:
                ops.append(Operation("loeschen", e["schluessel"], e["wertname"]))
            elif e.get("als_text"):
                ops.append(Operation("setzen", e["schluessel"], e["wertname"], "REG_SZ", str(wert), weich))
            else:
                typ = "REG_DWORD" if art == "decimal" else "REG_QWORD"
                ops.append(Operation("setzen", e["schluessel"], e["wertname"], typ, int(wert), weich))
        elif art == "text":
            if wert in (None, ""):
                ops.append(Operation("loeschen", e["schluessel"], e["wertname"]))
            else:
                typ = "REG_EXPAND_SZ" if e.get("erweiterbar") else "REG_SZ"
                ops.append(Operation("setzen", e["schluessel"], e["wertname"], typ, str(wert), weich))
        elif art == "multiText":
            eintraege = tuple(str(x) for x in (wert or []))
            ops.append(Operation("setzen", e["schluessel"], e["wertname"], "REG_MULTI_SZ", eintraege, weich))
        elif art == "enum":
            option = next((o for o in e["optionen"] if str(o["nr"]) == str(wert)), None)
            if option is not None:
                ops += _wert_op(e["schluessel"], e["wertname"], option["wert"], weich)
                ops += _liste_ops(option["liste"])
        elif art == "list":
            if not e.get("additiv"):
                ops.append(Operation("leeren", e["schluessel"]))
            typ = "REG_EXPAND_SZ" if e.get("erweiterbar") else "REG_SZ"
            for n, eintrag in enumerate(wert or [], 1):
                if e.get("expliziter_wert"):
                    name, _, daten = str(eintrag).partition("=")
                    ops.append(Operation("setzen", e["schluessel"], name.strip(), typ, daten.strip()))
                else:
                    ops.append(
                        Operation("setzen", e["schluessel"], f"{e.get('praefix', '')}{n}", typ, str(eintrag))
                    )
    return ops
