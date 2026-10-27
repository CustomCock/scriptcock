"""tools/admx_pruefen.py (monatlicher Workflow) – ohne Netz, mit nachgebauten Herstellerquellen."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT / "tools"))

import admx_pruefen as ap  # noqa: E402

URL = "https://download.microsoft.com/download/abc/Admin Templates.msi"
HASH = "a" * 64


def _ms_seite(urls: list[str], version: str = "5568.1000") -> str:
    # Ausschnitt wie auf microsoft.com/download/details.aspx (eingebettetes JSON)
    dateien = ",".join(f'{{"name":"x","url":"{u}"}}' for u in urls)
    return f'<script>window.__DLCDetails__={{"downloadFile":[{dateien}],"detailsSection_file_version":"{version}"}}'


def _edge(version: str) -> str:
    return json.dumps(
        [
            {"Product": "Stable", "Releases": [{"ProductVersion": "999.0"}]},
            {
                "Product": "Policy",
                "Releases": [
                    {"ProductVersion": "150.0.1.0", "Artifacts": []},
                    {
                        "ProductVersion": version,
                        "Artifacts": [
                            {"ArtifactName": "cab", "Location": "https://x/neu.cab", "Hash": "ABCD"}
                        ],
                    },
                ],
            },
        ]
    )


def _quellen(**paket: Any) -> dict[str, Any]:
    basis = {
        "id": "p",
        "name": "P",
        "format": "msi",
        "seite": "https://www.microsoft.com/s",
        "dateien": [{"url": URL, "sha256": HASH}],
    }
    return {"pakete": [{**basis, **paket}]}


def _holen(seiten: dict[str, str]):  # type: ignore[no-untyped-def]
    def holen(url: str) -> str:
        return seiten[url]

    return holen


def _arten(bericht: ap.Bericht) -> list[str]:
    return [b.art for b in bericht.befunde]


def test_ms_download_aktuell_und_neu() -> None:
    q = _quellen(aktualitaet="ms_download", seitenversion="5568.1000")
    ok = ap.pruefen(q, _holen({"https://www.microsoft.com/s": _ms_seite([URL])}), hashen=None)
    assert _arten(ok) == ["ok"] and not ok.zu_tun
    # Seite nennt eine neue Version
    neu = ap.pruefen(q, _holen({"https://www.microsoft.com/s": _ms_seite([URL], "5600.1000")}), hashen=None)
    assert _arten(neu) == ["neu"] and "5600.1000" in neu.befunde[0].text
    # Unsere Datei steht nicht mehr auf der Seite (neues Paket)
    weg = ap.pruefen(
        q,
        _holen({"https://www.microsoft.com/s": _ms_seite(["https://download.microsoft.com/neu.msi"])}),
        hashen=None,
    )
    assert _arten(weg) == ["neu"]
    # Seitenaufbau geändert → Fehler statt still „aktuell“
    kaputt = ap.pruefen(q, _holen({"https://www.microsoft.com/s": "<html></html>"}), hashen=None)
    assert _arten(kaputt) == ["fehler"]


def test_ms_download_ohne_seitenversion_vergleicht_nur_urls() -> None:
    q = _quellen(aktualitaet="ms_download")
    b = ap.pruefen(q, _holen({"https://www.microsoft.com/s": _ms_seite([URL], "1")}), hashen=None)
    assert _arten(b) == ["ok"]


def test_edge_api() -> None:
    q = _quellen(aktualitaet="edge_api", version="158.0.4344.0")
    gleich = ap.pruefen(q, _holen({ap.EDGE_API: _edge("158.0.4344.0")}), hashen=None)
    assert _arten(gleich) == ["ok"]
    neu = ap.pruefen(q, _holen({ap.EDGE_API: _edge("159.0.1.0")}), hashen=None)
    assert _arten(neu) == ["neu"]
    assert "https://x/neu.cab" in neu.befunde[0].text and "abcd" in neu.befunde[0].text  # Hash klein


def test_github_release() -> None:
    q = _quellen(aktualitaet="github_release", repo="mozilla/policy-templates", version="8.4")
    url = "https://api.github.com/repos/mozilla/policy-templates/releases/latest"
    assert _arten(ap.pruefen(q, _holen({url: '{"tag_name": "v8.4"}'}), hashen=None)) == ["ok"]
    assert _arten(ap.pruefen(q, _holen({url: '{"tag_name": "v8.10"}'}), hashen=None)) == [
        "neu"
    ]  # numerisch, nicht als Text


def test_hash_geaendert_und_unveraendert() -> None:
    q = _quellen(aktualitaet="hash")
    assert _arten(ap.pruefen(q, _holen({}), hashen=lambda _u: HASH)) == ["ok"]
    b = ap.pruefen(q, _holen({}), hashen=lambda _u: "b" * 64)
    assert _arten(b) == ["geaendert"] and b.zu_tun
    # Ohne Download wird nichts behauptet
    assert _arten(ap.pruefen(q, _holen({}), hashen=None)) == ["hand"]


def test_manuell_und_fehler_brechen_nicht_ab() -> None:
    q = {
        "pakete": [
            {"id": "m", "name": "M", "format": "manuell", "seite": "https://x"},
            {
                "id": "f",
                "name": "F",
                "format": "msi",
                "aktualitaet": "edge_api",
                "version": "1",
                "dateien": [],
            },
            {"id": "u", "name": "U", "format": "msi", "aktualitaet": "gibtsnicht", "dateien": []},
        ],
        "werkzeuge": [{"id": "w", "name": "W", "url": URL, "sha256": HASH, "aktualitaet": "hash"}],
    }

    def holen(url: str) -> str:
        raise OSError("nicht erreichbar")

    b = ap.pruefen(q, holen, hashen=lambda _u: HASH)
    assert [(x.eintrag, x.art) for x in b.befunde] == [
        ("m", "hand"),
        ("f", "fehler"),
        ("u", "fehler"),
        ("w", "ok"),
    ]
    text = b.markdown()
    assert "Quelle nicht erreichbar" in text and "admx_holen.py" in text


def test_echte_quellen_haben_gueltige_pruefart() -> None:
    quellen = yaml.safe_load((PROJEKT / "registry" / "admx-quellen.yaml").read_text(encoding="utf-8"))
    for e in quellen["pakete"] + quellen["werkzeuge"]:
        art = e.get("aktualitaet", "manuell")
        assert art in (*ap.PRUEFUNGEN, "hash", "manuell"), e["id"]
        if art == "manuell":
            assert e.get("format") == "manuell", (
                f"{e['id']}: herunterladbares Paket ohne automatische Prüfung"
            )
        if art == "github_release":
            assert e.get("repo"), e["id"]


def test_main_schreibt_bericht_und_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    datei = tmp_path / "q.yaml"
    datei.write_text(yaml.safe_dump(_quellen(aktualitaet="hash")), encoding="utf-8")
    monkeypatch.setattr(ap, "QUELLEN_YAML", datei)
    monkeypatch.setattr(ap, "hash_von_url", lambda _u: "c" * 64)
    assert ap.main(["--bericht", str(tmp_path / "b.md")]) == 1
    assert "geändert" in (tmp_path / "b.md").read_text(encoding="utf-8")
    assert ap.main(["--ohne-hash"]) == 0


def test_workflow_legt_issue_an() -> None:
    wf = yaml.safe_load((PROJEKT / ".github" / "workflows" / "admx-pruefen.yml").read_text(encoding="utf-8"))
    an = wf.get("on", wf.get(True))  # PyYAML liest „on“ als True
    assert "schedule" in an and "workflow_dispatch" in an
    assert wf["permissions"]["issues"] == "write"
    text = " ".join(str(s.get("run", "")) for s in wf["jobs"]["pruefen"]["steps"])
    assert "tools/admx_pruefen.py" in text and "gh issue create" in text and "gh issue comment" in text
