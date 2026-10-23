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


def test_software_katalog_im_browser(server: str, browser) -> None:
    """Suche, Kopieren (Clipboard-API und Fallback), „＋“, Mehrfachauswahl, Feld befüllen, Zielwechsel."""
    kontext = browser.new_context(viewport={"width": 1400, "height": 950})
    kontext.grant_permissions(["clipboard-read", "clipboard-write"])
    seite = kontext.new_page()
    js_fehler: list[str] = []
    seite.on("pageerror", lambda e: js_fehler.append(str(e)))

    # Eigene Seite: Suche + Kopieren über die Clipboard-API
    seite.goto(f"{server}/software")
    seite.locator("#katalog-anzahl", has_text="259 Treffer").wait_for()
    seite.fill("#katalog-suche", "Mozilla.Fire")
    seite.locator("#katalog-anzahl", has_text="2 Treffer").wait_for()
    assert seite.locator(".katalog-name").all_text_contents() == ["Mozilla Firefox", "Mozilla Firefox ESR"]
    seite.fill("#katalog-suche", "7zip")
    seite.locator(".katalog-eintrag:first-child .katalog-name", has_text="7-Zip").wait_for()
    assert seite.locator(".katalog-eintrag").first.locator("mark").count() >= 1
    seite.click("[data-plattform=windows]")
    knopf = seite.locator(".katalog-eintrag").first.locator(".katalog-id .knopf-klein").first
    knopf.click()
    seite.locator(".katalog-eintrag .kopiert", has_text="✓ Kopiert").wait_for()
    assert seite.evaluate("navigator.clipboard.readText()") == "7zip.7zip"
    seite.fill("#katalog-suche", "gibtesnichtxyz")
    seite.locator(".katalog-leer:not([hidden])").wait_for()

    # Fallback ohne sicheren Kontext (Intranet per HTTP/IP): execCommand('copy')
    seite.add_init_script("Object.defineProperty(window, 'isSecureContext', { value: false });")
    seite.goto(f"{server}/software")
    seite.fill("#katalog-suche", "vlc")
    seite.click("[data-plattform=linux]")
    seite.locator(".katalog-eintrag:first-child .katalog-name", has_text="VLC").wait_for()
    seite.locator(".katalog-eintrag").first.locator(".katalog-id .knopf-klein").first.click()
    seite.locator(".katalog-eintrag .kopiert").wait_for()
    assert seite.evaluate("navigator.clipboard.readText()") == "vlc"

    # Baukasten: "/" öffnet das Panel, Plattform folgt dem Zielsystem
    seite = kontext.new_page()
    seite.goto(f"{server}/baukasten?ziel=bash")
    seite.keyboard.press("/")
    seite.locator("#software-katalog[open]").wait_for()
    assert seite.get_attribute("[data-plattform=linux]", "aria-pressed") == "true"
    seite.keyboard.type("vlc")
    seite.locator(".katalog-eintrag:first-child .katalog-name", has_text="VLC").wait_for()
    seite.locator(".katalog-eintrag").first.locator(".knopf-uebernehmen").last.click()  # flatpak
    schritt = seite.locator("#schrittliste li.schritt[data-block=paket_installieren]").first
    schritt.wait_for()
    assert schritt.locator("input[data-typ=paketname]").input_value() == "org.videolan.VLC"
    seite.locator(
        "#bk-vorschau code", has_text="flatpak install -y --noninteractive flathub 'org.videolan.VLC'"
    ).wait_for(timeout=5000)

    # Mehrfachauswahl → mehrere Schritte in Reihenfolge
    seite.fill("#katalog-suche", "gimp")
    seite.locator(".katalog-eintrag:first-child .katalog-name", has_text="GIMP").wait_for()
    seite.locator(".katalog-auswahl").first.check()
    seite.fill("#katalog-suche", "7zip")
    seite.locator(".katalog-eintrag:first-child .katalog-name", has_text="7-Zip").wait_for()
    seite.locator(".katalog-auswahl").first.check()
    seite.locator("[data-katalog-auswahl]", has_text="(2)").click()
    seite.locator("#schrittliste li.schritt").nth(2).wait_for(timeout=5000)
    felder = seite.locator("#schrittliste input[data-typ=paketname]")
    assert [felder.nth(i).input_value() for i in range(3)][1:] == ["gimp", "7zip"]

    # Fokussiertes Paketfeld wird befüllt statt einen Schritt anzuhängen
    felder.nth(1).focus()
    seite.fill("#katalog-suche", "inkscape")
    seite.locator(".katalog-eintrag:first-child .katalog-name", has_text="Inkscape").wait_for()
    seite.locator(".katalog-eintrag").first.locator(".knopf-uebernehmen").first.click()
    assert felder.nth(1).input_value() == "inkscape"
    assert seite.locator("#schrittliste li.schritt").count() == 3

    # Zielwechsel → Plattform zieht mit, Windows-Tools fehlen unter macOS
    seite.click("label.ziel-option:has(input[value=zsh])")
    assert seite.get_attribute("[data-plattform=macos]", "aria-pressed") == "true"
    seite.fill("#katalog-suche", "sysinternals")
    seite.locator(".katalog-leer:not([hidden])").wait_for()

    # Rezept: Feld „Paketname“ und Paketmanager werden gesetzt
    seite.goto(f"{server}/rezepte/software_installieren?ziel=zsh")
    seite.focus("input[name='f.paket']")  # Paketfeld fokussiert → Katalog klappt auf
    seite.locator("#software-katalog[open]").wait_for()
    seite.fill("#katalog-suche", "firefox esr")
    seite.locator(".katalog-eintrag:first-child .katalog-name", has_text="Firefox ESR").wait_for()
    seite.locator(".katalog-eintrag").first.locator(".knopf-uebernehmen").first.click()
    assert seite.input_value("input[name='f.paket']") == "firefox@esr"
    assert seite.input_value("select[name='f.paketmanager']") == "brew_cask"
    assert js_fehler == []
    kontext.close()


