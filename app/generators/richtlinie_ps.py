"""PowerShell-Code für ``richtlinie_setzen`` und ``admin_werkzeug_bereitstellen`` (dynamische Bausteine).

Die Operationen kommen aus dem geprüften Richtlinien-Katalog bzw. aus ``registry/admx-quellen.yaml``;
jeder Wert wird einzeln über ``escaping`` eingesetzt. Nur die Funktionsaufrufe (Hilfen aus
``hilfen/registry.ps1`` und ``hilfen/richtlinien.ps1``) sind fester Generator-Code.
"""

from __future__ import annotations

from typing import Any

from app import escaping, werkzeuge
from app.escaping import Ziel
from app.ir import BlockSchritt
from app.registry import Registry
from app.richtlinien import ELEMENT_PRAEFIX, Operation, operationen
from app.validation import ValidierungsFehler, registry_daten


class CodeFehler(ValueError):
    pass


def _l(text: str) -> str:
    return str(escaping.powershell_literal(text))


def _wert(schritt: BlockSchritt, pid: str, standard: Any = None) -> Any:
    pv = schritt.parameter.get(pid)
    return pv.wert if pv is not None and pv.wert is not None else standard


ZUSTAND_TEXT = {
    "aktiviert": "aktiviert",
    "deaktiviert": "deaktiviert",
    "nicht_konfiguriert": "nicht konfiguriert",
}


def _daten(op: Operation) -> str:
    """Daten erneut prüfen (Katalog ist nur halb vertrauenswürdig) und als PS-Argument escapen."""
    try:
        roh: Any = list(op.daten) if isinstance(op.daten, tuple) else op.daten
        geprueft = registry_daten(roh if roh is not None else "", op.typ)
    except ValidierungsFehler as e:
        raise CodeFehler(f"Ungültige Daten in der Richtlinie: {e}") from None
    return str(escaping.registry_daten(Ziel.POWERSHELL, op.typ, geprueft))


def _lgpo_zeilen(ops: list[Operation], abschnitt: str) -> list[str]:
    """LGPO-Textformat: Abschnitt, Schlüssel, Wertname, Aktion – je Operation ein Block."""
    zeilen: list[str] = []
    for op in ops:
        if op.art == "leer_entfernen":
            continue  # Registry.pol kennt kein „Schlüssel entfernen“
        for teil in (op.pfad, op.name):
            if teil.startswith(";"):
                raise CodeFehler("Schlüssel/Wertname beginnt mit ; – geht mit LGPO nicht.")
        if op.art == "setzen":
            daten = op.daten
            if op.typ == "REG_DWORD":
                aktion = f"DWORD:{int(str(daten))}"
            elif op.typ == "REG_QWORD":
                aktion = f"QWORD:{int(str(daten))}"
            elif op.typ == "REG_EXPAND_SZ":
                aktion = f"EXSZ:{daten}"
            elif op.typ == "REG_MULTI_SZ":
                aktion = "MULTISZ:" + "\\0".join(daten if isinstance(daten, tuple) else ())
            else:
                aktion = f"SZ:{daten}"
            zeilen += [abschnitt, op.pfad, op.name, aktion, ""]
        elif op.art == "loeschen":
            zeilen += [abschnitt, op.pfad, op.name, "DELETE", ""]
        elif op.art == "leeren":
            zeilen += [abschnitt, op.pfad, "*", "DELETEALLVALUES", ""]
    return zeilen


def richtlinie_code(registry: Registry, schritt: BlockSchritt, dry: bool) -> list[str]:
    rid = str(_wert(schritt, "richtlinie", ""))
    r = registry.richtlinien.richtlinie(rid)
    if r is None:
        raise CodeFehler(f"Die Richtlinie {rid} gibt es im Katalog nicht (mehr).")
    zustand = str(_wert(schritt, "zustand", "aktiviert"))
    bereich = str(_wert(schritt, "bereich", "computer"))
    methode = str(_wert(schritt, "methode", "registry_direkt"))
    elemente = {pid: pv.wert for pid, pv in schritt.parameter.items() if pid.startswith(ELEMENT_PRAEFIX)}
    ops = operationen(r, zustand, elemente)
    sim = " -Simulation" if dry else ""
    zeilen = [f"Write-OkmInfo {_l('Richtlinie: ' + r['titel'] + ' → ' + ZUSTAND_TEXT.get(zustand, zustand))}"]
    if methode == "lokale_gruppenrichtlinie":
        abschnitt = "Computer" if bereich == "computer" else "User"
        lgpo = _lgpo_zeilen(ops, abschnitt)
        if not lgpo:
            return [*zeilen, "Write-OkmInfo 'Nichts in die lokale Gruppenrichtlinie zu schreiben.'"]
        zeilen.append("$okmLgpo = @(")
        zeilen += [f"    {_l(z)}," for z in lgpo[:-1]]
        zeilen += [f"    {_l(lgpo[-1])}", ")"]
        zeilen.append(f"Invoke-OkmLgpo -Zeilen $okmLgpo{sim}")
    else:
        for op in ops:
            pfad = f"HKLM\\{op.pfad}" if bereich == "computer" else op.pfad
            ziel = f"-Bereich {_l(bereich)} -Pfad {_l(pfad)}"
            if op.art == "setzen":
                wenn = "nur_wenn_fehlt" if op.nur_wenn_fehlt else "ueberschreiben"
                zeilen.append(
                    f"$null = Set-OkmRegistryWert {ziel} -Name {_l(op.name)} -Typ {_l(op.typ)} "
                    f"-Daten {_daten(op)} -WennVorhanden {_l(wenn)} -Ansicht '64'{sim}"
                )
            elif op.art == "loeschen":
                zeilen.append(f"Remove-OkmRegistryWert {ziel} -Name {_l(op.name)} -Ansicht '64'{sim}")
            elif op.art == "leeren":
                zeilen.append(f"Clear-OkmRegistrySchluessel {ziel} -Ansicht '64'{sim}")
            elif op.art == "leer_entfernen":
                zeilen.append(f"Remove-OkmRegistrySchluesselWennLeer {ziel} -Ansicht '64'{sim}")
    if not dry:
        zeilen.append(f"Register-OkmGpupdate {_l('computer' if bereich == 'computer' else 'user')}")
    return zeilen


