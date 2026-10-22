/* okm Script-Baukasten – Suche im Software-Katalog (reine Funktionen, ohne DOM).
   Läuft im Browser (window.OkmKatalogSuche) und unter Node (module.exports) für die Tests. */
(function (wurzel, fabrik) {
  "use strict";
  var api = fabrik();
  if (typeof module === "object" && module.exports) { module.exports = api; } else { wurzel.OkmKatalogSuche = api; }
})(this, function () {
  "use strict";

  var UMLAUTE = { "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss" };
  var IGNORIERT = /[\s\-._]/;
  var PLATTFORMEN = {
    windows: ["winget"],
    macos: ["brew", "brew_cask"],
    linux: ["apt", "flatpak"],
    alle: ["winget", "brew", "brew_cask", "apt", "flatpak"]
  };
  var ZIEL_PLATTFORM = { powershell: "windows", cmd: "windows", bash: "linux", zsh: "macos" };

  /* Normalisiert Text für die Suche und merkt sich zu jedem Zeichen die Position im Original
     (für das Hervorheben): klein, Umlaute → ae/oe/ue/ss, Akzente weg, - . _ und Leerzeichen weg. */
  function normalisiereMitIndex(text) {
    var s = "";
    var idx = [];
    text = String(text || "");
    for (var i = 0; i < text.length; i += 1) {
      var c = text.charAt(i).toLowerCase();
      var r;
      if (UMLAUTE[c]) {
        r = UMLAUTE[c];
      } else if (IGNORIERT.test(c)) {
        r = "";
      } else {
        r = c.normalize ? c.normalize("NFD").replace(/[̀-ͯ]/g, "") : c;
      }
      for (var j = 0; j < r.length; j += 1) { s += r.charAt(j); idx.push(i); }
    }
    return { s: s, idx: idx };
  }

  function normalisiere(text) { return normalisiereMitIndex(text).s; }

  function suchwoerter(anfrage) {
    return String(anfrage || "").trim().split(/\s+/).map(normalisiere).filter(Boolean);
  }

  function ids(paket, plattform) {
    return (PLATTFORMEN[plattform] || PLATTFORMEN.alle)
      .filter(function (feld) { return paket[feld]; })
      .map(function (feld) { return { feld: feld, id: paket[feld] }; });
  }

  function plattformPasst(paket, plattform) {
    return plattform === "alle" || ids(paket, plattform).length > 0;
  }

  /* Bereitet den Katalog einmalig für die Suche vor. */
  function baueIndex(pakete) {
    return pakete.map(function (p, i) {
      return {
        nr: i,
        paket: p,
        name: normalisiere(p.name),
        ids: ids(p, "alle").map(function (e) { return normalisiere(e.id); }),
        begriffe: (p.suchbegriffe || []).map(normalisiere),
        text: normalisiere(p.beschreibung) + " " + normalisiere(p.kategorie) + " " + normalisiere(p.hinweis)
      };
    });
  }

  function enthaeltEines(liste, wort) {
    for (var i = 0; i < liste.length; i += 1) { if (liste[i].indexOf(wort) >= 0) { return true; } }
    return false;
  }

  /* Rang eines Suchworts in einem Eintrag (kleiner = besser), -1 = kein Treffer.
     1 Name beginnt mit · 2 Name enthält · 3 Paket-ID · 4 Suchbegriffe · 5 Beschreibung/Kategorie */
  function rang(e, wort) {
    if (e.name.indexOf(wort) === 0) { return 1; }
    if (e.name.indexOf(wort) > 0) { return 2; }
    if (enthaeltEines(e.ids, wort)) { return 3; }
    if (enthaeltEines(e.begriffe, wort)) { return 4; }
    if (e.text.indexOf(wort) >= 0) { return 5; }
    return -1;
  }

  /* optionen: { anfrage, plattform ("windows"|"macos"|"linux"|"alle"), kategorien: [] }
     Ergebnis: [{ paket, nr, punkte }] – bester Treffer zuerst; ohne Suchwort in Datei-Reihenfolge. */
  function suche(index, optionen) {
    var woerter = suchwoerter(optionen.anfrage);
    var ganz = woerter.join("");
    var plattform = optionen.plattform || "alle";
    var kategorien = optionen.kategorien || [];
    var treffer = [];
    index.forEach(function (e) {
      if (!plattformPasst(e.paket, plattform)) { return; }
      if (kategorien.length && kategorien.indexOf(e.paket.kategorie) < 0) { return; }
      var punkte = 0;
      for (var i = 0; i < woerter.length; i += 1) {
        var r = rang(e, woerter[i]);
        if (r < 0) { return; }
        punkte += r;
      }
      if (woerter.length && e.name === ganz) { punkte = 0; }  // exakter Name schlägt alles
      treffer.push({ paket: e.paket, nr: e.nr, punkte: punkte });
    });
    if (woerter.length) {
      treffer.sort(function (a, b) {
        return a.punkte - b.punkte || a.paket.name.localeCompare(b.paket.name, "de") || a.nr - b.nr;
      });
    }
    return treffer;
  }

  /* Bereiche [start, ende) im Originaltext, die zu den Suchwörtern passen (für <mark>). */
  function trefferBereiche(text, anfrage) {
    var n = normalisiereMitIndex(text);
    var bereiche = [];
    suchwoerter(anfrage).forEach(function (wort) {
      var pos = n.s.indexOf(wort);
      while (pos >= 0) {
        bereiche.push([n.idx[pos], n.idx[pos + wort.length - 1] + 1]);
        pos = n.s.indexOf(wort, pos + wort.length);
      }
    });
    bereiche.sort(function (a, b) { return a[0] - b[0]; });
    var zusammen = [];
    bereiche.forEach(function (b) {
      var letzter = zusammen[zusammen.length - 1];
      if (letzter && b[0] <= letzter[1]) { letzter[1] = Math.max(letzter[1], b[1]); } else { zusammen.push(b.slice()); }
    });
    return zusammen;
  }

  /* Kompletter Installationsbefehl zum Kopieren (nicht fürs Script – das erzeugt der Server). */
  function befehl(feld, id) {
    switch (feld) {
      case "winget": return "winget install --id " + id + " -e --source winget --accept-package-agreements --accept-source-agreements";
      case "brew": return "brew install " + id;
      case "brew_cask": return "brew install --cask " + id;
      case "apt": return "sudo apt install -y " + id;
      case "flatpak": return "flatpak install -y flathub " + id;
      default: return id;
    }
  }

  return {
    PLATTFORMEN: PLATTFORMEN,
    ZIEL_PLATTFORM: ZIEL_PLATTFORM,
    normalisiere: normalisiere,
    normalisiereMitIndex: normalisiereMitIndex,
    ids: ids,
    plattformPasst: plattformPasst,
    baueIndex: baueIndex,
    suche: suche,
    trefferBereiche: trefferBereiche,
    befehl: befehl
  };
});
