/* okm Script-Baukasten – Blockly-Modus
 *
 * Blockly erzeugt hier KEIN Script. Die Arbeitsfläche wird in die Schrittliste (IR-Eingabe)
 * übersetzt und an /api/v1/vorschau bzw. /api/v1/skripte geschickt. Validierung, Escaping und
 * Generierung passieren ausschließlich im Backend – wie in den anderen Modi.
 */
(function () {
  "use strict";

  var SPEICHER_SCHLUESSEL = "okm-blockly-v1";
  var FARBEN = { gruen: "#2e7d32", gelb: "#b7791f", rot: "#c4161c" };
  var FARBE_ABLAUF = "#4a4a4a";
  var FARBE_START = "#141414";

  function init() {
    var datenEl = document.getElementById("bl-daten");
    if (!datenEl || !window.Blockly) { return; }
    var daten = JSON.parse(datenEl.textContent);
    var Blockly = window.Blockly;
    var katalog = {};
    daten.katalog.forEach(function (b) { katalog[b.id] = b; });

    var zielWahl = document.getElementById("bl-ziel");
    var titelEl = document.getElementById("bl-titel");
    var dryEl = document.getElementById("bl-dry");
    var rotBox = document.getElementById("bl-rot");
    var rotEl = document.getElementById("bl-rot-ok");
    var erzeugenKnopf = document.getElementById("bl-erzeugen");
    var statusEl = document.getElementById("bl-status");
    var fehlerEl = document.getElementById("bl-fehler");
    var codeRahmen = document.getElementById("bl-code-rahmen");
    var codeEl = document.getElementById("bl-code");
    var ergebnisEl = document.getElementById("bl-ergebnis");

    function ziel() {
      var r = zielWahl.querySelector("input[name=ziel]:checked");
      return r ? r.value : daten.ziel;
    }
    var RECHTS = (Blockly.inputs && Blockly.inputs.Align) ? Blockly.inputs.Align.RIGHT : Blockly.ALIGN_RIGHT;

    // --- Blockdefinitionen aus dem Katalog -------------------------------------------
    function feldFuer(p) {
      if (p.typ === "ja_nein") {
        return new Blockly.FieldCheckbox(p.standard ? "TRUE" : "FALSE");
      }
      if (p.typ === "zahl" || p.typ === "port") {
        var start = p.standard !== null ? p.standard : (p.beispiel !== null ? p.beispiel : (p.min !== null ? p.min : 1));
        var min = p.typ === "port" ? 1 : p.min;
        var max = p.typ === "port" ? 65535 : p.max;
        return new Blockly.FieldNumber(Number(start), min === null ? undefined : min, max === null ? undefined : max, 1);
      }
      if (p.typ === "auswahl") {
        var feld = new Blockly.FieldDropdown(p.optionen.map(function (o) { return [o.label, o.wert]; }));
        if (p.standard !== null) { feld.setValue(String(p.standard)); }
        return feld;
      }
      return new Blockly.FieldTextInput(p.standard !== null ? String(p.standard) : "");
    }

    function zielAnwenden(block, def) {
      var z = ziel();
      var genutzt = def.genutzt[z] || [];
      def.parameter.forEach(function (p) {
        var eingabe = block.getInput("P_" + p.id);
        if (eingabe) { eingabe.setVisible(genutzt.indexOf(p.id) >= 0); }
      });
      block.setWarningText(def.ziele.indexOf(z) >= 0 ? null : "Unter " + daten.ziele[z] + " nicht verfügbar.", "ziel");
    }

    daten.katalog.forEach(function (def) {
      Blockly.Blocks["bk_" + def.id] = {
        init: function () {
          this.appendDummyInput("KOPF").appendField(def.name);
          var block = this;
          def.parameter.forEach(function (p) {
            var pflicht = p.pflicht && p.typ !== "ja_nein" ? " *" : "";
            block.appendDummyInput("P_" + p.id).setAlign(RECHTS).appendField(p.label + pflicht).appendField(feldFuer(p), p.id);
          });
          this.setPreviousStatement(true, "schritt");
          this.setNextStatement(true, "schritt");
          this.setColour(FARBEN[def.risiko] || FARBE_ABLAUF);
          this.setTooltip(def.beschreibung + (def.hilfe ? "\n\n" + def.hilfe : "") + "\nRisiko: " + def.risiko);
          zielAnwenden(this, def);
        }
      };
    });

    Blockly.Blocks.ablauf_start = {
      init: function () {
        this.appendDummyInput().appendField("Script");
        this.appendStatementInput("SCHRITTE").setCheck("schritt");
        this.setColour(FARBE_START);
        this.setDeletable(false);
        this.setTooltip("Nur Bausteine in diesem Block landen im Script.");
      }
    };
    Blockly.Blocks.ablauf_wenn_fehler = {
      init: function () {
        this.appendDummyInput().appendField("Versuche");
        this.appendStatementInput("VERSUCHE").setCheck("schritt");
        this.appendDummyInput().appendField("Wenn das fehlschlägt");
        this.appendStatementInput("SONST").setCheck("schritt");
        this.setPreviousStatement(true, "schritt");
        this.setNextStatement(true, "schritt");
        this.setColour(FARBE_ABLAUF);
        this.setTooltip("Schlägt ein Schritt unter „Versuche“ fehl, laufen stattdessen die Schritte darunter. " +
          "Danach geht das Script normal weiter. Leer lassen = Fehler übergehen.");
      }
    };
    Blockly.Blocks.ablauf_wiederhole = {
      init: function () {
        this.appendDummyInput().appendField("Wiederhole")
          .appendField(new Blockly.FieldNumber(3, 1, daten.max_wiederholungen, 1), "ANZAHL").appendField("-mal");
        this.appendStatementInput("RUMPF").setCheck("schritt");
        this.setPreviousStatement(true, "schritt");
        this.setNextStatement(true, "schritt");
        this.setColour(FARBE_ABLAUF);
        this.setTooltip("Führt die Schritte darin mehrmals hintereinander aus (höchstens " + daten.max_wiederholungen + "-mal).");
      }
    };

    // --- Toolbox (automatisch aus der Registry) ----------------------------------------
    function toolbox() {
      var z = ziel();
      var kategorien = {};
      var reihenfolge = [];
      daten.katalog.forEach(function (def) {
        if (!kategorien[def.kategorie]) { kategorien[def.kategorie] = []; reihenfolge.push(def.kategorie); }
        kategorien[def.kategorie].push({ kind: "block", type: "bk_" + def.id, disabled: def.ziele.indexOf(z) < 0 });
      });
      return {
        kind: "categoryToolbox",
        contents: [{
          kind: "category", name: "Ablauf", colour: FARBE_ABLAUF,
          contents: [{ kind: "block", type: "ablauf_wenn_fehler" }, { kind: "block", type: "ablauf_wiederhole" }]
        }].concat(reihenfolge.map(function (k) {
          return { kind: "category", name: k, colour: "#b89f61", contents: kategorien[k] };
        }))
      };
    }

    var ws = Blockly.inject("bl-arbeitsflaeche", {
      toolbox: toolbox(),
      media: daten.basis + "/static/vendor/blockly/media/",
      trashcan: true,
      sounds: false,
      zoom: { controls: true, wheel: true, startScale: 0.85 },
      grid: { spacing: 24, length: 3, colour: "#e6d3a3", snap: true },
      move: { scrollbars: true, drag: true, wheel: false }
    });
    window.addEventListener("resize", function () { Blockly.svgResize(ws); });

    // --- Zustand laden ---------------------------------------------------------------
    function kette(knoten) {
      var zustaende = knoten.map(einzel).filter(Boolean);
      for (var i = zustaende.length - 2; i >= 0; i--) { zustaende[i].next = { block: zustaende[i + 1] }; }
      return zustaende[0] || null;
    }
    function einzel(k) {
      var z;
      if (k.art === "wenn_fehler") {
        z = { type: "ablauf_wenn_fehler", inputs: {} };
        var v = kette(k.versuche); if (v) { z.inputs.VERSUCHE = { block: v }; }
        var s = kette(k.sonst); if (s) { z.inputs.SONST = { block: s }; }
        return z;
      }
      if (k.art === "wiederhole") {
        z = { type: "ablauf_wiederhole", fields: { ANZAHL: k.anzahl }, inputs: {} };
        var r = kette(k.rumpf); if (r) { z.inputs.RUMPF = { block: r }; }
        return z;
      }
      var def = katalog[k.block_id];
      if (!def) { return null; }
      var felder = {};
      def.parameter.forEach(function (p) {
        if (k.parameter[p.id] === undefined) { return; }
        var wert = k.parameter[p.id];
        if (p.typ === "ja_nein") { wert = wert === "true" ? "TRUE" : "FALSE"; }
        else if (p.typ === "zahl" || p.typ === "port") { wert = Number(wert); }
        felder[p.id] = wert;
      });
      return { type: "bk_" + def.id, fields: felder };
    }
    function startBlock(schritte) {
      var zustand = { type: "ablauf_start", x: 24, y: 24, deletable: false, inputs: {} };
      var k = kette(schritte || []);
      if (k) { zustand.inputs.SCHRITTE = { block: k }; }
      Blockly.serialization.blocks.append(zustand, ws);
    }

    var gespeichert = null;
    try { gespeichert = JSON.parse(window.localStorage.getItem(SPEICHER_SCHLUESSEL) || "null"); } catch (e) { gespeichert = null; }
    if (daten.vorbelegung) {
      startBlock(daten.vorbelegung.schritte);
    } else if (gespeichert && gespeichert.zustand) {
      try {
        Blockly.serialization.workspaces.load(gespeichert.zustand, ws);
        if (gespeichert.titel) { titelEl.value = gespeichert.titel; }
      } catch (e) { ws.clear(); }
    }
    if (!ws.getBlocksByType("ablauf_start").length) { startBlock([]); }

    document.getElementById("bl-neu").addEventListener("click", function () {
      if (!window.confirm("Arbeitsfläche leeren und neu beginnen?")) { return; }
      ws.clear();
      startBlock([]);
      titelEl.value = "";
      try { window.localStorage.removeItem(SPEICHER_SCHLUESSEL); } catch (e) { /* egal */ }
    });

    // --- Arbeitsfläche → Schrittliste ------------------------------------------------
    function serialisieren() {
      var positionen = []; // Blockly-IDs in Vorordnung – entspricht "schritt" in Fehlermeldungen
      var hatRot = false;
      function liste(block) {
        var ergebnis = [];
        for (var b = block; b; b = b.getNextBlock()) {
          if (!b.isEnabled()) { continue; }
          ergebnis.push(knoten(b));
        }
        return ergebnis;
      }
      function knoten(b) {
        positionen.push(b.id);
        if (b.type === "ablauf_wenn_fehler") {
          return { art: "wenn_fehler", versuche: liste(b.getInputTargetBlock("VERSUCHE")), sonst: liste(b.getInputTargetBlock("SONST")) };
        }
        if (b.type === "ablauf_wiederhole") {
          return { art: "wiederhole", anzahl: b.getFieldValue("ANZAHL"), rumpf: liste(b.getInputTargetBlock("RUMPF")) };
        }
        var def = katalog[b.type.slice(3)];
        if (def.risiko === "rot") { hatRot = true; }
        var parameter = {};
        def.parameter.forEach(function (p) {
          var wert = b.getFieldValue(p.id);
          if (p.typ === "ja_nein") { wert = wert === "TRUE" ? "true" : "false"; }
          else if (wert !== null && wert !== undefined) { wert = String(wert); }
          parameter[p.id] = wert;
        });
        return { art: "block", block_id: def.id, parameter: parameter };
      }
      var start = ws.getBlocksByType("ablauf_start")[0];
      var schritte = start ? liste(start.getInputTargetBlock("SCHRITTE")) : [];
      return {
        anfrage: {
          ziel: ziel(),
          titel: titelEl.value.trim(),
          dry_run: dryEl.checked,
          rot_bestaetigt: rotEl.checked,
          quelle: "blockly",
          schritte: schritte
        },
        positionen: positionen,
        hatRot: hatRot
      };
    }

    function anfrage(url, nutzlast) {
      return window.fetch(daten.basis + url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Okm-Request": "1" },
        body: JSON.stringify(nutzlast)
      }).then(function (antwort) {
        if (antwort.status === 401) { window.location.href = daten.basis + "/login"; }
        return antwort.json().then(function (json) { return { status: antwort.status, json: json }; });
      });
    }

    function textListe(meldungen) {
      var ul = document.createElement("ul");
      meldungen.forEach(function (m) { var li = document.createElement("li"); li.textContent = m; ul.appendChild(li); });
      return ul;
    }

    function fehlerZeigen(fehler, positionen) {
      ws.getAllBlocks(false).forEach(function (b) { b.setWarningText(null, "server"); });
      fehlerEl.textContent = "";
      if (!fehler.length) { return; }
      var allgemein = [];
      fehler.forEach(function (f) {
        var block = (f.schritt !== null && f.schritt !== undefined) ? ws.getBlockById(positionen[f.schritt]) : null;
        if (block) { block.setWarningText(f.meldung, "server"); }
        allgemein.push(f.meldung);
      });
      var box = document.createElement("div");
      box.className = "fehlerbox";
      box.setAttribute("role", "alert");
      var h = document.createElement("h2");
      h.textContent = "Bitte noch korrigieren (Hinweise auch an den markierten Bausteinen)";
      box.appendChild(h);
      box.appendChild(textListe(allgemein));
      fehlerEl.appendChild(box);
    }

    var letzteAnfrage = 0;
    var zuletztOk = false;
    function vorschau() {
      var s = serialisieren();
      rotBox.hidden = !(s.hatRot && !daten.ist_admin && !dryEl.checked);
      ergebnisEl.textContent = "";
      try {
        window.localStorage.setItem(SPEICHER_SCHLUESSEL, JSON.stringify({
          zustand: Blockly.serialization.workspaces.save(ws), titel: titelEl.value
        }));
      } catch (e) { /* privater Modus o. Ä. */ }
      if (!s.anfrage.schritte.length) {
        fehlerZeigen([], s.positionen);
        codeRahmen.hidden = true;
        erzeugenKnopf.disabled = true;
        statusEl.textContent = "Noch keine Schritte im Block „Script“.";
        return;
      }
      var nr = ++letzteAnfrage;
      statusEl.textContent = "Vorschau wird erstellt …";
      anfrage("/api/v1/vorschau", s.anfrage).then(function (r) {
        if (nr !== letzteAnfrage) { return; } // veraltete Antwort
        if (r.status === 200) {
          fehlerZeigen([], s.positionen);
          codeEl.textContent = r.json.text;
          codeEl.className = "language-" + daten.sprachen[s.anfrage.ziel];
          delete codeEl.dataset.highlighted;
          if (window.hljs) { window.hljs.highlightElement(codeEl); }
          codeRahmen.hidden = false;
          zuletztOk = true;
          statusEl.textContent = "Live-Vorschau (" + daten.ziele[s.anfrage.ziel] + ") – gespeichert wird erst beim Erzeugen.";
        } else {
          fehlerZeigen(r.json.fehler || [{ meldung: "Unerwarteter Fehler." }], s.positionen);
          codeRahmen.hidden = true;
          zuletztOk = false;
          statusEl.textContent = "Download gesperrt, bis alle Fehler behoben sind.";
        }
        erzeugenKnopf.disabled = !zuletztOk;
      }).catch(function () {
        statusEl.textContent = "Server nicht erreichbar.";
        erzeugenKnopf.disabled = true;
      });
    }

    var zeitgeber = null;
    function spaeter() {
      window.clearTimeout(zeitgeber);
      zeitgeber = window.setTimeout(vorschau, 600);
    }
    ws.addChangeListener(function (ev) { if (!ev.isUiEvent) { spaeter(); } });
    titelEl.addEventListener("input", spaeter);
    dryEl.addEventListener("change", vorschau);
    rotEl.addEventListener("change", vorschau);
    zielWahl.addEventListener("change", function () {
      ws.updateToolbox(toolbox());
      ws.getAllBlocks(false).forEach(function (b) {
        var def = katalog[b.type.slice(3)];
        if (b.type.indexOf("bk_") === 0 && def) { zielAnwenden(b, def); }
        if (b.queueRender) { b.queueRender(); } else if (b.render) { b.render(); }
      });
      try { window.history.replaceState(null, "", "?ziel=" + encodeURIComponent(ziel())); } catch (e) { /* egal */ }
      vorschau();
    });

    erzeugenKnopf.addEventListener("click", function () {
      var s = serialisieren();
      erzeugenKnopf.disabled = true;
      anfrage("/api/v1/skripte", s.anfrage).then(function (r) {
        if (r.status === 200) {
          window.htmx.ajax("GET", daten.basis + "/skripte/" + r.json.id + "/ergebnis", { target: "#bl-ergebnis", swap: "innerHTML" })
            .then(function () { ergebnisEl.scrollIntoView({ behavior: "smooth", block: "start" }); });
        } else {
          fehlerZeigen(r.json.fehler || [{ meldung: "Unerwarteter Fehler." }], s.positionen);
        }
        erzeugenKnopf.disabled = false;
      });
    });

    vorschau();
    window.okmBlockly = { arbeitsflaeche: ws, serialisieren: serialisieren, vorschau: vorschau };
  }

  document.addEventListener("DOMContentLoaded", init);
})();
