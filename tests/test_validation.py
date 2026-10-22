from __future__ import annotations

from typing import Any

import pytest

from app.escaping import Ziel
from app.models.block import Option, ParameterDef, ParamTyp
from app.models.request import SchrittEingabe, ScriptRequest
from app.validation import (
    FehlerSammlung,
    ValidierungsFehler,
    ir_zu_request,
    pruefe_wert_fuer_ziel,
    validiere_request,
    validiere_wert,
)
from tests.conftest import FESTE_ZEIT


def p(typ: ParamTyp, **kw: Any) -> ParameterDef:
    return ParameterDef(id="x", label="X", typ=typ, **kw)


GUELTIG: list[tuple[ParamTyp, Any, Any]] = [
    (ParamTyp.TEXT_KURZ, "Max Mustermann-2_b.c", "Max Mustermann-2_b.c"),
    (ParamTyp.TEXT_KURZ, "  Ärger  ", "Ärger"),
    (
        ParamTyp.TEXT,
        "Fertig! Bitte (jetzt) neu starten: ja/nein?",
        "Fertig! Bitte (jetzt) neu starten: ja/nein?",
    ),
    (ParamTyp.ZAHL, "42", 42),
    (ParamTyp.ZAHL, 7, 7),
    (ParamTyp.IPV4, "192.168.1.10", "192.168.1.10"),
    (ParamTyp.HOSTNAME, "drucker01.okm.local", "drucker01.okm.local"),
    (ParamTyp.HOSTNAME, "server.", "server"),
    (ParamTyp.IP_ODER_HOSTNAME, "10.0.0.1", "10.0.0.1"),
    (ParamTyp.IP_ODER_HOSTNAME, "intranet", "intranet"),
    (ParamTyp.PORT, "443", 443),
    (ParamTyp.PFAD_WINDOWS, "C:\\Daten\\Ordner\\", "C:\\Daten\\Ordner"),
    (ParamTyp.PFAD_WINDOWS, "c:/temp/x", "c:\\temp\\x"),
    (ParamTyp.PFAD_WINDOWS, "C:\\", "C:\\"),
    (ParamTyp.PFAD_UNIX, "/home/max/Dokumente/", "/home/max/Dokumente"),
    (ParamTyp.PFAD_UNIX, "/", "/"),
    (ParamTyp.PFAD, "D:\\Sicherung", "D:\\Sicherung"),
    (ParamTyp.PFAD, "/tmp/x", "/tmp/x"),
    (ParamTyp.UNC_PFAD, "\\\\fileserver\\abteilung\\", "\\\\fileserver\\abteilung"),
    (ParamTyp.UNC_PFAD, "//10.0.0.5/share/Unter Ordner", "\\\\10.0.0.5\\share\\Unter Ordner"),
    (ParamTyp.LAUFWERKSBUCHSTABE, "z", "Z:"),
    (ParamTyp.LAUFWERKSBUCHSTABE, "Z:", "Z:"),
    (ParamTyp.DIENSTNAME, "Spooler", "Spooler"),
    (ParamTyp.DIENSTNAME, "getty@tty1.service", "getty@tty1.service"),
    (ParamTyp.PROZESSNAME, "notepad.EXE", "notepad"),
    (ParamTyp.PAKETNAME, "Mozilla.Firefox", "Mozilla.Firefox"),
    (ParamTyp.PAKETNAME, "g++", "g++"),
    (ParamTyp.PAKETNAME, "Microsoft.VCRedist.2015+.x64", "Microsoft.VCRedist.2015+.x64"),
    (ParamTyp.PAKETNAME, "python@3.13", "python@3.13"),
    (ParamTyp.PAKETNAME, "logi-options+", "logi-options+"),
    (ParamTyp.DRUCKERNAME, "Drucker-Empfang_2", "Drucker-Empfang_2"),
    (ParamTyp.BENUTZERNAME, "max.mustermann", "max.mustermann"),
    (ParamTyp.URL, "https://intranet.okm.local/a?b=c%20d", "https://intranet.okm.local/a?b=c%20d"),
    (
        ParamTyp.SHA256,
        "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    ),
    (ParamTyp.JA_NEIN, "true", True),
    (ParamTyp.JA_NEIN, "nein", False),
    (ParamTyp.JA_NEIN, False, False),
]

UNGUELTIG: list[tuple[ParamTyp, Any]] = [
    (ParamTyp.TEXT_KURZ, "a;b"),
    (ParamTyp.TEXT_KURZ, "-rf"),
    (ParamTyp.TEXT_KURZ, "x" * 101),
    (ParamTyp.TEXT, 'Anführung "x"'),
    (ParamTyp.TEXT, "$(whoami)"),
    (ParamTyp.TEXT, "100%"),
    (ParamTyp.TEXT, "a & b"),
    (ParamTyp.ZAHL, "4.5"),
    (ParamTyp.ZAHL, "1e3"),
    (ParamTyp.ZAHL, True),
    (ParamTyp.IPV4, "192.168.1.300"),
    (ParamTyp.IPV4, "192.168.001.1"),
    (ParamTyp.IPV4, "1.2.3"),
    (ParamTyp.HOSTNAME, "-evil"),
    (ParamTyp.HOSTNAME, "a_b.local"),
    (ParamTyp.HOSTNAME, "host name"),
    (ParamTyp.HOSTNAME, "$(id)"),
    (ParamTyp.IP_ODER_HOSTNAME, "10.0.0.256"),
    (ParamTyp.IP_ODER_HOSTNAME, "a;b"),
    (ParamTyp.PORT, "0"),
    (ParamTyp.PORT, "65536"),
    (ParamTyp.PORT, "http"),
    (ParamTyp.PFAD_WINDOWS, "Daten\\Ordner"),
    (ParamTyp.PFAD_WINDOWS, "C:\\a|b"),
    (ParamTyp.PFAD_WINDOWS, 'C:\\a"b'),
    (ParamTyp.PFAD_WINDOWS, "C:\\" + "a" * 300),
    (ParamTyp.PFAD_UNIX, "relativ/pfad"),
    (ParamTyp.PFAD_UNIX, "~/Dokumente"),
    (ParamTyp.PFAD, "Ordner"),
    (ParamTyp.UNC_PFAD, "\\\\server"),
    (ParamTyp.UNC_PFAD, "C:\\share"),
    (ParamTyp.UNC_PFAD, "\\\\ser ver\\share"),
    (ParamTyp.UNC_PFAD, "\\\\server\\sh*re"),
    (ParamTyp.LAUFWERKSBUCHSTABE, "ZZ"),
    (ParamTyp.LAUFWERKSBUCHSTABE, "1"),
    (ParamTyp.DIENSTNAME, "Spooler & calc"),
    (ParamTyp.DIENSTNAME, "--help"),
    (ParamTyp.PROZESSNAME, "a*"),
    (ParamTyp.PAKETNAME, "-y"),
    (ParamTyp.PAKETNAME, "pkg;rm"),
    (ParamTyp.PAKETNAME, "homebrew/cask/firefox"),
    (ParamTyp.PAKETNAME, "firefox esr"),
    (ParamTyp.PAKETNAME, ".versteckt"),
    (ParamTyp.PAKETNAME, "a" * 129),
    (ParamTyp.DRUCKERNAME, "Mit Leerzeichen"),
    (ParamTyp.BENUTZERNAME, "max mustermann"),
    (ParamTyp.BENUTZERNAME, "a" * 21),
    (ParamTyp.URL, "ftp://server/datei"),
    (ParamTyp.URL, "javascript:alert(1)"),
    (ParamTyp.URL, "https://a b.de"),
    (ParamTyp.URL, "https://x.de/'$(id)'"),
    (ParamTyp.URL, "https:///pfad"),
    (ParamTyp.SHA256, "abc"),
    (ParamTyp.SHA256, "g" * 64),
    (ParamTyp.JA_NEIN, "vielleicht"),
]


@pytest.mark.parametrize(("typ", "roh", "erwartet"), GUELTIG)
def test_gueltige_werte(typ: ParamTyp, roh: Any, erwartet: Any) -> None:
    assert validiere_wert(p(typ), roh).wert == erwartet


@pytest.mark.parametrize(("typ", "roh"), UNGUELTIG)
def test_ungueltige_werte(typ: ParamTyp, roh: Any) -> None:
    with pytest.raises(ValidierungsFehler) as e:
        validiere_wert(p(typ), roh)
    assert str(e.value)  # verständliche Meldung vorhanden


@pytest.mark.parametrize("roh", ["a\nb", "a\x00", "x\u202ey"])
@pytest.mark.parametrize("typ", [ParamTyp.TEXT, ParamTyp.PFAD_UNIX, ParamTyp.PFAD_WINDOWS, ParamTyp.URL])
def test_steuerzeichen_immer_abgelehnt(typ: ParamTyp, roh: str) -> None:
    with pytest.raises(ValidierungsFehler):
        validiere_wert(p(typ), "/" + roh if typ is ParamTyp.PFAD_UNIX else roh)


def test_ip_fehlermeldung_fuer_laien() -> None:
    with pytest.raises(ValidierungsFehler, match=r"keine gültige IP-Adresse, Beispiel: 192\.168\.1\.10"):
        validiere_wert(p(ParamTyp.IPV4), "999.1.1.1")


def test_zahl_grenzen() -> None:
    with pytest.raises(ValidierungsFehler, match="mindestens 1"):
        validiere_wert(p(ParamTyp.ZAHL, min=1, max=5), 0)
    with pytest.raises(ValidierungsFehler, match="höchstens 5"):
        validiere_wert(p(ParamTyp.ZAHL, min=1, max=5), 6)


def test_auswahl() -> None:
    param = p(ParamTyp.AUSWAHL, optionen=[Option(wert="apt", label="apt"), Option(wert="dnf", label="dnf")])
    assert validiere_wert(param, "dnf").wert == "dnf"
    with pytest.raises(ValidierungsFehler, match="vorgegebenen"):
        validiere_wert(param, "yum")


def test_pflicht_und_standard() -> None:
    with pytest.raises(ValidierungsFehler, match="ausgefüllt"):
        validiere_wert(p(ParamTyp.TEXT_KURZ), "  ")
    assert validiere_wert(p(ParamTyp.TEXT_KURZ, pflicht=False), "").wert is None
    assert validiere_wert(p(ParamTyp.ZAHL, standard=4), "").wert == 4
    assert validiere_wert(p(ParamTyp.JA_NEIN, standard=True), None).wert is True


def test_pfad_passend_zum_ziel() -> None:
    win = validiere_wert(p(ParamTyp.PFAD), "C:\\x")
    unix = validiere_wert(p(ParamTyp.PFAD), "/tmp/x")
    pruefe_wert_fuer_ziel(win, Ziel.CMD)
    pruefe_wert_fuer_ziel(unix, Ziel.BASH)
    with pytest.raises(ValidierungsFehler):
        pruefe_wert_fuer_ziel(win, Ziel.ZSH)
    with pytest.raises(ValidierungsFehler):
        pruefe_wert_fuer_ziel(unix, Ziel.POWERSHELL)


def test_request_sammelt_alle_fehler(registry) -> None:
    req = ScriptRequest(
        ziel=Ziel.BASH,
        titel="Test",
        schritte=[
            SchrittEingabe(block_id="ping", parameter={"ziel": "999.1.1.1"}),
            SchrittEingabe(block_id="gibt_es_nicht"),
            SchrittEingabe(block_id="ping", parameter={"ziel": "a", "unbekannt": 1}),
            SchrittEingabe(block_id="setupdiag"),
        ],
    )
    with pytest.raises(FehlerSammlung) as e:
        validiere_request(req, registry, autor="t", jetzt=FESTE_ZEIT)
    meldungen = [f.meldung for f in e.value.fehler]
    assert any("IP-Adresse" in m for m in meldungen)
    assert any("Unbekannter Baustein" in m for m in meldungen)
    assert any("Unbekannter Parameter" in m for m in meldungen)
    assert any("nicht verfügbar" in m for m in meldungen)


def test_rote_bloecke_brauchen_bestaetigung(registry) -> None:
    req = ScriptRequest(ziel=Ziel.BASH, schritte=[SchrittEingabe(block_id="temp_aufraeumen")])
    with pytest.raises(FehlerSammlung, match="Ich weiß, was dieses Script tut"):
        validiere_request(req, registry, autor="t", jetzt=FESTE_ZEIT)
    # Admins brauchen keine Zusatzbestätigung, Simulation ebenfalls nicht
    validiere_request(req, registry, autor="t", jetzt=FESTE_ZEIT, ist_admin=True)
    validiere_request(req.model_copy(update={"dry_run": True}), registry, autor="t", jetzt=FESTE_ZEIT)


@pytest.mark.parametrize("titel", ['a"b', "a$b", "a`b", "a%b", "Zeile\nUmbruch"])
def test_titel_wird_geprueft(registry, titel: str) -> None:
    req = ScriptRequest(ziel=Ziel.BASH, titel=titel, schritte=[SchrittEingabe(block_id="systeminfo")])
    with pytest.raises(FehlerSammlung):
        validiere_request(req, registry, autor="t", jetzt=FESTE_ZEIT)


def test_ir_rueckweg(registry) -> None:
    req = ScriptRequest(
        ziel=Ziel.ZSH,
        titel="Rückweg",
        schritte=[SchrittEingabe(block_id="ping", parameter={"ziel": "10.0.0.1", "anzahl": "3"})],
    )
    ir = validiere_request(req, registry, autor="t", jetzt=FESTE_ZEIT)
    ir2 = validiere_request(ir_zu_request(ir, Ziel.ZSH), registry, autor="t", jetzt=FESTE_ZEIT)
    assert ir2.schritte == ir.schritte
