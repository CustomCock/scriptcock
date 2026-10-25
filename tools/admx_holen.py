#!/usr/bin/env python3
"""Lädt die Administrativen Vorlagen (ADMX/ADML) laut registry/admx-quellen.yaml und legt sie entpackt ab.

    python tools/admx_holen.py                 # alle Pakete
    python tools/admx_holen.py edge chrome     # nur diese
    python tools/admx_holen.py --erster-download windows   # Hash fehlt noch: berechnen und anzeigen

Ablauf je Paket:
1. Download nach registry/quellen/<id>/download/ (nur wenn die Datei fehlt oder der Hash nicht passt)
2. SHA-256 prüfen – bei Abweichung Abbruch (nie still weitermachen)
3. Entpacken (msi: msiextract, exe: 7z, cab: cabextract, zip: Python; darin enthaltene .zip auch)
4. Passende .admx und .adml (de-DE, en-US) nach registry/quellen/<id>/admx/ kopieren

Pakete mit ``format: manuell`` (oder wenn der Download hier gesperrt ist): Dateien von Hand nach
registry/quellen/<id>/admx/ (*.admx, de-DE/*.adml, en-US/*.adml) legen – das Tool prüft dann nur, ob
sie da sind. registry/quellen/ ist nicht im Git (Größe, Lizenz der Hersteller).

Die Original-Dateien in registry/quellen/<id>/download/ liefert die App zugleich als Intranet-Spiegel aus
(GET /werkzeuge/<id>/<datei>, Baustein „Admin-Werkzeug bereitstellen“ mit Quelle „Intranet“).
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import yaml

WURZEL = Path(__file__).resolve().parent.parent
QUELLEN_YAML = WURZEL / "registry" / "admx-quellen.yaml"
ABLAGE = WURZEL / "registry" / "quellen"
MAX_GROESSE = 500 * 1024 * 1024  # Schutz gegen unerwartet große Downloads


class Abbruch(Exception):
    pass


def sha256(datei: Path) -> str:
    h = hashlib.sha256()
    with datei.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def herunterladen(url: str, ziel: Path) -> None:
    if not url.startswith("https://"):
        raise Abbruch(f"Nur https-Downloads: {url}")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    teil = ziel.with_suffix(ziel.suffix + ".teil")
    teile = urllib.parse.urlsplit(url)
    url = urllib.parse.urlunsplit(teile._replace(path=urllib.parse.quote(teile.path)))
    anfrage = urllib.request.Request(url, headers={"User-Agent": "okm-script-baukasten/admx_holen"})  # noqa: S310
    with urllib.request.urlopen(anfrage, timeout=120) as antwort, teil.open("wb") as aus:  # noqa: S310
        gelesen = 0
        while block := antwort.read(1 << 20):
            gelesen += len(block)
            if gelesen > MAX_GROESSE:
                raise Abbruch(f"Download größer als {MAX_GROESSE // 2**20} MB: {url}")
            aus.write(block)
    teil.replace(ziel)


def werkzeug(name: str) -> str:
    pfad = shutil.which(name)
    if pfad is None:
        raise Abbruch(f"Werkzeug „{name}“ fehlt (Debian/Ubuntu: apt install msitools 7zip cabextract)")
    return pfad


def ausfuehren(befehl: list[str]) -> None:
    r = subprocess.run(befehl, capture_output=True, text=True)
    if r.returncode != 0:
        raise Abbruch(f"{befehl[0]} ist fehlgeschlagen: {r.stderr.strip()[:500]}")


def sicher_entpacken_zip(datei: Path, ziel: Path) -> None:
    with zipfile.ZipFile(datei) as z:
        for eintrag in z.infolist():
            pfad = (ziel / eintrag.filename).resolve()
            if not pfad.is_relative_to(ziel.resolve()):
                raise Abbruch(f"Unsicherer Pfad im Archiv: {eintrag.filename}")
        z.extractall(ziel)


def entpacken(datei: Path, format_: str, ziel: Path) -> None:
    if ziel.exists():
        shutil.rmtree(ziel)
    ziel.mkdir(parents=True)
    if format_ == "msi":
        ausfuehren([werkzeug("msiextract"), "-C", str(ziel), str(datei)])
    elif format_ == "exe":
        ausfuehren([werkzeug("7z"), "x", "-y", f"-o{ziel}", str(datei)])
    elif format_ == "office":
        # Office-Installer: eingebettetes CAB mit flachen Namen (office16.adml, office16.adml0 … je Sprache)
        ausfuehren([werkzeug("cabextract"), "-q", "-d", str(ziel), str(datei)])
        office_sprachen_ordnen(ziel)
    elif format_ == "cab":
        ausfuehren([werkzeug("cabextract"), "-q", "-d", str(ziel), str(datei)])
    elif format_ == "zip":
        sicher_entpacken_zip(datei, ziel)
    else:
        raise Abbruch(f"Unbekanntes Format: {format_}")
    # Archive im Archiv (Edge: .cab → .zip) eine Ebene tiefer entpacken
    for inneres in list(ziel.rglob("*.zip")):
        sicher_entpacken_zip(inneres, inneres.parent / (inneres.stem + "_zip"))


def _lesen(datei: Path) -> str:
    roh = datei.read_bytes()
    for kodierung in ("utf-16", "utf-8-sig"):
        try:
            return roh.decode(kodierung)
        except UnicodeDecodeError:
            continue
    return roh.decode("latin-1")


def _anteil(text: str, woerter: tuple[str, ...]) -> float:
    return sum(text.count(w) for w in woerter) / max(len(text), 1)


DEUTSCH = (" und ", " der ", " die ", "Einstellung", " nicht ")
ENGLISCH = (" the ", " and ", " is ", " this ", "setting")


def office_sprachen_ordnen(ordner: Path) -> None:
    """Ordnet flache ADML-Varianten (name.adml, name.adml0 …) nach ihrem Inhalt de-DE/en-US zu.

    Die Zuordnung Endung → Sprache steht nur im Installer und kann sich ändern; der Inhalt nicht.
    """
    varianten: dict[str, list[Path]] = {}
    for datei in ordner.iterdir():
        name = datei.name.lower()
        if ".adml" in name:
            varianten.setdefault(name.split(".adml")[0], []).append(datei)
    for unter in ("admx", "admx/de-de", "admx/en-us"):
        (ordner / unter).mkdir(parents=True, exist_ok=True)
    for admx in ordner.glob("*.admx"):
        shutil.copy2(admx, ordner / "admx" / admx.name.lower())
    for stamm, dateien in varianten.items():
        texte = {d: _lesen(d) for d in dateien}
        de = max(dateien, key=lambda d: _anteil(texte[d], DEUTSCH) - _anteil(texte[d], ENGLISCH))
        en = max(dateien, key=lambda d: _anteil(texte[d], ENGLISCH) - _anteil(texte[d], DEUTSCH))
        if _anteil(texte[de], DEUTSCH) > _anteil(texte[de], ENGLISCH):
            shutil.copy2(de, ordner / "admx" / "de-de" / f"{stamm}.adml")
        if en != de:
            shutil.copy2(en, ordner / "admx" / "en-us" / f"{stamm}.adml")


def finden(basis: Path, muster: str) -> list[Path]:
    """Glob ohne Groß-/Kleinschreibung auf Pfade relativ zu ``basis``."""
    muster = muster.lower()
    treffer = []
    for pfad in basis.rglob("*"):
        if pfad.is_file():
            rel = pfad.relative_to(basis).as_posix().lower()
            if fnmatch.fnmatch(rel, muster) or (
                muster.startswith("**/") and fnmatch.fnmatch(rel, muster[3:])
            ):
                treffer.append(pfad)
    return sorted(treffer)


def ablegen(paket: dict, quelle: Path) -> tuple[int, int, int]:
    """Kopiert ADMX/ADML in die einheitliche Ablage registry/quellen/<id>/admx/{,de-DE,en-US}."""
    ziel = ABLAGE / paket["id"] / "admx"
    if ziel.exists():
        shutil.rmtree(ziel)
    anzahl = []
    for schluessel, unter in (("admx", ""), ("adml_de", "de-DE"), ("adml_en", "en-US")):
        dateien = finden(quelle, paket[schluessel])
        (ziel / unter).mkdir(parents=True, exist_ok=True)
        for d in dateien:
            shutil.copy2(d, ziel / unter / d.name)
        anzahl.append(len(dateien))
    return anzahl[0], anzahl[1], anzahl[2]


def hash_pruefen(datei: Path, erwartet: str, erster: bool, url: str) -> None:
    ist = sha256(datei)
    if not erwartet:
        if not erster:
            raise Abbruch(
                f"Für {url} ist kein SHA-256 eingetragen. Erst prüfen, dann mit --erster-download laden "
                f"und den angezeigten Hash in registry/admx-quellen.yaml eintragen."
            )
        print(f"    SHA-256 (bitte eintragen): {ist}")
    elif ist != erwartet.lower():
        raise Abbruch(f"SHA-256 passt nicht für {url}\n    erwartet {erwartet}\n    erhalten {ist}")


def paket_holen(paket: dict, erster: bool) -> None:
    print(f"== {paket['id']}: {paket['name']} {paket.get('version', '')}")
    if paket["format"] == "manuell":
        ziel = ABLAGE / paket["id"] / "admx"
        n = len(finden(ziel, "*.admx")) if ziel.exists() else 0
        if n:
            print(f"    manuell abgelegt: {n} ADMX-Dateien")
        else:
            print(f"    MANUELL: Dateien nach {ziel.relative_to(WURZEL)}/ legen (*.admx, de-DE/, en-US/)")
            print(f"    Quelle: {paket['seite']}")
            if paket.get("hinweis"):
                print(f"    Hinweis: {paket['hinweis']}")
        return
    download = ABLAGE / paket["id"] / "download"
    for eintrag in paket["dateien"]:
        url = eintrag["url"]
        name = eintrag.get("ziel") or url.rsplit("/", 1)[-1]
        datei = download / name
        if not datei.exists() or (eintrag.get("sha256") and sha256(datei) != eintrag["sha256"].lower()):
            print(f"    lade {url}")
            herunterladen(url, datei)
        hash_pruefen(datei, eintrag.get("sha256", ""), erster, url)
    if paket["format"] == "dateien":
        quelle = download
    else:
        quelle = ABLAGE / paket["id"] / "entpackt"
        erste = download / (paket["dateien"][0].get("ziel") or paket["dateien"][0]["url"].rsplit("/", 1)[-1])
        entpacken(erste, paket["format"], quelle)
    admx, de, en = ablegen(paket, quelle)
    print(f"    {admx} ADMX, {de} ADML de-DE, {en} ADML en-US")
    if admx == 0:
        raise Abbruch(f"Keine ADMX-Dateien gefunden (Muster {paket['admx']}) – Paketaufbau geändert?")


def werkzeug_holen(w: dict, erster: bool) -> None:
    """Werkzeug (z. B. LGPO.zip) für den Intranet-Spiegel laden und prüfen."""
    print(f"== {w['id']}: {w['name']} {w.get('version', '')}")
    datei = ABLAGE / w["id"] / "download" / w["url"].rsplit("/", 1)[-1]
    if not datei.exists() or (w.get("sha256") and sha256(datei) != w["sha256"].lower()):
        print(f"    lade {w['url']}")
        herunterladen(w["url"], datei)
    hash_pruefen(datei, w.get("sha256", ""), erster, w["url"])
    print(f"    bereit: {datei.relative_to(WURZEL)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("pakete", nargs="*", help="Paket-IDs (leer = alle)")
    parser.add_argument(
        "--erster-download", action="store_true", help="fehlende Hashes berechnen und anzeigen"
    )
    args = parser.parse_args(argv)
    daten = yaml.safe_load(QUELLEN_YAML.read_text(encoding="utf-8"))
    pakete = [p for p in daten["pakete"] if not args.pakete or p["id"] in args.pakete]
    fehler = 0
    for paket in pakete:
        try:
            paket_holen(paket, args.erster_download)
        except (Abbruch, OSError, ValueError) as e:
            fehler += 1
            print(f"    FEHLER: {e}", file=sys.stderr)
    for w in daten.get("werkzeuge", []):
        if args.pakete and w["id"] not in args.pakete:
            continue
        try:
            werkzeug_holen(w, args.erster_download)
        except (Abbruch, OSError, ValueError) as e:
            fehler += 1
            print(f"    FEHLER: {e}", file=sys.stderr)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
