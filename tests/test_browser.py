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


def warte_editor(seite, text: str, timeout: int = 5000) -> None:
    """Wartet, bis der Script-Editor sichtbar ist und ``text`` enthält."""
    seite.wait_for_function(
        "t => window.OkmEditor && !window.OkmEditor.wurzel.hidden && window.OkmEditor.wert().includes(t)",
        arg=text,
        timeout=timeout,
    )


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
    warte_editor(seite, "ping -c 4 '10.0.0.7'", 5000)

    # Umsortieren
    seite.click("#schrittliste li.schritt[data-block=ping] [data-hoch]")
    warte_editor(seite, "[1/2] Ping auf 10.0.0.7", 5000)

    # Zielwechsel: SetupDiag nur unter PowerShell
    assert seite.is_disabled("[data-hinzufuegen=setupdiag]")
    seite.click("label.ziel-option:has(input[value=powershell])")
    warte_editor(seite, "ping.exe -n 4 '10.0.0.7'", 5000)
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
    warte_editor(seite, "Durchlauf", 5000)
    assert "printf '%s\\n' 'Hallo'" in seite.evaluate("() => window.OkmEditor.wert()")
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
    warte_editor(seite, "flatpak install -y --noninteractive flathub 'org.videolan.VLC'", 5000)

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
    warte_editor(seite, "brew install --cask 'vlc'", 8000)
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


def test_rezeptuebersicht_live_suche(server: str, browser) -> None:
    """Punkt 8: Karten-Raster, umlauttolerante Live-Suche, Kategorie-Chips, sichtbarer Fokus."""
    seite = browser.new_page(viewport={"width": 1280, "height": 900})
    js_fehler: list[str] = []
    seite.on("pageerror", lambda e: js_fehler.append(str(e)))
    seite.goto(f"{server}/rezepte?ziel=zsh")
    sichtbar = "() => [...document.querySelectorAll('#rezeptliste .rezept-karte:not([hidden])')].map(k => k.dataset.rezept)"
    alle = seite.evaluate(sichtbar)
    assert len(alle) > 10
    seite.fill("#suchfeld", "langsam")
    seite.wait_for_timeout(250)
    treffer = seite.evaluate(sichtbar)
    assert "pc_ist_langsam" in treffer and len(treffer) < len(alle)
    # umlauttolerant: „groesse“ findet „Größe“, „loeschen“ = „löschen“
    seite.fill("#suchfeld", "loeschen")
    seite.wait_for_timeout(250)
    mit_oe = seite.evaluate(sichtbar)
    seite.fill("#suchfeld", "löschen")
    seite.wait_for_timeout(250)
    assert seite.evaluate(sichtbar) == mit_oe
    seite.fill("#suchfeld", "")
    seite.wait_for_timeout(250)
    # Kategorie-Chip: aktiv eindeutig (okm-Rot + ✓), filtert die Karten
    seite.click(".rezept-filter [data-kategorie=Drucker]")
    seite.mouse.move(0, 0)
    assert seite.get_attribute(".rezept-filter [data-kategorie=Drucker]", "aria-pressed") == "true"
    assert seite.eval_on_selector(
        ".rezept-filter [data-kategorie=Drucker]", "e => getComputedStyle(e).backgroundColor"
    ) == ("rgb(227, 38, 46)")
    kategorien = seite.evaluate(
        "() => [...document.querySelectorAll('#rezeptliste .rezept-karte:not([hidden])')].map(k => k.dataset.kategorie)"
    )
    assert kategorien and set(kategorien) == {"Drucker"}
    assert "passende" in seite.inner_text("#rezept-anzahl")
    seite.fill("#suchfeld", "gibtesnichtxyz")
    seite.wait_for_timeout(250)
    assert seite.is_visible("#rezept-leer")
    # Tastaturfokus sichtbar
    seite.fill("#suchfeld", "")
    seite.click(".rezept-filter [data-kategorie=Drucker]")
    seite.wait_for_timeout(250)
    seite.focus("#suchfeld")
    for _ in range(40):  # mit Tab bis zur ersten Karte – wie ein Tastaturnutzer
        seite.keyboard.press("Tab")
        if seite.evaluate("() => document.activeElement.matches('a.rezept-link')"):
            break
    assert seite.evaluate("() => getComputedStyle(document.activeElement).outlineStyle") == "solid"
    assert js_fehler == []


