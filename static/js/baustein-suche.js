/* okm Script-Baukasten – Suche nach Bausteinen (Palette im Listen-Modus und Blockly-Toolbox).
   Reine Funktionen ohne DOM; gleiche Normalisierung wie der Software-Katalog (katalog-suche.js:
   Umlaute, Groß/klein, Akzente, - . _ egal). Läuft im Browser (window.OkmBausteinSuche) und unter Node. */
(function (wurzel, fabrik) {
  "use strict";
  var S = (typeof module === "object" && module.exports) ? require("./katalog-suche.js") : wurzel.OkmKatalogSuche;
  var api = fabrik(S);
  if (typeof module === "object" && module.exports) { module.exports = api; } else { wurzel.OkmBausteinSuche = api; }
})(this, function (S) {
  "use strict";

  /* bausteine: [{id, name, beschreibung, kategorie}] */
  function baueIndex(bausteine) {
    return bausteine.map(function (b, i) {
      return {
        nr: i,
        baustein: b,
        name: S.normalisiere(b.name),
        id: S.normalisiere(b.id),
        kategorie: S.normalisiere(b.kategorie),
        text: S.normalisiere(b.beschreibung || "")
      };
    });
  }

  /* 1 Name beginnt mit · 2 Name enthält · 3 Baustein-ID · 4 Kategorie · 5 Beschreibung; -1 = kein Treffer */
  function rang(e, wort) {
    if (e.name.indexOf(wort) === 0) { return 1; }
    if (e.name.indexOf(wort) > 0) { return 2; }
    if (e.id.indexOf(wort) >= 0) { return 3; }
    if (e.kategorie.indexOf(wort) >= 0) { return 4; }
    if (e.text.indexOf(wort) >= 0) { return 5; }
    return -1;
  }

  /* Alle Wörter müssen vorkommen (Teilwörter genügen). Ergebnis: [{baustein, nr, punkte}], bester zuerst;
     ohne Suchwort alle in der ursprünglichen Reihenfolge. */
  function suche(index, anfrage) {
    var woerter = String(anfrage || "").trim().split(/\s+/).map(S.normalisiere).filter(Boolean);
    var treffer = [];
    index.forEach(function (e) {
      var punkte = 0;
      for (var i = 0; i < woerter.length; i += 1) {
        var r = rang(e, woerter[i]);
        if (r < 0) { return; }
        punkte += r;
      }
      if (woerter.length && e.name === woerter.join("")) { punkte = 0; }
      treffer.push({ baustein: e.baustein, nr: e.nr, punkte: punkte });
    });
    if (woerter.length) {
      treffer.sort(function (a, b) {
        return a.punkte - b.punkte || a.baustein.name.localeCompare(b.baustein.name, "de") || a.nr - b.nr;
      });
    }
    return treffer;
  }

  /* Liste der zuletzt benutzten IDs: neueste vorn, ohne Doppelte, höchstens ``max`` */
  function zuletztDazu(liste, id, max) {
    var neu = [id].concat((liste || []).filter(function (x) { return x !== id; }));
    return neu.slice(0, max || 8);
  }

  return { baueIndex: baueIndex, suche: suche, zuletztDazu: zuletztDazu, trefferBereiche: S.trefferBereiche };
});
