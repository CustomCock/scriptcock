"""Backlog P1, Paket 2: Registry- und Netzwerk-Bausteine.

http_check, ports_pruefen und wake_on_lan laufen echt gegen localhost (HTTP-Server, offener/geschlossener
Port, UDP-Empfänger) – in bash, zsh und pwsh. dns_abfrage mit dig-Attrappe. Die Registry-Bausteine stehen in tests/test_windows_registry.py.
"""

from __future__ import annotations

import http.server
import os
import re
import shutil
import socket
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.escaping import Ziel
from app.generators import generator_fuer
from app.registry import Registry
from tests.conftest import erzeuge
from tests.test_ausfuehrung import SH_ZIELE, ausfuehren
from tests.test_rueckgabe import ZEIGEN_ECHT, ir_aus, mit_bloecken

ALLE = [*SH_ZIELE, ("pwsh", Ziel.POWERSHELL)]


@pytest.fixture(scope="module")
def reg() -> Registry:
    return mit_bloecken(ZEIGEN_ECHT)


def werte(
    reg: Registry,
    tmp_path: Path,
    shell: str,
    ziel: Ziel,
    schritt: dict[str, Any],
    zahl: str | None = None,
    ok: str | None = None,
    attrappen: dict[str, str] | None = None,
) -> tuple[str, str, Any]:
    """Führt ``schritt`` + Test-Block „Wert zeigen“ aus → (Zahl, ja/nein, Ergebnis)."""
    pfad = tmp_path / "bin"
    pfad.mkdir(parents=True, exist_ok=True)
    for name, inhalt in (attrappen or {}).items():
        (pfad / name).write_text("#!/bin/sh\n" + inhalt + "\n", encoding="utf-8")
        (pfad / name).chmod(0o755)
    zeigen = {"block_id": "test_wert", "parameter": {k: v for k, v in (("zahl", zahl), ("ok", ok)) if v}}
    s = generator_fuer(ziel, reg).erzeuge(ir_aus(reg, ziel, [schritt, zeigen]))
    env = {"PATH": f"{pfad}:{os.environ['PATH']}"}
    if shell == "pwsh":
        env["TEMP"] = str(tmp_path)
    r = ausfuehren(shell, s.inhalt, tmp_path, env=env)
    m = re.search(r"OKM-ZAHL=(\S*) OKM-OK=(\S*)", r.stdout)
    return (m.group(1), m.group(2), r) if m else ("?", "?", r)


def ja(ziel: Ziel) -> str:
    return "True" if ziel is Ziel.POWERSHELL else "1"


def nein(ziel: Ziel) -> str:
    return "False" if ziel is Ziel.POWERSHELL else "0"


def freier_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --- http_check ----------------------------------------------------------------------------------


class _Antwort(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200 if self.path == "/" else 404)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture(scope="module")
def webserver() -> Iterator[str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Antwort)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.mark.parametrize(("shell", "ziel"), ALLE)
def test_http_check(reg: Registry, tmp_path: Path, webserver: str, shell: str, ziel: Ziel) -> None:
    if shell != "pwsh" and shutil.which("curl") is None:
        pytest.skip("curl fehlt")
    schritt = {"block_id": "http_check", "parameter": {"url": webserver + "/"}}
    status, ok, r = werte(reg, tmp_path / "a", shell, ziel, schritt, "1.status", "1.erreichbar")
    assert (status, ok) == ("200", ja(ziel)), r.stdout
    assert re.search(r"HTTP-Status: 200, Antwortzeit: \d+ ms", r.stdout)
    schritt = {"block_id": "http_check", "parameter": {"url": webserver + "/fehlt"}}
    status, ok, r = werte(reg, tmp_path / "b", shell, ziel, schritt, "1.status", "1.erreichbar")
    assert (status, ok) == ("404", nein(ziel)), r.stdout
    # keine Verbindung: Status unbekannt; mit „abbrechen“ endet das Script mit Fehler
    url = f"http://127.0.0.1:{freier_port()}/"
    schritt = {"block_id": "http_check", "parameter": {"url": url, "zeitlimit": 3}}
    status, ok, r = werte(reg, tmp_path / "c", shell, ziel, schritt, "1.status", "1.erreichbar")
    assert (status, ok) == ("", nein(ziel)), r.stdout
    schritt["parameter"]["abbrechen"] = True
    _, _, r = werte(reg, tmp_path / "d", shell, ziel, schritt, "1.status", "1.erreichbar")
    assert r.returncode != 0 and "OKM-ZAHL" not in r.stdout


