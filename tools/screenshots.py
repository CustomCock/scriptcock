#!/usr/bin/env python3
"""Screenshots der Oberfläche in vier Breiten nach ``docs/screenshots/`` (Playwright + Chromium).

Aufruf:  python tools/screenshots.py                # alles
         python tools/screenshots.py katalog rezepte  # nur bestimmte Bereiche

Chromium-Pfad optional über ``CHROMIUM_PFAD`` (sonst Playwright-Standard bzw. /opt/pw-browsers).
"""

from __future__ import annotations

import glob
import os
import socket
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

import uvicorn  # noqa: E402
from playwright.sync_api import Page, sync_playwright  # noqa: E402

from app.config import Einstellungen  # noqa: E402
from app.db import Datenbank  # noqa: E402
from app.main import create_app  # noqa: E402

ZIEL = PROJEKT / "docs" / "screenshots"
BREITEN = [360, 768, 1280, 1920]


def _server() -> tuple[str, uvicorn.Server]:
    db = Path(tempfile.mkdtemp()) / "s.db"
    app = create_app(
        Einstellungen(AUTH_DISABLED=True, DEV_ADMIN=False, APP_SECRET_KEY="x" * 32),
        None,
        Datenbank(f"sqlite:///{db}"),
    )
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    while not srv.started:
        time.sleep(0.05)
    return f"http://127.0.0.1:{port}", srv


def katalog_seite(seite: Page, url: str) -> None:
    seite.goto(f"{url}/software")
    seite.click("[data-plattform=alle]")
    seite.click("[data-kategorie=PDF]")
    seite.fill("#katalog-suche", "pdf")
    seite.wait_for_timeout(300)


def katalog_panel(seite: Page, url: str) -> None:
    """Baukasten: Katalog in der rechten Spalte unter der Vorschau (bzw. unten auf dem Handy)."""
    seite.goto(f"{url}/baukasten?ziel=powershell")
    seite.click("[data-hinzufuegen=paket_installieren]")
    seite.locator("#software-katalog[open]").wait_for()
    seite.fill("#katalog-suche", "visual c++")
    seite.wait_for_timeout(500)
    seite.locator("#software-katalog").scroll_into_view_if_needed()


def blockly(seite: Page, url: str) -> None:
    seite.goto(f"{url}/blockly?ziel=zsh")
    seite.locator(".blocklyDraggable").first.wait_for()
    seite.click("#software-katalog > summary")
    seite.fill("#katalog-suche", "firefox")
    seite.wait_for_timeout(500)


def rezepte(seite: Page, url: str) -> None:
    seite.goto(f"{url}/rezepte?ziel=powershell")
    seite.wait_for_timeout(300)


BEREICHE: dict[str, list[tuple[str, Callable[[Page, str], None]]]] = {
    "katalog": [("katalog-seite", katalog_seite), ("katalog-panel", katalog_panel), ("katalog-blockly", blockly)],
    "rezepte": [("rezepte", rezepte)],
}


def main() -> int:
    auswahl = sys.argv[1:] or list(BEREICHE)
    ZIEL.mkdir(parents=True, exist_ok=True)
    url, srv = _server()
    chromium = os.environ.get("CHROMIUM_PFAD") or next(
        iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"), reverse=True)), None
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium)
        for bereich in auswahl:
            for name, aktion in BEREICHE[bereich]:
                for breite in BREITEN:
                    seite = browser.new_page(viewport={"width": breite, "height": 900})
                    aktion(seite, url)
                    datei = ZIEL / f"{name}-{breite}.png"
                    seite.screenshot(path=str(datei))
                    print(datei.relative_to(PROJEKT))
                    seite.close()
        browser.close()
    srv.should_exit = True
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
