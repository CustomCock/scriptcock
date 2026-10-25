"""Admin-Werkzeuge und Vorlagen-Pakete für ``admin_werkzeug_bereitstellen`` (B4).

Quelle ist ``registry/admx-quellen.yaml`` (offizielle URLs + SHA-256). Für die Quelle „Intranet“ spiegelt
die App genau diese Original-Dateien (gleiche Namen, gleicher Hash) aus ``registry/quellen/<id>/download/``
unter ``GET /werkzeuge/<id>/<datei>`` – abgelegt von ``tools/admx_holen.py``. Ausgeliefert wird nur, was in
der YAML steht; ein Script verwendet nur Dateien, deren SHA-256 passt.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJEKT = Path(__file__).resolve().parent.parent
QUELLEN_YAML = PROJEKT / "registry" / "admx-quellen.yaml"
ABLAGE = PROJEKT / "registry" / "quellen"


@dataclass(frozen=True)
class Datei:
    """Eine herunterladbare Datei: offizielle URL, Pfad im Intranet-Spiegel, SHA-256."""

    url: str
    spiegel: str  # "<id>/<name>" unter /werkzeuge/
    sha256: str

    @property
    def name(self) -> str:
        return self.spiegel.split("/", 1)[1]


@lru_cache(maxsize=2)
def quellen(datei: Path = QUELLEN_YAML) -> dict[str, Any]:
    return dict(yaml.safe_load(datei.read_text(encoding="utf-8")))


def werkzeug(wid: str) -> dict[str, Any] | None:
    return next((w for w in quellen().get("werkzeuge", []) if w["id"] == wid), None)


def paket(pid: str) -> dict[str, Any] | None:
    return next((p for p in quellen().get("pakete", []) if p["id"] == pid), None)


def dateien(eintrag_id: str) -> list[Datei]:
    """Dateien eines Pakets oder Werkzeugs (leer bei ``format: manuell``)."""
    w = werkzeug(eintrag_id)
    if w is not None:
        return [Datei(w["url"], f"{eintrag_id}/{w['url'].rsplit('/', 1)[-1]}", w.get("sha256", ""))]
    p = paket(eintrag_id)
    if p is None or p.get("format") == "manuell":
        return []
    return [
        Datei(d["url"], f"{eintrag_id}/{d.get('ziel') or d['url'].rsplit('/', 1)[-1]}", d.get("sha256", ""))
        for d in p.get("dateien", [])
    ]


def gespiegelt(pfad: str, ablage: Path = ABLAGE) -> Path | None:
    """Lokale Datei für ``GET /werkzeuge/<pfad>`` – nur Einträge aus der YAML, nur aus der Ablage."""
    eintrag_id = pfad.split("/", 1)[0]
    for d in dateien(eintrag_id):
        if d.spiegel == pfad and d.sha256:
            lokal = (ablage / eintrag_id / "download" / d.name).resolve()
            if lokal.is_relative_to(ablage.resolve()) and lokal.is_file():
                return lokal
    return None