# --- Punkt 9: bearbeitbarer Script-Editor ----------------------------------------------------


def _zustand(seite) -> str:
    return seite.get_attribute("#script-editor", "data-zustand")


def _tippen_am_ende(seite, text: str) -> None:
    seite.click("#script-editor .CodeMirror")
    seite.keyboard.press("Control+End")
    seite.keyboard.type(text)


def test_editor_rezept_bearbeiten_pruefen_herunterladen(server: str, browser) -> None:
    import shutil

    seite = browser.new_page(viewport={"width": 1280, "height": 1000}, accept_downloads=True)
    js_fehler: list[str] = []
    seite.on("pageerror", lambda e: js_fehler.append(str(e)))
    seite.on("console", lambda m: js_fehler.append(m.text) if "Content Security Policy" in m.text else None)
    seite.goto(f"{server}/rezepte/drucker_einrichten?ziel=bash")
    seite.fill("[name='f.druckername']", "Empfang")
    seite.fill("[name='f.drucker_ip']", "10.0.0.5")
    seite.click("button[type=submit].knopf-primaer")
    warte_editor(seite, "Benötigte Rechte:")
    assert _zustand(seite) == "generiert"
    assert seite.is_visible("#script-editor .CodeMirror")  # CodeMirror ist geladen (CSP-konform)
    assert seite.is_hidden("[data-editor-banner]")
    generiert = seite.evaluate("() => window.OkmEditor.wert()")

    # Bearbeiten → Zustand, Banner, einmaliger Sicherheitshinweis
    _tippen_am_ende(seite, "echo ergaenzt")
    assert _zustand(seite) == "manuell"
    assert seite.is_visible("[data-editor-banner]")
    assert seite.is_visible("[data-editor-sicherheit]")
    seite.click("[data-editor=verstanden]")
    assert seite.is_hidden("[data-editor-sicherheit]")
    assert seite.evaluate("() => localStorage.getItem('okm-editor-hinweis-gelesen')") == "1"

    # Diff
    seite.click("[data-editor=diff]")
    assert "+ echo ergaenzt" in seite.inner_text("[data-editor-diff]")

    # Download über den Export-Endpunkt: bearbeiteter Text + Kopfzeile
    with seite.expect_download() as dl:
        seite.click("#ergebnis a.knopf-primaer[data-editor-bezug]")
    inhalt = Path(dl.value.path()).read_text(encoding="utf-8")
    assert "# Manuell bearbeitet: ja (nicht vom Baukasten geprüft)" in inhalt
    assert inhalt.rstrip().endswith("echo ergaenzt")
    assert "SHA-256" in seite.inner_text("[data-editor-hash]")

    # Syntax prüfen: Fehler mit Zeile wird markiert
    if shutil.which("bash"):
        _tippen_am_ende(seite, "\nif true; then")
        seite.click("[data-editor=pruefen]")
        seite.locator("[data-editor-pruefung] .editor-befunde li").first.wait_for(timeout=15000)
        assert "bash -n" in seite.inner_text("[data-editor-pruefung]")
        assert seite.locator("#script-editor .editor-fehlerzeile").count() >= 1

    # Rückgängig bis zur generierten Fassung → Zustand wieder „generiert“
    for _ in range(20):
        if _zustand(seite) == "generiert":
            break
        seite.click("[data-editor=rueckgaengig]")
    assert _zustand(seite) == "generiert"
    seite.click("[data-editor=wiederholen]")
    assert _zustand(seite) == "manuell"

    # Neu generieren verwirft die Änderungen
    seite.click("[data-editor=neu]")
    assert _zustand(seite) == "generiert"
    assert seite.evaluate("() => window.OkmEditor.wert()") == generiert
    assert js_fehler == []


