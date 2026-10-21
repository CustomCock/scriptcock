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

  document.addEventListener("click", function (ev) {
    var knopf = ev.target.closest("[data-kopieren]");
    if (!knopf) { return; }
    var quelle = document.querySelector(knopf.getAttribute("data-kopieren"));
    if (quelle) { kopieren(quelle.textContent, knopf); }
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
    function hinzufuegen(blockId, platzhalter) {
      var url = basis + "/baukasten/schritt?block=" + encodeURIComponent(blockId) + "&ziel=" + encodeURIComponent(ziel());
      if (platzhalter) {
        window.htmx.ajax("GET", url, { target: platzhalter, swap: "outerHTML" }).then(aendern);
      } else {
        window.htmx.ajax("GET", url, { target: liste, swap: "beforeend" });
      }
    }

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

  document.addEventListener("DOMContentLoaded", function () { hervorheben(document); baukasten(); });
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
