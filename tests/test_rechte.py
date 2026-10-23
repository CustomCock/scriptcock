"""Rechte pro Ziel (``rechte:``): Schema, Registry-Regeln, Generator (UAC-Neustart, sudo, nie_root)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import Datenbank
from app.escaping import Ziel
from app.main import create_app
from app.models.block import Recht
from app.registry import Registry, RegistryFehler, lade_registry
from tests.conftest import erzeuge
from tests.test_web import einst

MELDUNG = ("meldung", {"text": "x", "pause": False})


def _block(tmp_path: Path, yaml_text: str) -> Registry:
    bloecke = tmp_path / "blocks"
    bloecke.mkdir(exist_ok=True)
    (bloecke / "b.yaml").write_text(yaml_text, encoding="utf-8")
    (tmp_path / "recipes").mkdir(exist_ok=True)
    return lade_registry(bloecke, tmp_path / "recipes")


KOPF = "id: b\nname: B\nkategorie: Test\nbeschreibung: Test\nrisiko: gelb\n"


# --- Schema & Registry ------------------------------------------------------------------


def test_alter_schluessel_wird_abgelehnt(tmp_path: Path) -> None:
    with pytest.raises(RegistryFehler, match=r"admin_noetig.*rechte"):
        _block(tmp_path, KOPF + "admin_noetig: true\nziele:\n  bash: |\n    true\n")


@pytest.mark.parametrize(
    ("rechte", "meldung"),
    [
        ("powershell: root", "powershell"),
        ("bash: admin", "bash"),
        ("zsh: was", "zsh"),
        ("cmd: admin", "Ziele ohne Eintrag"),
    ],
)
def test_ungueltige_rechte(tmp_path: Path, rechte: str, meldung: str) -> None:
    with pytest.raises(RegistryFehler, match=meldung):
        _block(
            tmp_path,
            KOPF
            + f"rechte:\n  {rechte}\nziele:\n  powershell: |\n    $null = 1\n  bash: |\n    true\n  zsh: |\n    true\n",
        )


def test_root_block_braucht_sudo_platzhalter(tmp_path: Path) -> None:
    with pytest.raises(RegistryFehler, match="sudo"):
        _block(tmp_path, KOPF + "rechte:\n  bash: root\nziele:\n  bash: |\n    systemctl restart cups\n")
    with pytest.raises(RegistryFehler, match="sudo"):
        _block(tmp_path, KOPF + "ziele:\n  bash: |\n    {{ sudo }}systemctl restart cups\n")
    with pytest.raises(RegistryFehler, match="sudo"):
        _block(
            tmp_path, KOPF + "rechte:\n  powershell: admin\nziele:\n  powershell: |\n    {{ sudo }}Get-Date\n"
        )
    reg = _block(
        tmp_path, KOPF + "rechte:\n  bash: root\nziele:\n  bash: |\n    {{ sudo }}systemctl restart cups\n"
    )
    assert reg.bloecke["b"].recht(Ziel.BASH) is Recht.ROOT


def test_alle_bloecke_migriert(registry: Registry) -> None:
    for b in registry.bloecke.values():
        for z in b.ziele:
            if b.recht(z) is Recht.ROOT:
                assert "sudo" in registry.variablen[(b.id, "ziele", z)], (b.id, z)
    assert registry.bloecke["paket_installieren"].recht(Ziel.ZSH) is Recht.NIE_ROOT
    assert registry.bloecke["paket_installieren"].recht(Ziel.BASH) is Recht.ROOT
    assert registry.bloecke["dienst_neustarten"].recht(Ziel.POWERSHELL) is Recht.ADMIN


# --- Generator ------------------------------------------------------------------------------


@pytest.mark.parametrize("ziel", list(Ziel), ids=[z.value for z in Ziel])
def test_ohne_erhoehte_rechte(registry: Registry, ziel: Ziel) -> None:
    text = erzeuge(registry, ziel, [MELDUNG]).text
    assert "Benötigte Rechte:  keine" in text
    assert "ohne erhöhte Rechte" in text
    assert "RunAs" not in text and "sudo -v" not in text and "net session" not in text


def test_powershell_startet_sich_als_admin_neu(registry: Registry) -> None:
    text = erzeuge(registry, Ziel.POWERSHELL, [MELDUNG, ("dienst_neustarten", {"dienst": "Spooler"})]).text
    assert "Benötigte Rechte:  Administrator (Schritt 2)" in text
    assert "Schritt 2 (Dienst neu starten)" in text
    assert "-Verb RunAs" in text and "$PSCommandPath" in text
    assert "'-ExecutionPolicy', 'Bypass'" in text
    assert "abgelehnt" in text  # UAC abgelehnt → Meldung statt stillem Abbruch
    assert "als Administrator gestartet" in text


def test_cmd_startet_sich_als_admin_neu(registry: Registry) -> None:
    text = erzeuge(registry, Ziel.CMD, [("dienst_neustarten", {"dienst": "Spooler"})]).text
    assert "Benötigte Rechte:  Administrator (Schritt 1)" in text
    assert "net session >nul 2>&1" in text
    assert 'set "OKM_SELBST=%~f0"' in text
    assert "Start-Process -FilePath $env:OKM_SELBST -Verb RunAs" in text


@pytest.mark.parametrize("ziel", [Ziel.BASH, Ziel.ZSH], ids=["bash", "zsh"])
def test_sh_sudo_einmal_und_keepalive(registry: Registry, ziel: Ziel) -> None:
    text = erzeuge(registry, ziel, [MELDUNG, ("dienst_neustarten", {"dienst": "cups"})]).text
    assert "Benötigte Rechte:  sudo (Schritt 2)" in text
    assert "sudo -v" in text and "sudo -n true" in text
    assert "okm_sudo " in text
    assert "\nsudo " not in text, "nie das ganze Script mit sudo neu starten"


def test_nie_root_und_root_gemischt(registry: Registry) -> None:
    text = erzeuge(
        registry,
        Ziel.ZSH,
        [("dienst_neustarten", {"dienst": "org.cups.cupsd"}), ("paket_installieren", {"paket": "firefox"})],
    ).text
    assert "Benötigte Rechte:  sudo (Schritt 1)" in text
    assert "darf nicht als root" in text


# --- Ausführung (bash, als normaler Benutzer mit sudo-Attrappe) ------------------------------


@pytest.fixture
def offen() -> Path:
    """Verzeichnis, das auch „nobody“ lesen kann (tmp_path liegt unter einem 0700-Ordner)."""
    if os.geteuid() != 0 or shutil.which("setpriv") is None:
        pytest.skip("braucht root + setpriv, um als normaler Benutzer zu starten")
    pfad = Path(tempfile.mkdtemp(prefix="okm-rechte-", dir="/tmp"))
    pfad.chmod(0o777)
    yield pfad
    shutil.rmtree(pfad, ignore_errors=True)


def _als_nobody(tmp_path: Path, inhalt: bytes, sudo_v: int, *args: str) -> subprocess.CompletedProcess[str]:
    pfad = tmp_path / "bin"
    pfad.mkdir()
    pfad.chmod(0o755)
    sudo = pfad / "sudo"
    sudo.write_text(
        "#!/bin/sh\n"
        f'case "$1" in -v) exit {sudo_v} ;; -n) exit 0 ;; --) shift ;; esac\n'
        'printf "SUDO:%s\\n" "$*"\n',
        encoding="utf-8",
    )
    sudo.chmod(0o755)
    systemctl = pfad / "systemctl"  # kein systemd im Testcontainer
    systemctl.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    systemctl.chmod(0o755)
    datei = tmp_path / "s.sh"
    datei.write_bytes(inhalt)
    datei.chmod(0o755)
    return subprocess.run(
        ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "bash", str(datei), *args],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=60,
        stdin=subprocess.DEVNULL,
        env={"PATH": f"{pfad}:/usr/bin:/bin", "TMPDIR": str(tmp_path), "HOME": str(tmp_path)},
    )


def test_sudo_erfolgreich(registry: Registry, offen: Path) -> None:
    tmp_path = offen
    s = erzeuge(registry, Ziel.BASH, [MELDUNG, ("dienst_neustarten", {"dienst": "cups"})])
    r = _als_nobody(tmp_path, s.inhalt, 0)
    assert "Schritt 2 (Dienst neu starten)" in r.stdout
    assert "Rechte: sudo erfolgreich" in r.stdout
    assert "SUDO:systemctl restart cups" in r.stdout, r.stdout
    assert " Fertig: 2 von 2 Schritten erfolgreich." in r.stdout
    log = next(tmp_path.glob("okm-script-*.log"))
    assert log.stat().st_uid == 65534, "Protokoll muss dem Benutzer gehören, nicht root"


def test_sudo_abgelehnt(registry: Registry, offen: Path) -> None:
    s = erzeuge(registry, Ziel.BASH, [("dienst_neustarten", {"dienst": "cups"})])
    r = _als_nobody(offen, s.inhalt, 1)
    assert r.returncode == 1
    assert "sudo wurde abgelehnt" in r.stdout
    assert " Abgebrochen: fehlende Rechte." in r.stdout
    assert "SUDO:systemctl" not in r.stdout


def test_als_root_mit_nie_root_block_bricht_ab(registry: Registry, tmp_path: Path) -> None:
    if os.geteuid() != 0:
        pytest.skip("braucht root")
    reg = registry
    # bash kennt kein nie_root – Test über eine zsh-ähnliche Prüfung im bash-Ziel per Testblock
    bloecke = tmp_path / "blocks"
    bloecke.mkdir()
    (bloecke / "b.yaml").write_text(
        KOPF + "rechte:\n  bash: nie_root\nziele:\n  bash: |\n    printf '%s\\n' 'darf laufen'\n",
        encoding="utf-8",
    )
    (tmp_path / "recipes").mkdir()
    reg = lade_registry(bloecke, tmp_path / "recipes")
    datei = tmp_path / "s.sh"
    datei.write_bytes(erzeuge(reg, Ziel.BASH, [("b", {})]).inhalt)
    r = subprocess.run(
        ["bash", str(datei)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60
    )
    assert r.returncode == 1
    assert "darf nicht als root" in r.stdout and "darf laufen" not in r.stdout


# --- Oberfläche -------------------------------------------------------------------------------


@pytest.fixture
def client(registry: Registry, tmp_path: Path) -> TestClient:
    return TestClient(create_app(einst(), registry, Datenbank(f"sqlite:///{tmp_path}/t.db")))


def test_vorschau_badge_und_anleitung(client: TestClient) -> None:
    h = {"HX-Request": "true"}
    r = client.post("/rezepte/druckwarteschlange_neustarten/erzeugen", data={"ziel": "bash"}, headers=h)
    assert "Braucht sudo" in r.text and 'title="Schritt 1' in r.text
    assert "fragt einmal nach deinem Passwort" in r.text
    r = client.post("/rezepte/druckwarteschlange_neustarten/erzeugen", data={"ziel": "powershell"}, headers=h)
    assert "Braucht Admin" in r.text and "Administratorrechte an" in r.text