def test_editor_bibliothek_und_erneut_oeffnen(server: str, browser) -> None:
    seite = browser.new_page(viewport={"width": 1280, "height": 1000})
    js_fehler: list[str] = []
    seite.on("pageerror", lambda e: js_fehler.append(str(e)))
    seite.goto(f"{server}/baukasten?ziel=bash")
    seite.evaluate("() => localStorage.setItem('okm-editor-hinweis-gelesen', '1')")
    seite.click("[data-hinzufuegen=systeminfo]")
    warte_editor(seite, "Systeminfo")
    _tippen_am_ende(seite, "echo aus_dem_editor")
    assert _zustand(seite) == "manuell"
    assert seite.is_hidden("[data-editor-sicherheit]")  # schon einmal bestätigt

    # Live-Vorschau ändert sich (Titel) → bearbeiteter Text bleibt, Banner bleibt
    seite.click("details.optionen summary")
    seite.fill("#bk-titel", "Neuer Titel")
    seite.press("#bk-titel", "Tab")  # change-Ereignis jetzt, nicht erst beim Klick auf „Erzeugen“
    seite.wait_for_timeout(400)
    seite.wait_for_function("() => window.OkmEditor.generiert().includes('Neuer Titel')", timeout=5000)
    assert "echo aus_dem_editor" in seite.evaluate("() => window.OkmEditor.wert()")
    assert "Neuer Titel" not in seite.evaluate("() => window.OkmEditor.wert()")
    assert _zustand(seite) == "manuell"

    # Erzeugen + in Bibliothek speichern → bearbeiteter Text wird gespeichert
    seite.click("#bk-vorschau button.knopf-primaer")
    seite.locator("#bk-ergebnis a.knopf-primaer").wait_for(timeout=5000)
    sid = seite.get_attribute("#bk-ergebnis a.knopf-primaer", "href").split("/")[-2]
    seite.click("#bk-ergebnis .bib-speichern summary")
    seite.click("#bk-ergebnis .bib-speichern button")
    seite.locator("#bk-ergebnis .bib-status", has_text="gespeichert").wait_for(timeout=5000)
    text = seite.evaluate(f"() => fetch('/skripte/{sid}/download').then(r => r.text())")
    assert "echo aus_dem_editor" in text and "Manuell bearbeitet: ja" in text

    # Erneut öffnen → Editor startet mit dem bearbeiteten Text und Banner
    seite.goto(f"{server}/baukasten?aus={sid}")
    seite.wait_for_function(
        "() => window.OkmEditor && window.OkmEditor.wert().includes('echo aus_dem_editor')"
    )
    seite.wait_for_function("() => window.OkmEditor.generiert().includes('Neuer Titel')", timeout=5000)
    assert _zustand(seite) == "manuell"
    assert seite.is_visible("[data-editor-banner]")
    assert "echo aus_dem_editor" in seite.evaluate("() => window.OkmEditor.wert()")
    assert js_fehler == []


# --- Backlog P1: Ablauf-Blöcke „Wenn“, „Abbrechen“ … im Blockly-Modus ------------------------