def test_katalog_aktiver_filter_eindeutig(server: str, browser) -> None:
    """Punkt 4: aktive Chips/Umschalter gefüllt (okm-Rot) mit ✓ und fett; Filterzeile mit ×."""
    seite = browser.new_page(viewport={"width": 1280, "height": 900})
    seite.goto(f"{server}/software")
    seite.locator("#katalog-anzahl", has_text="259 Treffer").wait_for()
    seite.click("[data-kategorie=PDF]")
    seite.click("[data-kategorie='Backup & Cloud']")
    seite.click("[data-plattform=windows]")
    seite.mouse.move(0, 0)  # kein Hover-Zustand

    def stil(selektor: str, pseudo: str | None = None) -> dict[str, str]:
        return seite.eval_on_selector(
            selektor,
            "(el, p) => { const s = getComputedStyle(el, p); "
            "return {bg: s.backgroundColor, farbe: s.color, gewicht: s.fontWeight, inhalt: s.content}; }",
            pseudo,
        )

    rot = "rgb(227, 38, 46)"
    for sel in ("[data-kategorie=PDF]", "[data-plattform=windows]"):
        assert seite.get_attribute(sel, "aria-pressed") == "true"
        s = stil(sel)
        assert s["bg"] == rot and s["farbe"] == "rgb(255, 255, 255)" and int(s["gewicht"]) >= 700, s
        assert "✓" in stil(sel, "::before")["inhalt"]
    inaktiv = stil("[data-kategorie=Browser]")
    assert (
        inaktiv["bg"] in ("rgba(0, 0, 0, 0)", "transparent")
        and "✓" not in stil("[data-kategorie=Browser]", "::before")["inhalt"]
    )

    zeile = seite.locator(".katalog-filter")
    assert zeile.is_visible()
    assert zeile.inner_text().startswith("Gefiltert:")
    for text in ("PDF", "Backup & Cloud", "Windows", "Filter zurücksetzen"):
        assert text in zeile.inner_text()
    # Einzeln entfernen
    zeile.locator("button", has_text="PDF").click()
    assert seite.get_attribute("[data-kategorie=PDF]", "aria-pressed") == "false"
    assert "PDF" not in zeile.inner_text()
    zeile.locator("button", has_text="Windows").click()
    assert seite.get_attribute("[data-plattform=alle]", "aria-pressed") == "true"
    # Alles zurücksetzen
    zeile.locator("button", has_text="Filter zurücksetzen").click()
    assert not zeile.is_visible()
    seite.locator("#katalog-anzahl", has_text="259 Treffer").wait_for()


