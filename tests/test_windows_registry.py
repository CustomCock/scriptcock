"""Teil A: Registry-Bausteine – Bereiche, Schutzliste, Escaping je Ziel, Hilfsfunktionen.

Unter Linux gibt es keine Registry: geprüft werden Validierung, Script-Text und die reinen
PowerShell-Hilfsfunktionen (Umrechnung, .reg-Datei lesen, Schutz beim Import) unter pwsh.
Echte Registry-Zugriffe laufen im Windows-CI-Job (tests/windows/).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from app.escaping import Ziel
from app.generators import generator_fuer
from app.ir import BlockSchritt
from app.models.block import Risiko
from app.registry import Registry
from app.validation import FehlerSammlung
from tests.test_kontrolle import blk, ir_aus

HILFEN = Path(__file__).resolve().parent.parent / "app" / "generators" / "hilfen" / "registry.ps1"


def setzen(**kw: Any) -> dict[str, Any]:
    werte = {"bereich": "computer", "pfad": "HKLM\\SOFTWARE\\OkmTest", "wertname": "Wert", "typ": "REG_DWORD"}
    werte["daten"] = "1"
    werte.update(kw)
    return blk("registry_wert_setzen", **werte)


def text(registry: Registry, ziel: Ziel, schritte: list[dict[str, Any]], **kw: Any) -> str:
    ir = ir_aus(registry, ziel, schritte, rot_bestaetigt=True, **kw)
    return generator_fuer(ziel, registry).erzeuge(ir).text


def fehler(registry: Registry, ziel: Ziel, schritte: list[dict[str, Any]], **kw: Any) -> list[str]:
    kw.setdefault("rot_bestaetigt", True)
    with pytest.raises(FehlerSammlung) as e:
        ir_aus(registry, ziel, schritte, **kw)
    return [f"{f.feld}: {f.meldung}" for f in e.value.fehler]


# --- Bereich und Pfad -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bereich", "pfad", "erwartet"),
    [
        ("computer", "HKEY_LOCAL_MACHINE\\SOFTWARE\\OkmTest\\", "HKLM\\SOFTWARE\\OkmTest"),
        ("computer", "Registry::HKEY_LOCAL_MACHINE\\SOFTWARE\\OkmTest", "HKLM\\SOFTWARE\\OkmTest"),
        ("computer", "HKLM:\\SOFTWARE\\OkmTest", "HKLM\\SOFTWARE\\OkmTest"),
        ("angemeldeter_benutzer", "HKCU\\Software\\OkmTest", "Software\\OkmTest"),
        ("alle_benutzer", "HKEY_CURRENT_USER\\Software\\OkmTest", "Software\\OkmTest"),
        ("standardprofil", "Software\\OkmTest", "Software\\OkmTest"),
    ],
)
def test_pfad_je_bereich(registry: Registry, bereich: str, pfad: str, erwartet: str) -> None:
    ir = ir_aus(registry, Ziel.POWERSHELL, [setzen(bereich=bereich, pfad=pfad)])
    schritt = ir.schritte[0]
    assert isinstance(schritt, BlockSchritt)
    assert schritt.parameter["pfad"].wert == erwartet


@pytest.mark.parametrize(
    ("bereich", "pfad", "teil"),
    [
        ("computer", "HKCU\\Software\\OkmTest", "unter HKLM"),
        ("computer", "Software\\OkmTest", "unter HKLM"),
        ("computer", "HKU\\S-1-5-21-1\\Software", "unter HKLM"),
        ("angemeldeter_benutzer", "HKLM\\SOFTWARE\\OkmTest", "ohne Wurzel"),
        ("alle_benutzer", "HKU\\S-1-5-21-1\\Software", "ohne Wurzel"),
        ("computer", "HKLM", "nicht nur die Wurzel"),
        ("computer", "HKLM\\SOFTWARE\\\\x", "leeren Teil"),
        ("computer", 'HKLM\\SOFTWARE\\"x"', "Anführungszeichen"),
        ("computer", "HKLM\\" + "x" * 256, "höchstens 255"),
        ("computer", "HKLM\\" + "\\".join(["a" * 200] * 3), "höchstens 512"),
    ],
)
def test_pfad_abgelehnt(registry: Registry, bereich: str, pfad: str, teil: str) -> None:
    meldungen = fehler(registry, Ziel.POWERSHELL, [setzen(bereich=bereich, pfad=pfad)])
    assert any(m.startswith("pfad:") and teil in m for m in meldungen), meldungen


def test_lesen_erlaubt_weitere_wurzeln_unter_computer(registry: Registry) -> None:
    schritt = blk("registry_schluessel_anzeigen", bereich="computer", pfad="HKCR\\.txt")
    assert ir_aus(registry, Ziel.POWERSHELL, [schritt])
    # Schreiben dagegen nur HKLM
    assert fehler(registry, Ziel.POWERSHELL, [setzen(pfad="HKCR\\.txt")])


@pytest.mark.parametrize("bereich", ["alle_benutzer", "standardprofil", "alle_benutzer_und_standardprofil"])
def test_cmd_nur_computer_und_angemeldeter_benutzer(registry: Registry, bereich: str) -> None:
    meldungen = fehler(registry, Ziel.CMD, [setzen(bereich=bereich, pfad="Software\\OkmTest")])
    assert any("nur mit PowerShell" in m for m in meldungen)


# --- Schutzliste und Risiko -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("block_id", "pfad"),
    [
        ("registry_wert_setzen", "HKLM\\SAM\\SAM\\Domains"),
        ("registry_wert_setzen", "HKEY_LOCAL_MACHINE\\SECURITY\\Policy"),
        ("registry_schluessel_loeschen", "HKLM\\BCD00000000\\Objects"),
        ("registry_wert_loeschen", "hklm\\sam\\x"),
    ],
)
def test_gesperrte_bereiche(registry: Registry, block_id: str, pfad: str) -> None:
    werte = {"bereich": "computer", "pfad": pfad}
    if block_id == "registry_wert_setzen":
        werte |= {"wertname": "x", "typ": "REG_DWORD", "daten": "1"}
    meldungen = fehler(registry, Ziel.POWERSHELL, [blk(block_id, **werte)])
    assert any("gesperrt" in m for m in meldungen), meldungen


@pytest.mark.parametrize(
    ("bereich", "pfad"),
    # Ebenen unter der Wurzel: HKLM\\SOFTWARE = 1, HKCU\\Software\\Microsoft = 2 (mindestens 3 nötig)
    [("computer", "HKLM\\SOFTWARE"), ("angemeldeter_benutzer", "HKCU\\Software\\Microsoft")],
)
def test_zu_flach_zum_loeschen(registry: Registry, bereich: str, pfad: str) -> None:
    meldungen = fehler(
        registry, Ziel.POWERSHELL, [blk("registry_schluessel_loeschen", bereich=bereich, pfad=pfad)]
    )
    assert any("So weit oben wird nicht gelöscht" in m for m in meldungen), meldungen
    assert ir_aus(
        registry,
        Ziel.POWERSHELL,
        [blk("registry_schluessel_loeschen", bereich=bereich, pfad=pfad + "\\Firma\\OkmTest")],
        rot_bestaetigt=True,
    )


@pytest.mark.parametrize(
    ("bereich", "pfad", "rot"),
    [
        ("computer", "HKLM\\SOFTWARE\\OkmTest", False),
        ("computer", "HKLM\\SYSTEM\\CurrentControlSet\\Services\\OkmTest", True),
        ("computer", "HKLM\\SOFTWARE\\Policies\\Google\\Chrome", True),
        ("computer", "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon", True),
        ("angemeldeter_benutzer", "Software\\Policies\\Microsoft\\Edge", True),
        ("angemeldeter_benutzer", "Software\\OkmTest", False),
    ],
)
def test_rot_je_pfad(registry: Registry, bereich: str, pfad: str, rot: bool) -> None:
    ir = ir_aus(registry, Ziel.POWERSHELL, [setzen(bereich=bereich, pfad=pfad)], rot_bestaetigt=True)
    schritt = ir.schritte[0]
    assert isinstance(schritt, BlockSchritt)
    assert (schritt.risiko is Risiko.ROT) is rot
    script = generator_fuer(Ziel.POWERSHELL, registry).erzeuge(ir).text
    assert ("Zum Fortfahren JA eingeben" in script) is rot
    assert ("(Risiko: rot)" in script) is rot
    if rot:  # ohne Bestätigung im Formular wird ein roter Schritt abgelehnt
        meldungen = fehler(
            registry, Ziel.POWERSHELL, [setzen(bereich=bereich, pfad=pfad)], rot_bestaetigt=False
        )
        assert any(m.startswith("rot_bestaetigt") for m in meldungen)


# --- Daten und Escaping je Ziel ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("typ", "daten", "ps", "cmd"),
    [
        ("REG_DWORD", "4294967295", "-Daten '4294967295'", '/t "REG_DWORD" /d 0xFFFFFFFF'),
        ("REG_DWORD", "0x80000000", "-Daten '2147483648'", "/d 0x80000000"),
        ("REG_QWORD", "18446744073709551615", "-Daten '18446744073709551615'", "/d 0xFFFFFFFFFFFFFFFF"),
        ("REG_SZ", "C:\\Pfad\\", "-Daten 'C:\\Pfad\\'", '/d "C:\\Pfad\\\\"'),  # \ vor " verdoppelt
        ("REG_EXPAND_SZ", "%SystemRoot%\\okm", "-Daten '%SystemRoot%\\okm'", '/d "%%SystemRoot%%\\okm"'),
        ("REG_MULTI_SZ", "eins\nzwei drei", "-Daten @('eins', 'zwei drei')", '/d "eins\\0zwei drei"'),
        ("REG_BINARY", "0A 1b, ff", "-Daten '0a1bff'", "/d 0a1bff"),
        ("REG_SZ", "Größe ✓ 日本", "-Daten 'Größe ✓ 日本'", '/d "Größe ✓ 日本"'),
        ("REG_SZ", "it's", "-Daten 'it''s'", '/d "it\'s"'),
    ],
)
def test_daten_je_ziel(registry: Registry, typ: str, daten: str, ps: str, cmd: str) -> None:
    assert ps in text(registry, Ziel.POWERSHELL, [setzen(typ=typ, daten=daten)])
    assert cmd in text(registry, Ziel.CMD, [setzen(typ=typ, daten=daten)])


@pytest.mark.parametrize(
    ("ziel", "daten", "teil"),
    [
        (Ziel.CMD, 'a"b', "Anführungszeichen"),
        (Ziel.POWERSHELL, "a\u202eb", "Steuerzeichen"),
        (Ziel.CMD, "-x", "nicht mit - oder /"),
        (Ziel.CMD, "/f", "nicht mit - oder /"),
    ],
)
def test_daten_abgelehnt(registry: Registry, ziel: Ziel, daten: str, teil: str) -> None:
    meldungen = fehler(registry, ziel, [setzen(typ="REG_SZ", daten=daten)])
    assert any(teil in m for m in meldungen), meldungen


def test_multi_sz_ohne_nul_trenner(registry: Registry) -> None:
    meldungen = fehler(registry, Ziel.CMD, [setzen(typ="REG_MULTI_SZ", daten="a\\0b")])
    assert any("\\0" in m for m in meldungen)


def test_standardwert_und_ansicht(registry: Registry) -> None:
    cmd = text(registry, Ziel.CMD, [setzen(wertname="", ansicht="32")])
    assert 'reg add "HKLM\\SOFTWARE\\OkmTest" /ve /t "REG_DWORD" /d 0x1 /f /reg:32' in cmd
    ps = text(registry, Ziel.POWERSHELL, [setzen(wertname="(Standard)")])
    assert "-Name '' -Typ 'REG_DWORD'" in ps


def test_typ_schreibweisen(registry: Registry) -> None:
    assert "-Typ 'REG_EXPAND_SZ'" in text(registry, Ziel.POWERSHELL, [setzen(typ="expand_sz", daten="x")])
    meldungen = fehler(registry, Ziel.POWERSHELL, [setzen(typ="REG_LINK", daten="x")])
    assert any(m.startswith("typ:") for m in meldungen)


# --- Generierter Code -----------------------------------------------------------------------------


def test_hkcu_wird_nie_benutzt(registry: Registry) -> None:
    """Benutzer-Bereich: das Script ermittelt den Benutzer und schreibt nach HKU\\<SID>."""
    ps = text(
        registry, Ziel.POWERSHELL, [setzen(bereich="angemeldeter_benutzer", pfad="HKCU\\Software\\OkmTest")]
    )
    assert "-Bereich 'angemeldeter_benutzer' -Pfad 'Software\\OkmTest'" in ps
    code = [z for z in ps.splitlines() if not z.lstrip().startswith("#")]
    assert not any("HKCU:" in z or "Registry::HKEY_CURRENT_USER" in z for z in code)
    cmd = text(registry, Ziel.CMD, [setzen(bereich="angemeldeter_benutzer", pfad="Software\\OkmTest")])
    assert 'for /f "usebackq delims=" %%s in (`powershell' in cmd
    assert 'reg add "HKU\\%%s\\Software\\OkmTest" /v "Wert"' in cmd
    assert "HKCU" not in cmd.split("rem ----", 1)[1]


def test_hilfen_nur_mit_registry_baustein(registry: Registry) -> None:
    mit = text(registry, Ziel.POWERSHELL, [setzen()])
    assert "function Set-OkmRegistryWert" in mit and "Sysnative" in mit
    assert "$script:OkmRegGesperrt = @('HKLM\\SAM', 'HKLM\\SECURITY', 'HKLM\\BCD00000000')" in mit
    assert "Rückgängig machen" in mit and "Damit die Änderungen wirken" in mit
    ohne = text(registry, Ziel.POWERSHELL, [blk("meldung", text="x", pause=False)])
    assert "Set-OkmRegistryWert" not in ohne and "Sysnative" not in ohne and "OkmReg" not in ohne
    cmd = text(registry, Ziel.CMD, [setzen()])
    # eindeutiger Ordner per mkdir (schlägt fehl, wenn belegt) – nach der Rechteprüfung, leer am Ende wieder weg
    assert 'mkdir "%TEMP%\\okm-registry-backup-%OKM_TS%-%%i" >nul 2>&1 && set "OKM_REG_SICHERUNG=' in cmd
    assert cmd.index("net session") < cmd.index("for /l %%i in (1,1,99)")
    assert 'if exist "%OKM_REG_SICHERUNG%\\*.reg" echo( Rückgängig machen' in cmd
    assert 'rd "%OKM_REG_SICHERUNG%" >nul 2>&1' in cmd
    assert "OKM_REG_SICHERUNG" not in text(registry, Ziel.CMD, [blk("meldung", text="x", pause=False)])


def test_vorschau_vor_bestaetigung(registry: Registry) -> None:
    schritt = blk("registry_schluessel_loeschen", bereich="computer", pfad="HKLM\\SOFTWARE\\Firma\\Alt")
    ps = text(registry, Ziel.POWERSHELL, [schritt])
    assert (
        ps.index("Show-OkmRegistryLoeschVorschau")
        < ps.index("Zum Fortfahren JA")
        < ps.index("Remove-OkmRegistrySchluessel -Bereich")
    )
    cmd = text(registry, Ziel.CMD, [schritt])
    assert cmd.index('find /c "HKEY_"') < cmd.index("Zum Fortfahren JA") < cmd.index("reg delete")


def test_simulation_aendert_nichts(registry: Registry) -> None:
    ps = text(registry, Ziel.POWERSHELL, [setzen()], dry_run=True)
    aufrufe = [z.strip() for z in ps.splitlines() if "Set-OkmRegistryWert -Bereich" in z]
    assert aufrufe and all(z.endswith("-Simulation") for z in aufrufe)
    loeschen = blk("registry_wert_loeschen", bereich="computer", pfad="HKLM\\SOFTWARE\\X\\Y", wertname="a")
    ps = text(registry, Ziel.POWERSHELL, [loeschen], dry_run=True)
    assert (
        "Remove-OkmRegistryWert -Bereich 'computer' -Pfad 'HKLM\\SOFTWARE\\X\\Y' -Name 'a' -Ansicht '64' -Simulation"
        in ps
    )


def test_wirkung_in_zusammenfassung(registry: Registry) -> None:
    ps = text(registry, Ziel.POWERSHELL, [setzen(wirkung="abmelden")])
    assert "Add-OkmWirkung 'abmelden'" in ps
    cmd = text(registry, Ziel.CMD, [setzen(wirkung="neustart")])
    assert "if not errorlevel 1 if 4 GTR %OKM_WIRKUNG% set OKM_WIRKUNG=4" in cmd
    assert 'if "%OKM_WIRKUNG%"=="4" echo( Damit die Änderungen wirken: Rechner neu starten' in cmd


def test_import_cmd_prueft_hkcu_und_sperren(registry: Registry) -> None:
    schritt = blk("registry_import", datei="\\\\fs01\\IT\\app.reg")
    cmd = text(registry, Ziel.CMD, [schritt])
    assert '/c:"[HKEY_CURRENT_USER"' in cmd
    assert '/c:"HKEY_LOCAL_MACHINE\\\\SAM]" /c:"HKEY_LOCAL_MACHINE\\\\SAM\\\\"' in cmd
    assert cmd.index('findstr /i /c:"[HKEY_CURRENT_USER"') < cmd.index("reg import")


# --- PowerShell-Hilfsfunktionen unter pwsh ----------------------------------------------------------


def pwsh(code: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    if shutil.which("pwsh") is None:
        pytest.skip("pwsh fehlt")
    datei = tmp_path / "t.ps1"
    datei.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        "function Write-OkmInfo([string]$Text) { Write-Host $Text }\n"
        "function Write-OkmWarnung([string]$Text) { Write-Host ('WARNUNG ' + $Text) }\n"
        "$script:OkmRegGesperrt = @('HKLM\\SAM', 'HKLM\\SECURITY')\n"
        f". '{HILFEN}'\n" + code,
        encoding="utf-8-sig",
    )
    return subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(datei)], capture_output=True, text=True, timeout=120
    )


def test_umrechnung_dword_qword_binary_multi(tmp_path: Path) -> None:
    r = pwsh(
        "$a = [Microsoft.Win32.RegistryValueKind]\n"
        "foreach ($f in @(@('REG_DWORD','0'), @('REG_DWORD','2147483647'), @('REG_DWORD','2147483648'), "
        "@('REG_DWORD','4294967295'), @('REG_QWORD','9223372036854775808'), @('REG_QWORD','18446744073709551615'))) {\n"
        "  $w = ConvertTo-OkmRegistryWert $f[0] $f[1]\n"
        "  $art = $a::DWord; if ($f[0] -eq 'REG_QWORD') { $art = $a::QWord }\n"
        "  Write-Output ($w.GetType().Name + ' ' + (ConvertTo-OkmRegistryText $art $w))\n"
        "}\n"
        "$b = ConvertTo-OkmRegistryWert 'REG_BINARY' '00ff10'\n"
        "Write-Output ($b.GetType().Name + ' ' + (ConvertTo-OkmRegistryText $a::Binary $b))\n"
        "$m = ConvertTo-OkmRegistryWert 'REG_MULTI_SZ' @('x')\n"
        "Write-Output ($m.GetType().Name + ' ' + $m.Count)\n"
        "Write-Output (Format-OkmRegistryWert $a::DWord (ConvertTo-OkmRegistryWert 'REG_DWORD' '4294967295'))\n",
        tmp_path,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines() == [
        "Int32 0",
        "Int32 2147483647",
        "Int32 2147483648",  # als Int32 negativ gespeichert, vorzeichenlos angezeigt
        "Int32 4294967295",
        "Int64 9223372036854775808",
        "Int64 18446744073709551615",
        "Byte[] 00ff10",
        "String[] 1",
        "REG_DWORD 4294967295 (0xFFFFFFFF)",
    ]


def reg_datei(tmp_path: Path, zeilen: list[str], kodierung: str = "utf-16") -> Path:
    datei = tmp_path / "test.reg"
    datei.write_text(
        "\r\n".join(["Windows Registry Editor Version 5.00", "", *zeilen, ""]), encoding=kodierung
    )
    return datei


def test_reg_datei_lesen_utf16(tmp_path: Path) -> None:
    datei = reg_datei(
        tmp_path,
        [
            "[HKEY_LOCAL_MACHINE\\SOFTWARE\\OkmTest]",
            '"Name"="Wert"',
            '"Zahl"=dword:00000001',
            '"Bin"=hex:00,ff,\\',
            "  10,20",
            '@="Standard"',
            "",
            "[-HKEY_LOCAL_MACHINE\\SOFTWARE\\OkmAlt]",
        ],
    )
    r = pwsh(
        f"$i = Read-OkmRegDatei '{datei}'\n"
        "Write-Output ([string]$i.Schluessel.Count + ' ' + $i.Werte)\n"
        "$i.Schluessel | ForEach-Object { Write-Output ([string]$_.Loeschen + ' ' + $_.Pfad) }\n",
        tmp_path,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines() == [
        "2 4",
        "False HKEY_LOCAL_MACHINE\\SOFTWARE\\OkmTest",
        "True HKEY_LOCAL_MACHINE\\SOFTWARE\\OkmAlt",
    ]


@pytest.mark.parametrize(
    ("schluessel", "meldung"),
    [
        ("[HKEY_CURRENT_USER\\Software\\OkmTest]", "HKEY_CURRENT_USER"),
        ("[HKEY_LOCAL_MACHINE\\SAM\\x]", "gesperrten Bereich"),
        ("[-hkey_local_machine\\security]", "gesperrten Bereich"),
        ("[HKEY_PERFORMANCE_DATA\\x]", "Unbekannte Wurzel"),
    ],
)
def test_import_lehnt_ab_bevor_etwas_passiert(tmp_path: Path, schluessel: str, meldung: str) -> None:
    datei = reg_datei(
        tmp_path, ["[HKEY_LOCAL_MACHINE\\SOFTWARE\\OkmTest]", '"a"="b"', "", schluessel, '"x"="y"']
    )
    r = pwsh(f"Import-OkmRegistryDatei -Datei '{datei}' -Simulation", tmp_path)
    assert r.returncode != 0
    assert meldung in r.stdout + r.stderr


def test_import_simulation_zeigt_schluessel(tmp_path: Path) -> None:
    datei = reg_datei(tmp_path, ["[HKEY_LOCAL_MACHINE\\SOFTWARE\\OkmTest]", '"a"="b"'], kodierung="utf-8")
    r = pwsh(f"Import-OkmRegistryDatei -Datei '{datei}' -Simulation", tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1 Schlüssel, 1 Werte" in r.stdout
    assert "ändern: HKLM\\SOFTWARE\\OkmTest" in r.stdout
    assert "[SIMULATION] Die Datei würde importiert." in r.stdout
