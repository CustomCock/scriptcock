"""Parametertypen und Validierung (Whitelist vor dem Escaping).

Jede Eingabe wird hier gegen ihren Parametertyp geprüft und normalisiert.
Erst danach entsteht eine :class:`~app.ir.ScriptIR`. Fehlermeldungen sind für
Laien formuliert.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from app import __version__, werkzeuge
from app.escaping import UnsicherError, Ziel, pruefe_zeichen
from app.ir import (
    Abbrechen,
    Bestaetigung,
    BlockSchritt,
    FuerJeden,
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
from app.models.block import (
    REGISTRY_BEREICHE,
    REGISTRY_TYPEN,
    ZAHLENTYPEN,
    BlockDef,
    ParameterDef,
    ParamTyp,
    Risiko,
    RueckgabeDef,
    RueckgabeTyp,
)
from app.models.request import (
    AbbrechenEingabe,
    BestaetigungEingabe,
    EingabeKnoten,
    FuerJedenEingabe,
    KommentarEingabe,
    SchrittEingabe,
    ScriptRequest,
    WartenEingabe,
    WennEingabe,
    WennFehlerEingabe,
    WiederholeEingabe,
)
from app.regschutz import lade_schutz
from app.richtlinien import ELEMENT_PRAEFIX, operationen, parameter_fuer

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


def _ganzzahl(roh: Any, p: ParameterDef) -> int:
    """zahl/tage/dauer_sek: Standardbereich des Typs, im YAML per min/max enger."""
    untere, obere = ZAHLENTYPEN[p.typ.value]
    grenzen = p.model_copy(
        update={
            "min": p.min if p.min is not None else untere,
            "max": p.max if p.max is not None else obere,
        }
    )
    return _zahl(roh, grenzen)


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


_DATUM_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_DATUM_DE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")


def _datum(text: str, p: ParameterDef) -> str:
    if m := _DATUM_ISO.match(text):
        j, mo, t = (int(x) for x in m.groups())
    elif m := _DATUM_DE.match(text):
        t, mo, j = (int(x) for x in m.groups())
    else:
        raise ValidierungsFehler("Bitte ein Datum wie 24.12.2026 oder 2026-12-24 angeben.")
    try:
        d = date(j, mo, t)
    except ValueError:
        raise ValidierungsFehler("Dieses Datum gibt es nicht (z. B. 30. Februar).") from None
    if not 1970 <= d.year <= 2100:
        raise ValidierungsFehler("Bitte ein Datum zwischen 1970 und 2100 angeben.")
    return d.isoformat()


def _uhrzeit(text: str, p: ParameterDef) -> str:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not m or int(m[1]) > 23 or int(m[2]) > 59:
        raise ValidierungsFehler("Bitte eine Uhrzeit wie 08:30 angeben (00:00 bis 23:59).")
    return f"{int(m[1]):02d}:{m[2]}"


_GRUPPE = re.compile(r"^\w[\w .\-]{0,63}$")


def _gruppenname(text: str, p: ParameterDef) -> str:
    _kein_minus(text)
    if not _GRUPPE.match(text):
        raise ValidierungsFehler(
            "Das ist kein gültiger Gruppenname. Erlaubt sind Buchstaben (auch Umlaute), Ziffern, "
            "Leerzeichen und _ . - (höchstens 64 Zeichen), z. B. Domänen-Benutzer"
        )
    return text


_MUSTER = re.compile(r"^[\w.\-*? ]{1,100}$")


def _dateimuster(text: str, p: ParameterDef) -> str:
    _kein_minus(text)
    if not _MUSTER.match(text):
        raise ValidierungsFehler(
            "Bitte nur einen Dateinamen bzw. ein Muster ohne Ordner angeben – erlaubt sind Buchstaben, "
            "Ziffern, Leerzeichen, _ . - sowie * und ?, z. B. *.log"
        )
    if not re.search(r"[^*?.]", text):
        raise ValidierungsFehler(
            "Das Muster passt auf alle Dateien – bitte genauer angeben, z. B. *.log oder backup_*.zip"
        )
    return text


def _cidr(text: str, p: ParameterDef) -> str:
    fehler = ValidierungsFehler("Bitte ein Netz wie 192.168.1.0/24 angeben (Präfix 8 bis 32).")
    if not re.fullmatch(r"[0-9.]+/[0-9]{1,2}", text):
        raise fehler
    try:
        netz = ipaddress.IPv4Network(text, strict=False)
    except ValueError:
        raise fehler from None
    if not 8 <= netz.prefixlen <= 32:
        raise fehler
    if str(netz) != text:
        raise ValidierungsFehler(
            f"Das ist eine Adresse im Netz, nicht das Netz selbst – gemeint ist wohl {netz}."
        )
    return text


_MAC = re.compile(
    r"^(?:[0-9A-Fa-f]{2}([:-])(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}"
    r"|[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}|[0-9A-Fa-f]{12})$"
)


def _mac(text: str, p: ParameterDef) -> str:
    if not _MAC.match(text):
        raise ValidierungsFehler("Das ist keine gültige MAC-Adresse, Beispiel: 00:1A:2B:3C:4D:5E")
    hexa = re.sub(r"[:.\-]", "", text).upper()
    return ":".join(hexa[i : i + 2] for i in range(0, 12, 2))


def _domain(text: str, p: ParameterDef) -> str:
    name = text.rstrip(".").lower()
    teile = name.split(".")
    if (
        len(teile) < 2
        or len(name) > 253
        or not all(_HOST_LABEL.match(t) for t in teile)
        or not re.search("[a-z]", teile[-1])
    ):
        raise ValidierungsFehler("Das ist keine gültige Domain, Beispiel: okm.local oder example.de")
    return name


_HIVES = {
    "HKLM": "HKLM",
    "HKEY_LOCAL_MACHINE": "HKLM",
    "HKCU": "HKCU",
    "HKEY_CURRENT_USER": "HKCU",
    "HKCR": "HKCR",
    "HKEY_CLASSES_ROOT": "HKCR",
    "HKU": "HKU",
    "HKEY_USERS": "HKU",
    "HKCC": "HKCC",
    "HKEY_CURRENT_CONFIG": "HKCC",
}
# Langformen für den PowerShell-Provider (Registry::HKEY_…)
REGISTRY_LANGFORM = {
    "HKLM": "HKEY_LOCAL_MACHINE",
    "HKCU": "HKEY_CURRENT_USER",
    "HKCR": "HKEY_CLASSES_ROOT",
    "HKU": "HKEY_USERS",
    "HKCC": "HKEY_CURRENT_CONFIG",
}


def registry_teile(pfad: str) -> tuple[str | None, str]:
    """``HKLM\\SOFTWARE\\x`` → (``HKLM``, ``SOFTWARE\\x``); ohne Wurzel → (None, Pfad)."""
    kopf, _, rest = pfad.partition("\\")
    if kopf in REGISTRY_LANGFORM:
        return kopf, rest
    return None, pfad


def registry_ps_form(pfad: str) -> str:
    """Normalisierter Pfad → ``Registry::HKEY_LOCAL_MACHINE\\…`` (ohne Wurzel unverändert)."""
    wurzel, rest = registry_teile(pfad)
    return f"Registry::{REGISTRY_LANGFORM[wurzel]}\\{rest}" if wurzel else pfad


def _registry_pfad(text: str, p: ParameterDef) -> str:
    """Normalisiert auf ``HKLM\\SOFTWARE\\…``. Ohne Wurzel (``Software\\…``) bleibt der Pfad relativ –
    das ist nur für Benutzer-Bereiche erlaubt (Prüfung zusammen mit ``bereich``)."""
    roh = text
    if roh.lower().startswith("registry::"):
        roh = roh[len("registry::") :]
    m = re.fullmatch(r"([A-Za-z_]+):?(?:\\(.*))?", roh, re.S)
    wurzel: str | None = None
    rest = roh
    if m and m[1].upper() in _HIVES:
        wurzel = _HIVES[m[1].upper()]
        rest = m[2] or ""
    rest = rest.rstrip("\\")
    if not rest:
        raise ValidierungsFehler(
            "Bitte einen Schlüssel angeben, z. B. HKLM\\SOFTWARE\\Firma (nicht nur die Wurzel)."
        )
    teile = rest.split("\\")
    for teil in teile:
        if not teil:
            raise ValidierungsFehler("Der Registry-Pfad enthält einen leeren Teil (\\\\).")
        if len(teil) > 255:
            raise ValidierungsFehler("Ein Teil des Registry-Pfads ist zu lang (höchstens 255 Zeichen).")
        if '"' in teil:
            raise ValidierungsFehler('Anführungszeichen (") sind in Registry-Pfaden nicht erlaubt.')
    pfad = f"{wurzel}\\{rest}" if wurzel else rest
    if len(pfad) > 512:
        raise ValidierungsFehler("Der Registry-Pfad ist zu lang (höchstens 512 Zeichen).")
    return pfad


def _registry_wertname(text: str, p: ParameterDef) -> str:
    """Leer bzw. „(Standard)“ = Standardwert des Schlüssels (Rückgabe "")."""
    if text.lower() in ("(standard)", "(default)", "@"):
        return ""
    _kein_minus(text)
    if len(text) > 255:
        raise ValidierungsFehler("Der Wertname ist zu lang (höchstens 255 Zeichen).")
    if '"' in text:
        raise ValidierungsFehler('Anführungszeichen (") sind in Wertnamen nicht erlaubt.')
    return text


def _registry_typ(text: str, p: ParameterDef) -> str:
    typ = text.upper()
    if not typ.startswith("REG_"):
        typ = "REG_" + typ
    if typ not in REGISTRY_TYPEN:
        raise ValidierungsFehler("Bitte einen Typ wählen: " + ", ".join(REGISTRY_TYPEN) + ".")
    return typ


def _registry_bereich(text: str, p: ParameterDef) -> str:
    if text not in REGISTRY_BEREICHE:
        raise ValidierungsFehler("Bitte einen Bereich wählen: " + ", ".join(REGISTRY_BEREICHE) + ".")
    return text


MAX_REGISTRY_TEXT = 4096
_WERTNAME = ParameterDef(id="wertname", label="Wertname", typ=ParamTyp.REGISTRY_WERTNAME)
_RICHTLINIE_ID = re.compile(r"^[a-z0-9_]{1,40}:[A-Za-z0-9_.\-]{1,100}:[A-Za-z0-9_.\-]{1,200}$")


MAX_SOLL_EINTRAEGE = 50
_SOLL_PFAD = ParameterDef(id="pfad", label="Pfad", typ=ParamTyp.REGISTRY_PFAD)
_SOLL_TYP = ParameterDef(id="typ", label="Typ", typ=ParamTyp.REGISTRY_TYP)


def registry_soll_liste(roh: Any) -> list[str | int]:
    """Soll/Ist-Liste: eine Zeile (Blockly: ein Listeneintrag) pro Wert, „Pfad ; Wertname ; Typ ; Soll“.

    Jeder Teil wird wie im Einzelbaustein geprüft (Pfad, Wertname, Typ, Daten passend zum Typ). Ergebnis je
    Eintrag ``"Pfad ; Wertname ; TYP ; Daten"`` (normalisiert – erneutes Prüfen ändert nichts). Fürs Script
    macht der Generator daraus ``Pfad|Wertname|TYP|Daten`` (``soll_liste_script``); Pfad und Wertname dürfen
    deshalb kein ``|`` enthalten, die Daten schon. REG_MULTI_SZ geht hier nicht (mehrzeilig).
    """
    if isinstance(roh, list):
        zeilen = [str(z) for z in roh]
    elif isinstance(roh, str):
        zeilen = roh.replace("\r\n", "\n").split("\n")
    else:
        raise ValidierungsFehler("Bitte eine Zeile pro Wert angeben.")
    eintraege: list[str | int] = []
    for n, zeile in enumerate(zeilen, 1):
        if not zeile.strip():
            continue
        teile = [t.strip() for t in zeile.split(";", 3)]
        if len(teile) != 4:
            raise ValidierungsFehler(f"Zeile {n}: bitte „Pfad ; Wertname ; Typ ; Soll“ angeben.")
        pfad, name, typ, daten = teile
        try:
            pfad_n = validiere_wert(_SOLL_PFAD, pfad).wert
            name_n = _registry_wertname(name, _WERTNAME) if name else ""
            typ_n = validiere_wert(_SOLL_TYP, typ).wert
            if typ_n == "REG_MULTI_SZ":
                raise ValidierungsFehler("REG_MULTI_SZ bitte mit „Registry-Wert prüfen“ einzeln prüfen.")
            daten_n = registry_daten(daten, str(typ_n))
        except ValidierungsFehler as e:
            raise ValidierungsFehler(f"Zeile {n}: {e}") from None
        if "|" in f"{pfad_n}{name_n}":
            raise ValidierungsFehler(f"Zeile {n}: „|“ ist in Pfad und Wertname hier nicht erlaubt.")
        eintraege.append(f"{pfad_n} ; {name_n} ; {typ_n} ; {daten_n}")
    if not eintraege:
        raise ValidierungsFehler("Bitte mindestens einen Wert angeben.")
    if len(eintraege) > MAX_SOLL_EINTRAEGE:
        raise ValidierungsFehler(f"Höchstens {MAX_SOLL_EINTRAEGE} Werte pro Schritt.")
    return eintraege


def soll_liste_script(eintraege: list[str | int]) -> list[str | int]:
    """Geprüfte Soll/Ist-Liste → Einträge ``Pfad|Wertname|TYP|Daten`` für das Script."""
    return ["|".join(t.strip() for t in str(e).split(";", 3)) for e in eintraege]


def _registry_text(text: str, p: ParameterDef) -> str:
    """Text für einen Registry-Wert (URLs, Pfade, %Variablen% …) – keine Steuerzeichen, ≤ 4096."""
    if len(text) > MAX_REGISTRY_TEXT:
        raise ValidierungsFehler(f"Der Text ist zu lang (höchstens {MAX_REGISTRY_TEXT} Zeichen).")
    return text


def _richtlinie(text: str, p: ParameterDef) -> str:
    """Nur die Form – ob es die Richtlinie gibt, prüft der Baustein gegen den Katalog."""
    if not _RICHTLINIE_ID.match(text):
        raise ValidierungsFehler(
            "Bitte eine Richtlinie aus dem Katalog wählen (z. B. edge:msedge:HomepageLocation)."
        )
    return text


MAX_REGISTRY_BINAER = 4096


def registry_daten(roh: Any, regtyp: str) -> str | int | list[str | int]:
    """Prüft Registry-Daten passend zum Typ.

    DWORD/QWORD → int (dezimal oder 0x…), SZ/EXPAND_SZ → Text, MULTI_SZ → Liste (eine Zeile bzw.
    ein Listeneintrag pro Wert), BINARY → Hex-Bytes klein ohne Trenner (``0a1bff``).
    """
    if regtyp == "REG_MULTI_SZ":
        if isinstance(roh, list):
            teile: list[Any] = roh
        elif isinstance(roh, str):
            teile = roh.replace("\r\n", "\n").split("\n")
        else:
            raise ValidierungsFehler("Bitte einen Eintrag pro Zeile angeben.")
        eintraege: list[str | int] = []
        for n, teil in enumerate(teile, 1):
            if isinstance(teil, bool) or not isinstance(teil, str | int):
                raise ValidierungsFehler(f"Eintrag {n} ist kein Text.")
            eintrag = str(teil)
            if not eintrag.strip():
                continue
            try:
                pruefe_zeichen(eintrag)
            except UnsicherError as e:
                raise ValidierungsFehler(f"Eintrag {n}: {e}") from None
            if "\\0" in eintrag:
                raise ValidierungsFehler(f"Eintrag {n}: „\\0“ ist nicht erlaubt (Trenner von reg.exe).")
            if len(eintrag) > MAX_REGISTRY_TEXT:
                raise ValidierungsFehler(f"Eintrag {n} ist zu lang (höchstens {MAX_REGISTRY_TEXT} Zeichen).")
            eintraege.append(eintrag)
        if sum(len(str(e)) + 1 for e in eintraege) > 4 * MAX_REGISTRY_TEXT:
            raise ValidierungsFehler("Zu viele Daten (höchstens 16384 Zeichen insgesamt).")
        return eintraege
    if isinstance(roh, bool) or not isinstance(roh, str | int):
        raise ValidierungsFehler("Bitte einen Wert eingeben.")
    text = _text(roh)
    if regtyp in ("REG_DWORD", "REG_QWORD"):
        grenze = 0xFFFFFFFF if regtyp == "REG_DWORD" else 0xFFFFFFFFFFFFFFFF
        try:
            zahl = int(text[2:], 16) if text.lower().startswith("0x") else int(text, 10)
        except ValueError:
            raise ValidierungsFehler(
                "Bitte eine ganze Zahl angeben (dezimal oder hexadezimal mit 0x)."
            ) from None
        if not 0 <= zahl <= grenze:
            raise ValidierungsFehler(f"Bei {regtyp} sind Werte von 0 bis {grenze} erlaubt.")
        return zahl
    if regtyp == "REG_BINARY":
        hexa = re.sub(r"[\s,]", "", text.lower().removeprefix("hex:"))
        if not re.fullmatch(r"(?:[0-9a-f]{2})*", hexa):
            raise ValidierungsFehler(
                "Bitte Hex-Bytes angeben, z. B. 0a 1b ff (Leerzeichen oder Komma erlaubt)."
            )
        if len(hexa) // 2 > MAX_REGISTRY_BINAER:
            raise ValidierungsFehler(f"Zu viele Bytes (höchstens {MAX_REGISTRY_BINAER}).")
        return hexa
    if regtyp in ("REG_SZ", "REG_EXPAND_SZ"):
        if len(text) > MAX_REGISTRY_TEXT:
            raise ValidierungsFehler(f"Der Text ist zu lang (höchstens {MAX_REGISTRY_TEXT} Zeichen).")
        return text
    raise ValidierungsFehler("Unbekannter Registry-Typ.")


_DATEINAME = re.compile(r"^\w[\w .\-()+]{0,254}$")
# Unter Windows reservierte Gerätenamen – auch mit Endung (nul.txt) nicht anlegbar
_RESERVIERT = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$", re.I)


def _dateiname(text: str, p: ParameterDef) -> str:
    if not _DATEINAME.match(text) or text.endswith((".", " ")):
        raise ValidierungsFehler(
            "Bitte nur einen Namen ohne Ordner angeben – erlaubt sind Buchstaben, Ziffern, Leerzeichen "
            "und _ . - ( ) +, nicht am Ende ein Punkt, z. B. Bericht 2026.docx"
        )
    if _RESERVIERT.match(text):
        raise ValidierungsFehler(f"„{text}“ ist unter Windows ein reservierter Name.")
    return text


def _rechnername(text: str, p: ParameterDef) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,14}", text) or text.isdigit() or text.endswith("-"):
        raise ValidierungsFehler(
            "Bitte einen Rechnernamen mit 1–15 Zeichen angeben (Buchstaben, Ziffern, Bindestrich; "
            "nicht nur Ziffern, ohne Punkt), z. B. PC-EMPFANG-01"
        )
    return text.upper()


_DNS_LABEL = re.compile(r"^_?[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _dnsname(text: str, p: ParameterDef) -> str:
    name = text.rstrip(".").lower()
    if not name or len(name) > 253 or not all(_DNS_LABEL.match(t) for t in name.split(".")):
        raise ValidierungsFehler(
            "Das ist kein gültiger DNS-Name. Erlaubt sind Buchstaben, Ziffern, Bindestriche und Punkte; "
            "ein Teil darf mit _ beginnen, z. B. okm.local oder _ldap._tcp.okm.local"
        )
    return name


def _pfad_oder_unc(text: str, p: ParameterDef) -> str:
    if text.replace("/", "\\").startswith("\\\\"):
        return _unc(text, p)
    try:
        return _pfad_windows(text, p)
    except ValidierungsFehler:
        raise ValidierungsFehler(
            "Bitte einen Windows-Pfad (C:\\Setup\\app.msi) oder einen Netzwerkpfad "
            "(\\\\fileserver\\Software\\app.msi) angeben."
        ) from None


def _version(text: str, p: ParameterDef) -> str:
    if not re.fullmatch(r"[0-9]{1,9}(\.[0-9]{1,9}){0,3}", text):
        raise ValidierungsFehler("Bitte eine Versionsnummer wie 115.3.0 angeben (1 bis 4 Zahlen mit Punkt).")
    return text


def _kb_nummer(text: str, p: ParameterDef) -> str:
    treffer = re.fullmatch(r"(?:KB)?\s*([0-9]{6,8})", text, re.IGNORECASE)
    if not treffer:
        raise ValidierungsFehler("Bitte eine Update-Nummer wie KB5034441 angeben (6 bis 8 Ziffern).")
    return treffer.group(1)


_MSI_EIGENSCHAFT = re.compile(r"^[A-Z][A-Z0-9_]{0,63}=[A-Za-z0-9_.\-:\\{}]{0,200}$")


def _msi_eigenschaft(text: str, p: ParameterDef) -> str:
    if not _MSI_EIGENSCHAFT.match(text):
        raise ValidierungsFehler(
            "Bitte eine MSI-Eigenschaft wie ALLUSERS=1 angeben: Name in Großbuchstaben, Wert ohne "
            "Leerzeichen und Anführungszeichen (erlaubt: Buchstaben, Ziffern, _ . - : \\ { })."
        )
    return text


# Typen, deren Werte Leerzeichen enthalten dürfen – Listen davon trennt nur , oder ;
LISTEN_MIT_LEERZEICHEN = frozenset(
    {
        ParamTyp.TEXT_KURZ,
        ParamTyp.TEXT,
        ParamTyp.GRUPPENNAME,
        ParamTyp.DATEIMUSTER,
        ParamTyp.PFAD,
        ParamTyp.PFAD_WINDOWS,
        ParamTyp.PFAD_UNIX,
        ParamTyp.UNC_PFAD,
        ParamTyp.PROZESSNAME,
        ParamTyp.REGISTRY_PFAD,
        ParamTyp.DATEINAME,
        ParamTyp.PFAD_ODER_UNC,
    }
)
MAX_LISTE = 20


def _liste(roh: Any, p: ParameterDef) -> list[str | int]:
    if p.listen_typ is None:
        raise ValidierungsFehler("Für diese Liste ist kein Eintragstyp festgelegt.")
    if isinstance(roh, list):
        teile: list[Any] = roh
    else:
        trenner = r"[,;]" if p.listen_typ in LISTEN_MIT_LEERZEICHEN else r"[,;\s]"
        teile = [t.strip() for t in re.split(trenner, _text(roh))]
    teile = [t for t in teile if not (t is None or (isinstance(t, str) and not t.strip()))]
    if not teile:
        raise ValidierungsFehler("Dieses Feld muss ausgefüllt werden.")
    eintrag = p.model_copy(
        update={
            "typ": p.listen_typ,
            "listen_typ": None,
            "min_anzahl": None,
            "max_anzahl": None,
            "pflicht": True,
            "standard": None,
        }
    )
    werte: list[str | int] = []
    for i, roh_eintrag in enumerate(teile, 1):
        try:
            wert = validiere_wert(eintrag, roh_eintrag).wert
        except ValidierungsFehler as e:
            raise ValidierungsFehler(f"Eintrag {i} („{roh_eintrag}“): {e}") from None
        if isinstance(wert, str | int) and not isinstance(wert, bool) and wert not in werte:
            werte.append(wert)
    hoechstens = p.max_anzahl or MAX_LISTE
    mindestens = p.min_anzahl or 1
    if len(werte) > hoechstens:
        raise ValidierungsFehler(f"Bitte höchstens {hoechstens} Einträge angeben.")
    if len(werte) < mindestens:
        raise ValidierungsFehler(f"Bitte mindestens {mindestens} verschiedene Einträge angeben.")
    return werte


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
    ParamTyp.DATUM: _datum,
    ParamTyp.UHRZEIT: _uhrzeit,
    ParamTyp.GRUPPENNAME: _gruppenname,
    ParamTyp.DATEIMUSTER: _dateimuster,
    ParamTyp.CIDR: _cidr,
    ParamTyp.MAC: _mac,
    ParamTyp.DOMAIN: _domain,
    ParamTyp.REGISTRY_PFAD: _registry_pfad,
    ParamTyp.REGISTRY_WERTNAME: _registry_wertname,
    ParamTyp.REGISTRY_TYP: _registry_typ,
    ParamTyp.REGISTRY_BEREICH: _registry_bereich,
    ParamTyp.REGISTRY_TEXT: _registry_text,
    ParamTyp.RICHTLINIE: _richtlinie,
    ParamTyp.DATEINAME: _dateiname,
    ParamTyp.RECHNERNAME: _rechnername,
    ParamTyp.DNSNAME: _dnsname,
    ParamTyp.PFAD_ODER_UNC: _pfad_oder_unc,
    ParamTyp.VERSION: _version,
    ParamTyp.KB_NUMMER: _kb_nummer,
    ParamTyp.MSI_EIGENSCHAFT: _msi_eigenschaft,
}


def validiere_wert(p: ParameterDef, roh: Any, regtyp: str | None = None) -> ParamValue:
    """Prüft einen Rohwert gegen die Parameterdefinition.

    Leere Werte: Pflichtfeld → Fehler; sonst ``standard`` bzw. ``None``.
    ``regtyp``: bei ``registry_daten`` der gewählte Registry-Typ desselben Schritts (ohne ihn – z. B.
    bei der Live-Prüfung eines einzelnen Felds – wird als Text bzw. mehrzeilig als Liste geprüft).
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

    wert: str | int | bool | list[str | int]
    if p.typ is ParamTyp.REGISTRY_ZEILEN:
        return ParamValue(typ=p.typ, wert=[] if leer else registry_daten(roh, "REG_MULTI_SZ"))
    if p.typ is ParamTyp.REGISTRY_SOLL_LISTE:
        return ParamValue(typ=p.typ, wert=registry_soll_liste(roh))
    if p.typ is ParamTyp.REGISTRY_DATEN:
        if regtyp is None:
            regtyp = (
                "REG_MULTI_SZ"
                if isinstance(roh, list) or (isinstance(roh, str) and "\n" in roh)
                else "REG_SZ"
            )
        if regtyp == "REG_MULTI_SZ" and leer:
            return ParamValue(typ=p.typ, wert=[])
        return ParamValue(typ=p.typ, wert=registry_daten(roh, regtyp))
    if p.typ is ParamTyp.LISTE:
        return ParamValue(typ=p.typ, wert=_liste(roh, p), listen_typ=p.listen_typ)
    if p.typ.value in ZAHLENTYPEN:
        wert = _ganzzahl(roh, p)
    elif p.typ is ParamTyp.PORT:
        wert = _port(roh, p)
    elif p.typ is ParamTyp.JA_NEIN:
        wert = _ja_nein(roh, p)
    else:
        text = _text(roh)
        wert = _TEXT_PRUEFER[p.typ](text, p)
        if p.typ is ParamTyp.REGISTRY_WERTNAME and wert == "":
            return ParamValue(typ=p.typ, wert=None)  # Standardwert „(Standard)“
    return ParamValue(typ=p.typ, wert=wert)


