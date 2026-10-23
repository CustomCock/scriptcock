/* okm Script-Baukasten – bearbeitbarer Script-Editor (CodeMirror 5, vendort).
 *
 * Eine Komponente für Rezept-, Listen- und Blockly-Modus (Markup: _editor.html).
 * Zustände: „generiert“ (Text = letzte Fassung des Baukastens) und „manuell bearbeitet“
 * (Text weicht ab → Banner mit „Neu generieren“ / „Änderungen anzeigen“).
 * Download und Kopieren laufen über POST /api/script/export (mit manuell_bearbeitet → Kopfzeile),
 * „Syntax prüfen“ über POST /api/script/pruefen. Daten kommen nur als Text ins DOM (kein innerHTML).
 */
(function () {
  "use strict";

  var HINWEIS_SCHLUESSEL = "okm-editor-hinweis-gelesen";
  var MODUS = { powershell: "powershell", cmd: "okm-batch", bash: "shell", zsh: "shell" };
  var ZIEL_NAME = { powershell: "PowerShell", cmd: "CMD", bash: "bash", zsh: "zsh" };

  function batchModus() {
    if (!window.CodeMirror || !CodeMirror.defineSimpleMode || CodeMirror.modes["okm-batch"]) { return; }
    CodeMirror.defineSimpleMode("okm-batch", {
      start: [
        { regex: /\s*(?:rem(?:\s.*)?|::.*)$/i, token: "comment", sol: true },
        { regex: /\s*:[A-Za-z_][\w-]*/, token: "tag", sol: true },
        { regex: /"[^"]*"?/, token: "string" },
        { regex: /%%~?[A-Za-z]|%~?[a-z]*[0-9]|%[A-Za-z_][A-Za-z0-9_]*(?::[^%]*)?%/, token: "variable-2" },
        { regex: /@?echo\s+off\b/i, token: "keyword" },
        { regex: /(?:if|else|for|in|do|goto|call|exit|set|setlocal|endlocal|echo|not|exist|errorlevel|defined|equ|neq|lss|leq|gtr|geq|chcp|pause|pushd|popd|start|title)\b/i, token: "keyword" },
        { regex: /[()&|<>]/, token: "operator" },
        { regex: /\d+\b/, token: "number" },
        { regex: /[^\s"%()&|<>]+/, token: null },
        { regex: /\s+/, token: null }
      ]
    });
  }

  function speicherLesen(schluessel) {
    try { return window.localStorage.getItem(schluessel); } catch (e) { return null; }
  }
  function speicherSchreiben(schluessel, wert) {
    try { window.localStorage.setItem(schluessel, wert); } catch (e) { /* privater Modus o. Ä. */ }
  }

  function el(tag, klasse, text) {
    var e = document.createElement(tag);
    if (klasse) { e.className = klasse; }
    if (text !== undefined) { e.textContent = text; }
    return e;
  }

  /* --- Zeilen-Diff (LCS) ------------------------------------------------------------------ */

  function zeilenDiff(alt, neu) {
    // ein abschließender Zeilenumbruch ist kein Unterschied (der Export ergänzt ihn ohnehin)
    var a = alt.replace(/\n$/, "").split("\n"), b = neu.replace(/\n$/, "").split("\n");
    var anfang = 0;
    while (anfang < a.length && anfang < b.length && a[anfang] === b[anfang]) { anfang++; }
    var ende = 0;
    while (ende < a.length - anfang && ende < b.length - anfang &&
           a[a.length - 1 - ende] === b[b.length - 1 - ende]) { ende++; }
    var am = a.slice(anfang, a.length - ende), bm = b.slice(anfang, b.length - ende);
    var n = am.length, m = bm.length, i, j;
    var ergebnis = [];
    for (i = 0; i < anfang; i++) { ergebnis.push([" ", a[i]]); }
    if (n * m > 4000000) { // sehr große Änderung: grob, aber ohne den Browser einzufrieren
      am.forEach(function (z) { ergebnis.push(["-", z]); });
      bm.forEach(function (z) { ergebnis.push(["+", z]); });
    } else {
      var lcs = [];
      for (i = 0; i <= n; i++) { lcs.push(new Uint32Array(m + 1)); }
      for (i = n - 1; i >= 0; i--) {
        for (j = m - 1; j >= 0; j--) {
          lcs[i][j] = am[i] === bm[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
        }
      }
      i = 0; j = 0;
      while (i < n && j < m) {
        if (am[i] === bm[j]) { ergebnis.push([" ", am[i]]); i++; j++; }
        else if (lcs[i + 1][j] >= lcs[i][j + 1]) { ergebnis.push(["-", am[i]]); i++; }
        else { ergebnis.push(["+", bm[j]]); j++; }
      }
      for (; i < n; i++) { ergebnis.push(["-", am[i]]); }
      for (; j < m; j++) { ergebnis.push(["+", bm[j]]); }
    }
    for (i = a.length - ende; i < a.length; i++) { ergebnis.push([" ", a[i]]); }
    return ergebnis;
  }

  function diffZeigen(behaelter, alt, neu) {
    var zeilen = zeilenDiff(alt, neu);
    var KONTEXT = 2;
    var wichtig = zeilen.map(function () { return false; });
    zeilen.forEach(function (z, k) {
      if (z[0] === " ") { return; }
      for (var d = -KONTEXT; d <= KONTEXT; d++) {
        if (k + d >= 0 && k + d < zeilen.length) { wichtig[k + d] = true; }
      }
    });
    behaelter.textContent = "";
    var plus = zeilen.filter(function (z) { return z[0] === "+"; }).length;
    var minus = zeilen.filter(function (z) { return z[0] === "-"; }).length;
    behaelter.appendChild(el("p", "feldhilfe",
      plus || minus ? "Gegenüber der generierten Fassung: " + plus + " Zeile(n) neu/geändert, " + minus + " entfernt."
                    : "Keine Unterschiede zur generierten Fassung."));
    var pre = el("pre", "diff");
    var uebersprungen = 0;
    function luecke() {
      if (uebersprungen) { pre.appendChild(el("span", "diff-luecke", "… " + uebersprungen + " unveränderte Zeile(n) …\n")); }
      uebersprungen = 0;
    }
    zeilen.forEach(function (z, k) {
      if (!wichtig[k]) { uebersprungen++; return; }
      luecke();
      var klasse = z[0] === "+" ? "diff-plus" : z[0] === "-" ? "diff-minus" : "diff-gleich";
      pre.appendChild(el("span", "diff-zeile " + klasse, z[0] + " " + z[1] + "\n"));
    });
    luecke();
    behaelter.appendChild(pre);
  }

  /* --- Editor-Instanz --------------------------------------------------------------------- */

  function erstelle(wurzel) {
    batchModus();
    var textarea = wurzel.querySelector(".editor-quelle");
    var zustandEl = wurzel.querySelector("[data-editor-zustand]");
    var banner = wurzel.querySelector("[data-editor-banner]");
    var zielHinweis = wurzel.querySelector("[data-editor-zielhinweis]");
    var sicherheit = wurzel.querySelector("[data-editor-sicherheit]");
    var diffEl = wurzel.querySelector("[data-editor-diff]");
    var diffKnopf = wurzel.querySelector("[data-editor='diff']");
    var pruefEl = wurzel.querySelector("[data-editor-pruefung]");
    var hashEl = wurzel.querySelector("[data-editor-hash]");
    var knopf = function (name) { return wurzel.querySelector("[data-editor='" + name + "']"); };

    var ziel = wurzel.dataset.ziel;           // Ziel des Textes im Editor
    var dateiname = wurzel.dataset.dateiname || "script";
    var generiert = textarea.value;           // letzte Fassung des Baukastens
    var generiertZiel = ziel, generiertName = dateiname;
    var intern = false;
    var manuell = false;
    var markierte = [];

    var cm = window.CodeMirror ? CodeMirror.fromTextArea(textarea, {
      mode: MODUS[ziel], theme: "okm", lineNumbers: true, indentUnit: 4, tabSize: 4,
      indentWithTabs: false, viewportMargin: 30, lineWrapping: false,
      extraKeys: { "Ctrl-Y": "redo", "Cmd-Shift-Z": "redo", "Alt-G": "jumpToLine", "Tab": false, "Shift-Tab": false }
    }) : null;
    /* Ohne CodeMirror (Datei fehlt): das Textfeld bleibt als einfacher Editor nutzbar. */
    var api = cm ? {
      wert: function () { return cm.getValue(); },
      setzen: function (t) { cm.setValue(t); },
      aufZeile: function (nr) { cm.setCursor({ line: nr - 1, ch: 0 }); cm.scrollIntoView({ line: nr - 1, ch: 0 }, 60); cm.focus(); }
    } : {
      wert: function () { return textarea.value.replace(/\r\n/g, "\n"); },
      setzen: function (t) { textarea.value = t; },
      aufZeile: function () { textarea.focus(); }
    };

    function editorTextFelder() {
      document.querySelectorAll("input[data-editor-text]").forEach(function (f) {
        f.value = manuell ? api.wert() : "";
      });
    }

    function zustandSetzen(neu) {
      manuell = neu;
      wurzel.dataset.zustand = manuell ? "manuell" : "generiert";
      zustandEl.textContent = manuell ? "manuell bearbeitet" : "generiert";
      zustandEl.className = "marke editor-zustand" + (manuell ? " marke-gelb" : " marke-leise");
      banner.hidden = !manuell;
      if (!manuell) {
        diffEl.hidden = true;
        diffKnopf.setAttribute("aria-expanded", "false");
        diffKnopf.textContent = "Änderungen anzeigen";
      } else if (!diffEl.hidden) {
        diffZeigen(diffEl, generiert, api.wert());
      }
      zielHinweis.textContent = manuell && generiertZiel !== ziel
        ? " Das Zielsystem ist jetzt " + ZIEL_NAME[generiertZiel] + ", der Text ist noch für " + ZIEL_NAME[ziel] +
          " – „Neu generieren“ übernimmt das neue Ziel."
        : "";
      editorTextFelder();
      wurzel.dispatchEvent(new CustomEvent("okm-editor-zustand", { bubbles: true, detail: { manuell: manuell } }));
    }

    function zielSetzen(z, name) {
      ziel = z; dateiname = name || dateiname;
      wurzel.dataset.ziel = z;
      if (cm && cm.getOption("mode") !== MODUS[z]) { cm.setOption("mode", MODUS[z]); }
    }

    function nachAenderung() {
      if (intern) { return; }
      var abweichend = api.wert() !== generiert;
      if (abweichend && !manuell && speicherLesen(HINWEIS_SCHLUESSEL) !== "1") { sicherheit.hidden = false; }
      zustandSetzen(abweichend);
    }
    if (cm) { cm.on("changes", nachAenderung); } else { textarea.addEventListener("input", nachAenderung); }

    function programmatisch(text, verlaufLeeren) {
      intern = true;
      try {
        api.setzen(text);
        if (cm && verlaufLeeren) { cm.clearHistory(); }
      } finally { intern = false; }
      markierungenLoeschen();
    }

    function setzeGeneriert(text, z, name) {
      generiert = text;
      generiertZiel = z || generiertZiel;
      generiertName = name || generiertName;
      wurzel.hidden = false;
      if (!manuell) {
        zielSetzen(generiertZiel, generiertName);
        programmatisch(text, true);
        zustandSetzen(false);
      } else {
        zustandSetzen(true); // Diff/Zielhinweis aktualisieren
      }
      if (cm) { cm.refresh(); }
    }

    function neuGenerieren() {
      zielSetzen(generiertZiel, generiertName);
      programmatisch(generiert, false); // Verlauf bleibt: Strg+Z holt die Änderungen zurück
      zustandSetzen(false);
      pruefEl.hidden = true;
    }

    function leer() {
      // Keine gültige Vorschau (Fehler/leere Liste): ein generierter Text verschwindet,
      // eigene Änderungen bleiben sichtbar.
      if (!manuell) { wurzel.hidden = true; }
    }

    /* --- Export ------------------------------------------------------------------------- */

    function exportieren() {
      return window.OkmExport(api.wert(), ziel, dateiname, manuell);
    }

    function herunterladen() {
      return exportieren().then(function (antwort) {
        var sha = antwort.headers.get("X-Script-SHA256");
        var kopf = antwort.headers.get("Content-Disposition") || "";
        var m = /filename="([^"]+)"/.exec(kopf);
        return antwort.blob().then(function (blob) {
          var url = URL.createObjectURL(blob);
          var a = document.createElement("a");
          a.href = url;
          a.download = m ? m[1] : dateiname;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
          if (sha) {
            hashEl.hidden = false;
            hashEl.textContent = "";
            hashEl.appendChild(document.createTextNode("SHA-256 der heruntergeladenen Datei" + (manuell ? " (bearbeitet)" : "") + ": "));
            hashEl.appendChild(el("code", "", sha));
          }
        });
      }).catch(function (e) { pruefungMeldung("Download fehlgeschlagen: " + e.message); });
    }

    function kopieren(k) {
      return exportieren().then(function (a) { return a.text(); }).then(
        function (t) { window.OkmKopieren(t.replace(/^\ufeff/, ""), k); },
        function () { window.OkmKopieren(api.wert(), k); }
      );
    }

    /* --- Syntax prüfen ------------------------------------------------------------------ */

    function markierungenLoeschen() {
      if (!cm) { return; }
      markierte.forEach(function (h) { cm.removeLineClass(h, "background", "editor-fehlerzeile"); });
      markierte = [];
    }

    function pruefungMeldung(text) {
      pruefEl.hidden = false;
      pruefEl.textContent = "";
      pruefEl.appendChild(el("p", "fehlertext", text));
    }

    function pruefen() {
      var k = knopf("pruefen");
      var alt = k.lastChild.textContent;
      k.disabled = true;
      k.lastChild.textContent = " Prüfe …";
      markierungenLoeschen();
      var basis = document.body.dataset.basis || "";
      window.fetch(basis + "/api/script/pruefen", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Okm-Request": "1" },
        body: JSON.stringify({ text: api.wert(), ziel: ziel })
      }).then(function (r) {
        return r.json().then(function (j) { return { status: r.status, json: j }; });
      }).then(function (r) {
        if (r.status !== 200) {
          pruefungMeldung(typeof r.json.detail === "string" ? r.json.detail : "Prüfung nicht möglich (" + r.status + ").");
          return;
        }
        pruefungZeigen(r.json);
      }).catch(function () {
        pruefungMeldung("Server nicht erreichbar – nichts geprüft.");
      }).then(function () {
        k.disabled = false;
        k.lastChild.textContent = alt;
      });
    }

    function pruefungZeigen(erg) {
      pruefEl.hidden = false;
      pruefEl.textContent = "";
      pruefEl.className = "editor-pruefung " + (erg.ok ? "editor-pruefung-ok" : erg.befunde.length ? "editor-pruefung-fehler" : "editor-pruefung-offen");
      var titel;
      if (erg.befunde.length) {
        titel = erg.befunde.length + (erg.befunde.length === 1 ? " Befund" : " Befunde");
      } else if (erg.geprueft.length) {
        titel = "✓ Keine Fehler gefunden";
      } else {
        titel = "Nicht geprüft";
      }
      pruefEl.appendChild(el("p", "editor-pruefung-titel", titel +
        (erg.geprueft.length ? " (geprüft mit: " + erg.geprueft.join(", ") + ")" : "")));
      if (erg.befunde.length) {
        var liste = el("ul", "editor-befunde");
        erg.befunde.forEach(function (b) {
          var li = el("li");
          if (b.zeile) {
            var sprung = el("button", "knopf-link", "Zeile " + b.zeile);
            sprung.type = "button";
            sprung.addEventListener("click", function () { api.aufZeile(b.zeile); });
            li.appendChild(sprung);
            li.appendChild(document.createTextNode(" · "));
            if (cm) { // „Zeile n+1“ = Dateiende → letzte Zeile markieren
              markierte.push(cm.addLineClass(Math.min(b.zeile, cm.lineCount()) - 1, "background", "editor-fehlerzeile"));
            }
          }
          li.appendChild(el("span", "editor-werkzeug", b.werkzeug + ": "));
          li.appendChild(document.createTextNode(b.meldung));
          liste.appendChild(li);
        });
        pruefEl.appendChild(liste);
      }
      erg.hinweise.forEach(function (h) { pruefEl.appendChild(el("p", "feldhilfe", h)); });
    }

    /* --- Knöpfe ------------------------------------------------------------------------- */

    wurzel.addEventListener("click", function (ev) {
      var k = ev.target.closest("[data-editor]");
      if (!k || !wurzel.contains(k)) { return; }
      switch (k.dataset.editor) {
        case "rueckgaengig": if (cm) { cm.undo(); cm.focus(); } break;
        case "wiederholen": if (cm) { cm.redo(); cm.focus(); } break;
        case "pruefen": pruefen(); break;
        case "kopieren": kopieren(k); break;
        case "herunterladen": herunterladen(); break;
        case "neu": neuGenerieren(); break;
        case "verstanden":
          speicherSchreiben(HINWEIS_SCHLUESSEL, "1");
          sicherheit.hidden = true;
          break;
        case "diff":
          diffEl.hidden = !diffEl.hidden;
          k.setAttribute("aria-expanded", String(!diffEl.hidden));
          k.textContent = diffEl.hidden ? "Änderungen anzeigen" : "Änderungen ausblenden";
          if (!diffEl.hidden) { diffZeigen(diffEl, generiert, api.wert()); }
          break;
      }
    });

    /* „Erneut öffnen“ eines bearbeiteten Bibliotheks-Scripts */
    var vorbelegung = document.getElementById("editor-vorbelegung");
    if (vorbelegung) {
      try {
        var v = JSON.parse(vorbelegung.textContent);
        if (v && v.manuell && typeof v.text === "string") {
          programmatisch(v.text, true);
          wurzel.hidden = false;
          zustandSetzen(api.wert() !== generiert);
        }
      } catch (e) { /* kaputte Vorbelegung: generierter Text bleibt */ }
      vorbelegung.remove();
    }

    var instanz = {
      wurzel: wurzel,
      cm: cm,
      wert: api.wert,
      ziel: function () { return ziel; },
      dateiname: function () { return dateiname; },
      istManuell: function () { return manuell; },
      generiert: function () { return generiert; },
      setzeGeneriert: setzeGeneriert,
      neuGenerieren: neuGenerieren,
      leer: leer,
      herunterladen: herunterladen,
      kopieren: kopieren,
      pruefen: pruefen
    };
    zustandSetzen(manuell);
    return instanz;
  }

  function fuer(wurzel) {
    if (!wurzel) { return null; }
    if (!wurzel._okmEditor) {
      wurzel._okmEditor = erstelle(wurzel);
      window.OkmEditor = wurzel._okmEditor;
    }
    return wurzel._okmEditor;
  }

  /* Generierter Text aus einem htmx-Fragment (Listen-Modus: _bk_vorschau.html) */
  function fragmentUebernehmen(bereich) {
    var ed = fuer(document.getElementById("script-editor"));
    if (!ed || !bereich.querySelectorAll) { return; }
    var quelle = bereich.querySelector("[data-editor-generiert]");
    if (quelle) {
      ed.setzeGeneriert(quelle.value, quelle.dataset.ziel, quelle.dataset.dateiname);
    } else if (bereich.querySelector("[data-editor-leer]")) {
      ed.leer();
    }
  }

  /* Download-/Kopier-Knöpfe außerhalb des Editors (Ergebnisbereich nach „Erzeugen“):
     ist der Text bearbeitet, gilt der Editor-Inhalt. */
  document.addEventListener("click", function (ev) {
    var k = ev.target.closest("[data-editor-bezug]");
    var ed = window.OkmEditor;
    if (!k || !ed || !ed.istManuell()) { return; }
    ev.preventDefault();
    ev.stopImmediatePropagation();
    if (k.dataset.editorBezug === "kopieren") { ed.kopieren(k); } else { ed.herunterladen(); }
  }, true);

  function start(bereich) {
    (bereich.matches && bereich.matches(".script-editor") ? [bereich] : [])
      .concat(Array.prototype.slice.call(bereich.querySelectorAll ? bereich.querySelectorAll(".script-editor") : []))
      .forEach(fuer);
    if (window.OkmEditor) {
      bereich.querySelectorAll && bereich.querySelectorAll("input[data-editor-text]").forEach(function (f) {
        f.value = window.OkmEditor.istManuell() ? window.OkmEditor.wert() : "";
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () { start(document); });
  document.addEventListener("htmx:load", function (ev) { start(ev.target); });
  // htmx:load kommt pro eingefügtem Element – das Fragment wird als Ganzes am Swap-Ziel gelesen.
  document.addEventListener("htmx:afterSwap", function (ev) { fragmentUebernehmen(ev.detail.target); });

  window.ScriptEditor = { fuer: fuer, zeilenDiff: zeilenDiff };
})();
