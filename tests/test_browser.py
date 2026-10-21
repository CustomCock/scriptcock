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


def test_blockly_im_browser(server: str, browser) -> None:
    """Drag & Drop aus der Toolbox, Fehler am Baustein, Wiederöffnen mit Ablauf-Bausteinen."""
    import json
    import urllib.request

    seite = browser.new_page(viewport={"width": 1280, "height": 1100})
    js_fehler: list[str] = []
    seite.on("pageerror", lambda e: js_fehler.append(str(e)))
    seite.goto(f"{server}/blockly?ziel=bash")
    seite.locator(".blocklyDraggable", has_text="Script").first.wait_for()

    def ziehen(quelle, x: float, y: float) -> None:
        box = quelle.bounding_box()
        seite.mouse.move(box["x"] + 12, box["y"] + 8)
        seite.mouse.down()
        seite.mouse.move(box["x"] + 60, box["y"] + 40, steps=5)
        seite.mouse.move(x, y, steps=15)
        seite.mouse.up()

    start = seite.locator(".blocklyDraggable", has_text="Script").first.bounding_box()
    seite.click(".blocklyToolboxCategory:has-text('Allgemein'), .blocklyTreeRow:has-text('Allgemein')")
    ziehen(
        seite.locator(".blocklyFlyout .blocklyDraggable", has_text="Meldung").first,
        start["x"] + 30,
        start["y"] + start["height"] - 5,
    )
    # Leeres Pflichtfeld → Fehler vom Server, Download gesperrt
    seite.locator("#bl-fehler", has_text="Text der Meldung").wait_for(timeout=5000)
    assert seite.is_disabled("#bl-erzeugen")
    assert seite.locator(".blocklyIconGroup").count() >= 1  # Warnsymbol am Baustein

    # Wiederöffnen eines gespeicherten Scripts mit Ablauf-Bausteinen
    kontext = seite.context
    cookies = "; ".join(f"{c['name']}={c['value']}" for c in kontext.cookies())
    anfrage = urllib.request.Request(
        f"{server}/api/v1/skripte",
        data=json.dumps(
            {
                "ziel": "bash",
                "titel": "Aus Blockly",
                "quelle": "blockly",
                "schritte": [
                    {
                        "art": "wiederhole",
                        "anzahl": 2,
                        "rumpf": [
                            {
                                "art": "block",
                                "block_id": "meldung",
                                "parameter": {"text": "Hallo", "pause": "false"},
                            }
                        ],
                    }
                ],
            }
        ).encode(),
        headers={"Content-Type": "application/json", "X-Okm-Request": "1", "Cookie": cookies},
    )
    sid = json.loads(urllib.request.urlopen(anfrage).read())["id"]
    seite.goto(f"{server}/blockly?aus={sid}")
    seite.locator("#bl-code", has_text="Durchlauf").wait_for(timeout=5000)
    assert "printf '%s\\n' 'Hallo'" in seite.inner_text("#bl-code")
    assert not seite.is_disabled("#bl-erzeugen")
    seite.click("#bl-erzeugen")
    seite.locator("#bl-ergebnis a.knopf-primaer").wait_for(timeout=5000)
    assert seite.get_attribute("#bl-ergebnis a.knopf-primaer", "href").endswith("/download")
    assert js_fehler == []