@pytest.mark.parametrize("breite", [360, 768, 1280, 1920])
@pytest.mark.parametrize("ort", ["seite", "panel"])
def test_katalog_zeilen_brechen_nicht_chaotisch(server: str, browser, breite: int, ort: str) -> None:
    """Punkt 5: ID-Zeilen als Grid – ID ohne Umbruch (Ellipsis + title), Knöpfe in derselben Zeile."""
    seite = browser.new_page(viewport={"width": breite, "height": 900})
    if ort == "seite":
        seite.goto(f"{server}/software")
    else:
        seite.goto(f"{server}/baukasten?ziel=powershell")
        seite.click("#software-katalog > summary")
    seite.click("[data-plattform=alle]")
    seite.locator(".katalog-eintrag").first.wait_for()
    seite.fill("#katalog-suche", "visual c++")  # lange IDs wie Microsoft.VCRedist.2015+.x64
    seite.locator("#katalog-anzahl").filter(has_text="Treffer").wait_for()
    seite.wait_for_timeout(300)
    ergebnis = seite.evaluate(
        """() => [...document.querySelectorAll('.katalog-id')].slice(0, 40).map(z => {
            const code = z.querySelector('code').getBoundingClientRect();
            const knoepfe = [...z.querySelectorAll('button')].map(b => b.getBoundingClientRect());
            const c = z.querySelector('code');
            return {
              id: c.textContent, title: c.title,
              ws: getComputedStyle(c).whiteSpace, wb: getComputedStyle(c).wordBreak,
              codeHoehe: code.height, codeOben: code.top, codeUnten: code.bottom,
              knoepfe: knoepfe.map(k => ({oben: k.top, unten: k.bottom, breite: k.width})),
            };
        })"""
    )
    assert ergebnis, "keine ID-Zeilen"
    for z in ergebnis:
        assert z["title"] == z["id"], z
        assert z["ws"] == "nowrap" and z["wb"] != "break-all", z
        assert z["codeHoehe"] < 30, f"ID bricht um: {z}"
        for k in z["knoepfe"]:
            assert k["breite"] >= 28, z
            # Knopf liegt in derselben Zeile wie die ID (bzw. bei Kartenlayout direkt daneben)
            assert k["oben"] < z["codeUnten"] + 2 and k["unten"] > z["codeOben"] - 2, (
                f"Knopf rutscht weg: {z}"
            )


def test_baukasten_katalog_unter_vorschau(server: str, browser) -> None:
    """Punkt 6: Katalog in der rechten Spalte direkt unter der Vorschau, klappt bei Bedarf auf."""
    seite = browser.new_page(viewport={"width": 1400, "height": 900})
    js_fehler: list[str] = []
    seite.on("pageerror", lambda e: js_fehler.append(str(e)))
    seite.goto(f"{server}/baukasten?ziel=bash")
    katalog = seite.locator("#software-katalog")
    assert katalog.get_attribute("open") is None, "Katalog soll anfangs eingeklappt sein"
    # Position: in der rechten Spalte, unter der Vorschau
    assert seite.evaluate(
        "() => { const a = document.querySelector('.bk-ausgabe'); const k = document.getElementById('software-katalog');"
        " const v = document.getElementById('bk-vorschau');"
        " return a.contains(k) && a.contains(v) && (v.compareDocumentPosition(k) & Node.DOCUMENT_POSITION_FOLLOWING) > 0"
        " && getComputedStyle(a).position === 'sticky'; }"
    )
    # paket_installieren hinzufügen → Katalog klappt auf, Plattform passt zum Ziel
    seite.click("[data-hinzufuegen=paket_installieren]")
    seite.locator("#schrittliste li.schritt[data-block=paket_installieren]").wait_for()
    seite.locator("#software-katalog[open]").wait_for()
    assert seite.get_attribute("[data-plattform=linux]", "aria-pressed") == "true"
    # Paketfeld ist fokussiert → ＋ füllt genau dieses Feld
    feld = seite.locator("#schrittliste li.schritt[data-block=paket_installieren] input[data-typ=paketname]")
    feld.focus()
    seite.fill("#katalog-suche", "vlc")
    seite.locator(".katalog-eintrag:first-child .katalog-name", has_text="VLC").wait_for()
    seite.locator(".katalog-eintrag").first.locator(".knopf-uebernehmen").first.click()
    assert feld.input_value() == "vlc"
    assert seite.locator("#schrittliste li.schritt").count() == 1
    # Katalog wieder zu, Feld fokussieren → klappt auf
    seite.click("#software-katalog > summary")
    assert katalog.get_attribute("open") is None
    feld.focus()
    seite.locator("#software-katalog[open]").wait_for()
    assert js_fehler == []

    # Schmal: Blöcke → Vorschau → Katalog untereinander
    schmal = browser.new_page(viewport={"width": 600, "height": 900})
    schmal.goto(f"{server}/baukasten?ziel=bash")
    oben = schmal.evaluate(
        "() => ['#schrittliste', '#bk-vorschau', '#software-katalog'].map(s => document.querySelector(s)"
        ".getBoundingClientRect().top)"
    )
    assert oben == sorted(oben), oben