def pruefe_wert_fuer_ziel(wert: ParamValue, ziel: Ziel) -> None:
    """Zielabhängige Zusatzprüfungen (z. B. Windows-Pfad nicht unter Linux)."""
    if wert.wert is None:
        return
    if isinstance(wert.wert, list):
        for i, eintrag in enumerate(wert.wert, 1):
            try:
                pruefe_wert_fuer_ziel(ParamValue(typ=wert.listen_typ or ParamTyp.TEXT, wert=eintrag), ziel)
            except ValidierungsFehler as e:
                raise ValidierungsFehler(f"Eintrag {i}: {e}") from None
        return
    windows = ziel in (Ziel.POWERSHELL, Ziel.CMD)
    if wert.typ is ParamTyp.PFAD and isinstance(wert.wert, str):
        if windows and not pfad_ist_windows(wert.wert):
            raise ValidierungsFehler("Für Windows bitte einen Windows-Pfad angeben, z. B. C:\\Daten")
        if not windows and pfad_ist_windows(wert.wert):
            raise ValidierungsFehler("Für Linux/macOS bitte einen Pfad wie /home/max/Daten angeben.")
    if ziel is Ziel.CMD and wert.typ is ParamTyp.REGISTRY_DATEN and isinstance(wert.wert, str):
        if wert.wert.startswith(("-", "/")):
            raise ValidierungsFehler("Unter CMD dürfen Registry-Daten nicht mit - oder / beginnen.")
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
MAX_SCHLEIFENWERTE = 50
SCHLEIFENWERT = "schleifenwert"  # Parameterwert {"schleifenwert": true} = aktueller Wert der Schleife
# Typen, die den Schleifenwert nicht aufnehmen können (Listen, Verweise, Haken)
_OHNE_SCHLEIFENWERT = frozenset(
    {
        ParamTyp.LISTE,
        ParamTyp.VARIABLE,
        ParamTyp.JA_NEIN,
        ParamTyp.AUSWAHL,
        ParamTyp.REGISTRY_PFAD,
        ParamTyp.REGISTRY_TYP,
        ParamTyp.REGISTRY_DATEN,
        ParamTyp.REGISTRY_BEREICH,
        ParamTyp.REGISTRY_ZEILEN,
        ParamTyp.REGISTRY_SOLL_LISTE,
        ParamTyp.RICHTLINIE,
    }
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
        # Werte der offenen „Für jeden Wert“-Schleifen (innerste zuletzt)
        self.schleifen: list[list[str]] = []
        # Von „Admin-Werkzeug bereitstellen“ bisher bereitgestellt (z. B. "lgpo")
        self.bereitgestellt: set[str] = set()

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
        if isinstance(eingabe, FuerJedenEingabe):
            return self.fuer_jeden(i, eingabe, tiefe)
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

    def fuer_jeden(self, i: int, eingabe: FuerJedenEingabe, tiefe: int) -> FuerJeden:
        werte: list[str] = []
        try:
            werte = schleifenwerte(eingabe.werte)
        except ValidierungsFehler as e:
            self.fehler.append(Feldfehler(i, "werte", f"Werte: {e}"))
        if not eingabe.rumpf:
            self.fehler.append(Feldfehler(i, None, "„Für jeden Wert“ braucht mindestens einen Schritt."))
        self.schleifen.append(werte)
        rumpf = self.liste(eingabe.rumpf, tiefe + 1)
        self.schleifen.pop()
        return FuerJeden(werte=werte or ["?"], rumpf=rumpf)

    def schleifenwert(self, p: ParameterDef) -> ParamValue:
        """Parameter bekommt den Wert der innersten Schleife – jeder Wert wird gegen ``p`` geprüft."""
        if not self.schleifen:
            raise ValidierungsFehler("„Wert aus der Liste“ geht nur innerhalb von „Für jeden Wert“.")
        if p.typ in _OHNE_SCHLEIFENWERT:
            raise ValidierungsFehler("Dieses Feld kann keinen Wert aus der Liste übernehmen.")
        geprueft: list[str | int] = []
        for n, roh in enumerate(self.schleifen[-1], 1):
            try:
                wert = validiere_wert(p, roh)
                pruefe_wert_fuer_ziel(wert, self.ziel)
            except ValidierungsFehler as e:
                raise ValidierungsFehler(f"Wert {n} („{roh}“) aus der Liste passt nicht: {e}") from None
            if not isinstance(wert.wert, str | int) or isinstance(wert.wert, bool):
                raise ValidierungsFehler(f"Wert {n} („{roh}“) aus der Liste fehlt.")
            geprueft.append(wert.wert)
        return ParamValue(typ=p.typ, wert=geprueft, schleife=True)

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
        bekannt = {p.id for p in block.parameter}
        for name in sorted(set(eingabe.parameter) - bekannt):
            if block.dynamisch == "richtlinie" and name.startswith(ELEMENT_PRAEFIX):
                continue  # Elemente der Richtlinie – geprüft in richtlinie_pruefen
            self.fehler.append(Feldfehler(i, name, f"Unbekannter Parameter „{name}“."))
        werte: dict[str, ParamValue] = {}
        genutzt = self.registry.benutzte_parameter(block, self.ziel)
        # registry_daten zuletzt: braucht den gewählten Registry-Typ desselben Schritts
        reihenfolge = sorted(block.parameter, key=lambda q: q.typ is ParamTyp.REGISTRY_DATEN)
        for p in reihenfolge:
            if p.id not in genutzt and eingabe.parameter.get(p.id) in (None, ""):
                # Für dieses Zielsystem nicht verwendet – daher auch keine Pflicht.
                continue
            try:
                roh = eingabe.parameter.get(p.id)
                if ist_schleifenwert(roh):
                    werte[p.id] = self.schleifenwert(p)
                    continue
                regtyp: str | None = None
                if p.typ is ParamTyp.REGISTRY_DATEN:
                    typwert = werte.get(p.bezug or "typ")
                    if typwert is None or not isinstance(typwert.wert, str):
                        continue  # Fehler steht schon beim Typ
                    regtyp = typwert.wert
                wert = validiere_wert(p, roh, regtyp)
                pruefe_wert_fuer_ziel(wert, self.ziel)
                if p.typ is ParamTyp.VARIABLE and isinstance(wert.wert, str):
                    self.verweis_pruefen(nr, wert.wert, p.variable_typ)
                werte[p.id] = wert
            except ValidierungsFehler as e:
                self.fehler.append(Feldfehler(i, p.id, f"{p.label}: {e}"))
        risiko: Risiko | None = None
        stand: str | None = None
        if block.dynamisch == "richtlinie":
            risiko, stand = self.richtlinie_pruefen(i, block, eingabe, werte)
        elif block.dynamisch == "werkzeug":
            risiko = self.werkzeug_pruefen(i, werte)
        elif block.registry is not None:
            risiko = self.registry_pruefen(i, block, werte)
        if risiko is Risiko.ROT:
            self.hat_rot = True
        return BlockSchritt(
            block_id=block.id,
            block_version=block.version,
            parameter=werte,
            risiko=risiko,
            katalog_stand=stand,
        )

    def werkzeug_pruefen(self, i: int, werte: dict[str, ParamValue]) -> Risiko | None:
        """Ziel, Quelle und Paket für „Admin-Werkzeug bereitstellen“; Central Store = rot (ganze Domäne)."""
        was = str(getattr(werte.get("was"), "wert", "lgpo"))
        quelle = str(getattr(werte.get("quelle"), "wert", "intranet"))
        pid = "lgpo" if was == "lgpo" else str(getattr(werte.get("paket"), "wert", ""))
        if self.ziel is not Ziel.POWERSHELL:
            self.fehler.append(Feldfehler(i, None, "Admin-Werkzeuge gehen nur mit PowerShell."))
        if was != "software" and quelle == "intranet" and not self.registry.werkzeug_url:
            self.fehler.append(
                Feldfehler(
                    i,
                    "quelle",
                    "Quelle: „Intranet“ ist auf diesem Server nicht eingerichtet (OKM_WERKZEUG_URL) – "
                    "bitte „Hersteller“ wählen.",
                )
            )
        if was == "vorlagen" and not werkzeuge.dateien(pid):
            self.fehler.append(
                Feldfehler(i, "paket", "Paket: Dafür gibt es keinen geprüften Download der Vorlagen.")
            )
        if was == "software" and not (werkzeuge.paket(pid) or {}).get("software"):
            self.fehler.append(Feldfehler(i, "paket", "Paket: Dafür ist keine Software hinterlegt."))
        self.bereitgestellt.add(was)
        if was == "vorlagen" and getattr(werte.get("central_store"), "wert", False) is True:
            return Risiko.ROT
        return None

    def richtlinie_pruefen(
        self, i: int, block: BlockDef, eingabe: SchrittEingabe, werte: dict[str, ParamValue]
    ) -> tuple[Risiko | None, str | None]:
        """Richtlinie nachschlagen, Bereich zur Klasse passend machen, Elemente wie Parameter prüfen,
        Schutzliste auf alle Registry-Operationen anwenden."""
        rid = getattr(werte.get("richtlinie"), "wert", None)
        if not isinstance(rid, str):
            return None, None
        r = self.registry.richtlinien.richtlinie(rid)
        if r is None:
            self.fehler.append(
                Feldfehler(i, "richtlinie", "Diese Richtlinie gibt es im Katalog nicht (mehr).")
            )
            return None, None
        if self.ziel is not Ziel.POWERSHELL:
            self.fehler.append(Feldfehler(i, None, "Richtlinien gehen nur mit PowerShell."))
        # Standardwerte fest eintragen – Generator, Kopfzeile und Prüfung sehen denselben Zustand
        zustand = getattr(werte.get("zustand"), "wert", None) or "aktiviert"
        methode = getattr(werte.get("methode"), "wert", None) or "registry_direkt"
        werte["zustand"] = ParamValue(typ=ParamTyp.AUSWAHL, wert=zustand)
        werte["methode"] = ParamValue(typ=ParamTyp.AUSWAHL, wert=methode)
        bereich = getattr(werte.get("bereich"), "wert", None)
        if r["klasse"] == "machine":
            if bereich not in (None, "computer"):
                self.fehler.append(
                    Feldfehler(i, "bereich", "Bereich: Diese Richtlinie gilt nur für den Computer.")
                )
            bereich = "computer"
        elif r["klasse"] == "user":
            if bereich == "computer":
                self.fehler.append(
                    Feldfehler(
                        i,
                        "bereich",
                        "Bereich: Diese Richtlinie gilt nur für Benutzer – bitte wählen, für wen.",
                    )
                )
            bereich = bereich or "angemeldeter_benutzer"
        else:
            bereich = bereich or "computer"
        werte["bereich"] = ParamValue(typ=ParamTyp.REGISTRY_BEREICH, wert=bereich)
        if methode == "lokale_gruppenrichtlinie" and "lgpo" not in self.bereitgestellt:
            self.fehler.append(
                Feldfehler(
                    i,
                    "methode",
                    "Methode: Für die lokale Gruppenrichtlinie muss davor „Admin-Werkzeug bereitstellen“ "
                    "(LGPO.exe) stehen.",
                )
            )
        element_werte: dict[str, Any] = {}
        definiert = {p.id for p, _ in parameter_fuer(r)}
        for name in sorted(
            n for n in eingabe.parameter if n.startswith(ELEMENT_PRAEFIX) and n not in definiert
        ):
            self.fehler.append(Feldfehler(i, name, f"Unbekannter Parameter „{name}“."))
        for p, e in parameter_fuer(r):
            roh = eingabe.parameter.get(p.id)
            if zustand != "aktiviert":
                continue
            try:
                wert = validiere_wert(p, roh)
                pruefe_wert_fuer_ziel(wert, self.ziel)
                if isinstance(wert.wert, str) and len(wert.wert) > e.get("max_laenge", MAX_REGISTRY_TEXT):
                    raise ValidierungsFehler(f"Höchstens {e['max_laenge']} Zeichen.")
                if (
                    isinstance(wert.wert, list)
                    and e.get("max_eintraege")
                    and len(wert.wert) > e["max_eintraege"]
                ):
                    raise ValidierungsFehler(f"Höchstens {e['max_eintraege']} Einträge.")
                if isinstance(wert.wert, list) and e.get("expliziter_wert"):
                    for n, eintrag in enumerate(wert.wert, 1):
                        name, gleich, _ = str(eintrag).partition("=")
                        if not gleich or not name.strip():
                            raise ValidierungsFehler(f"Eintrag {n}: bitte als Name=Wert angeben.")
                        validiere_wert(_WERTNAME, name.strip())
                werte[p.id] = wert
                element_werte[p.id] = wert.wert
            except ValidierungsFehler as fehler:
                self.fehler.append(Feldfehler(i, p.id, f"{p.label}: {fehler}"))
        schutz = lade_schutz()
        risiko: Risiko | None = None
        wurzel = "HKLM" if bereich == "computer" else "HKCU"
        for op in operationen(r, zustand, element_werte):
            voll = f"{wurzel}\\{op.pfad}"
            if schutz.gesperrt_fuer(voll):
                self.fehler.append(
                    Feldfehler(
                        i, "richtlinie", f"Die Richtlinie schreibt in einen gesperrten Bereich ({voll})."
                    )
                )
                break
            # „Policies“ ist hier der Normalfall (dokumentierte Richtlinie) – zählt nicht als Rot-Grund
            if schutz.rot_fuer(voll, ausser=frozenset({"policies"})) and block.risiko is not Risiko.ROT:
                risiko = Risiko.ROT
        paket = self.registry.richtlinien.paket(r["paket"]) or {}
        return risiko, f"{r['paket']}@{paket.get('version', '')}"

    def registry_pruefen(self, i: int, block: BlockDef, werte: dict[str, ParamValue]) -> Risiko | None:
        """Registry-Bausteine: Pfad passend zum Bereich, Schutzliste, Risiko je Pfad.

        Gibt ``Risiko.ROT`` zurück, wenn ein geschützter Pfad den Schritt rot macht.
        """
        schutz = lade_schutz()
        risiko: Risiko | None = None
        for p in block.parameter:
            if p.typ is ParamTyp.REGISTRY_SOLL_LISTE:
                self.soll_liste_pruefen(i, block, p, werte)
                continue
            if p.typ is not ParamTyp.REGISTRY_PFAD:
                continue
            wert = werte.get(p.id)
            if wert is None or not isinstance(wert.wert, str):
                continue
            bereich_def = block.param(p.bezug or "bereich")
            bereich_wert = werte.get(bereich_def.id) if bereich_def is not None else None
            bereich = bereich_wert.wert if bereich_wert is not None else None
            try:
                pfad = registry_pfad_fuer_bereich(
                    wert.wert, bereich if isinstance(bereich, str) else None, block.registry == "lesen"
                )
                if self.ziel is Ziel.CMD and bereich not in (None, "computer", "angemeldeter_benutzer"):
                    raise ValidierungsFehler(
                        "Mehrere Benutzerprofile und das Standardprofil gehen nur mit PowerShell."
                    )
            except ValidierungsFehler as e:
                self.fehler.append(Feldfehler(i, p.id, f"{p.label}: {e}"))
                continue
            werte[p.id] = ParamValue(typ=wert.typ, wert=pfad)
            if block.registry == "lesen":
                continue
            voll = pfad if registry_teile(pfad)[0] else "HKCU\\" + pfad
            if schutz.gesperrt_fuer(voll):
                self.fehler.append(
                    Feldfehler(i, p.id, f"{p.label}: Dieser Bereich der Registry ist gesperrt ({voll}).")
                )
            elif block.registry == "schluessel_loeschen" and schutz.zu_flach_zum_loeschen(voll):
                self.fehler.append(
                    Feldfehler(
                        i,
                        p.id,
                        f"{p.label}: So weit oben wird nicht gelöscht – mindestens "
                        f"{schutz.loeschen_min_ebenen} Ebenen unter der Wurzel angeben.",
                    )
                )
            elif schutz.rot_fuer(voll) and block.risiko is not Risiko.ROT:
                risiko = Risiko.ROT
        return risiko

    def soll_liste_pruefen(
        self, i: int, block: BlockDef, p: ParameterDef, werte: dict[str, ParamValue]
    ) -> None:
        """Soll/Ist-Liste: jeden Pfad wie beim Lesen gegen den Bereich prüfen und in Script-Form bringen."""
        wert = werte.get(p.id)
        if wert is None or not isinstance(wert.wert, list):
            return
        bereich_wert = werte.get(p.bezug or "bereich")
        bereich = bereich_wert.wert if bereich_wert is not None else None
        neu: list[str | int] = []
        for n, eintrag in enumerate(wert.wert, 1):
            pfad, rest = (t.strip() for t in str(eintrag).split(";", 1))
            try:
                form = registry_pfad_fuer_bereich(pfad, bereich if isinstance(bereich, str) else None, True)
            except ValidierungsFehler as e:
                self.fehler.append(Feldfehler(i, p.id, f"{p.label}: Wert {n}: {e}"))
                continue
            neu.append(f"{form} ; {rest}")
        werte[p.id] = ParamValue(typ=wert.typ, wert=neu)

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


def registry_pfad_fuer_bereich(pfad: str, bereich: str | None, nur_lesen: bool) -> str:
    """Prüft einen normalisierten Registry-Pfad gegen den Bereich und liefert die Form fürs Script.

    ``computer``: HKLM (lesend auch HKCR/HKCC/HKU). Benutzer-Bereiche: Pfad ohne Wurzel; ``HKCU\\…``
    wird umgeschrieben (``HKCU`` selbst nutzt das Script nie – nach dem UAC-Neustart wäre das das
    Profil des Admin-Kontos). Ohne Bereich: Pfad mit Wurzel, aber nie HKCU.
    """
    wurzel, rest = registry_teile(pfad)
    if bereich is None or bereich == "computer":
        erlaubt = ("HKLM", "HKCR", "HKCC", "HKU") if nur_lesen else ("HKLM",)
        if wurzel == "HKCU" or (wurzel is None and bereich is not None):
            raise ValidierungsFehler(
                "Für „Computer“ bitte einen Pfad unter HKLM angeben. Benutzer-Einstellungen über den "
                "Bereich „Angemeldeter Benutzer“ bzw. „Alle Benutzerprofile“."
            )
        if wurzel not in erlaubt:
            raise ValidierungsFehler("Bitte einen Pfad unter " + " / ".join(erlaubt) + " angeben.")
        return pfad
    if wurzel in (None, "HKCU"):
        return rest
    raise ValidierungsFehler(
        "Für Benutzer-Bereiche den Pfad ohne Wurzel (Software\\…) oder mit HKCU\\ angeben – "
        "das Script schreibt dann in das richtige Benutzerprofil."
    )


def ist_schleifenwert(roh: Any) -> bool:
    return isinstance(roh, dict) and roh.get(SCHLEIFENWERT) is True and len(roh) == 1


def schleifenwerte(roh: Any) -> list[str]:
    """Werte für „Für jeden Wert“: Liste oder Text mit , bzw. ; getrennt (Leerzeichen bleiben)."""
    if isinstance(roh, str):
        teile: list[Any] = re.split(r"[,;]", roh)
    elif isinstance(roh, list):
        teile = roh
    else:
        raise ValidierungsFehler("Bitte mindestens einen Wert angeben (mehrere mit Komma trennen).")
    werte: list[str] = []
    for n, teil in enumerate(teile, 1):
        if isinstance(teil, bool) or not isinstance(teil, str | int):
            raise ValidierungsFehler(f"Wert {n} ist kein Text.")
        text = str(teil).strip()
        if not text:
            continue
        try:
            pruefe_zeichen(text)
        except (ValidierungsFehler, UnsicherError) as e:
            raise ValidierungsFehler(f"Wert {n} („{text}“): {e}") from None
        if len(text) > 260:
            raise ValidierungsFehler(f"Wert {n} ist zu lang (höchstens 260 Zeichen).")
        werte.append(text)
    if not werte:
        raise ValidierungsFehler("Bitte mindestens einen Wert angeben (mehrere mit Komma trennen).")
    if len(werte) > MAX_SCHLEIFENWERTE:
        raise ValidierungsFehler(f"Höchstens {MAX_SCHLEIFENWERTE} Werte.")
    return werte


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
    if isinstance(k, FuerJeden):
        return FuerJedenEingabe(
            art="fuer_jeden", werte=k.werte, rumpf=[_knoten_zu_eingabe(x) for x in k.rumpf]
        )
    if isinstance(k, Wiederhole):
        return WiederholeEingabe(
            art="wiederhole", anzahl=k.anzahl, rumpf=[_knoten_zu_eingabe(x) for x in k.rumpf]
        )
    return SchrittEingabe(
        block_id=k.block_id,
        parameter={
            n: {SCHLEIFENWERT: True} if v.schleife else v.wert
            for n, v in k.parameter.items()
            if v.wert is not None
        },
    )
