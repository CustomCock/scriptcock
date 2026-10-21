"""Optionaler End-to-End-Test des freien Baukastens im echten Browser (Playwright + Chromium).

Wird übersprungen, wenn Playwright nicht installiert ist. Chromium-Pfad optional über
die Umgebungsvariable ``CHROMIUM_PFAD``.
"""

from __future__ import annotations

import glob
import os
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")


def _chromium() -> str | None:
    if os.environ.get("CHROMIUM_PFAD"):
        return os.environ["CHROMIUM_PFAD"]
    treffer = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    return treffer[-1] if treffer else None


@pytest.fixture(scope="module")
def server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    import uvicorn

    from app.config import Einstellungen
    from app.db import Datenbank
    from app.main import create_app
    from app.registry import lade_registry

    db = Path(tmp_path_factory.mktemp("browser")) / "b.db"
    app = create_app(
        Einstellungen(AUTH_DISABLED=True, DEV_ADMIN=False, APP_SECRET_KEY="x" * 32),
        lade_registry(),
        Datenbank(f"sqlite:///{db}"),
    )
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch(executable_path=_chromium())
        except Exception as e:
            pytest.skip(f"Chromium nicht startbar: {e}")
        yield b
        b.close()


def test_baukasten_im_browser(server: str, browser) -> None:
    seite = browser.new_page(viewport={"width": 1280, "height": 1000})
    js_fehler: list[str] = []
    seite.on("pageerror", lambda e: js_fehler.append(str(e)))
    seite.goto(f"{server}/baukasten?ziel=bash")

    # Hinzufügen per Knopf und per Drag & Drop
    seite.click("[data-hinzufuegen=systeminfo]")
    seite.locator("#schrittliste li.schritt").first.wait_for()
    seite.locator(".palette-block[data-block=ping] .palette-name").drag_to(seite.locator("#schrittliste"))
    seite.locator("#schrittliste li.schritt").nth(1).wait_for(timeout=5000)
    seite.fill("#schrittliste li.schritt[data-block=ping] input[type=text]", "10.0.0.7")
    seite.locator("#bk-vorschau code", has_text="ping -c 4 '10.0.0.7'").wait_for(timeout=5000)

    # Umsortieren
    seite.click("#schrittliste li.schritt[data-block=ping] [data-hoch]")
    seite.locator("#bk-vorschau code", has_text="[1/2] Ping auf 10.0.0.7").wait_for(timeout=5000)

    # Zielwechsel: SetupDiag nur unter PowerShell
    assert seite.is_disabled("[data-hinzufuegen=setupdiag]")
    seite.click("label.ziel-option:has(input[value=powershell])")
    seite.locator("#bk-vorschau code", has_text="ping.exe -n 4 '10.0.0.7'").wait_for(timeout=5000)
    assert not seite.is_disabled("[data-hinzufuegen=setupdiag]")
    seite.click("[data-hinzufuegen=setupdiag]")
    seite.locator("#schrittliste li.schritt").nth(2).wait_for()
    seite.click("label.ziel-option:has(input[value=zsh])")
    seite.locator("#bk-vorschau .fehlerbox", has_text="Download gesperrt").wait_for(timeout=5000)
    assert seite.is_disabled("#bk-vorschau button.knopf-primaer")
    assert seite.locator("#schrittliste li.schritt-gesperrt[data-block=setupdiag]").count() == 1

    # Entfernen gibt den Download frei
    seite.click("#schrittliste li.schritt[data-block=setupdiag] [data-entfernen]")
    seite.locator("#bk-vorschau button.knopf-primaer:not([disabled])").wait_for(timeout=5000)
    seite.click("#bk-vorschau button.knopf-primaer")
    seite.locator("#bk-ergebnis a.knopf-primaer").wait_for(timeout=5000)
    assert seite.get_attribute("#bk-ergebnis a.knopf-primaer", "href").endswith("/download")
    assert js_fehler == []