def test_blockly_katalog(server: str, browser) -> None:
    """Punkt 7: dieselbe Komponente in Blockly – ＋ legt einen Baustein an bzw. setzt dessen ID."""
    seite = browser.new_page(viewport={"width": 1400, "height": 1000})
    js_fehler: list[str] = []
    seite.on("pageerror", lambda e: js_fehler.append(str(e)))
    seite.goto(f"{server}/blockly?ziel=zsh")
    seite.locator(".blocklyDraggable", has_text="Script").first.wait_for()
    seite.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")
    assert seite.evaluate(
        "() => { const a = document.querySelector('.bl-ausgabe'); const k = document.getElementById('software-katalog');"
        " return !!k && a.contains(k) && k.dataset.modus === 'blockly'; }"
    )
    seite.click("#software-katalog > summary")
    assert seite.get_attribute("[data-plattform=macos]", "aria-pressed") == "true"
    seite.fill("#katalog-suche", "firefox esr")
    seite.locator(".katalog-eintrag:first-child .katalog-name", has_text="Firefox ESR").wait_for()
    seite.locator(".katalog-eintrag").first.locator(".knopf-uebernehmen").first.click()
    bloecke = seite.evaluate(
        "() => window.okmBlockly.arbeitsflaeche.getAllBlocks(false).filter(b => b.type === 'bk_paket_installieren')"
        ".map(b => ({paket: b.getFieldValue('paket'), pm: b.getFieldValue('paketmanager'),"
        " imScript: !!b.getRootBlock() && b.getRootBlock().type === 'ablauf_start'}))"
    )
    assert bloecke == [{"paket": "firefox@esr", "pm": "brew_cask", "imScript": True}], bloecke
    # Neuer Block ist ausgewählt → ＋ setzt dessen ID statt einen weiteren anzulegen
    seite.fill("#katalog-suche", "vlc")
    seite.locator(".katalog-eintrag:first-child .katalog-name", has_text="VLC").wait_for()
    seite.locator(".katalog-eintrag").first.locator(".knopf-uebernehmen").first.click()
    bloecke = seite.evaluate(
        "() => window.okmBlockly.arbeitsflaeche.getAllBlocks(false).filter(b => b.type === 'bk_paket_installieren')"
        ".map(b => b.getFieldValue('paket'))"
    )
    assert bloecke == ["vlc"], bloecke
    seite.locator("#bl-code", has_text="brew install --cask 'vlc'").wait_for(timeout=8000)
    assert js_fehler == []


def test_katalog_ist_eine_komponente(server: str, browser) -> None:
    """Punkt 7: dieselbe Komponente (SoftwareKatalog.mount) auf allen vier Seiten."""
    seite = browser.new_page(viewport={"width": 1280, "height": 900})
    for pfad, modus in [
        ("/software", "seite"),
        ("/baukasten?ziel=bash", "baukasten"),
        ("/rezepte/software_installieren?ziel=bash", "rezept"),
        ("/blockly?ziel=bash", "blockly"),
    ]:
        seite.goto(server + pfad)
        assert seite.evaluate("() => typeof window.SoftwareKatalog.mount") == "function"
        assert seite.get_attribute("#software-katalog", "data-modus") == modus
        assert seite.locator("#software-katalog").count() == 1