def test_blockly_wenn_mit_rueckgabewert(server: str, browser) -> None:
    import json
    import urllib.request

    seite = browser.new_page(viewport={"width": 1280, "height": 1100})
    js_fehler: list[str] = []
    seite.on("pageerror", lambda e: js_fehler.append(str(e)))
    seite.goto(f"{server}/blockly?ziel=bash")
    seite.locator(".blocklyDraggable", has_text="Script").first.wait_for()
    seite.evaluate("() => { try { localStorage.clear(); } catch (e) {} }")

    # Per Blockly-API: Ping → Wenn (erreichbar ist nein) → Abbrechen; danach Notiz/Warten
    seite.evaluate(
        """() => {
          const ws = window.okmBlockly.arbeitsflaeche;
          const start = ws.getBlocksByType('ablauf_start')[0];
          const ping = ws.newBlock('bk_ping'); ping.initSvg(); ping.render();
          ping.setFieldValue('10.0.0.7', 'ziel');
          start.getInput('SCHRITTE').connection.connect(ping.previousConnection);
          const wenn = ws.newBlock('ablauf_wenn'); wenn.initSvg(); wenn.render();
          ping.nextConnection.connect(wenn.previousConnection);
          const ende = ws.newBlock('ablauf_abbrechen'); ende.initSvg(); ende.render();
          ende.setFieldValue('Drucker aus', 'MELDUNG'); ende.setFieldValue(3, 'CODE');
          wenn.getInput('DANN').connection.connect(ende.previousConnection);
          const notiz = ws.newBlock('ablauf_kommentar'); notiz.initSvg(); notiz.render();
          wenn.nextConnection.connect(notiz.previousConnection);
          window.okmTest = { wenn: wenn.id, ping: ping.id };
        }"""
    )
    # Auswahl zeigt die Werte des Schritts davor (Zielsystem bash)
    optionen = seite.evaluate(
        "() => window.okmBlockly.arbeitsflaeche.getBlockById(window.okmTest.wenn)"
        ".getField('WERT').getOptions(false).map(o => o[0])"
    )
    assert optionen == [
        "Schritt 1 · Ping auf Ziel: Das Ziel hat geantwortet",
        "Schritt 1 · Ping auf Ziel: Mittlere Antwortzeit in Millisekunden (leer, wenn keine Antwort)",
    ]
    seite.evaluate(
        """() => { const w = window.okmBlockly.arbeitsflaeche.getBlockById(window.okmTest.wenn);
                   w.setFieldValue(window.okmTest.ping + '|erreichbar', 'WERT');
                   w.setFieldValue('nein', 'VERGLEICH'); }"""
    )
    assert not seite.evaluate(
        "() => window.okmBlockly.arbeitsflaeche.getBlockById(window.okmTest.wenn).getField('ZAHL').isVisible()"
    )
    anfrage = seite.evaluate("() => window.okmBlockly.serialisieren().anfrage.schritte")
    assert anfrage[1] == {
        "art": "wenn",
        "wert": "1.erreichbar",
        "vergleich": "nein",
        "zahl": None,
        "dann": [{"art": "abbrechen", "meldung": "Drucker aus", "code": 3}],
        "sonst": [],
    }
    assert anfrage[2] == {"art": "kommentar", "text": "Was hier passiert"}
    warte_editor(seite, 'if [ "$okm_s1_erreichbar" = 0 ]; then', 8000)
    assert "Planmäßig beendet: " in seite.evaluate("() => window.OkmEditor.wert()")

    # Umsortieren: Wenn vor den Ping → Server meldet den Fehler am Wenn-Block
    seite.evaluate(
        """() => { const ws = window.okmBlockly.arbeitsflaeche;
                   const start = ws.getBlocksByType('ablauf_start')[0];
                   const wenn = ws.getBlockById(window.okmTest.wenn), ping = ws.getBlockById(window.okmTest.ping);
                   wenn.unplug(true); ping.unplug(true);
                   start.getInput('SCHRITTE').connection.connect(wenn.previousConnection);
                   wenn.nextConnection.connect(ping.previousConnection); }"""
    )
    seite.locator("#bl-fehler", has_text="vor diesem").wait_for(timeout=8000)

    # Gespeichertes Script mit den neuen Knoten erneut öffnen
    kontext = seite.context
    cookies = "; ".join(f"{c['name']}={c['value']}" for c in kontext.cookies())
    nutzlast = {
        "ziel": "bash",
        "titel": "Ablauf neu",
        "quelle": "blockly",
        "schritte": [
            {"art": "kommentar", "text": "Prüft den Drucker"},
            {"art": "block", "block_id": "ping", "parameter": {"ziel": "10.0.0.7", "anzahl": "1"}},
            {
                "art": "wenn",
                "wert": "1.ms",
                "vergleich": "groesser",
                "zahl": 100,
                "dann": [{"art": "warten", "sekunden": 2}],
                "sonst": [{"art": "bestaetigung", "meldung": "Weiter?"}],
            },
        ],
    }
    req = urllib.request.Request(
        f"{server}/api/v1/skripte",
        data=json.dumps(nutzlast).encode(),
        headers={"Content-Type": "application/json", "X-Okm-Request": "1", "Cookie": cookies},
    )
    sid = json.loads(urllib.request.urlopen(req).read())["id"]
    seite.goto(f"{server}/blockly?aus={sid}")
    warte_editor(seite, "Notiz: Prüft den Drucker", 8000)
    wieder = seite.evaluate("() => window.okmBlockly.serialisieren().anfrage.schritte")
    assert wieder[2]["wert"] == "1.ms" and wieder[2]["zahl"] == 100 and wieder[2]["vergleich"] == "groesser"
    assert wieder[2]["dann"] == [{"art": "warten", "sekunden": 2}]
    assert wieder[2]["sonst"] == [{"art": "bestaetigung", "meldung": "Weiter?"}]
    assert js_fehler == []
