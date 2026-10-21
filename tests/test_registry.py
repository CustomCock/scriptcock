from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from app.escaping import Ziel
from app.registry import RegistryFehler, lade_registry, platzhalter_in_quotes

GUELTIGER_BLOCK = """
id: test_block
name: Test
kategorie: Test
beschreibung: Ein Test.
risiko: gruen
parameter:
  - id: wert
    label: Wert
    typ: text_kurz
    beispiel: abc
ziele:
  bash: |
    printf '%s\\n' {{ wert }}
"""


def lade(tmp_path: Path, block: str, rezept: str | None = None) -> None:
    (tmp_path / "blocks").mkdir()
    (tmp_path / "recipes").mkdir()
    (tmp_path / "blocks" / "b.yaml").write_text(dedent(block), encoding="utf-8")
    if rezept:
        (tmp_path / "recipes" / "r.yaml").write_text(dedent(rezept), encoding="utf-8")
    lade_registry(tmp_path / "blocks", tmp_path / "recipes")


def test_echte_bibliothek_laedt(registry) -> None:
    assert len(registry.bloecke) >= 24
    assert len(registry.rezepte) >= 8
    for rezept in registry.rezepte.values():
        assert registry.rezept_ziele(rezept), rezept.id


def test_gueltiger_block(tmp_path: Path) -> None:
    lade(tmp_path, GUELTIGER_BLOCK)


@pytest.mark.parametrize(
    ("ersetzen", "durch", "meldung"),
    [
        ("{{ wert }}", "{{ unbekannt }}", "unbekannte Platzhalter"),
        ("{{ wert }}", "'{{ wert }}'", "in Anführungszeichen"),
        ("{{ wert }}", '"{{ wert }}"', "in Anführungszeichen"),
        ("printf", "eval printf", "'eval' ist verboten"),
        ("printf", "sudo printf", "'sudo'"),
        ("risiko: gruen", "risiko: lila", "risiko"),
        ("risiko: gruen", "risiko: gruen\nunbekanntes_feld: 1", "unbekanntes_feld"),
        ("    beispiel: abc", "    beispiel: 'a;b'", "beispiel"),
        ("    beispiel: abc", "", "beispiel"),
        ("typ: text_kurz", "typ: gibtsnicht", "typ"),
        ("{{ wert }}", "{{ wert ", "Syntaxfehler"),
        ("  bash: |", "  amiga: |", "ziele"),
    ],
)
def test_kaputte_bloecke_brechen_ab(tmp_path: Path, ersetzen: str, durch: str, meldung: str) -> None:
    with pytest.raises(RegistryFehler) as e:
        lade(tmp_path, GUELTIGER_BLOCK.replace(ersetzen, durch))
    text = str(e.value)
    assert "b.yaml" in text
    assert meldung in text


@pytest.mark.parametrize(
    ("vorlage", "meldung"),
    [
        ("echo %ERRORLEVEL%", "%ERRORLEVEL%"),
        ("setlocal EnableDelayedExpansion", "Delayed Expansion"),
        ("goto :ende", "'goto'"),
        ("call foo {{ wert }}", "'call'"),
        ("if x ( echo {{ wert }}", "Klammern"),
        ("exit /b 1", "'exit'"),
    ],
)
def test_cmd_regeln(tmp_path: Path, vorlage: str, meldung: str) -> None:
    block = GUELTIGER_BLOCK.replace("  bash: |\n    printf '%s\\n' {{ wert }}", f"  cmd: |\n    {vorlage}")
    assert "cmd:" in block
    with pytest.raises(RegistryFehler, match=meldung):
        lade(tmp_path, block)


def test_powershell_regeln(tmp_path: Path) -> None:
    block = GUELTIGER_BLOCK.replace(
        "  bash: |\n    printf '%s\\n' {{ wert }}", "  powershell: |\n    iex {{ wert }}"
    )
    with pytest.raises(RegistryFehler, match="Invoke-Expression"):
        lade(tmp_path, block)


def test_whatif_nur_powershell(tmp_path: Path) -> None:
    with pytest.raises(RegistryFehler, match="whatif"):
        lade(tmp_path, GUELTIGER_BLOCK.replace("{{ wert }}", "{{ wert }}{{ whatif }}"))


def test_rezept_verweise(tmp_path: Path) -> None:
    rezept = """
    id: r
    name: R
    kategorie: Test
    beschreibung: x
    felder:
      - id: feld
        label: Feld
        typ: ipv4
        beispiel: 10.0.0.1
    schritte:
      - block: test_block
        parameter: {wert: $feld, gibtsnicht: 1}
      - block: fehlt
    """
    with pytest.raises(RegistryFehler) as e:
        lade(tmp_path, GUELTIGER_BLOCK, rezept)
    text = str(e.value)
    assert "Typ ipv4" in text
    assert "keinen Parameter 'gibtsnicht'" in text
    assert "unbekannter Block 'fehlt'" in text


def test_platzhalter_heuristik() -> None:
    assert platzhalter_in_quotes("echo {{ a }}", Ziel.BASH) == []
    assert platzhalter_in_quotes("echo '{{ a }}'", Ziel.BASH) == [1]
    assert platzhalter_in_quotes('x\necho "a {{ a }}"', Ziel.POWERSHELL) == [2]
    assert platzhalter_in_quotes("tr -d '\"' {{ a }}", Ziel.BASH) == []
    assert platzhalter_in_quotes("{% if a.wert == 'x' %}{{ a }}{% endif %}", Ziel.BASH) == []
    # In CMD ist ' kein Quote-Zeichen
    assert platzhalter_in_quotes("for /f %%a in ('x') do echo {{ a }}", Ziel.CMD) == []
    assert platzhalter_in_quotes("echo it's {{ a }}", Ziel.CMD) == []
