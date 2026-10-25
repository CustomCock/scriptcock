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
  var FARBE_ABLAUF = "#8c7440"; // Sandgelb (dunkel) – gut lesbar auf dunklem Grund
  var FARBE_START = "#e3262e";
  var FARBE_NOTIZ = "#5c5c66";
  var VERGLEICHE = [
    ["<", "kleiner"], [">", "groesser"], ["=", "gleich"], ["≠", "ungleich"],
    ["≤", "kleiner_gleich"], ["≥", "groesser_gleich"],
    ["ist ja", "ja"], ["ist nein", "nein"], ["ist unbekannt", "unbekannt"]
  ];
  var MIT_ZAHL = { kleiner: true, groesser: true, gleich: true, ungleich: true, kleiner_gleich: true, groesser_gleich: true };

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
    var editor = window.ScriptEditor ? window.ScriptEditor.fuer(document.getElementById("script-editor")) : null;
    var ergebnisEl = document.getElementById("bl-ergebnis");

    function ziel() {
      var r = zielWahl.querySelector("input[name=ziel]:checked");
      return r ? r.value : daten.ziel;
    }
    var RECHTS = (Blockly.inputs && Blockly.inputs.Align) ? Blockly.inputs.Align.RIGHT : Blockly.ALIGN_RIGHT;

    // --- Schritte in Vorordnung (gleiche Reihenfolge wie Validierung und Generator) -----
    var KINDER = {
      ablauf_start: ["SCHRITTE"], ablauf_wenn_fehler: ["VERSUCHE", "SONST"],
      ablauf_wiederhole: ["RUMPF"], ablauf_fuer_jeden: ["RUMPF"], ablauf_wenn: ["DANN", "SONST"]
    };
    function durchlaufe(block, besuch) {
      for (var b = block; b; b = b.getNextBlock()) {
        if (!b.isEnabled()) { continue; }
        if (besuch(b) === false) { return false; }
        var kinder = KINDER[b.type] || [];
        for (var i = 0; i < kinder.length; i++) {
          if (durchlaufe(b.getInputTargetBlock(kinder[i]), besuch) === false) { return false; }
        }
      }
      return true;
    }
    function scriptStart() {
      var start = ws.getBlocksByType("ablauf_start")[0];
      return start ? start.getInputTargetBlock("SCHRITTE") : null;
    }
    /* Block-ID -> Schrittnummer (nur Bausteine zählen, wie "[3/7]" im Script) */
    function nummern() {
      var n = 0, karte = {};
      durchlaufe(scriptStart(), function (b) { if (b.type.indexOf("bk_") === 0) { karte[b.id] = ++n; } });
      return karte;
    }
    /* "Block-ID|wert" (stabil beim Umsortieren) -> "3.wert" für das Backend */
    function verweisText(wert) {
      var trenner = wert ? wert.lastIndexOf("|") : -1; // Blockly-IDs können selbst "|" enthalten
      if (trenner < 0) { return ""; }
      var nr = nummern()[wert.slice(0, trenner)];
      return nr ? nr + "." + wert.slice(trenner + 1) : "";
    }
    /* Auswahl der Rückgabewerte aller Schritte vor diesem Block; typ = "zahl"/"ja_nein"/null */
    function verweisOptionen(feld, typ) {
      var eigener = feld.getSourceBlock();
      var optionen = [];
      var n = 0;
      if (ws && eigener) {
        durchlaufe(scriptStart(), function (b) {
          if (b.id === eigener.id) { return false; }
          if (b.type.indexOf("bk_") !== 0) { return true; }
          n++;
          var def = katalog[b.type.slice(3)];
          ((def && def.rueckgabe[ziel()]) || []).forEach(function (r) {
            if (typ && r.typ !== typ) { return; }
            optionen.push(["Schritt " + n + " · " + def.name + ": " + r.beschreibung, b.id + "|" + r.id]);
          });
          return true;
        });
      }
      var aktuell = feld.getValue();
      if (aktuell && !optionen.some(function (o) { return o[1] === aktuell; })) {
        optionen.unshift(["(Wert nicht mehr verfügbar)", aktuell]);
      }
      if (!optionen.length) { optionen.push(["(kein passender Wert davor)", ""]); }
      return optionen;
    }
    /* Dropdown, das auch Werte annimmt, die (noch) nicht in der Liste stehen – z. B. beim Laden,
       bevor die vorherigen Schritte verbunden sind. Geprüft wird ohnehin im Backend. */
    class VerweisFeld extends Blockly.FieldDropdown {
      constructor(typ) {
        super(function () { return verweisOptionen(this, typ); });
      }
      doClassValidation_(wert) { return typeof wert === "string" ? wert : null; }
      // Optionen hängen von der Arbeitsfläche ab – Blockly würde sie sonst zwischenspeichern
      doValueUpdate_(wert) {
        this.generatedOptions = null;
        super.doValueUpdate_(wert);
      }
      aktualisieren() {
        this.doValueUpdate_(this.getValue());
        this.forceRerender();
      }
    }
    function verweiseAktualisieren() {
      ws.getAllBlocks(false).forEach(function (b) {
        b.inputList.forEach(function (eingabe) {
          eingabe.fieldRow.forEach(function (f) { if (f instanceof VerweisFeld) { f.aktualisieren(); } });
        });
      });
    }

    // --- Blockdefinitionen aus dem Katalog -------------------------------------------
    function feldFuer(p) {
      if (p.typ === "variable") { return new VerweisFeld(p.variable_typ); }
      if (p.typ === "ja_nein") {
        return new Blockly.FieldCheckbox(p.standard ? "TRUE" : "FALSE");
      }
      if (p.typ === "port" || daten.zahlentypen[p.typ]) {
        var bereich = daten.zahlentypen[p.typ] || [1, 65535];
        var min = p.min !== null ? p.min : bereich[0];
        var max = p.max !== null ? p.max : bereich[1];
        var start = p.standard !== null ? p.standard : (p.beispiel !== null ? p.beispiel : (min !== null ? min : 1));
        return new Blockly.FieldNumber(Number(start), min === null ? undefined : min, max === null ? undefined : max, 1);
      }
      if (p.optionen && p.optionen.length) {  // auswahl und Typen mit festen Optionen (registry_typ, …)
        var feld = new Blockly.FieldDropdown(p.optionen.map(function (o) { return [o.label, o.wert]; }));
        if (p.standard !== null) { feld.setValue(String(p.standard)); }
        return feld;
      }
      if (p.typ === "liste") {
        // Mehrere Werte mit Komma getrennt; das Backend prüft jeden Eintrag einzeln
        var vorgabe = p.standard !== null ? p.standard : "";
        return new Blockly.FieldTextInput(Array.isArray(vorgabe) ? vorgabe.join(", ") : String(vorgabe));
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
      if (block.type === "bk_richtlinie_setzen" && block.getInput("P_bereich")) {
        // Bereich nur bei Benutzer-Richtlinien (Computer-Richtlinien gelten immer für den Computer)
        var info = richtlinienInfo[block.okmRichtlinie];
        block.getInput("P_bereich").setVisible(!!info && info.klasse !== "machine");
      }
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

    // --- „Richtlinie setzen“: Felder entstehen aus der gewählten Richtlinie ---------------
    // Titel und Optionen (Parameter-Definitionen) stehen im extraState, damit Entwurf (localStorage)
    // und „Erneut öffnen“ den Block vollständig wiederherstellen – ohne erneute Anfrage.
    var richtlinienInfo = daten.richtlinien || {};
    var RL_DEF = katalog.richtlinie_setzen;
    class KnopfFeld extends Blockly.FieldLabel {
      constructor(text, aktion) {
        super(text, "okm-feldknopf");
        this.aktion = aktion;
        this.SERIALIZABLE = false;
        this.CURSOR = "pointer";
      }
      showEditor_() { this.aktion(this.getSourceBlock()); }
    }
    function richtlinieWaehlen(block) {
      if (!window.okmRegistry) { return; }
      window.okmRegistry.waehleRichtlinie(function (schritt, info) {
        var rid = schritt.parameter.richtlinie;
        var r = (info.richtlinien || {})[rid];
        if (r) { richtlinienInfo[rid] = { titel: r.titel, klasse: r.klasse, parameter: r.parameter }; }
        var vorher = JSON.stringify(block.saveExtraState());
        Blockly.Events.setGroup(true);
        block.richtlinieSetzen(rid, richtlinienInfo[rid]);
        Blockly.Events.fire(new Blockly.Events.BlockChange(block, "mutation", null, vorher, JSON.stringify(block.saveExtraState())));
        Object.keys(schritt.parameter).forEach(function (pid) {
          if (pid !== "richtlinie" && block.getField(pid)) { block.setFieldValue(blocklyWert(feldDef(block, pid), schritt.parameter[pid]), pid); }
        });
        Blockly.Events.setGroup(false);
      }, block.okmRichtlinie, "diesen Baustein");
    }
    function feldDef(block, pid) {
      return RL_DEF.parameter.concat(block.okmElemente || []).filter(function (p) { return p.id === pid; })[0] || {};
    }
    if (RL_DEF) {
      Blockly.Blocks.bk_richtlinie_setzen = {
        init: function () {
          var block = this;
          this.okmRichtlinie = "";
          this.okmElemente = [];
          this.appendDummyInput("KOPF").appendField(RL_DEF.name);
          this.appendDummyInput("RICHTLINIE").setAlign(RECHTS).appendField("Richtlinie *")
            .appendField(new Blockly.FieldLabelSerializable("(keine gewählt)"), "RL_TITEL")
            .appendField(new KnopfFeld("wählen …", richtlinieWaehlen), "RL_WAEHLEN");
          RL_DEF.parameter.forEach(function (p) {
            if (p.id === "richtlinie") { return; }
            block.appendDummyInput("P_" + p.id).setAlign(RECHTS).appendField(p.label).appendField(feldFuer(p), p.id);
          });
          this.setPreviousStatement(true, "schritt");
          this.setNextStatement(true, "schritt");
          this.setColour(FARBEN[RL_DEF.risiko] || FARBE_ABLAUF);
          this.setTooltip(RL_DEF.beschreibung + "\n\n„wählen …“ öffnet das Registry-Panel.");
          zielAnwenden(this, RL_DEF);
          this.richtlinieSetzen("", null);
        },
        saveExtraState: function () {
          if (!this.okmRichtlinie) { return null; }
          var block = this;
          var info = richtlinienInfo[this.okmRichtlinie] || {};
          // Werte der Optionen mitspeichern: beim Rückgängig-Machen baut loadExtraState die Felder neu auf
          var werte = {};
          this.okmElemente.forEach(function (p) { if (block.getField(p.id)) { werte[p.id] = block.getFieldValue(p.id); } });
          return { richtlinie: this.okmRichtlinie, titel: info.titel || "", klasse: info.klasse || "", parameter: this.okmElemente, werte: werte };
        },
        loadExtraState: function (s) {
          var block = this;
          if (s && s.richtlinie) {
            richtlinienInfo[s.richtlinie] = richtlinienInfo[s.richtlinie] || { titel: s.titel, klasse: s.klasse, parameter: s.parameter || [] };
          }
          this.richtlinieSetzen(s && s.richtlinie, s && s.richtlinie ? richtlinienInfo[s.richtlinie] : null);
          Object.keys((s && s.werte) || {}).forEach(function (pid) {
            if (block.getField(pid)) { block.setFieldValue(s.werte[pid], pid); }
          });
        },
        /* Neue Richtlinie: Titel setzen, alte Options-Eingänge weg, neue aus den Elementen aufbauen */
        richtlinieSetzen: function (rid, info) {
          var block = this;
          this.okmRichtlinie = rid || "";
          this.setFieldValue(info ? info.titel : (rid ? rid + " (nicht im Katalog)" : "(keine gewählt)"), "RL_TITEL");
          (this.okmElemente || []).forEach(function (p) { if (block.getInput("E_" + p.id)) { block.removeInput("E_" + p.id); } });
          this.okmElemente = info ? (info.parameter || []) : [];
          this.okmElemente.forEach(function (p) {
            var pflicht = p.pflicht && p.typ !== "ja_nein" ? " *" : "";
            block.appendDummyInput("E_" + p.id).setAlign(RECHTS).appendField(p.label + pflicht).appendField(feldFuer(p), p.id);
          });
          // Computer-Richtlinien: Bereich ausblenden; Benutzer-Richtlinien: angemeldeter Benutzer vorbelegen
          var bereich = this.getInput("P_bereich");
          var klasse = info ? info.klasse : "";
          if (bereich) {
            bereich.setVisible(klasse === "user" || klasse === "both");
            if (klasse === "user" && this.getFieldValue("bereich") === "computer") { this.setFieldValue("angemeldeter_benutzer", "bereich"); }
          }
          if (this.rendered) { this.render(); }
        }
      };
    }
    /* Wert aus Panel/Server → Feldwert in Blockly */
    function blocklyWert(p, wert) {
      if (p.typ === "ja_nein") { return wert === true || wert === "true" ? "TRUE" : "FALSE"; }
      if (Array.isArray(wert)) { return wert.join(" | "); }
      if (p.typ === "port" || daten.zahlentypen[p.typ]) { return Number(wert); }
      return wert === null || wert === undefined ? "" : String(wert);
    }

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
    // „Für jeden Wert“: im Rumpf steht {wert} in einem Textfeld für den aktuellen Wert
    var SCHLEIFENWERT = "{wert}";
    Blockly.Blocks.ablauf_fuer_jeden = {
      init: function () {
        this.appendDummyInput().appendField("Für jeden Wert aus")
          .appendField(new Blockly.FieldTextInput("PC-01, PC-02"), "WERTE");
        this.appendStatementInput("RUMPF").setCheck("schritt");
        this.setPreviousStatement(true, "schritt");
        this.setNextStatement(true, "schritt");
        this.setColour(FARBE_ABLAUF);
        this.setTooltip("Führt die Schritte darin einmal pro Wert aus (Werte mit Komma trennen, höchstens " +
          daten.max_schleifenwerte + "). In einem Textfeld darin steht " + SCHLEIFENWERT +
          " für den aktuellen Wert – er wird für jedes Feld einzeln geprüft.");
      }
    };
    Blockly.Blocks.ablauf_wenn = {
      init: function () {
        var block = this;
        this.appendDummyInput("BEDINGUNG").appendField("Wenn")
          .appendField(new VerweisFeld(null), "WERT")
          .appendField(new Blockly.FieldDropdown(VERGLEICHE, function (neu) {
            var zahl = block.getField("ZAHL");
            if (zahl) { zahl.setVisible(!!MIT_ZAHL[neu]); }
            return neu;
          }), "VERGLEICH")
          .appendField(new Blockly.FieldNumber(10), "ZAHL");
        this.appendStatementInput("DANN").setCheck("schritt").appendField("dann");
        this.appendStatementInput("SONST").setCheck("schritt").appendField("sonst");
        this.setPreviousStatement(true, "schritt");
        this.setNextStatement(true, "schritt");
        this.setColour(FARBE_ABLAUF);
        this.setTooltip("Prüft einen Wert, den ein Schritt davor geliefert hat (z. B. freier Speicher in %). " +
          "Ist der Wert unbekannt, gilt nur „ist unbekannt“ als erfüllt.");
      }
    };
    Blockly.Blocks.ablauf_abbrechen = {
      init: function () {
        this.appendDummyInput().appendField("Script beenden:")
          .appendField(new Blockly.FieldTextInput("Nichts zu tun"), "MELDUNG");
        this.appendDummyInput().setAlign(RECHTS).appendField("Exit-Code")
          .appendField(new Blockly.FieldNumber(0, 0, 99, 1), "CODE");
        this.setPreviousStatement(true, "schritt");
        this.setColour(FARBE_ABLAUF);
        this.setTooltip("Beendet das Script hier mit dieser Meldung. Exit-Code 0 = ohne Fehler " +
          "(wichtig für Fernwartung/Monitoring). Nicht innerhalb von „Versuche“.");
      }
    };
    Blockly.Blocks.ablauf_warten = {
      init: function () {
        this.appendDummyInput().appendField("Warte")
          .appendField(new Blockly.FieldNumber(5, 1, daten.max_warten, 1), "SEKUNDEN").appendField("Sekunden");
        this.setPreviousStatement(true, "schritt");
        this.setNextStatement(true, "schritt");
        this.setColour(FARBE_ABLAUF);
        this.setTooltip("Wartet, z. B. bis ein Dienst gestartet ist (höchstens " + daten.max_warten + " Sekunden).");
      }
    };
    Blockly.Blocks.ablauf_bestaetigung = {
      init: function () {
        this.appendDummyInput().appendField("Weiter nur bei JA:")
          .appendField(new Blockly.FieldTextInput("Wirklich fortfahren?"), "MELDUNG");
        this.setPreviousStatement(true, "schritt");
        this.setNextStatement(true, "schritt");
        this.setColour(FARBE_ABLAUF);
        this.setTooltip("Fragt den Benutzer. Nur bei der Eingabe JA geht es weiter, sonst wird abgebrochen " +
          "(auch ohne Benutzer, z. B. in der Fernwartung).");
      }
    };
    Blockly.Blocks.ablauf_kommentar = {
      init: function () {
        this.appendDummyInput().appendField("Notiz:")
          .appendField(new Blockly.FieldTextInput("Was hier passiert"), "TEXT");
        this.setPreviousStatement(true, "schritt");
        this.setNextStatement(true, "schritt");
        this.setColour(FARBE_NOTIZ);
        this.setTooltip("Steht nur als Kommentar im Script – zur Dokumentation, ohne Ausgabe.");
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
          contents: [
            { kind: "block", type: "ablauf_wenn" }, { kind: "block", type: "ablauf_wenn_fehler" },
            { kind: "block", type: "ablauf_wiederhole" }, { kind: "block", type: "ablauf_fuer_jeden" },
            { kind: "block", type: "ablauf_warten" },
            { kind: "block", type: "ablauf_bestaetigung" }, { kind: "block", type: "ablauf_abbrechen" },
            { kind: "block", type: "ablauf_kommentar" }
          ]
        }].concat(reihenfolge.map(function (k) {
          return { kind: "category", name: k, colour: "#b89f61", contents: kategorien[k] };
        }))
      };
    }

    // Dunkles Theme passend zur Oberfläche
    var thema = Blockly.Theme.defineTheme("okmDunkel", {
      name: "okmDunkel",
      base: Blockly.Themes.Classic,
      componentStyles: {
        workspaceBackgroundColour: "#111114",
        toolboxBackgroundColour: "#16161a",
        toolboxForegroundColour: "#d8d8dc",
        flyoutBackgroundColour: "#1d1d22",
        flyoutForegroundColour: "#d8d8dc",
        flyoutOpacity: 0.97,
        scrollbarColour: "#3d3d45",
        scrollbarOpacity: 0.8,
        insertionMarkerColour: "#e6d3a3",
        insertionMarkerOpacity: 0.4,
        markerColour: "#e6d3a3",
        cursorColour: "#e6d3a3"
      },
      fontStyle: { family: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif", size: 11 }
    });

    var ws = Blockly.inject("bl-arbeitsflaeche", {
      theme: thema,
      toolbox: toolbox(),
      media: daten.basis + "/static/vendor/blockly/media/",
      trashcan: true,
      sounds: false,
      zoom: { controls: true, wheel: true, startScale: 0.85 },
      grid: { spacing: 24, length: 2, colour: "#2b2b31", snap: true },
      move: { scrollbars: true, drag: true, wheel: false }
    });
    window.addEventListener("resize", function () { Blockly.svgResize(ws); });

    // --- Zustand laden ---------------------------------------------------------------
    function kette(knoten) {
      var zustaende = knoten.map(einzel).filter(Boolean);
      for (var i = zustaende.length - 2; i >= 0; i--) { zustaende[i].next = { block: zustaende[i + 1] }; }
      return zustaende[0] || null;
    }
    var ladeNr = 0;
    /* "3.wert" -> "okm-s3|wert" (Bausteine bekommen beim Laden die IDs okm-s1, okm-s2 …) */
    function verweisLaden(text) {
      var m = /^(\d+)\.(\w+)$/.exec(text || "");
      return m ? "okm-s" + m[1] + "|" + m[2] : "";
    }
    function einzel(k) {
      var z;
      if (k.art === "wenn") {
        z = {
          type: "ablauf_wenn", inputs: {},
          fields: { WERT: verweisLaden(k.wert), VERGLEICH: k.vergleich, ZAHL: k.zahl === null || k.zahl === undefined ? 10 : k.zahl }
        };
        var d = kette(k.dann); if (d) { z.inputs.DANN = { block: d }; }
        var so = kette(k.sonst); if (so) { z.inputs.SONST = { block: so }; }
        return z;
      }
      if (k.art === "abbrechen") { return { type: "ablauf_abbrechen", fields: { MELDUNG: k.meldung, CODE: k.code } }; }
      if (k.art === "warten") { return { type: "ablauf_warten", fields: { SEKUNDEN: k.sekunden } }; }
      if (k.art === "bestaetigung") { return { type: "ablauf_bestaetigung", fields: { MELDUNG: k.meldung } }; }
      if (k.art === "kommentar") { return { type: "ablauf_kommentar", fields: { TEXT: k.text } }; }
      if (k.art === "wenn_fehler") {
        z = { type: "ablauf_wenn_fehler", inputs: {} };
        var v = kette(k.versuche); if (v) { z.inputs.VERSUCHE = { block: v }; }
        var s = kette(k.sonst); if (s) { z.inputs.SONST = { block: s }; }
        return z;
      }
      if (k.art === "fuer_jeden") {
        z = { type: "ablauf_fuer_jeden", fields: { WERTE: k.werte }, inputs: {} };
        var fr = kette(k.rumpf); if (fr) { z.inputs.RUMPF = { block: fr }; }
        return z;
      }
      if (k.art === "wiederhole") {
        z = { type: "ablauf_wiederhole", fields: { ANZAHL: k.anzahl }, inputs: {} };
        var r = kette(k.rumpf); if (r) { z.inputs.RUMPF = { block: r }; }
        return z;
      }
      var def = katalog[k.block_id];
      if (!def) { return null; }
      var id = "okm-s" + (++ladeNr);
      var felder = {};
      var params = def.parameter;
      var extra = null;
      if (k.block_id === "richtlinie_setzen" && k.parameter.richtlinie) {
        // Optionen der Richtlinie als zusätzliche Felder; Definitionen kommen in den extraState
        var info = richtlinienInfo[k.parameter.richtlinie];
        extra = { richtlinie: k.parameter.richtlinie, titel: info ? info.titel : "", klasse: info ? info.klasse : "", parameter: info ? info.parameter : [] };
        params = params.concat(extra.parameter);
      }
      params.forEach(function (p) {
        if (k.parameter[p.id] === undefined || (extra && p.id === "richtlinie")) { return; }
        var wert = k.parameter[p.id];
        if (p.typ === "ja_nein") { wert = wert === "true" || wert === true ? "TRUE" : "FALSE"; }
        else if (wert === SCHLEIFENWERT) { /* bleibt Text */ }
        else if (Array.isArray(wert)) { wert = wert.join(" | "); }
        else if (p.typ === "port" || daten.zahlentypen[p.typ]) { wert = Number(wert); }
        else if (p.typ === "variable") { wert = verweisLaden(wert); }
        felder[p.id] = wert;
      });
      var zustand = { type: "bk_" + def.id, id: id, fields: felder };
      if (extra) { zustand.extraState = extra; }
      return zustand;
    }
    function startBlock(schritte) {
      ladeNr = 0;
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
        if (b.type === "ablauf_fuer_jeden") {
          return { art: "fuer_jeden", werte: b.getFieldValue("WERTE"), rumpf: liste(b.getInputTargetBlock("RUMPF")) };
        }
        if (b.type === "ablauf_wenn") {
          var vergleich = b.getFieldValue("VERGLEICH");
          return {
            art: "wenn", wert: verweisText(b.getFieldValue("WERT")), vergleich: vergleich,
            zahl: MIT_ZAHL[vergleich] ? b.getFieldValue("ZAHL") : null,
            dann: liste(b.getInputTargetBlock("DANN")), sonst: liste(b.getInputTargetBlock("SONST"))
          };
        }
        if (b.type === "ablauf_abbrechen") { return { art: "abbrechen", meldung: b.getFieldValue("MELDUNG"), code: b.getFieldValue("CODE") }; }
        if (b.type === "ablauf_warten") { return { art: "warten", sekunden: b.getFieldValue("SEKUNDEN") }; }
        if (b.type === "ablauf_bestaetigung") { return { art: "bestaetigung", meldung: b.getFieldValue("MELDUNG") }; }
        if (b.type === "ablauf_kommentar") { return { art: "kommentar", text: b.getFieldValue("TEXT") }; }
        var def = katalog[b.type.slice(3)];
        if (def.risiko === "rot") { hatRot = true; }
        var parameter = {};
        var params = def.parameter;
        if (b.type === "bk_richtlinie_setzen") {
          parameter.richtlinie = b.okmRichtlinie || "";
          params = params.filter(function (p) { return p.id !== "richtlinie"; }).concat(b.okmElemente || []);
          if (b.getInput("P_bereich") && !b.getInput("P_bereich").isVisible()) {
            params = params.filter(function (p) { return p.id !== "bereich"; });  // Computer-Richtlinie
          }
        }
        params.forEach(function (p) {
          var wert = b.getFieldValue(p.id);
          if (p.typ === "registry_zeilen") {
            parameter[p.id] = String(wert || "").split("|").map(function (e) { return e.trim(); }).filter(Boolean);
            return;
          }
          if (p.typ === "ja_nein") { wert = wert === "TRUE" ? "true" : "false"; }
          else if (p.typ === "variable") { wert = verweisText(wert); }
          else if (wert === SCHLEIFENWERT) { wert = { schleifenwert: true }; }  // Backend prüft, ob in Schleife
          else if (p.typ === "registry_daten" && b.getFieldValue(p.bezug || "typ") === "REG_MULTI_SZ") {
            // Blockly hat kein mehrzeiliges Feld: Einträge mit | trennen
            wert = String(wert || "").split("|").map(function (e) { return e.trim(); }).filter(Boolean);
          }
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
        if (editor) { editor.leer(); }
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
          if (editor) { editor.setzeGeneriert(r.json.text, s.anfrage.ziel, r.json.dateiname); }
          zuletztOk = true;
          statusEl.textContent = "Live-Vorschau (" + daten.ziele[s.anfrage.ziel] + ") – gespeichert wird erst beim Erzeugen.";
        } else {
          fehlerZeigen(r.json.fehler || [{ meldung: "Unerwarteter Fehler." }], s.positionen);
          if (editor) { editor.leer(); }
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
    ws.addChangeListener(function (ev) {
      if (ev.isUiEvent) { return; }
      // Schrittnummern/verfügbare Werte ändern sich beim Verschieben – Anzeige nachziehen
      if (ev.type === Blockly.Events.BLOCK_MOVE || ev.type === Blockly.Events.BLOCK_CREATE ||
          ev.type === Blockly.Events.BLOCK_DELETE) { verweiseAktualisieren(); }
      spaeter();
    });
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
      verweiseAktualisieren();
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

    // --- Schritte aus dem Registry-Panel einfügen -------------------------------------------
    /* Neuen Block unter „nach“ einhängen (ausgewählter Block bzw. zuletzt eingefügter), sonst ans Ende */
    function anhaengen(neu, nach) {
      if (nach && nach.type === "ablauf_start") {
        nach.getInput("SCHRITTE").connection.connect(neu.previousConnection);
      } else if (nach && nach.nextConnection && nach.workspace === ws && !nach.isInFlyout) {
        nach.nextConnection.connect(neu.previousConnection);
      } else {
        var start = ws.getBlocksByType("ablauf_start")[0];
        if (!start) { return; }
        var verbindung = start.getInput("SCHRITTE").connection;
        var letzter = verbindung.targetBlock();
        while (letzter && letzter.getNextBlock()) { letzter = letzter.getNextBlock(); }
        if (letzter) { letzter.nextConnection.connect(neu.previousConnection); } else { verbindung.connect(neu.previousConnection); }
      }
    }
    function einfuegen(schritte, info) {
      Object.keys((info && info.richtlinien) || {}).forEach(function (rid) {
        var r = info.richtlinien[rid];
        if (r) { richtlinienInfo[rid] = { titel: r.titel, klasse: r.klasse, parameter: r.parameter }; }
      });
      var sel = Blockly.getSelected ? Blockly.getSelected() : null;
      var letzter = null;
      Blockly.Events.setGroup(true);
      schritte.forEach(function (s) {
        var zustand = einzel({ art: "block", block_id: s.block_id, parameter: s.parameter });
        if (!zustand) { return; }
        delete zustand.id;  // Blockly vergibt eine neue ID
        var neu = Blockly.serialization.blocks.append(zustand, ws);
        anhaengen(neu, letzter || sel);
        letzter = neu;
      });
      Blockly.Events.setGroup(false);
      if (letzter) {
        if (Blockly.common && Blockly.common.setSelected) { Blockly.common.setSelected(letzter); } else if (letzter.select) { letzter.select(); }
        letzter.workspace.centerOnBlock && letzter.workspace.centerOnBlock(letzter.id);
      }
    }

    vorschau();
    window.okmBlockly = { arbeitsflaeche: ws, serialisieren: serialisieren, vorschau: vorschau, einfuegen: einfuegen };
  }

  document.addEventListener("DOMContentLoaded", init);
})();