# --- ports_pruefen --------------------------------------------------------------------------------

# zsh-Variante nutzt „nc -z -G 3“ (macOS); unter Linux als Attrappe über /dev/tcp nachgebaut
NC = 'for a; do h=$p; p=$a; done\nexec timeout 3 bash -c \'exec 3<>"/dev/tcp/$1/$2"\' x "$h" "$p" 2>/dev/null'


@pytest.mark.parametrize(("shell", "ziel"), ALLE)
def test_ports_pruefen(reg: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    auf = socket.socket()
    auf.bind(("127.0.0.1", 0))
    auf.listen(10)
    try:
        offen, zu = auf.getsockname()[1], freier_port()
        schritt = {"block_id": "ports_pruefen", "parameter": {"ziel": "127.0.0.1", "ports": f"{offen}, {zu}"}}
        attrappen = {"nc": NC} if ziel is Ziel.ZSH else None
        anzahl, alle, r = werte(
            reg, tmp_path / "a", shell, ziel, schritt, "1.offen", "1.alle_offen", attrappen
        )
        assert (anzahl, alle) == ("1", nein(ziel)), r.stdout
        assert f"Port {offen}: offen" in r.stdout and f"Port {zu}: ZU" in r.stdout
        schritt = {"block_id": "ports_pruefen", "parameter": {"ziel": "127.0.0.1", "ports": str(offen)}}
        anzahl, alle, r = werte(
            reg, tmp_path / "b", shell, ziel, schritt, "1.offen", "1.alle_offen", attrappen
        )
        assert (anzahl, alle) == ("1", ja(ziel)), r.stdout
        schritt = {
            "block_id": "ports_pruefen",
            "parameter": {"ziel": "127.0.0.1", "ports": f"{offen} {zu}", "abbrechen": True},
        }
        _, _, r = werte(reg, tmp_path / "c", shell, ziel, schritt, "1.offen", "1.alle_offen", attrappen)
        assert r.returncode != 0 and "Mindestens ein Port ist zu" in r.stdout
    finally:
        auf.close()


# --- wake_on_lan --------------------------------------------------------------------------------


@pytest.mark.parametrize(("shell", "ziel"), ALLE)
def test_wake_on_lan(registry: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    if shell != "pwsh" and shutil.which("python3") is None:
        pytest.skip("python3 fehlt")
    empfang = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    empfang.bind(("127.0.0.1", 0))
    empfang.settimeout(10)
    try:
        port = empfang.getsockname()[1]
        s = erzeuge(
            registry,
            ziel,
            [("wake_on_lan", {"mac": "00-1a-2b-3c-4d-5e", "broadcast": "127.0.0.1", "port": port})],
        )
        r = ausfuehren(shell, s.inhalt, tmp_path, env={"TEMP": str(tmp_path)} if shell == "pwsh" else None)
        assert r.returncode == 0, r.stdout + r.stderr
        paket, _ = empfang.recvfrom(200)
        assert paket == b"\xff" * 6 + bytes.fromhex("001a2b3c4d5e") * 16
        assert "Magic Packet gesendet" in r.stdout
    finally:
        empfang.close()


# --- dns_abfrage ---------------------------------------------------------------------------------


@pytest.mark.parametrize(("shell", "ziel"), SH_ZIELE)
def test_dns_abfrage(reg: Registry, tmp_path: Path, shell: str, ziel: Ziel) -> None:
    aufrufe = tmp_path / "dig.txt"
    dig = f"printf '%s\\n' \"$*\" >> '{aufrufe}'\ncase \"$*\" in *MX*) echo '10 mail.example.de.' ;; esac"
    schritt = {
        "block_id": "dns_abfrage",
        "parameter": {"name": "Example.DE", "typ": "MX", "server": "1.1.1.1"},
    }
    _, gefunden, r = werte(reg, tmp_path / "a", shell, ziel, schritt, ok="1.gefunden", attrappen={"dig": dig})
    assert gefunden == "1", r.stdout
    assert "10 mail.example.de." in r.stdout
    assert aufrufe.read_text() == "+short -t MX example.de @1.1.1.1\n"
    schritt = {"block_id": "dns_abfrage", "parameter": {"name": "_ldap._tcp.okm.local", "typ": "SRV"}}
    _, gefunden, r = werte(reg, tmp_path / "b", shell, ziel, schritt, ok="1.gefunden", attrappen={"dig": dig})
    assert gefunden == "0" and "Kein Eintrag gefunden" in r.stdout
