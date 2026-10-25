/* okm Script-Baukasten – schlankes Vanilla-JS (keine Inline-Scripte wegen CSP) */
(function () {
  "use strict";

  function hervorheben(wurzel) {
    if (!window.hljs) { return; }
    wurzel.querySelectorAll("pre code[class*='language-']").forEach(function (el) {
      if (!el.dataset.highlighted) { window.hljs.highlightElement(el); }
    });
  }

  function kopieren(text, knopf) {
    function erfolg() {
      var alt = knopf.textContent;
      knopf.textContent = "✓ Kopiert";
      knopf.classList.add("kopiert");
      setTimeout(function () { knopf.textContent = alt; knopf.classList.remove("kopiert"); }, 2000);
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(erfolg, function () { altKopieren(text) && erfolg(); });
    } else if (altKopieren(text)) {
      erfolg();
    }
  }

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

  /* Script-Text über den Export-Endpunkt in das Dateiformat des Ziels bringen (Zeilenenden, chcp …).
     Liefert ein Promise mit der Response (Bytes für den Download, Text fürs Kopieren). */
  function exportieren(text, ziel, dateiname, manuell) {
    var basis = document.body.dataset.basis || "";
    return fetch(basis + "/api/script/export", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Okm-Request": "1" },
      body: JSON.stringify({ text: text, ziel: ziel, dateiname: dateiname || "script", manuell_bearbeitet: !!manuell })
    }).then(function (antwort) {
      if (!antwort.ok) { throw new Error("Export fehlgeschlagen (" + antwort.status + ")"); }
      return antwort;
    });
  }
  window.OkmExport = exportieren;
  window.OkmKopieren = kopieren;

  document.addEventListener("click", function (ev) {
    var knopf = ev.target.closest("[data-kopieren]");
    if (!knopf) { return; }
    var quelle = document.querySelector(knopf.getAttribute("data-kopieren"));
    if (!quelle) { return; }
    var ziel = knopf.getAttribute("data-ziel");
    if (!ziel) { kopieren(quelle.textContent, knopf); return; }
    // Gleiche Regeln wie beim Download; schlägt der Export fehl, wird der angezeigte Text kopiert.
    exportieren(quelle.textContent, ziel).then(function (a) { return a.text(); }).then(
      function (text) { kopieren(text.replace(/^\ufeff/, ""), knopf); },
      function () { kopieren(quelle.textContent, knopf); }
    );
  });

  // --- Baustein-Palette (Listen-Modus) ----------------------------------------
  /* Aufklappbare Kategorien, Suche (wie Software-Katalog), Favoriten und „Zuletzt benutzt“ (localStorage),
     „Nur für <Ziel>“, Tastatur und Hinzufügen ohne Ziehen (unter den markierten Schritt). */
  var SPEICHER = { offen: "okm.palette.offen", favoriten: "okm.palette.favoriten", zuletzt: "okm.bausteine.zuletzt",
    nurZiel: "okm.palette.nurziel" };
  function lesenJson(k, standard) {
    try { var w = JSON.parse(window.localStorage.getItem(k)); return w === null ? standard : w; } catch (e) { return standard; }
  }
  function schreibenJson(k, w) {
    try { window.localStorage.setItem(k, JSON.stringify(w)); } catch (e) { /* ohne Speicher geht es auch */ }
  }

  function palette(liste, ziel, hinzufuegen) {
    var wurzel = document.getElementById("bk-palette");
    var leer = { markieren: function () {}, zielGeaendert: function () {}, benutzt: function () {} };
    if (!wurzel || !window.OkmBausteinSuche) { return leer; }
    var B = window.OkmBausteinSuche;
    var suchfeld = document.getElementById("bk-suche");
    var nurZiel = document.getElementById("bk-nur-ziel");
    var anzahlEl = wurzel.querySelector("[data-palette-anzahl]");
    var leerEl = wurzel.querySelector(".palette-leer");
    var gruppen = [].slice.call(wurzel.querySelectorAll(".palette-gruppe[data-kategorie]"));
    var fest = { favoriten: wurzel.querySelector("[data-fest=favoriten]"), zuletzt: wurzel.querySelector("[data-fest=zuletzt]") };
    var original = [].slice.call(wurzel.querySelectorAll(".palette-gruppe[data-kategorie] .palette-block"));
    var nachId = {};
    original.forEach(function (el) { nachId[el.dataset.block] = el; });
    var index = B.baueIndex(original.map(function (el) {
      return { id: el.dataset.block, name: el.dataset.name, beschreibung: el.dataset.beschreibung, kategorie: el.dataset.kategorie };
    }));
    var zustand = {
      favoriten: lesenJson(SPEICHER.favoriten, []).filter(function (id) { return nachId[id]; }),
      zuletzt: lesenJson(SPEICHER.zuletzt, []).filter(function (id) { return nachId[id]; }),
      offen: lesenJson(SPEICHER.offen, []),
      vorSuche: null,  // Auf/Zu vor der Suche – Esc stellt ihn wieder her
      markiert: null
    };
    nurZiel.checked = lesenJson(SPEICHER.nurZiel, true) !== false;

    function verfuegbar(el) { return el.dataset.ziele.split(" ").indexOf(ziel()) >= 0; }
    function zielName() {
      var r = document.querySelector("#ziel-wahl input[name=ziel]:checked");
      return r ? r.parentNode.querySelector("span").textContent : "";
    }

    // --- Namen mit Hervorhebung (nur Textknoten) ---
    function nameSetzen(el, anfrage) {
      var span = el.querySelector(".palette-name");
      var text = el.dataset.name;
      span.textContent = "";
      var pos = 0;
      (anfrage ? B.trefferBereiche(text, anfrage) : []).forEach(function (b) {
        if (b[0] > pos) { span.appendChild(document.createTextNode(text.slice(pos, b[0]))); }
        var m = document.createElement("mark");
        m.textContent = text.slice(b[0], b[1]);
        span.appendChild(m);
        pos = b[1];
      });
      if (pos < text.length) { span.appendChild(document.createTextNode(text.slice(pos))); }
    }

    // --- Favoriten / Zuletzt benutzt: Kopien der Bausteine oben ---
    function festeGruppe(name, ids) {
      var gruppe = fest[name];
      var ul = gruppe.querySelector(".palette-liste");
      ul.textContent = "";
      ids.forEach(function (id) {
        var kopie = nachId[id].cloneNode(true);
        kopie.removeAttribute("aria-describedby");
        kopie.querySelector(".palette-beschreibung").removeAttribute("id");
        ul.appendChild(kopie);
      });
    }
    function festeAktualisieren() {
      festeGruppe("favoriten", zustand.favoriten);
      festeGruppe("zuletzt", zustand.zuletzt);
      original.forEach(function (el) {
        var an = zustand.favoriten.indexOf(el.dataset.block) >= 0;
        wurzel.querySelectorAll(".palette-block[data-block='" + el.dataset.block + "'] [data-stern]").forEach(function (s) {
          s.setAttribute("aria-pressed", String(an));
          s.textContent = an ? "★" : "☆";
          s.title = an ? "Favorit entfernen" : "Als Favorit merken";
        });
      });
      filtern();
    }

    // --- Filtern: Ziel, Suche, Anzahl je Kategorie ---
    function filtern() {
      var anfrage = suchfeld.value.trim();
      var treffer = null;
      if (anfrage) {
        treffer = {};
        B.suche(index, anfrage).forEach(function (t) { treffer[t.baustein.id] = true; });
      }
      var sichtbarGesamt = 0;
      wurzel.querySelectorAll(".palette-block").forEach(function (el) {
        var ok = verfuegbar(el);
        el.classList.toggle("nicht-verfuegbar", !ok);
        el.querySelector(".hinzufuegen").disabled = !ok;
        el.title = ok ? el.dataset.beschreibung : "Unter " + zielName() + " nicht verfügbar";
        var sichtbar = (ok || !nurZiel.checked) && (!treffer || treffer[el.dataset.block]);
        el.hidden = !sichtbar;
        nameSetzen(el, anfrage);
      });
      gruppen.concat([fest.favoriten, fest.zuletzt]).forEach(function (g) {
        var bloecke = [].slice.call(g.querySelectorAll(".palette-block"));
        var sichtbar = bloecke.filter(function (el) { return !el.hidden; }).length;
        var moeglich = bloecke.filter(verfuegbar).length;
        g.querySelector(".palette-zahl").textContent = String(treffer ? sichtbar : moeglich);
        g.hidden = sichtbar === 0;
        if (g.dataset.kategorie) {
          sichtbarGesamt += sichtbar;
          if (treffer) { g.open = sichtbar > 0; }
        }
      });
      leerEl.hidden = sichtbarGesamt > 0;
      anzahlEl.textContent = treffer ? (sichtbarGesamt === 1 ? "1 Treffer" : sichtbarGesamt + " Treffer") : "";
      wurzel.querySelector("[data-ziel-name]").textContent = zielName();
    }

    // --- Auf/Zu merken ---
    function offenMerken() {
      if (zustand.vorSuche) { return; }  // während der Suche nicht überschreiben
      zustand.offen = gruppen.filter(function (g) { return g.open; }).map(function (g) { return g.dataset.kategorie; });
      schreibenJson(SPEICHER.offen, zustand.offen);
    }
    gruppen.forEach(function (g) {
      g.open = zustand.offen.indexOf(g.dataset.kategorie) >= 0;  // Standard: alle zu
      g.addEventListener("toggle", offenMerken);
    });
    function alle(offen) {
      zustand.vorSuche = null;
      gruppen.forEach(function (g) { g.open = offen; });
      offenMerken();
    }
    wurzel.querySelector("[data-alle-auf]").addEventListener("click", function () { alle(true); });
    wurzel.querySelector("[data-alle-zu]").addEventListener("click", function () { alle(false); });
    nurZiel.addEventListener("change", function () { schreibenJson(SPEICHER.nurZiel, nurZiel.checked); filtern(); });

    // --- Suche ---
    var zeit = null;
    suchfeld.addEventListener("input", function () {
      if (suchfeld.value.trim() && !zustand.vorSuche) {
        zustand.vorSuche = gruppen.map(function (g) { return g.open; });
      }
      clearTimeout(zeit);
      zeit = setTimeout(function () {
        filtern();
        if (!suchfeld.value.trim()) { sucheBeenden(false); }
      }, 80);
    });
    function sucheBeenden(leeren) {
      if (leeren) { suchfeld.value = ""; }
      if (zustand.vorSuche) {
        var vorher = zustand.vorSuche;
        gruppen.forEach(function (g, i) { g.open = vorher[i]; });
        zustand.vorSuche = null;
      }
      filtern();
    }

    // --- Hinzufügen (Doppelklick, Enter, ＋): ans Ende oder unter den markierten Schritt ---
    function markieren(schritt) {
      if (zustand.markiert) { zustand.markiert.classList.remove("markiert"); }
      zustand.markiert = schritt && liste.contains(schritt) ? schritt : null;
      if (zustand.markiert) { zustand.markiert.classList.add("markiert"); }
    }
    function benutzt(id) {
      zustand.zuletzt = B.zuletztDazu(zustand.zuletzt, id, 8);
      schreibenJson(SPEICHER.zuletzt, zustand.zuletzt);
      festeAktualisieren();
    }
    function dazu(el) {
      if (!el || el.classList.contains("nicht-verfuegbar")) { return; }
      var id = el.dataset.block;
      benutzt(id);
      var nach = zustand.markiert && liste.contains(zustand.markiert) ? zustand.markiert : null;
      if (nach) {
        var platz = document.createElement("li");
        platz.className = "schritt-platzhalter";
        nach.parentNode.insertBefore(platz, nach.nextSibling);
        hinzufuegen(id, platz).then(function () { markieren(nach.nextElementSibling); });
      } else {
        hinzufuegen(id);
      }
    }
    wurzel.addEventListener("click", function (ev) {
      var stern = ev.target.closest("[data-stern]");
      var block = ev.target.closest(".palette-block");
      if (stern && block) {
        var id = block.dataset.block;
        var pos = zustand.favoriten.indexOf(id);
        if (pos >= 0) { zustand.favoriten.splice(pos, 1); } else { zustand.favoriten.push(id); }
        schreibenJson(SPEICHER.favoriten, zustand.favoriten);
        festeAktualisieren();
        return;
      }
      if (ev.target.closest("[data-hinzufuegen]") && block) { dazu(block); }
    });
    wurzel.addEventListener("dblclick", function (ev) {
      var block = ev.target.closest(".palette-block");
      if (block && !ev.target.closest("button")) { dazu(block); }
    });

    // --- Tastatur ---
    function fokussierbar() {
      return [].slice.call(wurzel.querySelectorAll("#bk-palette-gruppen .palette-gruppe:not([hidden]) > summary, " +
        "#bk-palette-gruppen .palette-gruppe[open]:not([hidden]) .palette-block:not([hidden])"));
    }
    function bewegen(von, schritt) {
      var liste2 = fokussierbar();
      var i = liste2.indexOf(von);
      var ziel2 = liste2[i + schritt];
      if (ziel2) { ziel2.focus(); } else if (schritt < 0) { suchfeld.focus(); }
    }
    suchfeld.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") {
        ev.preventDefault();
        ev.stopPropagation();
        sucheBeenden(true);
      } else if (ev.key === "ArrowDown") {
        ev.preventDefault();
        var erster = fokussierbar().filter(function (e) { return e.classList.contains("palette-block"); })[0];
        (erster || fokussierbar()[0] || suchfeld).focus();
      } else if (ev.key === "Enter") {
        ev.preventDefault();
        var t = fokussierbar().filter(function (e) { return e.classList.contains("palette-block"); })[0];
        if (t && suchfeld.value.trim()) { dazu(t); }
      }
    });
    wurzel.addEventListener("keydown", function (ev) {
      var el = ev.target;
      var istBlock = el.classList && el.classList.contains("palette-block");
      var istKopf = el.tagName === "SUMMARY";
      if (!istBlock && !istKopf) { return; }
      if (ev.key === "ArrowDown") { ev.preventDefault(); bewegen(el, 1); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); bewegen(el, -1); }
      else if (ev.key === "ArrowRight" && istKopf) { ev.preventDefault(); el.parentNode.open = true; }
      else if (ev.key === "ArrowLeft") {
        ev.preventDefault();
        var g = el.closest(".palette-gruppe");
        if (istBlock) { g.querySelector("summary").focus(); } else { g.open = false; }
      } else if (ev.key === "Enter" && istBlock) { ev.preventDefault(); dazu(el); }
      else if (ev.key === "Escape" && suchfeld.value) { ev.preventDefault(); sucheBeenden(true); suchfeld.focus(); }
    });
    // „/“ fokussiert die Suche (Vorrang vor dem Software-Katalog auf dieser Seite)
    document.addEventListener("keydown", function (ev) {
      if (ev.key !== "/" || ev.ctrlKey || ev.metaKey || ev.altKey) { return; }
      var a = document.activeElement;
      if (a && (a.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName))) { return; }
      ev.preventDefault();
      ev.stopImmediatePropagation();
      wurzel.classList.add("offen");
      suchfeld.focus();
      suchfeld.select();
    });

    // --- Schmale Bildschirme: Leiste auf/zu ---
    var schalter = wurzel.querySelector(".bk-palette-schalter");
    schalter.addEventListener("click", function () {
      var auf = !wurzel.classList.contains("offen");
      wurzel.classList.toggle("offen", auf);
      schalter.setAttribute("aria-expanded", String(auf));
    });

    festeAktualisieren();
    return { markieren: markieren, zielGeaendert: filtern, benutzt: benutzt };
  }

  // --- Freier Baukasten -------------------------------------------------------
  function baukasten() {
    var form = document.getElementById("baukasten");
    if (!form) { return; }
    var liste = document.getElementById("schrittliste");
    var basis = form.dataset.basis || "";

    function ziel() {
      var r = form.querySelector("input[name=ziel]:checked");
      return r ? r.value : "powershell";
    }
    function aendern() {
      form.classList.toggle("bk-leer", !liste.querySelector("li.schritt"));
      window.htmx.trigger(form, "bk-aendern");
    }
    // werte (optional): Parameter vorbelegen, z. B. { paket: "7zip.7zip" } aus dem Software-Katalog
    function hinzufuegen(blockId, platzhalter, werte) {
      var url = basis + "/baukasten/schritt?block=" + encodeURIComponent(blockId) + "&ziel=" + encodeURIComponent(ziel());
      Object.keys(werte || {}).forEach(function (k) {
        url += "&p." + encodeURIComponent(k) + "=" + encodeURIComponent(werte[k]);
      });
      if (platzhalter) {
        return window.htmx.ajax("GET", url, { target: platzhalter, swap: "outerHTML" }).then(aendern);
      }
      return window.htmx.ajax("GET", url, { target: liste, swap: "beforeend" });
    }
    window.OkmBaukasten = {
      ziel: ziel,
      hinzufuegen: function (blockId, werte) { return hinzufuegen(blockId, null, werte); },
      // Schritt neu vom Server holen (z. B. nach „Richtlinie wählen …“), Position bleibt
      ersetzen: function (schritt, blockId, werte) { return hinzufuegen(blockId, schritt, werte); }
    };
    var pal = palette(liste, ziel, hinzufuegen);

    document.addEventListener("click", function (ev) {
      var schritt = ev.target.closest("li.schritt");
      if (!schritt) { return; }
      pal.markieren(schritt);
      if (ev.target.closest("[data-entfernen]")) {
        pal.markieren(null);
        schritt.remove();
        aendern();
      } else if (ev.target.closest("[data-hoch]") && schritt.previousElementSibling) {
        liste.insertBefore(schritt, schritt.previousElementSibling);
        aendern();
      } else if (ev.target.closest("[data-runter]") && schritt.nextElementSibling) {
        liste.insertBefore(schritt.nextElementSibling, schritt);
        aendern();
      }
    });

    form.addEventListener("change", function (ev) {
      if (ev.target.name === "ziel") {
        pal.zielGeaendert();
        try { window.history.replaceState(null, "", "?ziel=" + encodeURIComponent(ziel())); } catch (e) { /* egal */ }
      }
    });

    document.body.addEventListener("htmx:afterSwap", function (ev) {
      if (ev.target === liste) { aendern(); }
    });

    if (window.Sortable) {
      document.querySelectorAll(".palette-liste").forEach(function (ul) {
        window.Sortable.create(ul, {
          group: { name: "bausteine", pull: "clone", put: false },
          sort: false,
          filter: ".nicht-verfuegbar, .hinzufuegen, .palette-stern",
          preventOnFilter: false,
          delay: 150,
          delayOnTouchOnly: true,
          animation: 150
        });
      });
      window.Sortable.create(liste, {
        group: { name: "bausteine", pull: false, put: true },
        handle: ".griff, .palette-name",
        animation: 150,
        onAdd: function (evt) { pal.benutzt(evt.item.dataset.block); hinzufuegen(evt.item.dataset.block, evt.item); },
        onUpdate: aendern
      });
    }

    // „Erneut öffnen“: vorbelegte Schritte sofort in der Vorschau zeigen
    if (liste.querySelector("li.schritt")) { setTimeout(aendern, 0); }
  }

  // --- Rezept-Übersicht: Live-Suche (umlauttolerant wie der Software-Katalog) + Kategorie-Chips ---
  function rezeptFilter() {
    var form = document.getElementById("rezept-filter");
    var S = window.OkmKatalogSuche;
    if (!form || !S) { return; }
    var feld = document.getElementById("suchfeld");
    var anzahl = document.getElementById("rezept-anzahl");
    var leer = document.getElementById("rezept-leer");
    var zuletzt = document.getElementById("zuletzt-benutzt");
    var chips = form.querySelectorAll("[data-kategorie]");
    var karten = [].slice.call(document.querySelectorAll("#rezeptliste .rezept-karte")).map(function (k) {
      return { el: k, text: S.normalisiere(k.dataset.suche), kategorie: k.dataset.kategorie };
    });
    function filtern() {
      var woerter = feld.value.trim().split(/\s+/).map(S.normalisiere).filter(Boolean);
      var kategorien = [].slice.call(chips).filter(function (c) { return c.getAttribute("aria-pressed") === "true"; })
        .map(function (c) { return c.dataset.kategorie; });
      var sichtbar = 0;
      karten.forEach(function (k) {
        var ok = woerter.every(function (w) { return k.text.indexOf(w) >= 0; }) &&
          (!kategorien.length || kategorien.indexOf(k.kategorie) >= 0);
        k.el.hidden = !ok;
        if (ok && !k.el.classList.contains("nicht-verfuegbar")) { sichtbar += 1; }
      });
      document.querySelectorAll("#rezeptliste .rezept-gruppe").forEach(function (g) {
        g.hidden = !g.querySelector(".rezept-karte:not([hidden])");
      });
      var gefiltert = woerter.length > 0 || kategorien.length > 0;
      if (zuletzt) { zuletzt.hidden = gefiltert; }
      anzahl.textContent = gefiltert ? (sichtbar === 1 ? "1 passendes Rezept" : sichtbar + " passende Rezepte") : "";
      leer.hidden = !!document.querySelector("#rezeptliste .rezept-karte:not([hidden])");
    }
    var zeit = null;
    feld.addEventListener("input", function () { clearTimeout(zeit); zeit = setTimeout(filtern, 100); });
    form.addEventListener("submit", function (ev) { ev.preventDefault(); filtern(); });
    chips.forEach(function (c) {
      c.addEventListener("click", function () {
        c.setAttribute("aria-pressed", String(c.getAttribute("aria-pressed") !== "true"));
        filtern();
      });
    });
    feld.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && feld.value) { feld.value = ""; filtern(); }
    });
    filtern();
  }

  // --- Tag-Feld für Listen (Parametertyp "liste") ------------------------------------
  /* Das ursprüngliche Textfeld bleibt Quelle für Formular, htmx und Live-Prüfung (Werte mit ", "
     getrennt); das Tag-Feld schreibt nur hinein. Ohne JavaScript bleibt das Textfeld nutzbar. */
  function tagfeld(quelle) {
    if (quelle.dataset.tagfeld) { return; }
    quelle.dataset.tagfeld = "1";
    var mitLeerzeichen = quelle.dataset.mitLeerzeichen === "ja";
    var trenner = mitLeerzeichen ? /[,;]/ : /[,;\s]/;
    var rahmen = document.createElement("div");
    rahmen.className = "tagfeld";
    var liste = document.createElement("ul");
    liste.className = "tagfeld-liste";
    var eingabe = document.createElement("input");
    eingabe.type = "text";
    eingabe.className = "tagfeld-eingabe";
    eingabe.autocomplete = "off";
    eingabe.spellcheck = false;
    eingabe.placeholder = quelle.placeholder;
    // Label und Beschreibung zeigen auf das sichtbare Eingabefeld
    eingabe.id = quelle.id;
    quelle.id = quelle.id + "-wert";
    eingabe.setAttribute("aria-describedby", quelle.getAttribute("aria-describedby") || "");
    quelle.classList.add("tagfeld-quelle");
    quelle.tabIndex = -1;
    quelle.setAttribute("aria-hidden", "true");
    quelle.parentNode.insertBefore(rahmen, quelle);
    rahmen.appendChild(liste);
    rahmen.appendChild(eingabe);

    function werte() {
      return Array.prototype.map.call(liste.querySelectorAll(".tag-text"), function (s) { return s.textContent; });
    }
    function speichern() {
      quelle.value = werte().join(", ");
      quelle.dispatchEvent(new Event("change", { bubbles: true }));
    }
    function tag(text) {
      text = text.trim();
      if (!text || werte().indexOf(text) >= 0) { return; }
      var li = document.createElement("li");
      li.className = "tag";
      var s = document.createElement("span");
      s.className = "tag-text";
      s.textContent = text;
      var weg = document.createElement("button");
      weg.type = "button";
      weg.className = "tag-weg";
      weg.textContent = "×";
      weg.setAttribute("aria-label", text + " entfernen");
      weg.addEventListener("click", function () { li.remove(); speichern(); eingabe.focus(); });
      li.appendChild(s);
      li.appendChild(weg);
      liste.appendChild(li);
    }
    function uebernehmen() {
      var teile = eingabe.value.split(trenner);
      if (teile.length === 1 && !teile[0].trim()) { return; }
      teile.forEach(tag);
      eingabe.value = "";
      speichern();
    }
    quelle.value.split(trenner).forEach(tag);
    eingabe.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.key === "," || ev.key === ";" || (!mitLeerzeichen && ev.key === " ")) {
        ev.preventDefault();
        uebernehmen();
      } else if (ev.key === "Backspace" && !eingabe.value && liste.lastElementChild) {
        liste.lastElementChild.remove();
        speichern();
      }
    });
    eingabe.addEventListener("paste", function () { window.setTimeout(uebernehmen, 0); });
    // Von außen (Software-Katalog): quelle.dispatchEvent(new CustomEvent("okm:tags", {detail: ["a", "b"]}))
    quelle.addEventListener("okm:tags", function (ev) { (ev.detail || []).forEach(tag); speichern(); });
    eingabe.addEventListener("blur", uebernehmen);
    rahmen.addEventListener("click", function (ev) { if (ev.target === rahmen || ev.target === liste) { eingabe.focus(); } });
  }
  function tagfelder(wurzel) {
    if (!wurzel.querySelectorAll) { return; }
    wurzel.querySelectorAll("input[data-typ=liste]").forEach(tagfeld);
  }
  document.addEventListener("htmx:load", function (ev) { tagfelder(ev.target); });

  document.addEventListener("DOMContentLoaded", function () {
    hervorheben(document); baukasten(); rezeptFilter(); tagfelder(document);
  });
  document.addEventListener("htmx:afterSwap", function (ev) {
    hervorheben(ev.target);
    // Nur zum Ergebnis von „Erzeugen“ scrollen – nicht bei jeder Live-Vorschau im Baukasten.
    if (ev.target.id === "ergebnis" || ev.target.id === "bk-ergebnis") {
      var vorschau = ev.target.querySelector(".vorschau, .fehlerbox");
      if (vorschau) { vorschau.scrollIntoView({ behavior: "smooth", block: "start" }); }
    }
  });
  // Fehlerantworten (422/400) trotzdem anzeigen
  document.addEventListener("htmx:beforeSwap", function (ev) {
    if (ev.detail.xhr.status === 422 || ev.detail.xhr.status === 400) {
      ev.detail.shouldSwap = true;
      ev.detail.isError = false;
    }
  });
})();
