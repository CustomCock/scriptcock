"""Parametertypen und Validierung (Whitelist vor dem Escaping).

Jede Eingabe wird hier gegen ihren Parametertyp geprüft und normalisiert.
Erst danach entsteht eine :class:`~app.ir.ScriptIR`. Fehlermeldungen sind für
Laien formuliert.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from app import __version__
from app.escaping import UnsicherError, Ziel, pruefe_zeichen
from app.ir import (
    Abbrechen,
    Bestaetigung,
    BlockSchritt,
    Knoten,
    Kommentar,
    Optionen,
    ParamValue,
    ScriptIR,
    ScriptMeta,
    Vergleich,
    Warten,
    Wenn,
    WennFehler,
    Wiederhole,
)
from app.models.block import BlockDef, ParameterDef, ParamTyp, Risiko, RueckgabeDef, RueckgabeTyp
from app.models.request import (
    AbbrechenEingabe,
    BestaetigungEingabe,
    EingabeKnoten,
    KommentarEingabe,
    SchrittEingabe,
    ScriptRequest,
    WartenEingabe,
    WennEingabe,
    WennFehlerEingabe,
    WiederholeEingabe,
)

if TYPE_CHECKING:
    from app.registry import Registry


class ValidierungsFehler(ValueError):
    """Einzelner, für Laien verständlicher Fehler zu einem Wert."""


@dataclass
class Feldfehler:
    schritt: int | None  # Index des Schritts (None = allgemein)
    feld: str | None  # Parameter-ID
    meldung: str


@dataclass
class FehlerSammlung(Exception):
    fehler: list[Feldfehler] = field(default_factory=list)

    def __str__(self) -> str:
        return "; ".join(f.meldung for f in self.fehler)


# --- Einzeltypen --------------------------------------------------------------

_TEXT_KURZ = re.compile(r"^[\w\-. ]{1,100}$")
_TEXT_SONDER = set(".,:;!?-_()/+#'@=* ")
_HOST_LABEL = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_DIENST = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.@\-]{0,254}$")
_PROZESS = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_. \-]{0,63}$")
_PAKET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+@-]{0,127}$")
_DRUCKER = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,62}$")
_BENUTZER = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,19}$")
_WIN_PFAD = re.compile(r"^[A-Za-z]:\\")
_WIN_VERBOTEN = set('<>:"|?*')
_UNC_TEIL = re.compile(r"^[^\\/:*?\"<>|]+$")
_URL_VERBOTEN = set(" \"'<>`{}|\\^")


def _text(roh: Any) -> str:
    if roh is None:
        return ""
    if isinstance(roh, bool) or not isinstance(roh, str | int):
        raise ValidierungsFehler("Bitte einen Text eingeben.")
    text = str(roh).strip()
    try:
        pruefe_zeichen(text)
    except UnsicherError as e:
        raise ValidierungsFehler(str(e)) from None
    return text


def _kein_minus(text: str) -> None:
    # Werte, die mit "-" beginnen, könnten von Programmen als Option gelesen
    # werden (Option-Injection) – auch wenn sie korrekt gequotet sind.
    if text.startswith("-"):
        raise ValidierungsFehler("Der Wert darf nicht mit einem Minuszeichen (-) beginnen.")


def _text_kurz(text: str, p: ParameterDef) -> str:
    _kein_minus(text)
    if not _TEXT_KURZ.match(text):
        raise ValidierungsFehler(
            "Bitte nur Buchstaben, Ziffern, Leerzeichen und - _ . verwenden (höchstens 100 Zeichen)."
        )
    return text


def _text_frei(text: str, p: ParameterDef) -> str:
    if len(text) > 300:
        raise ValidierungsFehler("Der Text ist zu lang (höchstens 300 Zeichen).")
    for z in text:
        if not (z.isalnum() or z in _TEXT_SONDER):
            raise ValidierungsFehler(
                f"Das Zeichen „{z}“ ist hier nicht erlaubt. Erlaubt sind Buchstaben, Ziffern, "
                "Leerzeichen und . , : ; ! ? - _ ( ) / + # ' @ = *"
            )
    return text


def _zahl(roh: Any, p: ParameterDef) -> int:
    if isinstance(roh, bool):
        raise ValidierungsFehler("Bitte eine ganze Zahl eingeben, z. B. 4.")
    if isinstance(roh, int):
        n = roh
    else:
        text = _text(roh)
        if not re.fullmatch(r"-?[0-9]{1,9}", text):
            raise ValidierungsFehler("Bitte eine ganze Zahl eingeben, z. B. 4.")
        n = int(text)
    if p.min is not None and n < p.min:
        raise ValidierungsFehler(f"Die Zahl muss mindestens {p.min} sein.")
    if p.max is not None and n > p.max:
        raise ValidierungsFehler(f"Die Zahl darf höchstens {p.max} sein.")
    return n


def _port(roh: Any, p: ParameterDef) -> int:
    try:
        n = _zahl(roh, ParameterDef(id="port", label="Port", typ=ParamTyp.ZAHL, min=1, max=65535))
    except ValidierungsFehler:
        raise ValidierungsFehler(
            "Das ist kein gültiger Port. Ein Port ist eine Zahl von 1 bis 65535, z. B. 443."
        ) from None
    return n


def _ipv4(text: str, p: ParameterDef) -> str:
    try:
        return str(ipaddress.IPv4Address(text))
    except ValueError:
        raise ValidierungsFehler("Das ist keine gültige IP-Adresse, Beispiel: 192.168.1.10") from None


def _hostname(text: str, p: ParameterDef) -> str:
    name = text.rstrip(".")
    if not name or len(name) > 253 or not all(_HOST_LABEL.match(t) for t in name.split(".")):
        raise ValidierungsFehler(
            "Das ist kein gültiger Rechnername. Erlaubt sind Buchstaben, Ziffern, Bindestriche "
            "und Punkte, Beispiel: drucker01.okm.local"
        )
    return name


def _ip_oder_hostname(text: str, p: ParameterDef) -> str:
    if re.fullmatch(r"[0-9.]+", text):
        return _ipv4(text, p)
    try:
        return _hostname(text, p)
    except ValidierungsFehler:
        raise ValidierungsFehler(
            "Bitte eine IP-Adresse (z. B. 192.168.1.10) oder einen Rechnernamen "
            "(z. B. server01.okm.local) eingeben."
        ) from None


def _pfad_windows(text: str, p: ParameterDef) -> str:
    pfad = text.replace("/", "\\")
    if not _WIN_PFAD.match(pfad):
        raise ValidierungsFehler(
            "Bitte einen vollständigen Windows-Pfad mit Laufwerksbuchstaben angeben, "
            "z. B. C:\\Daten\\Projekte"
        )
    if any(z in _WIN_VERBOTEN for z in pfad[2:]):
        raise ValidierungsFehler('Ein Windows-Pfad darf diese Zeichen nicht enthalten: < > : " | ? *')
    if len(pfad) > 259:
        raise ValidierungsFehler("Der Pfad ist zu lang (höchstens 259 Zeichen).")
    if len(pfad) > 3:
        pfad = pfad.rstrip("\\")
    return pfad


def _pfad_unix(text: str, p: ParameterDef) -> str:
    if text.startswith("~"):
        raise ValidierungsFehler(
            "Bitte den vollständigen Pfad ohne ~ angeben, z. B. /home/max/Dokumente bzw. /Users/max/Documents"
        )
    if not text.startswith("/"):
        raise ValidierungsFehler("Bitte einen vollständigen Pfad angeben, der mit / beginnt, z. B. /tmp/test")
    if len(text) > 1024:
        raise ValidierungsFehler("Der Pfad ist zu lang (höchstens 1024 Zeichen).")
    if len(text) > 1:
        text = text.rstrip("/")
    return text


def _pfad(text: str, p: ParameterDef) -> str:
    if _WIN_PFAD.match(text.replace("/", "\\")):
        return _pfad_windows(text, p)
    if text.startswith(("/", "~")):
        return _pfad_unix(text, p)
    raise ValidierungsFehler(
        "Bitte einen vollständigen Pfad angeben – Windows: C:\\Daten\\Ordner, Linux/macOS: /home/max/Ordner"
    )


def pfad_ist_windows(wert: str) -> bool:
    return bool(_WIN_PFAD.match(wert))


def _unc(text: str, p: ParameterDef) -> str:
    pfad = text.replace("/", "\\")
    teile = pfad[2:].rstrip("\\").split("\\") if pfad.startswith("\\\\") else []
    fehler = ValidierungsFehler("Das ist kein gültiger Netzwerkpfad, Beispiel: \\\\fileserver\\abteilung")
    if len(teile) < 2:
        raise fehler
    try:
        _ip_oder_hostname(teile[0], p)
    except ValidierungsFehler:
        raise fehler from None
    if not all(_UNC_TEIL.match(t) for t in teile[1:]):
        raise fehler
    if len(pfad) > 259:
        raise ValidierungsFehler("Der Pfad ist zu lang (höchstens 259 Zeichen).")
    return "\\\\" + "\\".join(teile)


def _laufwerk(text: str, p: ParameterDef) -> str:
    if not re.fullmatch(r"[A-Za-z]:?", text):
        raise ValidierungsFehler("Bitte einen einzelnen Laufwerksbuchstaben angeben, z. B. Z")
    return text[0].upper() + ":"


def _regex_typ(muster: re.Pattern[str], meldung: str) -> Any:
    def pruefe(text: str, p: ParameterDef) -> str:
        _kein_minus(text)
        if not muster.match(text):
            raise ValidierungsFehler(meldung)
        return text

    return pruefe


def _prozessname(text: str, p: ParameterDef) -> str:
    if text.lower().endswith(".exe"):
        text = text[:-4]
    pruefe = _regex_typ(
        _PROZESS,
        "Das ist kein gültiger Prozessname. Erlaubt sind Buchstaben, Ziffern, Leerzeichen und _ . -, "
        "z. B. notepad",
    )
    result: str = pruefe(text, p)
    return result


def _sha256(text: str, p: ParameterDef) -> str:
    wert = text.replace(" ", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", wert):
        raise ValidierungsFehler(
            "Das ist keine gültige SHA-256-Prüfsumme (64 Zeichen 0–9 und a–f), "
            "z. B. e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )
    return wert


def _url(text: str, p: ParameterDef) -> str:
    fehler = ValidierungsFehler(
        "Das ist keine gültige Internetadresse. Sie muss mit http:// oder https:// beginnen, "
        "z. B. https://intranet.okm.local/datei.zip"
    )
    if len(text) > 2048 or any(z in _URL_VERBOTEN for z in text):
        raise fehler
    try:
        teile = urlsplit(text)
    except ValueError:
        raise fehler from None
    if teile.scheme.lower() not in ("http", "https") or not teile.hostname:
        raise fehler
    return text


_VERWEIS = re.compile(r"^([1-9][0-9]{0,2})\.([a-z][a-z0-9_]{0,39})$")


def _variable(text: str, p: ParameterDef) -> str:
    """Verweis ``<schritt>.<rueckgabe_id>`` – ob es den Wert dort gibt, prüft ``_BaumPruefer``."""
    if not _VERWEIS.match(text):
        raise ValidierungsFehler(
            "Bitte einen Wert aus einem vorherigen Schritt wählen "
            "(Schritt-Nummer und Wert, z. B. 3.frei_prozent)."
        )
    return text


def verweis_teile(wert: str) -> tuple[int, str]:
    nr, rid = wert.split(".", 1)
    return int(nr), rid


def _auswahl(text: str, p: ParameterDef) -> str:
    erlaubt = [o.wert for o in p.optionen]
    if text not in erlaubt:
        labels = ", ".join(o.label for o in p.optionen)
        raise ValidierungsFehler(f"Bitte eine der vorgegebenen Möglichkeiten wählen: {labels}")
    return text


def _ja_nein(roh: Any, p: ParameterDef) -> bool:
    if isinstance(roh, bool):
        return roh
    text = _text(roh).lower()
    if text in ("1", "true", "ja", "on", "yes", "j"):
        return True
    if text in ("", "0", "false", "nein", "off", "no", "n"):
        return False
    raise ValidierungsFehler("Bitte Ja oder Nein wählen.")


_TEXT_PRUEFER: dict[ParamTyp, Any] = {
    ParamTyp.TEXT_KURZ: _text_kurz,
    ParamTyp.TEXT: _text_frei,
    ParamTyp.IPV4: _ipv4,
    ParamTyp.HOSTNAME: _hostname,
    ParamTyp.IP_ODER_HOSTNAME: _ip_oder_hostname,
    ParamTyp.PFAD: _pfad,
    ParamTyp.PFAD_WINDOWS: _pfad_windows,
    ParamTyp.PFAD_UNIX: _pfad_unix,
    ParamTyp.UNC_PFAD: _unc,
    ParamTyp.LAUFWERKSBUCHSTABE: _laufwerk,
    ParamTyp.DIENSTNAME: _regex_typ(
        _DIENST,
        "Das ist kein gültiger Dienstname. Erlaubt sind Buchstaben, Ziffern und _ . @ -, "
        "ohne Leerzeichen, z. B. Spooler",
    ),
    ParamTyp.PROZESSNAME: _prozessname,
    ParamTyp.PAKETNAME: _regex_typ(
        _PAKET,
        "Das ist kein gültiger Paketname. Erlaubt sind Buchstaben, Ziffern und _ . + - @, "
        "z. B. Mozilla.Firefox oder firefox",
    ),
    ParamTyp.DRUCKERNAME: _regex_typ(
        _DRUCKER,
        "Das ist kein gültiger Druckername. Erlaubt sind Buchstaben, Ziffern und _ . -, ohne "
        "Leerzeichen (höchstens 63 Zeichen), z. B. Drucker-Empfang",
    ),
    ParamTyp.BENUTZERNAME: _regex_typ(
        _BENUTZER,
        "Das ist kein gültiger Benutzername. Erlaubt sind Buchstaben, Ziffern und _ . -, ohne "
        "Leerzeichen (höchstens 20 Zeichen), z. B. max.mustermann",
    ),
    ParamTyp.URL: _url,
    ParamTyp.SHA256: _sha256,
    ParamTyp.AUSWAHL: _auswahl,
    ParamTyp.VARIABLE: _variable,
}


def validiere_wert(p: ParameterDef, roh: Any) -> ParamValue:
    """Prüft einen Rohwert gegen die Parameterdefinition.

    Leere Werte: Pflichtfeld → Fehler; sonst ``standard`` bzw. ``None``.
    """
    leer = roh is None or (isinstance(roh, str) and roh.strip() == "")
    if leer and p.typ is not ParamTyp.JA_NEIN:
        if p.standard is not None:
            roh = p.standard
        elif p.pflicht:
            raise ValidierungsFehler("Dieses Feld muss ausgefüllt werden.")
        else:
            return ParamValue(typ=p.typ, wert=None)
    if leer and p.typ is ParamTyp.JA_NEIN and p.standard is not None:
        roh = p.standard

    wert: str | int | bool
    if p.typ is ParamTyp.ZAHL:
        wert = _zahl(roh, p)
    elif p.typ is ParamTyp.PORT:
        wert = _port(roh, p)
    elif p.typ is ParamTyp.JA_NEIN:
        wert = _ja_nein(roh, p)
    else:
        text = _text(roh)
        wert = _TEXT_PRUEFER[p.typ](text, p)
    return ParamValue(typ=p.typ, wert=wert)


def pruefe_wert_fuer_ziel(wert: ParamValue, ziel: Ziel) -> None:
    """Zielabhängige Zusatzprüfungen (z. B. Windows-Pfad nicht unter Linux)."""
    if wert.wert is None:
        return
    windows = ziel in (Ziel.POWERSHELL, Ziel.CMD)
    if wert.typ is ParamTyp.PFAD and isinstance(wert.wert, str):
        if windows and not pfad_ist_windows(wert.wert):
            raise ValidierungsFehler("Für Windows bitte einen Windows-Pfad angeben, z. B. C:\\Daten")
        if not windows and pfad_ist_windows(wert.wert):
            raise ValidierungsFehler("Für Linux/macOS bitte einen Pfad wie /home/max/Daten angeben.")
    if ziel is Ziel.CMD and isinstance(wert.wert, str) and '"' in wert.wert:
        raise ValidierungsFehler('Anführungszeichen (") sind in Windows-CMD-Scripten nicht erlaubt.')


# --- Ganzer Request -> IR -------------------------------------------------------

_TITEL_VERBOTEN = set('"`$%^&|<>\\')


def _meta_text(roh: str, max_laenge: int, mehrzeilig: bool) -> str:
    text = roh.replace("\r\n", "\n").strip()
    zeilen = text.split("\n") if mehrzeilig else [text]
    for zeile in zeilen:
        pruefe_zeichen(zeile)
    if len(text) > max_laenge:
        raise ValidierungsFehler(f"Der Text ist zu lang (höchstens {max_laenge} Zeichen).")
    return text


MAX_BLOECKE = 100
MAX_TIEFE = 4
MAX_WIEDERHOLUNGEN = 50
_ANZAHL = ParameterDef(
    id="anzahl", label="Anzahl Wiederholungen", typ=ParamTyp.ZAHL, min=1, max=MAX_WIEDERHOLUNGEN
)
MAX_WARTEN = 3600
_SEKUNDEN = ParameterDef(id="sekunden", label="Sekunden", typ=ParamTyp.ZAHL, min=1, max=MAX_WARTEN)
_CODE = ParameterDef(id="code", label="Exit-Code", typ=ParamTyp.ZAHL, min=0, max=99)
_MELDUNG = ParameterDef(id="meldung", label="Meldung", typ=ParamTyp.TEXT)
_NOTIZ = ParameterDef(id="text", label="Notiz", typ=ParamTyp.TEXT)
_VERWEIS_WERT = ParameterDef(id="wert", label="Wert", typ=ParamTyp.VARIABLE, variable_typ=RueckgabeTyp.ZAHL)
_VERGLEICHSZAHL = ParameterDef(
    id="zahl", label="Vergleichszahl", typ=ParamTyp.ZAHL, min=-999_999_999, max=999_999_999
)


class _BaumPruefer:
    """Prüft den Schritt-Baum rekursiv.

    ``Feldfehler.schritt`` ist die Position des Knotens in Vorordnung (Pre-Order) über
    *alle* Knoten. Bei flachen Listen entspricht das dem Listenindex.
    """

    def __init__(self, registry: Registry, ziel: Ziel, fehler: list[Feldfehler]) -> None:
        self.registry = registry
        self.ziel = ziel
        self.fehler = fehler
        self.position = 0
        self.anzahl_bloecke = 0
        self.hat_rot = False
        # Für Verweise auf Rückgabewerte: Schrittnummer -> (Block, umgebende „Versuche“-Blöcke).
        # bash/zsh führen „Versuche“ in einer Subshell aus – dort gesetzte Werte gibt es danach nicht.
        self.versuche: list[int] = []
        self.anzahl_versuche = 0
        self.bekannt: dict[int, tuple[BlockDef, tuple[int, ...]]] = {}

    def liste(self, eingaben: list[EingabeKnoten], tiefe: int) -> list[Knoten]:
        ergebnis: list[Knoten] = []
        for eingabe in eingaben:
            knoten = self.knoten(eingabe, tiefe)
            if knoten is not None:
                ergebnis.append(knoten)
        return ergebnis

    def knoten(self, eingabe: EingabeKnoten, tiefe: int) -> Knoten | None:
        i = self.position
        self.position += 1
        if isinstance(eingabe, SchrittEingabe):
            return self.block(i, eingabe)
        if isinstance(eingabe, AbbrechenEingabe | WartenEingabe | BestaetigungEingabe | KommentarEingabe):
            return self.blatt(i, eingabe)
        if tiefe >= MAX_TIEFE:
            self.fehler.append(Feldfehler(i, None, f"Höchstens {MAX_TIEFE} Ebenen ineinander verschachteln."))
        if isinstance(eingabe, WennFehlerEingabe):
            if not eingabe.versuche:
                self.fehler.append(Feldfehler(i, None, "„Versuche“ braucht mindestens einen Schritt."))
            self.anzahl_versuche += 1
            self.versuche.append(self.anzahl_versuche)
            versuche = self.liste(eingabe.versuche, tiefe + 1)
            self.versuche.pop()
            sonst = self.liste(eingabe.sonst, tiefe + 1)
            return WennFehler(versuche=versuche, sonst=sonst)
        if isinstance(eingabe, WennEingabe):
            return self.wenn(i, eingabe, tiefe)
        # WiederholeEingabe
        anzahl = 1
        try:
            wert = validiere_wert(_ANZAHL, eingabe.anzahl).wert
            anzahl = wert if isinstance(wert, int) else 1
        except ValidierungsFehler as e:
            self.fehler.append(Feldfehler(i, "anzahl", f"{_ANZAHL.label}: {e}"))
        if not eingabe.rumpf:
            self.fehler.append(Feldfehler(i, None, "„Wiederhole“ braucht mindestens einen Schritt."))
        return Wiederhole(anzahl=anzahl, rumpf=self.liste(eingabe.rumpf, tiefe + 1))

    def _wert(self, i: int, p: ParameterDef, roh: Any) -> Any:
        try:
            return validiere_wert(p, roh).wert
        except ValidierungsFehler as e:
            self.fehler.append(Feldfehler(i, p.id, f"{p.label}: {e}"))
            return None

    def blatt(
        self, i: int, eingabe: AbbrechenEingabe | WartenEingabe | BestaetigungEingabe | KommentarEingabe
    ) -> Knoten:
        if isinstance(eingabe, AbbrechenEingabe):
            if self.versuche:
                self.fehler.append(
                    Feldfehler(
                        i,
                        None,
                        "„Abbrechen“ geht nicht innerhalb von „Versuche“ – dort würde nur der Versuch "
                        "beendet. Bitte dahinter setzen oder „Wenn …“ verwenden.",
                    )
                )
            meldung = self._wert(i, _MELDUNG, eingabe.meldung)
            code = self._wert(i, _CODE, eingabe.code)
            return Abbrechen(meldung=meldung or "", code=code if isinstance(code, int) else 1)
        if isinstance(eingabe, WartenEingabe):
            sek = self._wert(i, _SEKUNDEN, eingabe.sekunden)
            return Warten(sekunden=sek if isinstance(sek, int) else 1)
        if isinstance(eingabe, BestaetigungEingabe):
            return Bestaetigung(meldung=self._wert(i, _MELDUNG, eingabe.meldung) or "")
        return Kommentar(text=self._wert(i, _NOTIZ, eingabe.text) or "")

    def wenn(self, i: int, eingabe: WennEingabe, tiefe: int) -> Wenn:
        wert = self._wert(i, _VERWEIS_WERT, eingabe.wert)
        try:
            vergleich = Vergleich(str(eingabe.vergleich))
        except ValueError:
            vergleich = Vergleich.UNBEKANNT
            self.fehler.append(
                Feldfehler(
                    i,
                    "vergleich",
                    "Bitte einen Vergleich wählen (=, ≠, <, >, ≤, ≥, ist ja, ist nein, ist unbekannt).",
                )
            )
        zahl: int | None = None
        if vergleich.mit_zahl:
            leer = eingabe.zahl is None or (isinstance(eingabe.zahl, str) and not eingabe.zahl.strip())
            if leer:
                self.fehler.append(Feldfehler(i, "zahl", "Bitte eine Vergleichszahl angeben."))
            else:
                z = self._wert(i, _VERGLEICHSZAHL, eingabe.zahl)
                zahl = z if isinstance(z, int) else None
        if isinstance(wert, str):
            try:
                r = self.verweis_pruefen(self.anzahl_bloecke + 1, wert, None)
                if r.typ is RueckgabeTyp.ZAHL and vergleich in (Vergleich.JA, Vergleich.NEIN):
                    raise ValidierungsFehler(
                        f"„{r.id}“ ist eine Zahl – „ist ja“/„ist nein“ gehen nur bei ja/nein-Werten."
                    )
                if r.typ is RueckgabeTyp.JA_NEIN and vergleich.mit_zahl:
                    raise ValidierungsFehler(
                        f"„{r.id}“ ist ja/nein – Vergleiche wie < oder = gehen nur bei Zahlen."
                    )
            except ValidierungsFehler as e:
                self.fehler.append(Feldfehler(i, "wert", f"Wert: {e}"))
        dann = self.liste(eingabe.dann, tiefe + 1)
        sonst = self.liste(eingabe.sonst, tiefe + 1)
        if not eingabe.dann and not eingabe.sonst:
            self.fehler.append(
                Feldfehler(i, None, "„Wenn“ braucht mindestens einen Schritt bei „dann“ oder „sonst“.")
            )
        return Wenn(
            wert=wert if isinstance(wert, str) else "1.x",
            vergleich=vergleich,
            zahl=zahl,
            dann=dann,
            sonst=sonst,
        )

    def block(self, i: int, eingabe: SchrittEingabe) -> BlockSchritt | None:
        self.anzahl_bloecke += 1
        nr = self.anzahl_bloecke
        block = self.registry.bloecke.get(eingabe.block_id)
        if block is not None:
            self.bekannt[nr] = (block, tuple(self.versuche))
        if block is None:
            self.fehler.append(Feldfehler(i, None, f"Unbekannter Baustein „{eingabe.block_id}“."))
            return None
        if not block.verfuegbar(self.ziel):
            self.fehler.append(
                Feldfehler(i, None, f"„{block.name}“ ist für dieses Zielsystem nicht verfügbar.")
            )
        if block.risiko is Risiko.ROT:
            self.hat_rot = True
        for name in sorted(set(eingabe.parameter) - {p.id for p in block.parameter}):
            self.fehler.append(Feldfehler(i, name, f"Unbekannter Parameter „{name}“."))
        werte: dict[str, ParamValue] = {}
        genutzt = self.registry.benutzte_parameter(block, self.ziel)
        for p in block.parameter:
            if p.id not in genutzt and eingabe.parameter.get(p.id) in (None, ""):
                # Für dieses Zielsystem nicht verwendet – daher auch keine Pflicht.
                continue
            try:
                wert = validiere_wert(p, eingabe.parameter.get(p.id))
                pruefe_wert_fuer_ziel(wert, self.ziel)
                if p.typ is ParamTyp.VARIABLE and isinstance(wert.wert, str):
                    self.verweis_pruefen(nr, wert.wert, p.variable_typ)
                werte[p.id] = wert
            except ValidierungsFehler as e:
                self.fehler.append(Feldfehler(i, p.id, f"{p.label}: {e}"))
        return BlockSchritt(block_id=block.id, block_version=block.version, parameter=werte)

    def verweis_pruefen(self, nr: int, wert: str, erwartet: RueckgabeTyp | None) -> RueckgabeDef:
        """Löst ``"<schritt>.<id>"`` auf; ``nr`` = Nummer des Blocks, der den Wert liest."""
        quelle_nr, rid = verweis_teile(wert)
        if quelle_nr >= nr:
            raise ValidierungsFehler(
                f"Der Wert aus Schritt {quelle_nr} ist hier nicht verfügbar – er muss aus einem Schritt "
                "vor diesem stammen."
            )
        if quelle_nr not in self.bekannt:
            raise ValidierungsFehler(f"Schritt {quelle_nr} gibt es nicht.")
        quelle, kette = self.bekannt[quelle_nr]
        if not quelle.rueckgabe:
            raise ValidierungsFehler(f"Schritt {quelle_nr} ({quelle.name}) liefert keine Werte.")
        r = quelle.rueckgabe_def(rid)
        if r is None:
            namen = ", ".join(x.id for x in quelle.rueckgabe)
            raise ValidierungsFehler(
                f"Schritt {quelle_nr} ({quelle.name}) liefert keinen Wert „{rid}“ (nur: {namen})."
            )
        if r not in quelle.rueckgaben(self.ziel):
            raise ValidierungsFehler(
                f"Der Wert „{rid}“ aus Schritt {quelle_nr} ist für dieses Zielsystem nicht verfügbar."
            )
        if erwartet is not None and r.typ is not erwartet:
            raise ValidierungsFehler(
                f"„{rid}“ aus Schritt {quelle_nr} ist {r.typ.anzeige}, "
                f"hier wird {erwartet.anzeige} gebraucht."
            )
        if tuple(self.versuche[: len(kette)]) != kette:
            raise ValidierungsFehler(
                f"Der Wert aus Schritt {quelle_nr} entsteht in einem „Versuche“-Block und ist außerhalb "
                "davon nicht verfügbar."
            )
        return r


def validiere_request(
    req: ScriptRequest,
    registry: Registry,
    *,
    autor: str,
    jetzt: datetime,
    ist_admin: bool = False,
) -> ScriptIR:
    """Wandelt die (unsichere) UI-Eingabe in eine geprüfte IR um.

    Sammelt alle Fehler, damit die UI sie gemeinsam anzeigen kann.
    """
    fehler: list[Feldfehler] = []
    titel = "Script"
    beschreibung = ""
    try:
        titel = _meta_text(req.titel, 120, mehrzeilig=False) or "Script"
        if any(z in _TITEL_VERBOTEN for z in titel):
            raise ValidierungsFehler('Der Titel darf diese Zeichen nicht enthalten: " ` $ % ^ & | < > \\')
    except (ValidierungsFehler, UnsicherError) as e:
        fehler.append(Feldfehler(None, "titel", str(e)))
    try:
        beschreibung = _meta_text(req.beschreibung, 1000, mehrzeilig=True)
    except (ValidierungsFehler, UnsicherError) as e:
        fehler.append(Feldfehler(None, "beschreibung", str(e)))

    if not req.schritte:
        fehler.append(Feldfehler(None, None, "Das Script enthält noch keinen Schritt."))

    pruefer = _BaumPruefer(registry, req.ziel, fehler)
    schritte = pruefer.liste(req.schritte, tiefe=0)
    hat_rot = pruefer.hat_rot
    if pruefer.anzahl_bloecke > MAX_BLOECKE:
        fehler.append(Feldfehler(None, None, f"Höchstens {MAX_BLOECKE} Bausteine pro Script."))

    if hat_rot and not req.rot_bestaetigt and not ist_admin and not req.dry_run:
        fehler.append(
            Feldfehler(
                None,
                "rot_bestaetigt",
                "Das Script enthält destruktive (rote) Schritte. Bitte bestätige "
                "„Ich weiß, was dieses Script tut“.",
            )
        )

    if fehler:
        raise FehlerSammlung(fehler)

    return ScriptIR(
        meta=ScriptMeta(
            titel=titel,
            beschreibung=beschreibung,
            autor=autor,
            erstellt_am=jetzt,
            baukasten_version=__version__,
            quelle=req.quelle,
        ),
        optionen=Optionen(dry_run=req.dry_run, rot_bestaetigt=req.rot_bestaetigt or ist_admin),
        schritte=schritte,
    )


def ir_zu_request(ir: ScriptIR, ziel: Ziel) -> ScriptRequest:
    """Rückweg für „erneut öffnen“: IR → Request (wird danach neu validiert)."""
    return ScriptRequest(
        ziel=ziel,
        titel=ir.meta.titel,
        beschreibung=ir.meta.beschreibung,
        dry_run=ir.optionen.dry_run,
        rot_bestaetigt=ir.optionen.rot_bestaetigt,
        quelle=ir.meta.quelle,
        schritte=[_knoten_zu_eingabe(k) for k in ir.schritte],
    )


def _knoten_zu_eingabe(k: Knoten) -> EingabeKnoten:
    if isinstance(k, Wenn):
        return WennEingabe(
            art="wenn",
            wert=k.wert,
            vergleich=k.vergleich.value,
            zahl=k.zahl,
            dann=[_knoten_zu_eingabe(x) for x in k.dann],
            sonst=[_knoten_zu_eingabe(x) for x in k.sonst],
        )
    if isinstance(k, Abbrechen):
        return AbbrechenEingabe(art="abbrechen", meldung=k.meldung, code=k.code)
    if isinstance(k, Warten):
        return WartenEingabe(art="warten", sekunden=k.sekunden)
    if isinstance(k, Bestaetigung):
        return BestaetigungEingabe(art="bestaetigung", meldung=k.meldung)
    if isinstance(k, Kommentar):
        return KommentarEingabe(art="kommentar", text=k.text)
    if isinstance(k, WennFehler):
        return WennFehlerEingabe(
            art="wenn_fehler",
            versuche=[_knoten_zu_eingabe(x) for x in k.versuche],
            sonst=[_knoten_zu_eingabe(x) for x in k.sonst],
        )
    if isinstance(k, Wiederhole):
        return WiederholeEingabe(
            art="wiederhole", anzahl=k.anzahl, rumpf=[_knoten_zu_eingabe(x) for x in k.rumpf]
        )
    return SchrittEingabe(
        block_id=k.block_id,
        parameter={n: v.wert for n, v in k.parameter.items() if v.wert is not None},
    )
