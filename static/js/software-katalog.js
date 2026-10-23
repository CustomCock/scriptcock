/* okm Script-Baukasten – Software-Katalog als EINE Komponente.
 *
 *   var katalog = SoftwareKatalog.mount(element, {
 *     daten:            [...],                  // Pakete (JSON aus #software-katalog-daten)
 *     zielPlattform:    function () {…},        // "windows" | "macos" | "linux" | "" (Filter folgt dem Ziel)
 *     onUebernehmen:    function (eintrag) {…}, // ＋ – eintrag = {feld: "winget", id: "7zip.7zip"}
 *     kannUebernehmen:  function () {…},        // ob ＋ angezeigt wird (Standard: wenn onUebernehmen da ist)
 *     onMehrfach:       function (eintraege) {…} // Checkboxen + „Ausgewählte installieren (n)“
 *   });
 *   katalog.oeffnen(); katalog.zielGeaendert(); katalog.aktualisieren();
 *
 * Unten stehen die Adapter für /software, Rezept, Baukasten (Listen-Modus) und Blockly.
 * Daten nur über Textknoten ins DOM – kein innerHTML. Suche: katalog-suche.js.
 */
(function () {
  "use strict";

  var LABEL = { winget: "winget", brew: "brew", brew_cask: "brew --cask", apt: "apt", flatpak: "flatpak" };
  var FELD_PLATTFORM = { winget: "windows", brew: "macos", brew_cask: "macos", apt: "linux", flatpak: "linux" };
  var PLATTFORM_NAME = { windows: "Windows", macos: "macOS", linux: "Linux" };
  var SPEICHER_PLATTFORM = "okm.katalog.plattform";
  var SPEICHER_KATEGORIEN = "okm.katalog.kategorien";

  function lesen(schluessel) {
    try { return window.localStorage.getItem(schluessel); } catch (e) { return null; }
  }
  function schreiben(schluessel, wert) {
    try { window.localStorage.setItem(schluessel, wert); } catch (e) { /* ohne Speicher geht es auch */ }
  }

  function el(tag, klasse, text) {
    var e = document.createElement(tag);
    if (klasse) { e.className = klasse; }
    if (text !== undefined && text !== null) { e.textContent = text; }
    return e;
  }

  /* Text mit <mark>-Hervorhebung – ausschließlich über Textknoten aufgebaut. */
  function markiert(tag, klasse, text, anfrage) {
    var e = el(tag, klasse);
    var pos = 0;
    window.OkmKatalogSuche.trefferBereiche(text, anfrage).forEach(function (b) {
      if (b[0] > pos) { e.appendChild(document.createTextNode(text.slice(pos, b[0]))); }
      e.appendChild(el("mark", null, text.slice(b[0], b[1])));
      pos = b[1];
    });
    if (pos < text.length) { e.appendChild(document.createTextNode(text.slice(pos))); }
    return e;
  }

  // --- Kopieren (Clipboard-API, Fallback für HTTP, sonst markieren + „Strg+C“) -------------
  function altKopieren(text) {
    var feld = document.createElement("textarea");
    feld.value = text;
    feld.setAttribute("readonly", "");
    feld.className = "sr-only";
    document.body.appendChild(feld);
    feld.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(feld);
    return ok;
  }

  // ======================================================================================
  // Komponente
  // ======================================================================================
  function mount(wurzel, optionen) {
    optionen = optionen || {};
    var S = window.OkmKatalogSuche;
    var index = S.baueIndex(optionen.daten || []);
    var eingeklappt = wurzel.tagName === "DETAILS";
    var $ = function (sel) { return wurzel.querySelector(sel); };
    var suchfeld = $(".katalog-suche");
    var liste = $(".katalog-liste");
    var anzahl = $("#katalog-anzahl");
    var leer = $(".katalog-leer");
    var meldung = $("#katalog-meldung");
    var auswahlKnopf = $("[data-katalog-auswahl]");
    var filterZeile = $(".katalog-filter");
    var zustand = { plattform: "alle", kategorien: [], treffer: [], aktiv: -1, auswahl: {}, gezeigt: false };

    function zielPlattform() { return optionen.zielPlattform ? optionen.zielPlattform() || "" : ""; }
    function kannUebernehmen() {
      if (!optionen.onUebernehmen) { return false; }
      return optionen.kannUebernehmen ? optionen.kannUebernehmen() : true;
    }
    function melden(text) {
      meldung.textContent = "";
      setTimeout(function () { meldung.textContent = text; }, 30);
    }
    /* ID eines Pakets, die zum aktuellen Zielsystem passt (Checkboxen, Mehrfachauswahl). */
    function zielEintrag(paket) {
      var ids = S.ids(paket, zielPlattform() || "alle");
      return ids.length ? ids[0] : null;
    }

    function rueckmeldung(knopf, text) {
      if (knopf.dataset.alt === undefined) { knopf.dataset.alt = knopf.textContent; }
      knopf.textContent = "✓ Kopiert";
      knopf.classList.add("kopiert");
      clearTimeout(knopf._zeit);
      knopf._zeit = setTimeout(function () {
        knopf.textContent = knopf.dataset.alt;
        knopf.classList.remove("kopiert");
      }, 1500);
      melden(text + " kopiert.");
    }
    function fehlschlag(code) {
      var bereich = document.createRange();
      bereich.selectNodeContents(code);
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(bereich);
      var zeile = code.closest(".katalog-id");
      if (zeile && !zeile.querySelector(".katalog-strgc")) {
        var hinweis = el("span", "katalog-strgc", "Mit Strg+C kopieren");
        zeile.appendChild(hinweis);
        setTimeout(function () { hinweis.remove(); }, 4000);
      }
      melden("Kopieren nicht möglich – Text ist markiert, mit Strg+C kopieren.");
    }
    function kopieren(text, knopf, code) {
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(function () { rueckmeldung(knopf, text); }, function () {
          if (altKopieren(text)) { rueckmeldung(knopf, text); } else { fehlschlag(code); }
        });
      } else if (altKopieren(text)) {
        rueckmeldung(knopf, text);
      } else {
        fehlschlag(code);
      }
    }

    // --- Darstellung -------------------------------------------------------------------
    function knopf(text, klasse, titel, beschriftung, aktion) {
      var k = el("button", klasse, text);
      k.type = "button";
      k.title = titel;
      k.setAttribute("aria-label", beschriftung);
      k.addEventListener("click", aktion);
      return k;
    }

    function idZeile(eintrag, uebernahme) {
      var zeile = el("div", "katalog-id");
      zeile.appendChild(el("span", "katalog-id-label", LABEL[eintrag.feld]));
      // Eine Zeile, bei Platzmangel „…“ – die volle ID steht im Tooltip und wird immer ganz kopiert
      var code = el("code", null, eintrag.id);
      code.title = eintrag.id;
      zeile.appendChild(code);
      var knoepfe = el("span", "katalog-id-knoepfe");
      var kop = knopf("⧉", "knopf-klein", "ID kopieren", "ID kopieren: " + eintrag.id, function () {
        kopieren(eintrag.id, kop, code);
      });
      var bef = knopf("▾", "knopf-klein", "Installationsbefehl kopieren", "Installationsbefehl kopieren: " + eintrag.id,
        function () { kopieren(S.befehl(eintrag.feld, eintrag.id), bef, code); });
      knoepfe.appendChild(kop);
      knoepfe.appendChild(bef);
      if (uebernahme) {
        var passt = !zielPlattform() || FELD_PLATTFORM[eintrag.feld] === zielPlattform();
        var plus = knopf("＋", "knopf-klein knopf-uebernehmen",
          passt ? "Ins Script übernehmen" : "Passt nicht zum gewählten Zielsystem",
          "Ins Script übernehmen: " + eintrag.id, function () { optionen.onUebernehmen(eintrag); });
        plus.disabled = !passt;
        knoepfe.appendChild(plus);
      }
      zeile.appendChild(knoepfe);
      return zeile;
    }

    function eintragElement(t, nr, anfrage) {
      var p = t.paket;
      var li = el("li", "katalog-eintrag");
      li.id = "katalog-eintrag-" + nr;
      var mehrfach = !!optionen.onMehrfach;
      var kopf = el("div", "katalog-eintrag-kopf" + (mehrfach ? " mit-auswahl" : ""));
      if (mehrfach) {
        var ziel = zielEintrag(p);
        var box = el("input");
        box.type = "checkbox";
        box.className = "katalog-auswahl";
        box.disabled = !ziel;
        box.checked = !!(ziel && zustand.auswahl[p.name]);
        box.setAttribute("aria-label", p.name + " auswählen");
        box.addEventListener("change", function () {
          if (box.checked) { zustand.auswahl[p.name] = p; } else { delete zustand.auswahl[p.name]; }
          auswahlAktualisieren();
        });
        kopf.appendChild(box);
      }
      kopf.appendChild(markiert("strong", "katalog-name", p.name, anfrage));
      kopf.appendChild(el("span", "marke marke-leise", p.kategorie));
      li.appendChild(kopf);
      var beschreibung = markiert("p", "katalog-beschreibung", p.beschreibung, anfrage);
      beschreibung.title = p.beschreibung;  // höchstens zwei Zeilen sichtbar
      li.appendChild(beschreibung);
      if (p.hinweis) { li.appendChild(el("p", "katalog-hinweis", p.hinweis)); }
      var uebernahme = kannUebernehmen();
      S.ids(p, zustand.plattform).forEach(function (e) { li.appendChild(idZeile(e, uebernahme)); });
      if (p.hersteller_url) {
        var a = el("a", "katalog-link", "Herstellerseite");
        a.href = p.hersteller_url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        li.appendChild(a);
      }
      if (p.intern) {
        var z = el("div", "katalog-id");
        z.appendChild(el("span", "katalog-id-label", "intern"));
        var intern = el("code", null, p.intern);
        intern.title = p.intern;
        z.appendChild(intern);
        li.appendChild(z);
      }
      return li;
    }

    /* „Gefiltert: PDF ×, Backup × · Windows × · Filter zurücksetzen“ – jeder Filter einzeln entfernbar */
    function filterZeigen() {
      if (!filterZeile) { return; }
      filterZeile.textContent = "";
      var aktiv = zustand.kategorien.length > 0 || zustand.plattform !== "alle";
      filterZeile.hidden = !aktiv;
      if (!aktiv) { return; }
      function marke(text, beschriftung, entfernen) {
        filterZeile.appendChild(knopf(text + " ×", "katalog-filter-marke", beschriftung, beschriftung,
          function () { entfernen(); zeigen(); }));
      }
      filterZeile.appendChild(el("span", null, "Gefiltert:"));
      zustand.kategorien.forEach(function (k) {
        marke(k, "Filter " + k + " entfernen", function () {
          kategorienSetzen(zustand.kategorien.filter(function (x) { return x !== k; }));
        });
      });
      if (zustand.plattform !== "alle") {
        if (zustand.kategorien.length) { filterZeile.appendChild(el("span", null, "·")); }
        marke(PLATTFORM_NAME[zustand.plattform], "Plattformfilter entfernen", function () { plattformSetzen("alle", true); });
      }
      filterZeile.appendChild(el("span", null, "·"));
      var reset = el("button", "katalog-filter-reset", "Filter zurücksetzen");
      reset.type = "button";
      reset.addEventListener("click", function () { kategorienSetzen([]); plattformSetzen("alle", true); zeigen(); });
      filterZeile.appendChild(reset);
    }

    function zeigen() {
      zustand.gezeigt = true;
      filterZeigen();
      var anfrage = suchfeld.value;
      zustand.treffer = S.suche(index, { anfrage: anfrage, plattform: zustand.plattform, kategorien: zustand.kategorien });
      zustand.aktiv = -1;
      var fragment = document.createDocumentFragment();
      zustand.treffer.forEach(function (t, nr) { fragment.appendChild(eintragElement(t, nr, anfrage)); });
      liste.textContent = "";
      liste.appendChild(fragment);
      var n = zustand.treffer.length;
      anzahl.textContent = n === 1 ? "1 Treffer" : n + " Treffer";
      leer.hidden = n > 0;
    }

    function aktivSetzen(nr) {
      var alt = liste.querySelector(".katalog-aktiv");
      if (alt) { alt.classList.remove("katalog-aktiv"); }
      if (!zustand.treffer.length) { zustand.aktiv = -1; return; }
      zustand.aktiv = Math.max(0, Math.min(nr, zustand.treffer.length - 1));
      var li = document.getElementById("katalog-eintrag-" + zustand.aktiv);
      li.classList.add("katalog-aktiv");
      li.scrollIntoView({ block: "nearest" });
      suchfeld.setAttribute("aria-activedescendant", li.id);
      melden(zustand.treffer[zustand.aktiv].paket.name);
    }

    function auswahlAktualisieren() {
      if (!auswahlKnopf) { return; }
      var n = Object.keys(zustand.auswahl).filter(function (k) { return zielEintrag(zustand.auswahl[k]); }).length;
      auswahlKnopf.querySelector("[data-anzahl]").textContent = String(n);
      auswahlKnopf.disabled = n === 0;
    }

    // --- Filter --------------------------------------------------------------------------
    function plattformSetzen(wert, merken) {
      zustand.plattform = S.PLATTFORMEN[wert] ? wert : "alle";
      wurzel.querySelectorAll("[data-plattform]").forEach(function (k) {
        k.setAttribute("aria-pressed", String(k.dataset.plattform === zustand.plattform));
      });
      if (merken) { schreiben(SPEICHER_PLATTFORM, zustand.plattform); }
    }
    function kategorienSetzen(neu) {
      var vorhanden = {};
      wurzel.querySelectorAll("[data-kategorie]").forEach(function (k) { vorhanden[k.dataset.kategorie] = k; });
      zustand.kategorien = neu.filter(function (k) { return vorhanden[k]; });
      Object.keys(vorhanden).forEach(function (k) {
        vorhanden[k].setAttribute("aria-pressed", String(zustand.kategorien.indexOf(k) >= 0));
      });
      var zaehler = $("[data-kategorien-anzahl]");
      if (zaehler) { zaehler.textContent = zustand.kategorien.length ? "(" + zustand.kategorien.length + " gewählt)" : ""; }
      schreiben(SPEICHER_KATEGORIEN, JSON.stringify(zustand.kategorien));
    }

    wurzel.querySelectorAll("[data-plattform]").forEach(function (k) {
      k.addEventListener("click", function () { plattformSetzen(k.dataset.plattform, true); zeigen(); });
    });
    wurzel.querySelectorAll("[data-kategorie]").forEach(function (k) {
      k.addEventListener("click", function () {
        var neu = zustand.kategorien.slice();
        var pos = neu.indexOf(k.dataset.kategorie);
        if (pos >= 0) { neu.splice(pos, 1); } else { neu.push(k.dataset.kategorie); }
        kategorienSetzen(neu);
        zeigen();
      });
    });

    // Startzustand: Zielsystem gewinnt, sonst gemerkte Plattform
    plattformSetzen(zielPlattform() || lesen(SPEICHER_PLATTFORM) || "alle", false);
    try { kategorienSetzen(JSON.parse(lesen(SPEICHER_KATEGORIEN) || "[]") || []); } catch (e) { kategorienSetzen([]); }

    // --- Suche & Tastatur ----------------------------------------------------------------
    var zeit = null;
    suchfeld.addEventListener("input", function () {
      clearTimeout(zeit);
      zeit = setTimeout(zeigen, 100);
    });
    suchfeld.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowDown") { ev.preventDefault(); aktivSetzen(zustand.aktiv + 1); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); aktivSetzen(zustand.aktiv - 1); }
      else if (ev.key === "Enter") {
        ev.preventDefault();
        var li = document.getElementById("katalog-eintrag-" + Math.max(zustand.aktiv, 0));
        var k = li && li.querySelector(".katalog-id .knopf-klein");
        if (k) { k.click(); }
      } else if (ev.key === "Escape") {
        ev.preventDefault();
        ev.stopPropagation();
        if (suchfeld.value) { suchfeld.value = ""; zeigen(); }
      }
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key !== "/" || ev.ctrlKey || ev.metaKey || ev.altKey) { return; }
      var a = document.activeElement;
      if (a && (a.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName))) { return; }
      if (a && a.closest && a.closest(".blocklyDiv, .blocklyWidgetDiv")) { return; }
      ev.preventDefault();
      oeffnen(true);
    });

    if (auswahlKnopf) {
      auswahlKnopf.addEventListener("click", function () {
        var eintraege = Object.keys(zustand.auswahl)
          .map(function (k) { return zielEintrag(zustand.auswahl[k]); })
          .filter(Boolean);
        if (!eintraege.length) { return; }
        Promise.resolve(optionen.onMehrfach(eintraege)).then(function () {
          zustand.auswahl = {};
          auswahlAktualisieren();
          zeigen();
        });
      });
    }

    // --- Ein-/Ausklappen -----------------------------------------------------------------
    function oeffnen(fokus) {
      if (eingeklappt && !wurzel.open) { wurzel.open = true; }
      if (!zustand.gezeigt) { zeigen(); }
      if (fokus) { suchfeld.focus(); suchfeld.select(); }
    }
    if (eingeklappt) {
      wurzel.addEventListener("toggle", function () { if (wurzel.open && !zustand.gezeigt) { zeigen(); } });
    } else {
      zeigen();
    }

    return {
      oeffnen: oeffnen,
      melden: melden,
      aktualisieren: function () { if (zustand.gezeigt) { auswahlAktualisieren(); zeigen(); } },
      /* Zielsystem gewechselt → Plattformfilter zieht mit */
      zielGeaendert: function () {
        plattformSetzen(zielPlattform() || "alle", false);
        auswahlAktualisieren();
        if (zustand.gezeigt) { zeigen(); }
      }
    };
  }

  window.SoftwareKatalog = { mount: mount };

  // ======================================================================================
  // Adapter je Seite
  // ======================================================================================

  /* Paketfeld im Formular befüllen (+ passenden Paketmanager im selben Schritt bzw. Formular). */
  function feldBefuellen(feld, eintrag) {
    feld.value = eintrag.id;
    feld.dispatchEvent(new Event("input", { bubbles: true }));
    feld.dispatchEvent(new Event("change", { bubbles: true }));
    var behaelter = feld.closest("li.schritt") || feld.form;
    var auswahl = behaelter && behaelter.querySelector("select[name$='.paketmanager']");
    if (auswahl && auswahl.querySelector("option[value='" + eintrag.feld + "']")) {
      auswahl.value = eintrag.feld;
      auswahl.dispatchEvent(new Event("change", { bubbles: true }));
    }
    feld.focus();
  }

  /* Merkt sich das zuletzt fokussierte Paketname-Feld; Fokus darauf klappt den Katalog auf. */
  function paketfeldVerfolgen(wurzel, katalog) {
    var letztes = null;
    document.addEventListener("focusin", function (ev) {
      var z = ev.target;
      if (wurzel.contains(z)) { return; }
      if (z.matches && z.matches("input[data-typ='paketname']")) { letztes = z; katalog.oeffnen(false); }
      else if (z.matches && z.matches("input, select, textarea")) { letztes = null; }
    });
    return function () { return letztes && document.body.contains(letztes) ? letztes : null; };
  }

  function zielRadios(container) {
    return function () {
      var r = container && container.querySelector("input[name=ziel]:checked");
      return r ? window.OkmKatalogSuche.ZIEL_PLATTFORM[r.value] || "" : "";
    };
  }

  var ADAPTER = {
    seite: function (wurzel, daten) {
      return mount(wurzel, { daten: daten });
    },

    rezept: function (wurzel, daten) {
      var feldImFormular = function () { return document.querySelector("form input[data-typ='paketname']"); };
      var paketfeld = null;
      var katalog = mount(wurzel, {
        daten: daten,
        zielPlattform: function () { return window.OkmKatalogSuche.ZIEL_PLATTFORM[wurzel.dataset.ziel] || ""; },
        kannUebernehmen: function () { return !!feldImFormular(); },
        onUebernehmen: function (eintrag) {
          var feld = (paketfeld && paketfeld()) || feldImFormular();
          if (feld) { feldBefuellen(feld, eintrag); katalog.melden(eintrag.id + " eingetragen."); }
        }
      });
      paketfeld = paketfeldVerfolgen(wurzel, katalog);
      return katalog;
    },

    baukasten: function (wurzel, daten) {
      var bk = window.OkmBaukasten;
      var zielWahl = document.getElementById("ziel-wahl");
      var paketfeld = null;
      var katalog = null;
      function anhaengen(eintraege) {
        var kette = Promise.resolve();
        eintraege.forEach(function (e) {
          kette = kette.then(function () {
            return bk.hinzufuegen("paket_installieren", { paket: e.id, paketmanager: e.feld });
          });
        });
        return kette.then(function () {
          katalog.melden(eintraege.length === 1 ? eintraege[0].id + " zum Script hinzugefügt."
            : eintraege.length + " Pakete zum Script hinzugefügt.");
        });
      }
      katalog = mount(wurzel, {
        daten: daten,
        zielPlattform: zielRadios(zielWahl),
        // Fokussiertes Paketfeld → genau dieses Feld; sonst neuen Schritt anhängen
        onUebernehmen: function (eintrag) {
          var feld = paketfeld && paketfeld();
          if (feld) { feldBefuellen(feld, eintrag); katalog.melden(eintrag.id + " eingetragen."); }
          else { anhaengen([eintrag]); }
        },
        onMehrfach: anhaengen
      });
      paketfeld = paketfeldVerfolgen(wurzel, katalog);
      if (zielWahl) { zielWahl.addEventListener("change", katalog.zielGeaendert); }
      // Neuer Schritt „Paket installieren“ → Katalog aufklappen
      var schritte = document.getElementById("schrittliste");
      if (schritte && window.MutationObserver) {
        new MutationObserver(function (aenderungen) {
          aenderungen.forEach(function (a) {
            a.addedNodes.forEach(function (n) {
              if (n.nodeType === 1 && n.matches("li.schritt[data-block=paket_installieren]")) { katalog.oeffnen(false); }
            });
          });
        }).observe(schritte, { childList: true });
      }
      return katalog;
    },

    blockly: function (wurzel, daten) {
      var zielWahl = document.getElementById("bl-ziel");
      var TYP = "bk_paket_installieren";
      var katalog = null;
      function ausgewaehlt() {
        var B = window.Blockly;
        if (!B) { return null; }
        if (B.getSelected) { return B.getSelected(); }
        return B.selected || null;
      }
      function uebernehmen(eintrag) {
        var bl = window.okmBlockly;
        if (!bl) { return; }
        var ws = bl.arbeitsflaeche;
        var sel = ausgewaehlt();
        if (sel && sel.type === TYP) {
          // Ausgewählter „Paket installieren“-Baustein → nur dessen ID setzen
          sel.setFieldValue(eintrag.id, "paket");
          sel.setFieldValue(eintrag.feld, "paketmanager");
          katalog.melden(eintrag.id + " eingetragen.");
          return;
        }
        var neu = ws.newBlock(TYP);
        neu.setFieldValue(eintrag.id, "paket");
        neu.setFieldValue(eintrag.feld, "paketmanager");
        neu.initSvg();
        neu.render();
        if (sel && sel.type === "ablauf_start") {
          sel.getInput("SCHRITTE").connection.connect(neu.previousConnection);
        } else if (sel && sel.nextConnection) {
          sel.nextConnection.connect(neu.previousConnection);  // unter dem ausgewählten Baustein einfügen
        } else {
          // Nichts ausgewählt → ans Ende des Scripts hängen
          var start = ws.getTopBlocks(false).filter(function (b) { return b.type === "ablauf_start"; })[0];
          if (start) {
            var verbindung = start.getInput("SCHRITTE").connection;
            var letzter = verbindung.targetBlock();
            while (letzter && letzter.getNextBlock()) { letzter = letzter.getNextBlock(); }
            if (letzter) { letzter.nextConnection.connect(neu.previousConnection); }
            else { verbindung.connect(neu.previousConnection); }
          }
        }
        // Neuen Baustein auswählen – das nächste ＋ setzt dann dessen ID
        var B = window.Blockly;
        if (B.common && B.common.setSelected) { B.common.setSelected(neu); } else if (neu.select) { neu.select(); }
        katalog.melden(eintrag.id + " als Baustein hinzugefügt.");
      }
      katalog = mount(wurzel, {
        daten: daten,
        zielPlattform: zielRadios(zielWahl),
        onUebernehmen: uebernehmen
      });
      if (zielWahl) { zielWahl.addEventListener("change", katalog.zielGeaendert); }
      // „Paket installieren“ angelegt oder ausgewählt → Katalog aufklappen
      function beobachten() {
        var bl = window.okmBlockly;
        if (!bl) { return false; }
        bl.arbeitsflaeche.addChangeListener(function (ev) {
          var id = ev.newElementId || ev.blockId;
          var b = id && bl.arbeitsflaeche.getBlockById(id);
          if (b && b.type === TYP && (ev.type === "selected" || ev.type === "create")) { katalog.oeffnen(false); }
        });
        return true;
      }
      // blockly-modus.js richtet die Arbeitsfläche erst nach diesem Script ein
      if (!beobachten()) { window.addEventListener("load", beobachten); }
      return katalog;
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    var wurzel = document.getElementById("software-katalog");
    var datenEl = document.getElementById("software-katalog-daten");
    if (!wurzel || !datenEl || !window.OkmKatalogSuche) { return; }
    var adapter = ADAPTER[wurzel.dataset.modus];
    if (adapter) { window.okmKatalog = adapter(wurzel, JSON.parse(datenEl.textContent)); }
  });
})();
