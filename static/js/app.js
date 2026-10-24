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
    function paletteAktualisieren() {
      var r = form.querySelector("input[name=ziel]:checked");
      var anzeige = r ? r.dataset.anzeige : "";
      document.querySelectorAll(".palette-block").forEach(function (el) {
        var ok = el.dataset.ziele.split(" ").indexOf(ziel()) >= 0;
        el.classList.toggle("nicht-verfuegbar", !ok);
        el.querySelector(".hinzufuegen").disabled = !ok;
        el.title = ok ? el.dataset.beschreibung : "Unter " + anzeige + " nicht verfügbar";
      });
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
    window.OkmBaukasten = { ziel: ziel, hinzufuegen: function (blockId, werte) { return hinzufuegen(blockId, null, werte); } };

    document.addEventListener("click", function (ev) {
      var knopf = ev.target.closest("[data-hinzufuegen]");
      if (knopf) { hinzufuegen(knopf.getAttribute("data-hinzufuegen")); return; }
      var schritt = ev.target.closest("li.schritt");
      if (!schritt) { return; }
      if (ev.target.closest("[data-entfernen]")) {
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
        paletteAktualisieren();
        try { window.history.replaceState(null, "", "?ziel=" + encodeURIComponent(ziel())); } catch (e) { /* egal */ }
      }
    });

    var suche = document.getElementById("bk-suche");
    suche.addEventListener("input", function () {
      var woerter = suche.value.toLowerCase().split(/\s+/).filter(Boolean);
      document.querySelectorAll(".palette-gruppe").forEach(function (gruppe) {
        var sichtbar = 0;
        gruppe.querySelectorAll(".palette-block").forEach(function (el) {
          var treffer = woerter.every(function (w) { return el.dataset.suche.indexOf(w) >= 0; });
          el.hidden = !treffer;
          if (treffer) { sichtbar += 1; }
        });
        gruppe.hidden = sichtbar === 0;
      });
    });

    document.body.addEventListener("htmx:afterSwap", function (ev) {
      if (ev.target === liste) { aendern(); }
    });

    if (window.Sortable) {
      document.querySelectorAll(".palette-liste").forEach(function (ul) {
        window.Sortable.create(ul, {
          group: { name: "bausteine", pull: "clone", put: false },
          sort: false,
          filter: ".nicht-verfuegbar, .hinzufuegen",
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
        onAdd: function (evt) { hinzufuegen(evt.item.dataset.block, evt.item); },
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