def werkzeug_code(registry: Registry, schritt: BlockSchritt, dry: bool) -> list[str]:
    was = str(_wert(schritt, "was", "lgpo"))
    quelle = str(_wert(schritt, "quelle", "intranet"))
    pid = "lgpo" if was == "lgpo" else str(_wert(schritt, "paket", ""))
    basis = registry.werkzeug_url.rstrip("/")
    if was != "software" and quelle == "intranet" and not basis:
        raise CodeFehler(
            "Die Quelle „Intranet“ ist nicht eingerichtet (OKM_WERKZEUG_URL fehlt) – „Hersteller“ wählen."
        )

    def url(d: werkzeuge.Datei) -> str:
        return f"{basis}/werkzeuge/{d.spiegel}" if quelle == "intranet" else d.url

    if was == "lgpo":
        w = werkzeuge.werkzeug("lgpo")
        liste = werkzeuge.dateien("lgpo")
        if w is None or len(liste) != 1 or not liste[0].sha256:
            raise CodeFehler("LGPO ist in registry/admx-quellen.yaml nicht (vollständig) eingetragen.")
        d = liste[0]
        if dry:
            return [f"Write-OkmInfo {_l('[SIMULATION] LGPO.exe würde bereitgestellt: ' + url(d))}"]
        return [
            f"Install-OkmWerkzeug -Name 'lgpo' -Version {_l(str(w['version']))} -Url {_l(url(d))} "
            f"-Sha256 {_l(d.sha256)} -ZipEintrag {_l(w['datei'])} -EintragSha256 {_l(w['datei_sha256'])}"
        ]
    p = werkzeuge.paket(pid)
    if p is None:
        raise CodeFehler(f"Unbekanntes Vorlagen-Paket „{pid}“.")
    if was == "software":
        if not p.get("software"):
            raise CodeFehler(f"Für {p['name']} ist keine winget-ID hinterlegt.")
        if dry:
            return [f"Write-OkmInfo {_l('[SIMULATION] würde installiert, falls es fehlt: ' + p['software'])}"]
        return [f"Install-OkmSoftwareFallsFehlt -WingetId {_l(p['software'])}"]
    # Vorlagen (ADMX/ADML) nach PolicyDefinitions bzw. in den Central Store
    admx = registry.richtlinien.admx_dateien(pid)
    if not admx:
        raise CodeFehler(f"Für {p['name']} gibt es keine Vorlagen im Katalog.")
    liste = werkzeuge.dateien(pid)
    if not liste:
        raise CodeFehler(f"Für {p['name']} gibt es keinen Download (Vorlagen von Hand verteilen).")
    if any(not d.sha256 for d in liste):
        raise CodeFehler(f"Für {p['name']} fehlt ein SHA-256 in registry/admx-quellen.yaml.")
    if dry:
        return [f"Write-OkmInfo {_l('[SIMULATION] Vorlagen würden installiert: ' + ', '.join(admx))}"]
    zeilen = ["$okmDateien = @("]
    zeilen += [
        f"    @{{ Url = {_l(url(d))}; Sha256 = {_l(d.sha256)}; Ziel = {_l(d.name)} }}"
        + ("," if n < len(liste) - 1 else "")
        for n, d in enumerate(liste)
    ]
    zeilen.append(")")
    zeilen.append(f"$okmAdmx = @({', '.join(_l(a) for a in admx)})")
    central = " -CentralStore" if _wert(schritt, "central_store", False) else ""
    zeilen.append(
        f"Install-OkmVorlagen -Name {_l(pid)} -Format {_l(p['format'])} -Dateien $okmDateien "
        f"-Admx $okmAdmx{central}"
    )
    return zeilen
