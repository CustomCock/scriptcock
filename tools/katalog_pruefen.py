#!/usr/bin/env python3
"""Prüft alle Paket-IDs des Software-Katalogs gegen die offiziellen Quellen.

Braucht Netz und ``git`` – läuft daher NICHT im normalen CI, sondern per Hand oder monatlich
(.github/workflows/katalog-pruefen.yml legt bei Fehlern ein Issue an).

Quellen:
  winget   github.com/microsoft/winget-pkgs (blobless Clone, nur Verzeichnisbaum)
  brew     github.com/Homebrew/homebrew-core (Formeln) + homebrew-cask (Casks)
  apt      Packages-Index von Ubuntu 24.04 LTS (main+universe) und Debian Stable (main)
  flatpak  Flathub-API, ersatzweise die Repositories unter github.com/flathub

Aufruf:
  python tools/katalog_pruefen.py                    # alles prüfen
  python tools/katalog_pruefen.py --nur winget,brew  # nur bestimmte Quellen
  python tools/katalog_pruefen.py --aktualisieren    # bei Erfolg geprueft_am auf heute setzen
  python tools/katalog_pruefen.py --bericht b.md     # Ergebnis zusätzlich als Markdown

Exit-Code: 0 = alles gültig, 1 = ungültige IDs gefunden, 2 = Quelle nicht erreichbar.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import gzip
import json
import lzma
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.katalog import KATALOG_DATEI, lade_katalog

UBUNTU = "http://archive.ubuntu.com/ubuntu/dists/noble/{bereich}/binary-amd64/Packages"
UBUNTU_BEREICHE = ("main", "universe")
DEBIAN = "https://deb.debian.org/debian/dists/stable/main/binary-amd64/Packages"
FLATHUB_API = "https://flathub.org/api/v2/appstream"
FLATHUB_GITHUB = "https://api.github.com/orgs/flathub/repos?per_page=100&page={seite}"


# Nur der Verzeichnisbaum des neuesten Commits, keine Dateiinhalte
GIT_CLONE = ["git", "clone", "--quiet", "--depth", "1", "--filter=blob:none", "--no-checkout"]


class QuelleNichtErreichbar(Exception):
    pass


@dataclass
class Ergebnis:
    fehler: list[str] = field(default_factory=list)  # ungültige IDs
    warnungen: list[str] = field(default_factory=list)  # z. B. apt nur unter Ubuntu


def laden(url: str, kopf: dict[str, str] | None = None) -> bytes:
    # Nur die festen http(s)-Quellen oben – keine file:- oder sonstigen Schemata
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"unerwartete URL: {url}")
    anfrage = urllib.request.Request(  # noqa: S310 – Schema oben geprüft
        url, headers={"User-Agent": "okm-katalog-pruefen", **(kopf or {})}
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=120) as antwort:  # noqa: S310
            daten: bytes = antwort.read()
            return daten
    except OSError as e:
        raise QuelleNichtErreichbar(f"{url}: {e}") from None


def git_baum(repo: str, ziel: Path) -> list[str]:
    """Alle Dateipfade des Default-Branches – ohne Dateiinhalte herunterzuladen."""
    if not (ziel / ".git").exists():
        r = subprocess.run(
            [*GIT_CLONE, repo, str(ziel)],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            raise QuelleNichtErreichbar(f"{repo}: {r.stderr.strip()}")
    else:
        subprocess.run(["git", "-C", str(ziel), "fetch", "--quiet", "--depth", "1"], check=False)
        subprocess.run(["git", "-C", str(ziel), "reset", "--quiet", "--soft", "FETCH_HEAD"], check=False)
    r = subprocess.run(
        ["git", "-C", str(ziel), "ls-tree", "-r", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout.splitlines()


def git_datei(ziel: Path, pfad: str) -> str:
    r = subprocess.run(["git", "-C", str(ziel), "show", f"HEAD:{pfad}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


# --- Quellen -------------------------------------------------------------------------


def winget_ids(cache: Path) -> set[str]:
    ids = set()
    for pfad in git_baum("https://github.com/microsoft/winget-pkgs.git", cache / "winget-pkgs"):
        if not pfad.startswith("manifests/"):
            continue
        name = pfad.rsplit("/", 1)[-1]
        if name.endswith(".installer.yaml"):
            ids.add(name.removesuffix(".installer.yaml").lower())
    return ids


def brew_ids(cache: Path) -> tuple[set[str], set[str], dict[str, str]]:
    formeln = set()
    core = cache / "homebrew-core"
    for pfad in git_baum("https://github.com/Homebrew/homebrew-core.git", core):
        if pfad.startswith("Formula/") and pfad.endswith(".rb"):
            formeln.add(pfad.rsplit("/", 1)[-1].removesuffix(".rb"))
        elif pfad.startswith("Aliases/"):
            formeln.add(pfad.rsplit("/", 1)[-1])
    casks = set()
    cask = cache / "homebrew-cask"
    for pfad in git_baum("https://github.com/Homebrew/homebrew-cask.git", cask):
        if pfad.startswith("Casks/") and pfad.endswith(".rb"):
            casks.add(pfad.rsplit("/", 1)[-1].removesuffix(".rb"))
    umbenannt: dict[str, str] = {}
    for repo, datei in ((core, "formula_renames.json"), (cask, "cask_renames.json")):
        try:
            umbenannt.update(json.loads(git_datei(repo, datei) or "{}"))
        except json.JSONDecodeError:
            pass
    return formeln, casks, umbenannt


def _packages(url: str) -> set[str]:
    try:
        roh = lzma.decompress(laden(url + ".xz"))
    except QuelleNichtErreichbar:
        roh = gzip.decompress(laden(url + ".gz"))
    return set(re.findall(r"^Package: (\S+)$", roh.decode("utf-8", "replace"), re.M))


def apt_ids() -> tuple[set[str], set[str]]:
    ubuntu: set[str] = set()
    for bereich in UBUNTU_BEREICHE:
        ubuntu |= _packages(UBUNTU.format(bereich=bereich))
    return ubuntu, _packages(DEBIAN)


def flatpak_ids() -> set[str]:
    try:
        daten = json.loads(laden(FLATHUB_API))
        ids = {d if isinstance(d, str) else d.get("id", "") for d in daten}
        if ids:
            return ids
    except (QuelleNichtErreichbar, json.JSONDecodeError):
        pass
    kopf = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"} if os.environ.get("GITHUB_TOKEN") else {}
    ids = set()
    for seite in range(1, 200):
        repos = json.loads(laden(FLATHUB_GITHUB.format(seite=seite), kopf))
        if not repos:
            break
        ids |= {r["name"] for r in repos}
    return ids


def flathub_eol(app_id: str) -> str:
    """Die App-Liste enthält keine abgekündigten Apps – deren Detailseite gibt es aber noch."""
    try:
        daten = json.loads(laden(f"{FLATHUB_API}/{app_id}"))
    except (QuelleNichtErreichbar, json.JSONDecodeError):
        return ""
    if isinstance(daten, dict) and daten.get("is_eol"):
        return " – auf Flathub als veraltet (EOL) markiert"
    return ""


# --- Prüfung -------------------------------------------------------------------------


def vorschlag(pid: str, kandidaten: Iterable[str]) -> str:
    klein = pid.lower()
    # Vorauswahl nach Anfangsbuchstabe hält die Suche in den ~400 000 winget-IDs schnell
    pool = [k for k in kandidaten if k[:1].lower() == klein[:1]]
    treffer = difflib.get_close_matches(klein, pool, n=3, cutoff=0.7)
    return f" – ähnlich: {', '.join(treffer)}" if treffer else ""


def pruefen(quellen: set[str], cache: Path) -> Ergebnis:
    katalog = lade_katalog()
    erg = Ergebnis()

    def fehlt(feld: str, name: str, pid: str, kandidaten: Iterable[str], extra: str = "") -> None:
        erg.fehler.append(f"{feld:<9} {pid!r:<40} ({name}){extra or vorschlag(pid, kandidaten)}")

    if "winget" in quellen:
        print("winget: lade Verzeichnisbaum von microsoft/winget-pkgs …", file=sys.stderr)
        ids = winget_ids(cache)
        for p in katalog.pakete:
            if p.winget and p.winget.lower() not in ids:
                fehlt("winget", p.name, p.winget, ids)
    if "brew" in quellen:
        print("brew: lade homebrew-core und homebrew-cask …", file=sys.stderr)
        formeln, casks, umbenannt = brew_ids(cache)
        for p in katalog.pakete:
            for feld, vorhanden in (("brew", formeln), ("brew_cask", casks)):
                pid = getattr(p, feld)
                if pid and pid not in vorhanden:
                    neu = umbenannt.get(pid)
                    fehlt(feld, p.name, pid, vorhanden, f" – umbenannt in {neu}" if neu else "")
    if "apt" in quellen:
        print("apt: lade Packages-Index von Ubuntu 24.04 und Debian Stable …", file=sys.stderr)
        ubuntu, debian = apt_ids()
        for p in katalog.pakete:
            if not p.apt:
                continue
            if p.apt not in ubuntu:
                fehlt("apt", p.name, p.apt, ubuntu)
            elif p.apt not in debian and not p.hinweis:
                erg.warnungen.append(
                    f"apt       {p.apt!r:<40} ({p.name}) – nicht in Debian Stable (hinweis ergänzen?)"
                )
    if "flatpak" in quellen:
        print("flatpak: lade App-Liste von Flathub …", file=sys.stderr)
        ids = flatpak_ids()
        klein = {i.lower() for i in ids}
        for p in katalog.pakete:
            if p.flatpak and p.flatpak.lower() not in klein:
                fehlt("flatpak", p.name, p.flatpak, ids, flathub_eol(p.flatpak))
    return erg


def datum_setzen(datei: Path, datum: dt.date) -> None:
    text = datei.read_text(encoding="utf-8")
    zeile = f'geprueft_am: "{datum.isoformat()}"'
    neu, anzahl = re.subn(r'^geprueft_am: ".*"$', zeile, text, count=1, flags=re.M)
    if anzahl != 1:
        raise SystemExit(f"{datei}: Zeile geprueft_am nicht gefunden")
    datei.write_text(neu, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--nur", default="winget,brew,apt,flatpak", help="Kommagetrennte Quellen")
    parser.add_argument("--cache", type=Path, help="Ordner für die Git-Clones (wird wiederverwendet)")
    parser.add_argument(
        "--aktualisieren", action="store_true", help="bei Erfolg geprueft_am auf heute setzen"
    )
    parser.add_argument("--bericht", type=Path, help="Ergebnis zusätzlich als Markdown-Datei schreiben")
    args = parser.parse_args()
    quellen = {q.strip() for q in args.nur.split(",") if q.strip()}
    unbekannt = quellen - {"winget", "brew", "apt", "flatpak"}
    if unbekannt:
        parser.error(f"unbekannte Quelle(n): {', '.join(sorted(unbekannt))}")

    with tempfile.TemporaryDirectory(prefix="okm-katalog-") as tmp:
        cache = args.cache or Path(tmp)
        cache.mkdir(parents=True, exist_ok=True)
        try:
            erg = pruefen(quellen, cache)
        except QuelleNichtErreichbar as e:
            print(f"Quelle nicht erreichbar: {e}", file=sys.stderr)
            return 2

    zeilen = [f"Software-Katalog geprüft ({', '.join(sorted(quellen))}), {dt.date.today():%d.%m.%Y}", ""]
    if erg.fehler:
        zeilen += [f"{len(erg.fehler)} ungültige ID(s):", "", *(f"- {f}" for f in erg.fehler), ""]
    else:
        zeilen += ["Alle IDs gültig.", ""]
    if erg.warnungen:
        zeilen += [f"{len(erg.warnungen)} Hinweis(e):", "", *(f"- {w}" for w in erg.warnungen), ""]
    text = "\n".join(zeilen)
    print(text)
    if args.bericht:
        args.bericht.write_text("```\n" + text + "```\n", encoding="utf-8")
    if erg.fehler:
        return 1
    if args.aktualisieren and quellen == {"winget", "brew", "apt", "flatpak"}:
        datum_setzen(KATALOG_DATEI, dt.date.today())
        print(f"geprueft_am in {KATALOG_DATEI.name} auf heute gesetzt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
