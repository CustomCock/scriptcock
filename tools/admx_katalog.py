#!/usr/bin/env python3
"""Erzeugt den Richtlinien-Katalog registry/katalog/<paket>.jsonl aus registry/quellen/<paket>/admx/.

    python tools/admx_holen.py        # zuerst: Vorlagen holen und entpacken
    python tools/admx_katalog.py      # dann: Katalog schreiben + Statistik

Format (JSON Lines, eine Zeile pro Eintrag, sortiert – Hersteller-Updates ergeben lesbare Diffs):
    {"art": "paket", "id": …, "name": …, "version": …, "software": …}
    {"art": "kategorie", "id": "<namespace>:<name>", "name": …, "eltern": …}
    {"art": "richtlinie", …}            (siehe app/admx.py)

Die Statistik landet zusätzlich in docs/richtlinien-katalog.md (zwischen den STATISTIK-Markern).
Die App baut daraus beim Start einen SQLite-Suchindex (app/richtlinien.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from app.admx import pakete_parsen  # noqa: E402

QUELLEN_YAML = WURZEL / "registry" / "admx-quellen.yaml"
QUELLEN = WURZEL / "registry" / "quellen"
KATALOG = WURZEL / "registry" / "katalog"
DOKU = WURZEL / "docs" / "richtlinien-katalog.md"
MARKER_START = "<!-- STATISTIK-START -->"
MARKER_ENDE = "<!-- STATISTIK-ENDE -->"


def zeile(daten: dict) -> str:
    return json.dumps(daten, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--quellen", type=Path, default=QUELLEN)
    parser.add_argument("--ziel", type=Path, default=KATALOG)
    parser.add_argument("--quellen-yaml", type=Path, default=QUELLEN_YAML)
    parser.add_argument("--keine-doku", action="store_true", help="Statistik nicht in die Doku schreiben")
    args = parser.parse_args(argv)

    meta = {p["id"]: p for p in yaml.safe_load(args.quellen_yaml.read_text(encoding="utf-8"))["pakete"]}
    ordner = {
        pid: args.quellen / pid / "admx"
        for pid in meta
        if (args.quellen / pid / "admx").is_dir() and any((args.quellen / pid / "admx").glob("*.admx"))
    }
    if not ordner:
        print("Keine Vorlagen gefunden – zuerst tools/admx_holen.py ausführen.", file=sys.stderr)
        return 1
    ergebnis, gesamt, stat = pakete_parsen(ordner)

    args.ziel.mkdir(parents=True, exist_ok=True)
    for pid, richtlinien in ergebnis.items():
        p = meta[pid]
        zeilen = [
            zeile(
                {
                    "art": "paket",
                    "id": pid,
                    "name": p["name"],
                    "version": p.get("version", ""),
                    "seite": p.get("seite", ""),
                    "software": p.get("software"),
                }
            )
        ]
        kategorien = sorted(
            (k for k in gesamt.kategorien.values() if k["paket"] == pid), key=lambda k: k["id"]
        )
        zeilen += [
            zeile({"art": "kategorie", **{k: v for k, v in kat.items() if k != "paket"}})
            for kat in kategorien
        ]
        zeilen += [zeile({"art": "richtlinie", **r}) for r in richtlinien]
        (args.ziel / f"{pid}.jsonl").write_text("\n".join(zeilen) + "\n", encoding="utf-8")

    tabelle = [
        "| Paket | Version | Richtlinien | ohne deutsche Übersetzung | ausgelassen |",
        "|---|---|---|---|---|",
    ]
    for pid in ergebnis:
        tabelle.append(
            f"| {meta[pid]['name']} | {meta[pid].get('version', '')} | {stat.richtlinien[pid]} | "
            f"{stat.ohne_deutsch[pid]} | {stat.ausgelassen[pid]} |"
        )
    fehlend = [meta[p]["name"] for p in meta if p not in ordner]
    text = "\n".join(tabelle)
    if fehlend:
        text += "\n\nNicht im Katalog (Vorlagen nicht abgelegt): " + ", ".join(fehlend) + "."
    if stat.gruende:
        text += "\n\nGründe für ausgelassene Richtlinien: " + ", ".join(
            f"{g} ({n})" for g, n in stat.gruende.most_common()
        )
    if stat.nicht_unterstuetzt:
        text += "\n\nNicht unterstützte Konstrukte (Richtlinie trotzdem im Katalog): " + ", ".join(
            f"{g} ({n})" for g, n in stat.nicht_unterstuetzt.most_common()
        )
    print(text)
    if not args.keine_doku and DOKU.exists():
        doku = DOKU.read_text(encoding="utf-8")
        if MARKER_START in doku and MARKER_ENDE in doku:
            vorne, rest = doku.split(MARKER_START, 1)
            _, hinten = rest.split(MARKER_ENDE, 1)
            DOKU.write_text(f"{vorne}{MARKER_START}\n{text}\n{MARKER_ENDE}{hinten}", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
