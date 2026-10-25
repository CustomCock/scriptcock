/* okm Script-Baukasten – Registry-Panel als EINE Komponente (wie software-katalog.js).
 *
 *   var panel = RegistryKatalog.mount(element, {
 *     windows:         function () {…},               // true, wenn das Zielsystem PowerShell/CMD ist
 *     onUebernehmen:   function (schritte, info) {…}, // ＋ – schritte = [{block_id, parameter}], info.richtlinien
 *     kannUebernehmen: function () {…}                 // ob ＋ angezeigt wird (Standard: wenn onUebernehmen da ist)
 *   });
 *   panel.oeffnen(); panel.zielGeaendert();
 *   panel.waehleRichtlinie(function (schritt, info) {…}, aktuelleId);  // „Richtlinie wählen …“
 *
 * Drei Reiter: Richtlinien (ADMX, Suche per API), Häufige Einstellungen, Eigener Eintrag (+ .reg).
 * Daten nur über Textknoten ins DOM – kein innerHTML. Prüfen tut das Backend beim Erzeugen.
 */
(function () {
  "use strict";

  var ZUSTAENDE = [["aktiviert", "Aktiviert"], ["deaktiviert", "Deaktiviert"], ["nicht_konfiguriert", "Nicht konfiguriert (Werte entfernen)"]];
  var METHODEN = [["registry_direkt", "Registry direkt (wirkt sofort)"], ["lokale_gruppenrichtlinie", "Lokale Gruppenrichtlinie (LGPO, in gpedit sichtbar)"]];
  var BENUTZER_BEREICHE = [["angemeldeter_benutzer", "Angemeldeter Benutzer"], ["alle_benutzer", "Alle Benutzerprofile"], ["standardprofil", "Standardprofil (neue Benutzer)"]];
  var WIRKUNG = { sofort: "wirkt sofort", explorer_neustart: "nach Explorer-Neustart", gpupdate: "nach gpupdate", abmelden: "nach Neuanmeldung", neustart: "nach Neustart" };
  var SPEICHER_REITER = "okm.registry.reiter";

  function el(tag, klasse, text) {
    var e = document.createElement(tag);
    if (klasse) { e.className = klasse; }
    if (text !== undefined && text !== null) { e.textContent = text; }
    return e;
  }
  function lesen(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function schreiben(k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* egal */ } }
  function basis() { return document.body.getAttribute("data-basis") || ""; }

  function holen(pfad, nutzlast) {
    var opt = { credentials: "same-origin", headers: { "X-Okm-Request": "1" } };
    if (nutzlast !== undefined) {
      opt.method = "POST";
      opt.headers["Content-Type"] = "application/json";
      opt.body = JSON.stringify(nutzlast);
    }
    return window.fetch(basis() + pfad, opt).then(function (a) {
      if (a.status === 401) { window.location.href = basis() + "/login"; }
      return a.json().then(function (j) {
        if (!a.ok) { throw new Error(j.detail || j.fehler || "Fehler " + a.status); }
        return j;
      });
    });
  }
  function abfrage(werte) {
    return Object.keys(werte).filter(function (k) { return werte[k] !== "" && werte[k] !== null && werte[k] !== undefined; })
      .map(function (k) { return encodeURIComponent(k) + "=" + encodeURIComponent(werte[k]); }).join("&");
  }

  function kopieren(text, knopf) {
    function ok() {
      var alt = knopf.textContent;
      knopf.textContent = "✓";
      setTimeout(function () { knopf.textContent = alt; }, 1200);
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(ok, function () { /* markieren bleibt */ });
      return;
    }
    var f = document.createElement("textarea");
    f.value = text;
    f.className = "sr-only";
    document.body.appendChild(f);
    f.select();
    try { if (document.execCommand("copy")) { ok(); } } catch (e) { /* egal */ }
    document.body.removeChild(f);
  }

  function auswahl(optionen, wert) {
    var s = el("select");
    optionen.forEach(function (o) {
      var opt = el("option", null, o[1]);
      opt.value = o[0];
      if (o[0] === wert) { opt.selected = true; }
      s.appendChild(opt);
    });
    return s;
  }

  /* Formularfeld für einen Parameter (dynamische Elemente einer Richtlinie) */
  function feldFuer(p, id) {
    var e;
    if (p.typ === "ja_nein") {
      e = el("input");
      e.type = "checkbox";
      e.checked = p.standard === true;
    } else if (p.optionen && p.optionen.length) {
      e = auswahl(p.optionen.map(function (o) { return [o.wert, o.label]; }), p.standard === null ? null : String(p.standard));
    } else if (p.typ === "zahl") {
      e = el("input");
      e.type = "number";
      if (p.min !== null) { e.min = p.min; }
      if (p.max !== null) { e.max = p.max; }
      if (p.standard !== null) { e.value = p.standard; }
    } else if (p.typ === "registry_zeilen") {
      e = el("textarea");
      e.rows = 3;
      e.placeholder = p.hilfe || "Eine Zeile pro Eintrag";
    } else {
      e = el("input");
      e.type = "text";
      if (p.standard !== null) { e.value = p.standard; }
    }
    e.id = id;
    e.dataset.param = p.id;
    e.dataset.typ = p.typ;
    e.spellcheck = false;
    return e;
  }
  function feldWert(e) {
    if (e.type === "checkbox") { return e.checked; }
    if (e.dataset.typ === "registry_zeilen") {
      return e.value.split("\n").map(function (z) { return z.trim(); }).filter(Boolean);
    }
    return e.value;
  }

  // ======================================================================================
  // Komponente
  // ======================================================================================
  function mount(wurzel, optionen) {
    optionen = optionen || {};
    var eingeklappt = wurzel.tagName === "DETAILS";
    var $ = function (sel) { return wurzel.querySelector(sel); };
    var meldungEl = $("[data-meldung]");
    var zustand = {
      reiter: "richtlinien", geladen: {}, q: "", paket: "", klasse: "", kategorie: "", seite: 1,
      gesamt: 0, detail: null, auswahl: null, regSchritte: []
    };

    function melden(text) {
      meldungEl.textContent = "";
      setTimeout(function () { meldungEl.textContent = text; }, 30);
    }
    function windows() { return optionen.windows ? optionen.windows() : true; }
    function kannUebernehmen() {
      if (zustand.auswahl) { return true; }
      if (!optionen.onUebernehmen) { return false; }
      return optionen.kannUebernehmen ? optionen.kannUebernehmen() : true;
    }
    function uebernehmen(schritte, info) {
      if (!windows()) { melden("Registry-Bausteine gibt es nur für Windows."); return; }
      if (zustand.auswahl && schritte.length === 1 && schritte[0].block_id === "richtlinie_setzen") {
        var rueckruf = zustand.auswahl.rueckruf;
        auswahlBeenden();
        rueckruf(schritte[0], info || {});
        melden("Richtlinie in den Schritt übernommen.");
        return;
      }
      Promise.resolve(optionen.onUebernehmen(schritte, info || {})).then(function () {
        melden(schritte.length === 1 ? "Ins Script übernommen." : schritte.length + " Schritte übernommen.");
      });
    }
    function plusKnopf(text, aktion) {
      var k = el("button", "knopf knopf-uebernehmen", "＋ " + text);
      k.type = "button";
      k.hidden = !kannUebernehmen();
      k.disabled = !windows();
      k.title = windows() ? "Ins Script übernehmen" : "Nur für Windows-Zielsysteme";
      k.dataset.plus = "";
      k.addEventListener("click", aktion);
      return k;
    }
    function plusAktualisieren() {
      wurzel.querySelectorAll("[data-plus]").forEach(function (k) {
        k.hidden = !kannUebernehmen();
        k.disabled = !windows();
      });
      var hinweis = $("[data-ziel-hinweis]");
      hinweis.hidden = windows() || !kannUebernehmen();
      $("[data-eigen-uebernehmen]").hidden = !kannUebernehmen();
      $("[data-eigen-uebernehmen]").disabled = !windows();
      $("[data-reg-uebernehmen]").hidden = !kannUebernehmen();
      regAuswahlZaehlen();
    }

    // --- Reiter ------------------------------------------------------------------------------
    var reiterKnoepfe = Array.prototype.slice.call(wurzel.querySelectorAll("[data-reiter]"));
    function reiterZeigen(name, fokus) {
      zustand.reiter = name;
      reiterKnoepfe.forEach(function (k) {
        var an = k.dataset.reiter === name;
        k.setAttribute("aria-selected", String(an));
        k.tabIndex = an ? 0 : -1;
        document.getElementById(k.getAttribute("aria-controls")).hidden = !an;
        if (an && fokus) { k.focus(); }
      });
      schreiben(SPEICHER_REITER, name);
      laden(name);
    }
    reiterKnoepfe.forEach(function (k, nr) {
      k.addEventListener("click", function () { reiterZeigen(k.dataset.reiter, false); });
      k.addEventListener("keydown", function (ev) {
        var n = reiterKnoepfe.length;
        var ziel = ev.key === "ArrowRight" ? (nr + 1) % n : ev.key === "ArrowLeft" ? (nr - 1 + n) % n
          : ev.key === "Home" ? 0 : ev.key === "End" ? n - 1 : -1;
        if (ziel >= 0) { ev.preventDefault(); reiterZeigen(reiterKnoepfe[ziel].dataset.reiter, true); }
      });
    });
    function laden(name) {
      if (zustand.geladen[name]) { return; }
      zustand.geladen[name] = true;
      if (name === "richtlinien") { paketeLaden(); baumLaden(null, $("[data-baum]")); suchen(); }
      else if (name === "haeufig") { haeufigLaden(); }
      else if (name === "eigen") { pfadVorschau(); }
    }

    // --- Richtlinien: Filter, Baum, Suche ------------------------------------------------------
    var suchfeld = $("#regkat-suche");
    var paketWahl = $("[data-filter-paket]");
    function paketeLaden() {
      holen("/api/registry/pakete").then(function (j) {
        j.pakete.forEach(function (p) {
          var o = el("option", null, p.name + " (" + p.anzahl + ")");
          o.value = p.id;
          paketWahl.appendChild(o);
        });
      }).catch(function () { /* Filter bleibt „alle“ */ });
    }
    paketWahl.addEventListener("change", function () {
      zustand.paket = paketWahl.value;
      zustand.kategorie = "";
      var baum = $("[data-baum]");
      baum.textContent = "";
      baumLaden(null, baum);
      kategorieMarkieren();
      suchen();
    });
    wurzel.querySelectorAll("[data-klasse]").forEach(function (k) {
      k.addEventListener("click", function () {
        zustand.klasse = k.dataset.klasse;
        wurzel.querySelectorAll("[data-klasse]").forEach(function (x) {
          x.setAttribute("aria-pressed", String(x.dataset.klasse === zustand.klasse));
        });
        suchen();
      });
    });

    function kategorieMarkieren() {
      wurzel.querySelectorAll(".regkat-baum [data-kategorie]").forEach(function (k) {
        k.setAttribute("aria-pressed", String(k.dataset.kategorie === zustand.kategorie));
      });
    }
    $(".regkat-baum-alle").addEventListener("click", function () { zustand.kategorie = ""; kategorieMarkieren(); suchen(); });

    /* Kategoriebaum: Ebene für Ebene nachladen (Aufklappen = Kinder holen) */
    function baumLaden(eltern, ul) {
      holen("/api/registry/kategorien?" + abfrage({ eltern: eltern || "", paket: eltern ? "" : zustand.paket })).then(function (j) {
        j.kategorien.forEach(function (k) {
          var li = el("li");
          li.setAttribute("role", "treeitem");
          var zeile = el("div", "regkat-baum-zeile");
          var auf = el("button", "regkat-baum-auf", k.hat_kinder ? "▸" : "");
          auf.type = "button";
          auf.disabled = !k.hat_kinder;
          auf.setAttribute("aria-label", k.hat_kinder ? k.name + " aufklappen" : "");
          if (k.hat_kinder) { li.setAttribute("aria-expanded", "false"); } else { auf.setAttribute("aria-hidden", "true"); }
          var name = el("button", "regkat-baum-name");
          name.type = "button";
          name.dataset.kategorie = k.id;
          name.setAttribute("aria-pressed", "false");
          name.appendChild(el("span", null, k.name));
          name.appendChild(el("span", "regkat-anzahl", String(k.anzahl)));
          name.addEventListener("click", function () { zustand.kategorie = k.id; kategorieMarkieren(); suchen(); });
          zeile.appendChild(auf);
          zeile.appendChild(name);
          li.appendChild(zeile);
          var kinder = el("ul");
          kinder.setAttribute("role", "group");
          kinder.hidden = true;
          li.appendChild(kinder);
          auf.addEventListener("click", function () {
            var offen = kinder.hidden;
            kinder.hidden = !offen;
            auf.textContent = offen ? "▾" : "▸";
            li.setAttribute("aria-expanded", String(offen));
            if (offen && !kinder.dataset.geladen) { kinder.dataset.geladen = "1"; baumLaden(k.id, kinder); }
          });
          ul.appendChild(li);
        });
        kategorieMarkieren();
      }).catch(function () { ul.appendChild(el("li", "fehlertext", "Kategorien konnten nicht geladen werden.")); });
    }

    var suchZeit = null;
    var anfrageNr = 0;
    suchfeld.addEventListener("input", function () {
      clearTimeout(suchZeit);
      suchZeit = setTimeout(suchen, 150);
    });
    suchfeld.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && suchfeld.value) { ev.preventDefault(); ev.stopPropagation(); suchfeld.value = ""; suchen(); }
      else if (ev.key === "ArrowDown") {
        var erster = $("[data-liste] .regkat-treffer-knopf");
        if (erster) { ev.preventDefault(); erster.focus(); }
      }
    });
    $("[data-zurueck]").addEventListener("click", function () { if (zustand.seite > 1) { suchen(zustand.seite - 1); } });
    $("[data-weiter]").addEventListener("click", function () { if (zustand.seite * 25 < zustand.gesamt) { suchen(zustand.seite + 1); } });

    function suchen(seite) {
      zustand.seite = seite || 1;
      var nr = ++anfrageNr;
      var q = suchfeld.value.trim();
      holen("/api/registry/suche?" + abfrage({
        q: q, paket: zustand.paket, klasse: zustand.klasse, kategorie: zustand.kategorie, seite: zustand.seite
      })).then(function (j) {
        if (nr !== anfrageNr) { return; }  // veraltete Antwort
        zustand.gesamt = j.gesamt;
        trefferZeigen(j.treffer);
        $("[data-anzahl]").textContent = j.gesamt === 1 ? "1 Richtlinie" : j.gesamt.toLocaleString("de-DE") + " Richtlinien";
        $("[data-leer]").hidden = j.gesamt > 0;
        var seiten = Math.ceil(j.gesamt / 25);
        $("[data-seiten]").hidden = seiten <= 1;
        $("[data-seite]").textContent = "Seite " + zustand.seite + " von " + seiten;
        $("[data-zurueck]").disabled = zustand.seite <= 1;
        $("[data-weiter]").disabled = zustand.seite >= seiten;
      }).catch(function () { $("[data-anzahl]").textContent = "Suche nicht möglich."; });
    }

    function trefferZeigen(treffer) {
      var liste = $("[data-liste]");
      liste.textContent = "";
      treffer.forEach(function (t, nr) {
        var li = el("li", "katalog-eintrag regkat-eintrag");
        var k = el("button", "regkat-treffer-knopf");
        k.type = "button";
        k.appendChild(el("strong", "katalog-name", t.titel));
        var zeile = el("span", "regkat-treffer-info");
        zeile.appendChild(el("span", "marke marke-leise", t.paket));
        zeile.appendChild(el("span", "marke marke-leise", t.klasse_text));
        if (t.pfad) { zeile.appendChild(el("span", "regkat-pfad", t.pfad)); }
        k.appendChild(zeile);
        k.addEventListener("click", function () { detailLaden(t.id); });
        k.addEventListener("keydown", function (ev) {
          var alle = liste.querySelectorAll(".regkat-treffer-knopf");
          if (ev.key === "ArrowDown" && alle[nr + 1]) { ev.preventDefault(); alle[nr + 1].focus(); }
          else if (ev.key === "ArrowUp") { ev.preventDefault(); (alle[nr - 1] || suchfeld).focus(); }
        });
        li.appendChild(k);
        liste.appendChild(li);
      });
    }

    // --- Richtlinie: Detail + Formular -------------------------------------------------------------
    var detailEl = $("[data-detail]");
    function detailLaden(id) {
      return holen("/api/registry/richtlinie?" + abfrage({ id: id })).then(function (d) {
        zustand.detail = d;
        detailZeigen(d);
        detailEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }).catch(function (e) { melden(e.message); });
    }
    function zeileMit(label, inhalt) {
      var z = el("div", "regkat-detail-zeile");
      z.appendChild(el("span", "katalog-id-label", label));
      if (typeof inhalt === "string") { z.appendChild(el("span", null, inhalt)); } else { z.appendChild(inhalt); }
      return z;
    }
    function feldBlock(label, feld) {
      var f = el("div", "feld");
      var l = el("label", null, label);
      l.htmlFor = feld.id;
      if (feld.type === "checkbox") {
        var schalter = el("label", "schalter");
        schalter.appendChild(feld);
        schalter.appendChild(document.createTextNode(" " + label));
        f.appendChild(schalter);
      } else {
        f.appendChild(l);
        f.appendChild(feld);
      }
      return f;
    }
    function detailZeigen(d) {
      detailEl.textContent = "";
      detailEl.hidden = false;
      var kopf = el("div", "regkat-detail-kopf");
      kopf.appendChild(el("h3", null, d.titel));
      var zu = el("button", "knopf-klein", "✕");
      zu.type = "button";
      zu.setAttribute("aria-label", "Details schließen");
      zu.addEventListener("click", function () { detailEl.hidden = true; zustand.detail = null; });
      kopf.appendChild(zu);
      detailEl.appendChild(kopf);
      detailEl.appendChild(zeileMit("Paket", d.paket_name + (d.paket_version ? " " + d.paket_version : "") + " · " + d.datei));
      detailEl.appendChild(zeileMit("Gilt für", d.klasse_text));
      detailEl.appendChild(zeileMit("Kategorie", d.kategorie_pfad.join(" › ")));
      if (d.unterstuetzt) { detailEl.appendChild(zeileMit("Unterstützt auf", d.unterstuetzt)); }
      detailEl.appendChild(zeileMit("ID", (function () {
        var c = el("code", null, d.id);
        return c;
      })()));
      d.orte.forEach(function (o) {
        var z = el("div", "katalog-id");
        z.appendChild(el("span", "katalog-id-label", o.wertname ? "Wert" : "Schlüssel"));
        var code = el("code", null, o.schluessel + (o.wertname ? " → " + o.wertname : ""));
        code.title = code.textContent;
        z.appendChild(code);
        var knoepfe = el("span", "katalog-id-knoepfe");
        var k1 = el("button", "knopf-klein", "⧉");
        k1.type = "button";
        k1.title = "Schlüssel kopieren";
        k1.setAttribute("aria-label", "Schlüssel kopieren: " + o.schluessel);
        k1.addEventListener("click", function () { kopieren(o.schluessel, k1); });
        knoepfe.appendChild(k1);
        if (o.wertname) {
          var k2 = el("button", "knopf-klein", "W");
          k2.type = "button";
          k2.title = "Wertname kopieren";
          k2.setAttribute("aria-label", "Wertname kopieren: " + o.wertname);
          k2.addEventListener("click", function () { kopieren(o.wertname, k2); });
          knoepfe.appendChild(k2);
        }
        z.appendChild(knoepfe);
        detailEl.appendChild(z);
      });
      if (d.sprache !== "de") { detailEl.appendChild(el("p", "katalog-hinweis", "Keine deutsche Übersetzung – Text vom Hersteller auf Englisch.")); }
      var erkl = el("details", "regkat-erklaerung");
      erkl.open = true;
      erkl.appendChild(el("summary", null, "Erklärung"));
      erkl.appendChild(el("p", "regkat-erklaerung-text", d.erklaerung || "–"));
      detailEl.appendChild(erkl);

      // Formular: Zustand, Bereich (nur Benutzer-Richtlinien), Methode, Elemente
      var form = el("div", "regkat-formular");
      var zustandWahl = auswahl(ZUSTAENDE, "aktiviert");
      zustandWahl.id = "regkat-d-zustand";
      form.appendChild(feldBlock("Zustand", zustandWahl));
      var bereichWahl = null;
      if (d.klasse !== "machine") {
        var bereiche = (d.klasse === "both" ? [["computer", "Computer"]] : []).concat(BENUTZER_BEREICHE);
        bereichWahl = auswahl(bereiche, d.klasse === "both" ? "computer" : "angemeldeter_benutzer");
        bereichWahl.id = "regkat-d-bereich";
        form.appendChild(feldBlock("Für wen?", bereichWahl));
      }
      var methodeWahl = auswahl(METHODEN, "registry_direkt");
      methodeWahl.id = "regkat-d-methode";
      form.appendChild(feldBlock("Methode", methodeWahl));
      var lgpoHinweis = el("p", "feldhilfe", "Lokale Gruppenrichtlinie braucht davor den Schritt „Admin-Werkzeug bereitstellen“ (LGPO). " +
        "Bei Benutzer-Richtlinien gilt sie für alle Benutzer des Rechners.");
      lgpoHinweis.hidden = true;
      methodeWahl.addEventListener("change", function () { lgpoHinweis.hidden = methodeWahl.value !== "lokale_gruppenrichtlinie"; });
      form.appendChild(lgpoHinweis);
      var elemente = el("fieldset", "regkat-elemente");
      if (d.parameter.length) {
        elemente.appendChild(el("legend", null, "Optionen"));
        d.parameter.forEach(function (p) {
          var feld = feldFuer(p, "regkat-d-" + p.id);
          var block = feldBlock(p.label + (p.pflicht && p.typ !== "ja_nein" ? " *" : ""), feld);
          if (p.hilfe) { block.appendChild(el("p", "feldhilfe", p.hilfe)); }
          elemente.appendChild(block);
        });
        form.appendChild(elemente);
      }
      zustandWahl.addEventListener("change", function () { elemente.hidden = zustandWahl.value !== "aktiviert" || !d.parameter.length; });
      elemente.hidden = !d.parameter.length;
      detailEl.appendChild(form);

      var aktionen = el("div", "aktionen");
      aktionen.appendChild(plusKnopf(zustand.auswahl ? "In den Schritt übernehmen" : "Ins Script übernehmen", function () {
        var parameter = { richtlinie: d.id, zustand: zustandWahl.value, methode: methodeWahl.value };
        if (bereichWahl) { parameter.bereich = bereichWahl.value; }
        if (zustandWahl.value === "aktiviert") {
          elemente.querySelectorAll("[data-param]").forEach(function (f) { parameter[f.dataset.param] = feldWert(f); });
        }
        var info = { richtlinien: {} };
        info.richtlinien[d.id] = d;
        uebernehmen([{ block_id: "richtlinie_setzen", parameter: parameter }], info);
      }));
      if (!kannUebernehmen()) {
        aktionen.appendChild(el("p", "feldhilfe", "Zum Übernehmen im Baukasten, in Blockly oder in einem Rezept öffnen."));
      }
      detailEl.appendChild(aktionen);
    }

    // --- „Richtlinie wählen …“ für einen bestehenden Schritt/Block ----------------------------------
    var auswahlEl = $("[data-auswahlmodus]");
    function auswahlBeenden() {
      zustand.auswahl = null;
      auswahlEl.hidden = true;
      auswahlEl.textContent = "";
      plusAktualisieren();
    }
    function waehleRichtlinie(rueckruf, aktuelleId, bezeichnung) {
      zustand.auswahl = { rueckruf: rueckruf };
      auswahlEl.textContent = "";
      auswahlEl.appendChild(el("span", null, "Richtlinie wählen" + (bezeichnung ? " für " + bezeichnung : "") +
        " – „＋ In den Schritt übernehmen“ füllt den Schritt."));
      var ab = el("button", "katalog-filter-reset", "Abbrechen");
      ab.type = "button";
      ab.addEventListener("click", auswahlBeenden);
      auswahlEl.appendChild(ab);
      auswahlEl.hidden = false;
      oeffnen(false);
      reiterZeigen("richtlinien", false);
      plusAktualisieren();
      if (aktuelleId) { detailLaden(aktuelleId); }
      suchfeld.focus();
    }

    // --- Häufige Einstellungen ---------------------------------------------------------------------
    function haeufigLaden() {
      var ziel = $("[data-karten]");
      holen("/api/registry/haeufig").then(function (j) {
        var gruppen = {};
        var reihenfolge = [];
        j.eintraege.forEach(function (e) {
          if (!gruppen[e.gruppe]) { gruppen[e.gruppe] = []; reihenfolge.push(e.gruppe); }
          gruppen[e.gruppe].push(e);
        });
        reihenfolge.forEach(function (g) {
          ziel.appendChild(el("h3", "regkat-gruppe", g));
          var raster = el("ul", "katalog-liste regkat-kartenraster");
          gruppen[g].forEach(function (e) { raster.appendChild(karte(e, j.richtlinien)); });
          ziel.appendChild(raster);
        });
      }).catch(function () { ziel.appendChild(el("p", "fehlertext", "Häufige Einstellungen konnten nicht geladen werden.")); });
    }
    function karte(e, richtlinien) {
      var li = el("li", "katalog-eintrag regkat-karte");
      var kopf = el("div", "katalog-eintrag-kopf");
      kopf.appendChild(el("strong", "katalog-name", e.titel));
      kopf.appendChild(el("span", "risiko risiko-" + e.risiko, e.risiko));
      li.appendChild(kopf);
      li.appendChild(el("p", "katalog-beschreibung", e.beschreibung));
      var marken = el("div", "regkat-marken");
      marken.appendChild(el("span", "marke marke-leise", e.bereich === "computer" ? "Computer" : "Benutzer"));
      marken.appendChild(el("span", "marke marke-leise", WIRKUNG[e.wirkung] || e.wirkung));
      li.appendChild(marken);
      var ul = el("ul", "regkat-schritte");
      e.schritte.forEach(function (s) {
        var p = s.parameter;
        var text;
        if (s.block_id === "richtlinie_setzen") {
          var r = richtlinien[p.richtlinie];
          // Kategorie dazu: gleich benannte Richtlinien (z. B. je Office-Anwendung) unterscheidbar machen
          text = (r ? r.kategorie_pfad[0] + ": „" + r.titel + "“" : p.richtlinie) + " → " + p.zustand.replace("_", " ");
        } else {
          text = p.pfad + (p.wertname !== undefined ? " → " + (p.wertname || "(Standard)") : "") + (p.daten !== undefined ? " = " + p.daten : "");
        }
        ul.appendChild(el("li", null, text));
      });
      li.appendChild(ul);
      if (e.hinweis) { li.appendChild(el("p", "katalog-hinweis", e.hinweis)); }
      if (e.quelle) {
        var a = el("a", "katalog-link", "Quelle: " + e.quelle.titel);
        a.href = e.quelle.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        li.appendChild(a);
      } else {
        li.appendChild(el("p", "regkat-quelle", "Quelle: Administrative Vorlage des Herstellers"));
      }
      var aktionen = el("div", "aktionen");
      aktionen.appendChild(plusKnopf("Übernehmen", function () {
        uebernehmen(e.schritte, { richtlinien: richtlinien });
        if (e.anpassen && e.anpassen.length) { melden("Übernommen – bitte die Beispielwerte im Schritt anpassen."); }
      }));
      li.appendChild(aktionen);
      return li;
    }

    // --- Eigener Eintrag -----------------------------------------------------------------------------
    var eigen = $("[data-eigen]");
    function eigenFeld(id) { return eigen.querySelector("[name='regkat." + id + "']:not([type=hidden])"); }
    var pfadZeit = null;
    function pfadVorschau() {
      var pfad = eigenFeld("pfad").value.trim();
      var reg = $("[data-pfad-reg]"), ps = $("[data-pfad-ps]"), hinweis = $("[data-pfad-hinweis]");
      if (!pfad) { reg.textContent = "–"; ps.textContent = "–"; hinweis.textContent = ""; return; }
      holen("/api/registry/pfad?" + abfrage({ pfad: pfad, bereich: eigenFeld("bereich").value })).then(function (j) {
        reg.textContent = j.ok ? j.reg : "–";
        ps.textContent = j.ok ? j.ps : "–";
        hinweis.textContent = j.ok ? (j.hinweis || "") : j.fehler;
        hinweis.classList.toggle("fehlertext", !j.ok);
      }).catch(function () { /* Vorschau ist nur Komfort */ });
    }
    ["pfad", "bereich"].forEach(function (id) {
      var f = eigenFeld(id);
      f.addEventListener("input", function () { clearTimeout(pfadZeit); pfadZeit = setTimeout(pfadVorschau, 200); });
      f.addEventListener("change", pfadVorschau);
    });
    $("[data-eigen-uebernehmen]").addEventListener("click", function () {
      var parameter = {};
      ["bereich", "pfad", "wertname", "typ", "daten", "wenn_vorhanden", "wirkung"].forEach(function (id) {
        var f = eigenFeld(id);
        if (!f) { return; }
        var wert = f.value;
        if (id === "daten" && eigenFeld("typ").value === "REG_MULTI_SZ") {
          wert = wert.split("\n").map(function (z) { return z.trim(); }).filter(Boolean);
        }
        if (wert !== "" && !(Array.isArray(wert) && !wert.length)) { parameter[id] = wert; }
      });
      if (!parameter.pfad) { melden("Bitte einen Schlüssel angeben."); eigenFeld("pfad").focus(); return; }
      uebernehmen([{ block_id: "registry_wert_setzen", parameter: parameter }], {});
    });

    // --- .reg-Import ---------------------------------------------------------------------------------
    var regText = $("[data-reg-text]");
    var regErgebnis = $("[data-reg-ergebnis]");
    var regUebernehmen = $("[data-reg-uebernehmen]");
    $("[data-reg-datei]").addEventListener("change", function (ev) {
      var datei = ev.target.files && ev.target.files[0];
      if (!datei) { return; }
      if (datei.size > 1000000) { melden("Die Datei ist zu groß (höchstens 1 MB)."); return; }
      var leser = new FileReader();
      leser.onload = function () {
        var bytes = new Uint8Array(leser.result);
        var text;
        // regedit speichert UTF-16 LE mit BOM; REGEDIT4 ist ANSI
        if (bytes[0] === 0xff && bytes[1] === 0xfe) { text = new TextDecoder("utf-16le").decode(bytes.subarray(2)); }
        else {
          try { text = new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
          catch (e) { text = new TextDecoder("windows-1252").decode(bytes); }
        }
        regText.value = text.replace(/^﻿/, "");
        regAuswerten();
      };
      leser.readAsArrayBuffer(datei);
    });
    $("[data-reg-auswerten]").addEventListener("click", regAuswerten);
    function regAuswerten() {
      if (!regText.value.trim()) { melden("Bitte zuerst .reg-Inhalt einfügen."); return; }
      regErgebnis.textContent = "Wird ausgewertet …";
      holen("/api/registry/reg", { text: regText.value }).then(function (j) {
        zustand.regSchritte = j.schritte;
        regErgebnis.textContent = "";
        if (j.hinweise.length || j.fehler.length) {
          var box = el("div", j.fehler.length ? "fehlerbox" : "hinweis");
          var ul = el("ul");
          j.fehler.concat(j.hinweise).forEach(function (t) { ul.appendChild(el("li", null, t)); });
          box.appendChild(ul);
          regErgebnis.appendChild(box);
        }
        var liste = el("ul", "regkat-reg-liste");
        j.schritte.forEach(function (s, nr) {
          var li = el("li", "regkat-reg-eintrag" + (s.fehler.length ? " mit-fehler" : ""));
          var box = el("input");
          box.type = "checkbox";
          box.checked = !s.fehler.length;
          box.disabled = !!s.fehler.length;
          box.dataset.nr = String(nr);
          box.id = "regkat-reg-" + nr;
          box.addEventListener("change", regAuswahlZaehlen);
          var label = el("label");
          label.htmlFor = box.id;
          label.appendChild(el("span", "risiko risiko-" + s.risiko, s.risiko));
          label.appendChild(el("strong", null, " " + s.name + " "));
          label.appendChild(el("code", null, s.text));
          label.appendChild(el("span", "regkat-zeile", " (Zeile " + s.zeile + ")"));
          li.appendChild(box);
          li.appendChild(label);
          s.fehler.forEach(function (f) { li.appendChild(el("p", "fehlertext", f)); });
          liste.appendChild(li);
        });
        if (!j.schritte.length) { regErgebnis.appendChild(el("p", "katalog-leer", "Keine übernehmbaren Einträge gefunden.")); }
        regErgebnis.appendChild(liste);
        regAuswahlZaehlen();
      }).catch(function (e) { regErgebnis.textContent = ""; regErgebnis.appendChild(el("p", "fehlertext", e.message)); });
    }
    function regAusgewaehlt() {
      return Array.prototype.slice.call(regErgebnis.querySelectorAll("input[type=checkbox]:checked"))
        .map(function (b) { var s = zustand.regSchritte[Number(b.dataset.nr)]; return { block_id: s.block_id, parameter: s.parameter }; });
    }
    function regAuswahlZaehlen() {
      var n = regAusgewaehlt().length;
      $("[data-anzahl-reg]").textContent = String(n);
      regUebernehmen.disabled = n === 0 || !windows();
    }
    regUebernehmen.addEventListener("click", function () {
      var schritte = regAusgewaehlt();
      if (schritte.length) { uebernehmen(schritte, {}); }
    });

    // --- Ein-/Ausklappen -----------------------------------------------------------------------------
    function oeffnen(fokus) {
      if (eingeklappt && !wurzel.open) { wurzel.open = true; }
      laden(zustand.reiter);
      if (fokus) { suchfeld.focus(); }
    }
    var gemerkt = lesen(SPEICHER_REITER);
    if (gemerkt && document.getElementById("regkat-" + gemerkt)) { zustand.reiter = gemerkt; }
    reiterKnoepfe.forEach(function (k) {
      var an = k.dataset.reiter === zustand.reiter;
      k.setAttribute("aria-selected", String(an));
      k.tabIndex = an ? 0 : -1;
      document.getElementById(k.getAttribute("aria-controls")).hidden = !an;
    });
    if (eingeklappt) {
      wurzel.addEventListener("toggle", function () { if (wurzel.open) { laden(zustand.reiter); } });
    } else {
      laden(zustand.reiter);
    }
    plusAktualisieren();

    return {
      oeffnen: oeffnen,
      melden: melden,
      waehleRichtlinie: waehleRichtlinie,
      zielGeaendert: plusAktualisieren
    };
  }

  window.RegistryKatalog = { mount: mount };

  // ======================================================================================
  // Adapter je Seite
  // ======================================================================================

  /* Parameterwerte → Formular-/Abfragetext (Listen zeilenweise, ja/nein als true/false) */
  function alsText(wert) {
    if (Array.isArray(wert)) { return wert.join("\n"); }
    if (wert === true || wert === false) { return wert ? "true" : "false"; }
    return wert === null || wert === undefined ? "" : String(wert);
  }
  function flach(parameter) {
    var aus = {};
    Object.keys(parameter).forEach(function (k) { aus[k] = alsText(parameter[k]); });
    return aus;
  }
  function windowsZiel(container) {
    return function () {
      var r = container && container.querySelector("input[name=ziel]:checked");
      return !r || r.value === "powershell" || r.value === "cmd";
    };
  }

  var ADAPTER = {
    seite: function (wurzel) { return mount(wurzel, {}); },

    rezept: function (wurzel) {
      var form = document.querySelector("main form");
      function feld(sel) { return form && form.querySelector(sel); }
      function selectMit(wert) {
        var s = null;
        if (form) {
          form.querySelectorAll("select").forEach(function (x) { if (!s && x.querySelector("option[value='" + wert + "']")) { s = x; } });
        }
        return s;
      }
      function setzen(f, wert) {
        if (!f) { return; }
        f.value = wert;
        f.dispatchEvent(new Event("input", { bubbles: true }));
        f.dispatchEvent(new Event("change", { bubbles: true }));
      }
      var panel = mount(wurzel, {
        windows: function () { return ["powershell", "cmd"].indexOf(wurzel.dataset.ziel) >= 0; },
        kannUebernehmen: function () { return !!(feld("input[data-typ='richtlinie']") || feld("input[data-typ='registry_pfad']")); },
        onUebernehmen: function (schritte) {
          var s = schritte[0];
          var p = s.parameter;
          if (s.block_id === "richtlinie_setzen" && feld("input[data-typ='richtlinie']")) {
            setzen(feld("input[data-typ='richtlinie']"), p.richtlinie);
          } else if (s.block_id.indexOf("registry_") === 0 && feld("input[data-typ='registry_pfad']")) {
            setzen(feld("input[data-typ='registry_pfad']"), p.pfad);
            if (p.wertname !== undefined) { setzen(feld("input[data-typ='registry_wertname']"), p.wertname); }
            if (p.typ) { setzen(selectMit("REG_DWORD"), p.typ); }
            if (p.daten !== undefined) { setzen(feld("textarea[data-typ='registry_daten']"), alsText(p.daten)); }
            if (p.bereich) { setzen(selectMit("angemeldeter_benutzer"), p.bereich); }
          } else {
            panel.melden("Dieses Rezept hat kein passendes Feld – im Baukasten übernehmen.");
            return;
          }
          if (schritte.length > 1) { panel.melden("Nur der erste Eintrag passt ins Rezept – für mehrere den Baukasten nutzen."); }
        }
      });
      return panel;
    },

    baukasten: function (wurzel) {
      var bk = window.OkmBaukasten;
      var zielWahl = document.getElementById("ziel-wahl");
      var panel = mount(wurzel, {
        windows: windowsZiel(zielWahl),
        onUebernehmen: function (schritte) {
          var kette = Promise.resolve();
          schritte.forEach(function (s) {
            kette = kette.then(function () { return bk.hinzufuegen(s.block_id, flach(s.parameter)); });
          });
          return kette;
        }
      });
      if (zielWahl) { zielWahl.addEventListener("change", panel.zielGeaendert); }
      // „Richtlinie wählen …“ im Schritt → Panel; die Auswahl lädt den Schritt mit den Optionen neu
      document.addEventListener("click", function (ev) {
        var knopf = ev.target.closest("[data-richtlinie-waehlen]");
        if (!knopf) { return; }
        var li = knopf.closest("li.schritt");
        panel.waehleRichtlinie(function (schritt) {
          var werte = flach(schritt.parameter);
          // Nicht-Richtlinien-Felder des Schritts (Methode …) behalten, falls nicht neu gewählt
          bk.ersetzen(li, "richtlinie_setzen", werte);
        }, knopf.dataset.richtlinie || "", "diesen Schritt");
      });
      return panel;
    },

    blockly: function (wurzel) {
      var zielWahl = document.getElementById("bl-ziel");
      var panel = mount(wurzel, {
        windows: windowsZiel(zielWahl),
        onUebernehmen: function (schritte, info) {
          if (window.okmBlockly && window.okmBlockly.einfuegen) { window.okmBlockly.einfuegen(schritte, info); }
        }
      });
      if (zielWahl) { zielWahl.addEventListener("change", panel.zielGeaendert); }
      return panel;
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    var wurzel = document.getElementById("registry-katalog");
    if (!wurzel) { return; }
    var adapter = ADAPTER[wurzel.dataset.modus];
    if (adapter) { window.okmRegistry = adapter(wurzel); }
  });
})();
