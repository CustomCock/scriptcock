#!/usr/bin/env python3
"""Prüft, ob es neuere Administrative Vorlagen (ADMX) oder Werkzeuge gibt als in registry/admx-quellen.yaml.

    python tools/admx_pruefen.py                      # Bericht auf der Konsole
    python tools/admx_pruefen.py --bericht bericht.md # zusätzlich als Markdown (für das Issue)
    python tools/admx_pruefen.py --ohne-hash          # keine Dateien herunterladen

Braucht Netz. Monatlich per .github/workflows/admx-pruefen.yml; Exit-Code 1, wenn etwas zu tun ist
(neue Version, geänderte Datei, Quelle nicht erreichbar) – der Workflow legt dann ein Issue an.

Je Paket/Werkzeug sagt ``aktualitaet`` in registry/admx-quellen.yaml, wie geprüft wird:

    ms_download     offizielle Microsoft-Downloadseite (``seite``): stehen unsere URLs noch darauf,
                    und nennt die Seite noch die Version ``seitenversion`` (falls eingetragen)?
    edge_api        offizielle Produktliste https://edgeupdates.microsoft.com/api/products?view=enterprise
                    (Produkt „Policy“): Version und SHA-256 der CAB-Datei
    github_release  neuestes Release auf GitHub (``repo``) gegenüber ``version``
    hash            nur SHA-256 der eingetragenen Datei (für „immer aktuelle“ URLs wie Chrome)
    manuell         nichts automatisch – erscheint im Bericht als „von Hand prüfen“

Zusätzlich (außer mit ``--ohne-hash``) wird jede eingetragene Datei geladen und ihr SHA-256 verglichen:
Ein Hersteller, der unter derselben URL eine andere Datei ausliefert, fällt so auf, bevor
tools/admx_holen.py oder ein erzeugtes Script daran scheitert. Es wird nichts geändert – Aktualisieren
bleibt Handarbeit nach docs/richtlinien-katalog.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

WURZEL = Path(__file__).resolve().parent.parent
QUELLEN_YAML = WURZEL / "registry" / "admx-quellen.yaml"
EDGE_API = "https://edgeupdates.microsoft.com/api/products?view=enterprise"
MAX_GROESSE = 500 * 1024 * 1024
AGENT = "okm-script-baukasten/admx_pruefen"

Abrufen = Callable[[str], str]
Hashen = Callable[[str], str]


@dataclass
class Befund:
    eintrag: str
    art: str  # neu | geaendert | fehler | hand | ok
    text: str


@dataclass
class Bericht:
    befunde: list[Befund] = field(default_factory=list)

    def add(self, eintrag: str, art: str, text: str) -> None:
        self.befunde.append(Befund(eintrag, art, text))

    @property
    def zu_tun(self) -> list[Befund]:
        return [b for b in self.befunde if b.art in ("neu", "geaendert", "fehler")]

    def markdown(self) -> str:
        titel = {
            "neu": "Neuere Version verfügbar",
            "geaendert": "Datei unter gleicher URL geändert (SHA-256)",
            "fehler": "Quelle nicht erreichbar / Seite verändert",
            "hand": "Von Hand prüfen (kein automatischer Abgleich)",
            "ok": "Aktuell",
        }
        zeilen = ["# Administrative Vorlagen: Prüfung", ""]
        for art in ("neu", "geaendert", "fehler", "hand", "ok"):
            teil = [b for b in self.befunde if b.art == art]
            if not teil:
                continue
            zeilen += [f"## {titel[art]}", ""]
            zeilen += [f"- **{b.eintrag}**: {b.text}" for b in teil]
            zeilen.append("")
        if self.zu_tun:
            zeilen += [
                "Vorgehen: Herstellerseite prüfen, `version`/`url`/`sha256` in",
                "`registry/admx-quellen.yaml` anpassen, `python tools/admx_holen.py <id>` und",
                "`python tools/admx_katalog.py` laufen lassen, Katalog-Diff ansehen und committen",
                "(siehe `docs/richtlinien-katalog.md`).",
                "",
            ]
        return "\n".join(zeilen)


# --- Netz ------------------------------------------------------------------------------------------
def _url(url: str) -> str:
    if not url.startswith("https://"):
        raise ValueError(f"Nur https: {url}")
    teile = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(teile._replace(path=urllib.parse.quote(teile.path)))


def abrufen(url: str) -> str:
    kopf = {"User-Agent": AGENT}
    if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
        kopf["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    anfrage = urllib.request.Request(_url(url), headers=kopf)  # noqa: S310
    with urllib.request.urlopen(anfrage, timeout=60) as antwort:  # noqa: S310
        return str(antwort.read(20 * 1024 * 1024).decode("utf-8", errors="replace"))


def hash_von_url(url: str) -> str:
    h = hashlib.sha256()
    anfrage = urllib.request.Request(_url(url), headers={"User-Agent": AGENT})  # noqa: S310
    with urllib.request.urlopen(anfrage, timeout=300) as antwort:  # noqa: S310
        gelesen = 0
        while block := antwort.read(1 << 20):
            gelesen += len(block)
            if gelesen > MAX_GROESSE:
                raise ValueError(f"Download größer als {MAX_GROESSE // 2**20} MB")
            h.update(block)
    return h.hexdigest()


# --- Prüfungen -------------------------------------------------------------------------------------
def _version_tupel(v: str) -> tuple[int, ...]:
    return tuple(int(t) for t in re.findall(r"\d+", v))


def _dateien(e: dict[str, Any]) -> list[dict[str, Any]]:
    if "url" in e:  # Werkzeug
        return [{"url": e["url"], "sha256": e.get("sha256", "")}]
    return list(e.get("dateien") or [])


def pruefe_ms_download(e: dict[str, Any], bericht: Bericht, holen: Abrufen) -> None:
    seite = holen(e["seite"])
    urls = {
        urllib.parse.unquote(u.replace("\\u0026", "&")) for u in re.findall(r'"url":"(https://[^"]+)"', seite)
    }
    if not urls:
        bericht.add(
            e["id"], "fehler", f"Keine Download-Links auf {e['seite']} gefunden – Seitenaufbau geändert?"
        )
        return
    fehlt = [d["url"] for d in _dateien(e) if urllib.parse.unquote(d["url"]) not in urls]
    if fehlt:
        bericht.add(e["id"], "neu", f"Eingetragene Datei nicht mehr auf {e['seite']}: {', '.join(fehlt)}")
        return
    treffer = re.search(r'"detailsSection_file_version":"([^"]+)"', seite)
    erwartet = str(e.get("seitenversion", ""))
    if erwartet and (not treffer or treffer.group(1) != erwartet):
        jetzt = treffer.group(1) if treffer else "(keine)"
        bericht.add(e["id"], "neu", f"Seite nennt Version {jetzt}, eingetragen ist {erwartet} ({e['seite']})")
        return
    bericht.add(e["id"], "ok", f"Datei noch auf der Downloadseite (Version {e.get('version', '')})")


def pruefe_edge_api(e: dict[str, Any], bericht: Bericht, holen: Abrufen) -> None:
    produkte = json.loads(holen(EDGE_API))
    policy = next((p for p in produkte if p.get("Product") == "Policy"), None)
    if not policy or not policy.get("Releases"):
        bericht.add(e["id"], "fehler", "Produkt „Policy“ fehlt in der Edge-Produktliste")
        return
    neu = max(policy["Releases"], key=lambda r: _version_tupel(r.get("ProductVersion", "0")))
    cab = next((a for a in neu.get("Artifacts", []) if a.get("ArtifactName") == "cab"), {})
    if _version_tupel(neu["ProductVersion"]) > _version_tupel(str(e.get("version", "0"))):
        bericht.add(
            e["id"],
            "neu",
            f"Version {neu['ProductVersion']} (eingetragen {e.get('version')}), "
            f"URL {cab.get('Location', '?')}, SHA-256 {str(cab.get('Hash', '?')).lower()}",
        )
    else:
        bericht.add(e["id"], "ok", f"Version {e.get('version')} ist die neueste")


def pruefe_github_release(e: dict[str, Any], bericht: Bericht, holen: Abrufen) -> None:
    daten = json.loads(holen(f"https://api.github.com/repos/{e['repo']}/releases/latest"))
    tag = str(daten.get("tag_name", ""))
    if _version_tupel(tag) > _version_tupel(str(e.get("version", "0"))):
        bericht.add(
            e["id"], "neu", f"Release {tag} (eingetragen {e.get('version')}): {daten.get('html_url', '')}"
        )
    else:
        bericht.add(e["id"], "ok", f"Release {tag} ist eingetragen")


PRUEFUNGEN: dict[str, Callable[[dict[str, Any], Bericht, Abrufen], None]] = {
    "ms_download": pruefe_ms_download,
    "edge_api": pruefe_edge_api,
    "github_release": pruefe_github_release,
}


def pruefe_hashes(e: dict[str, Any], bericht: Bericht, hashen: Hashen) -> bool:
    """True, wenn alle Dateien den eingetragenen SHA-256 haben."""
    alles_gleich = True
    for d in _dateien(e):
        erwartet = str(d.get("sha256", "")).lower()
        ist = hashen(d["url"])
        if ist != erwartet:
            alles_gleich = False
            bericht.add(
                e["id"], "geaendert", f"{d['url']}: erwartet {erwartet or '(kein Hash)'}, jetzt {ist}"
            )
    return alles_gleich


def pruefen(
    quellen: dict[str, Any],
    holen: Abrufen = abrufen,
    hashen: Hashen | None = hash_von_url,
    nur: set[str] | None = None,
) -> Bericht:
    bericht = Bericht()
    for e in list(quellen.get("pakete", [])) + list(quellen.get("werkzeuge", [])):
        if nur and e["id"] not in nur:
            continue
        art = e.get("aktualitaet", "manuell")
        try:
            if art == "manuell" or e.get("format") == "manuell":
                bericht.add(e["id"], "hand", f"{e.get('name', '')}: {e.get('seite', '')}")
                continue
            if art in PRUEFUNGEN:
                PRUEFUNGEN[art](e, bericht, holen)
            elif art != "hash":
                bericht.add(e["id"], "fehler", f"Unbekannte Prüfart „{art}“ in admx-quellen.yaml")
                continue
            if hashen is not None:
                gleich = pruefe_hashes(e, bericht, hashen)
                if art == "hash" and gleich:
                    bericht.add(e["id"], "ok", "SHA-256 unverändert")
            elif art == "hash":
                bericht.add(e["id"], "hand", "nur per SHA-256 prüfbar (ohne --ohne-hash laufen lassen)")
        except Exception as fehler:  # jede Quelle einzeln melden, nicht abbrechen
            bericht.add(e["id"], "fehler", f"{type(fehler).__name__}: {fehler}")
    return bericht


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("ids", nargs="*", help="nur diese Pakete/Werkzeuge")
    parser.add_argument("--bericht", type=Path, help="Markdown-Bericht hierhin schreiben")
    parser.add_argument("--ohne-hash", action="store_true", help="Dateien nicht laden und hashen")
    args = parser.parse_args(argv)
    quellen = yaml.safe_load(QUELLEN_YAML.read_text(encoding="utf-8"))
    bericht = pruefen(quellen, hashen=None if args.ohne_hash else hash_von_url, nur=set(args.ids) or None)
    text = bericht.markdown()
    print(text)
    if args.bericht:
        args.bericht.write_text(text, encoding="utf-8")
    return 1 if bericht.zu_tun else 0


if __name__ == "__main__":
    sys.exit(main())
