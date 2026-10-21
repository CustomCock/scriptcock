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

  document.addEventListener("DOMContentLoaded", function () { hervorheben(document); });
  document.addEventListener("htmx:afterSwap", function (ev) {
    hervorheben(ev.target);
    var vorschau = ev.target.querySelector && ev.target.querySelector(".vorschau, .fehlerbox");
    if (vorschau) { vorschau.scrollIntoView({ behavior: "smooth", block: "start" }); }
  });
  // Fehlerantworten (422/400) trotzdem anzeigen
  document.addEventListener("htmx:beforeSwap", function (ev) {
    if (ev.detail.xhr.status === 422 || ev.detail.xhr.status === 400) {
      ev.detail.shouldSwap = true;
      ev.detail.isError = false;
    }
  });
})();
