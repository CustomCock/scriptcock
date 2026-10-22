/* okm Script-Baukasten – Software-Katalog (Panel im Baukasten/Rezept und Seite /software).
   Daten: eingebettetes JSON (#software-katalog-daten). Suche: katalog-suche.js. Kein innerHTML mit Daten. */
(function () {
  "use strict";

  var LABEL = { winget: "winget", brew: "brew", brew_cask: "brew --cask", apt: "apt", flatpak: "flatpak" };
  var FELD_PLATTFORM = { winget: "windows", brew: "macos", brew_cask: "macos", apt: "linux", flatpak: "linux" };
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

  /* ID als <code> mit Umbruchstellen (<wbr>) nach . - / – damit lange IDs nicht mitten im Wort brechen.
     <wbr> ist kein Zeichen: Markieren und Kopieren liefern weiterhin exakt die ID. */
  function idCode(id) {
    var code = el("code");
    var teil = "";
    for (var i = 0; i < id.length; i += 1) {
      teil += id.charAt(i);
      if (".-/".indexOf(id.charAt(i)) >= 0 && i < id.length - 1) {
        code.appendChild(document.createTextNode(teil));
        code.appendChild(document.createElement("wbr"));
        teil = "";
      }
    }
    code.appendChild(document.createTextNode(teil));
    return code;
  }

  function start() {
    var wurzel = document.getElementById("software-katalog");
    var daten = document.getElementById("software-katalog-daten");
    if (!wurzel || !daten || !window.OkmKatalogSuche) { return; }
    var S = window.OkmKatalogSuche;
    var pakete = JSON.parse(daten.textContent);
    var index = S.baueIndex(pakete);
    var modus = wurzel.dataset.modus;
    var suchfeld = document.getElementById("katalog-suche");
    var liste = document.getElementById("katalog-liste");
    var anzahl = document.getElementById("katalog-anzahl");
    var leer = wurzel.querySelector(".katalog-leer");
    var meldung = document.getElementById("katalog-meldung");
    var auswahlKnopf = wurzel.querySelector("[data-katalog-auswahl]");
    var oeffnen = document.querySelectorAll("[data-katalog-oeffnen]");

    var zustand = { plattform: "alle", kategorien: [], treffer: [], aktiv: -1, auswahl: {} };
    var letztesPaketfeld = null;

    function melden(text) {
      meldung.textContent = "";
      setTimeout(function () { meldung.textContent = text; }, 30);
    }

    // --- Zielsystem → Plattform ------------------------------------------------
    function zielsystem() {
      if (window.OkmBaukasten) { return window.OkmBaukasten.ziel(); }
      return wurzel.dataset.ziel || "";
    }
    function zielPlattform() { return S.ZIEL_PLATTFORM[zielsystem()] || ""; }

    // --- Übernahme ins Script --------------------------------------------------
    function paketfeld() {
      if (letztesPaketfeld && document.body.contains(letztesPaketfeld)) { return letztesPaketfeld; }
      if (modus === "rezept") { return document.querySelector("form input[data-typ='paketname']"); }
      return null;
    }
    function kannUebernehmen() {
      return modus === "baukasten" || (modus === "rezept" && !!document.querySelector("form input[data-typ='paketname']"));
    }
    function feldBefuellen(feld, eintrag) {
      feld.value = eintrag.id;
      feld.dispatchEvent(new Event("input", { bubbles: true }));
      feld.dispatchEvent(new Event("change", { bubbles: true }));
      // Passenden Paketmanager im selben Schritt bzw. Formular mitsetzen
      var behaelter = feld.closest("li.schritt") || feld.form;
      var auswahl = behaelter && behaelter.querySelector("select[name$='.paketmanager']");
      if (auswahl && auswahl.querySelector("option[value='" + eintrag.feld + "']")) {
        auswahl.value = eintrag.feld;
        auswahl.dispatchEvent(new Event("change", { bubbles: true }));
      }
      feld.focus();
      melden(eintrag.id + " eingetragen.");
    }
    function bausteinHinzufuegen(eintraege) {
      var kette = Promise.resolve();
      eintraege.forEach(function (e) {
        kette = kette.then(function () {
          return window.OkmBaukasten.hinzufuegen("paket_installieren", { paket: e.id, paketmanager: e.feld });
        });
      });
      return kette.then(function () {
        melden(eintraege.length === 1 ? eintraege[0].id + " zum Script hinzugefügt." : eintraege.length + " Pakete zum Script hinzugefügt.");
      });
    }
    function uebernehmen(eintrag) {
      var feld = paketfeld();
      if (feld) { feldBefuellen(feld, eintrag); return; }
      if (window.OkmBaukasten) { bausteinHinzufuegen([eintrag]); }
    }
    /* ID eines Pakets, die zum aktuellen Zielsystem passt (für Auswahl-Checkboxen). */
    function zielEintrag(paket) {
      var ids = S.ids(paket, zielPlattform() || "alle");
      return ids.length ? ids[0] : null;
    }

    // --- Kopieren --------------------------------------------------------------
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

    // --- Darstellung -----------------------------------------------------------
    function idZeile(eintrag, uebernahme) {
      var zeile = el("div", "katalog-id");
      zeile.appendChild(el("span", "katalog-id-label", LABEL[eintrag.feld]));
      var code = idCode(eintrag.id);
      zeile.appendChild(code);
      var knoepfe = el("span", "katalog-id-knoepfe");
      var kop = el("button", "knopf-klein", "⧉");
      kop.type = "button";
      kop.title = "ID kopieren";
      kop.setAttribute("aria-label", "ID kopieren: " + eintrag.id);
      kop.addEventListener("click", function () { kopieren(eintrag.id, kop, code); });
      knoepfe.appendChild(kop);
      var bef = el("button", "knopf-klein", "▾");
      bef.type = "button";
      bef.title = "Installationsbefehl kopieren";
      bef.setAttribute("aria-label", "Installationsbefehl kopieren: " + eintrag.id);
      bef.addEventListener("click", function () { kopieren(S.befehl(eintrag.feld, eintrag.id), bef, code); });
      knoepfe.appendChild(bef);
      if (uebernahme) {
        var plus = el("button", "knopf-klein knopf-uebernehmen", "＋");
        plus.type = "button";
        var passt = !zielPlattform() || FELD_PLATTFORM[eintrag.feld] === zielPlattform();
        plus.disabled = !passt;
        plus.title = passt ? "Ins Script übernehmen" : "Passt nicht zum gewählten Zielsystem";
        plus.setAttribute("aria-label", "Ins Script übernehmen: " + eintrag.id);
        plus.addEventListener("click", function () { uebernehmen(eintrag); });
        knoepfe.appendChild(plus);
      }
      zeile.appendChild(knoepfe);
      return zeile;
    }

    function eintragElement(t, nr, anfrage) {
      var p = t.paket;
      var li = el("li", "katalog-eintrag");
      li.id = "katalog-eintrag-" + nr;
      var kopf = el("div", "katalog-eintrag-kopf");
      if (modus === "baukasten") {
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
      li.appendChild(markiert("p", "katalog-beschreibung", p.beschreibung, anfrage));
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
        z.appendChild(el("code", null, p.intern));
        li.appendChild(z);
      }
      return li;
    }

    function zeigen() {
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

    // --- Filter ----------------------------------------------------------------
    function plattformSetzen(wert, merken) {
      zustand.plattform = S.PLATTFORMEN[wert] ? wert : "alle";
      wurzel.querySelectorAll("[data-plattform]").forEach(function (k) {
        k.setAttribute("aria-pressed", String(k.dataset.plattform === zustand.plattform));
      });
      if (merken) { schreiben(SPEICHER_PLATTFORM, zustand.plattform); }
    }
    function kategorienSetzen(liste_) {
      var vorhanden = {};
      wurzel.querySelectorAll("[data-kategorie]").forEach(function (k) { vorhanden[k.dataset.kategorie] = k; });
      zustand.kategorien = liste_.filter(function (k) { return vorhanden[k]; });
      Object.keys(vorhanden).forEach(function (k) {
        vorhanden[k].setAttribute("aria-pressed", String(zustand.kategorien.indexOf(k) >= 0));
      });
      var zaehler = wurzel.querySelector("[data-kategorien-anzahl]");
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

    // Startzustand: Zielsystem gewinnt (Baukasten/Rezept), sonst gemerkte Plattform
    plattformSetzen(zielPlattform() || lesen(SPEICHER_PLATTFORM) || "alle", false);
    try { kategorienSetzen(JSON.parse(lesen(SPEICHER_KATEGORIEN) || "[]") || []); } catch (e) { kategorienSetzen([]); }

    // Zielsystem im Baukasten gewechselt → Filter zieht mit
    var zielWahl = document.getElementById("ziel-wahl");
    if (zielWahl) {
      zielWahl.addEventListener("change", function () {
        plattformSetzen(zielPlattform(), false);
        auswahlAktualisieren();
        zeigen();
      });
    }

    // --- Suche & Tastatur --------------------------------------------------------
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
        var knopf = li && li.querySelector(".katalog-id .knopf-klein");
        if (knopf) { knopf.click(); }
      } else if (ev.key === "Escape") {
        ev.preventDefault();
        ev.stopPropagation();
        if (suchfeld.value) { suchfeld.value = ""; zeigen(); } else if (modus !== "seite") { schliessen(); }
      }
    });

    document.addEventListener("keydown", function (ev) {
      if (ev.key === "/" && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
        var a = document.activeElement;
        var tippt = a && (a.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName));
        if (tippt) { return; }
        ev.preventDefault();
        oeffnenPanel();
      } else if (ev.key === "Escape" && modus !== "seite" && !wurzel.hidden) {
        schliessen();
      }
    });

    // Merken, welches Paketname-Feld zuletzt aktiv war (dann füllt „＋“ nur dieses Feld)
    document.addEventListener("focusin", function (ev) {
      var z = ev.target;
      if (wurzel.contains(z)) { return; }
      if (z.matches && z.matches("input[data-typ='paketname']")) { letztesPaketfeld = z; }
      else if (z.matches && z.matches("input, select, textarea")) { letztesPaketfeld = null; }
    });

    // --- Panel öffnen/schließen ----------------------------------------------------
    function oeffnenPanel() {
      if (modus === "seite") { suchfeld.focus(); suchfeld.select(); return; }
      wurzel.hidden = false;
      document.body.classList.add("katalog-offen");
      oeffnen.forEach(function (k) { k.setAttribute("aria-expanded", "true"); });
      if (!liste.childElementCount) { zeigen(); }
      suchfeld.focus();
      suchfeld.select();
    }
    function schliessen() {
      if (modus === "seite") { return; }
      wurzel.hidden = true;
      document.body.classList.remove("katalog-offen");
      oeffnen.forEach(function (k) { k.setAttribute("aria-expanded", "false"); });
      if (oeffnen.length) { oeffnen[0].focus(); }
    }
    oeffnen.forEach(function (k) {
      k.addEventListener("click", function () { if (wurzel.hidden) { oeffnenPanel(); } else { schliessen(); } });
    });
    var zu = wurzel.querySelector("[data-katalog-schliessen]");
    if (zu) { zu.addEventListener("click", schliessen); }

    if (auswahlKnopf) {
      auswahlKnopf.addEventListener("click", function () {
        var eintraege = Object.keys(zustand.auswahl)
          .map(function (k) { return zielEintrag(zustand.auswahl[k]); })
          .filter(Boolean);
        if (!eintraege.length || !window.OkmBaukasten) { return; }
        bausteinHinzufuegen(eintraege).then(function () {
          zustand.auswahl = {};
          auswahlAktualisieren();
          zeigen();
        });
      });
    }

    if (modus === "seite") { zeigen(); }
  }

  document.addEventListener("DOMContentLoaded", start);
})();
