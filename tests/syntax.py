"""Externe Syntax-Prüfer. Fehlt ein Werkzeug, wird der Test mit Hinweis übersprungen."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

# Ausnahmen, Befehle und CMD-Regeln liegen in app/syntaxpruefung.py – dieselben Checks wie der
# Knopf „Syntax prüfen“ im Editor.
from app.syntaxpruefung import (  # noqa: F401
    PSSA_AUSNAHMEN,
    cmd_lint,
    pwsh_auswerten,
    pwsh_skript,
    shellcheck_befehl,
)


def werkzeug(name: str) -> str:
    pfad = shutil.which(name)
    if pfad is None:
        pytest.skip(f"{name} ist nicht installiert – Syntax-Check übersprungen")
    return pfad


def bash_n(datei: Path) -> None:
    r = subprocess.run([werkzeug("bash"), "-n", str(datei)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def zsh_n(datei: Path) -> None:
    r = subprocess.run([werkzeug("zsh"), "-n", str(datei)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def shellcheck(dateien: list[Path]) -> None:
    r = subprocess.run(shellcheck_befehl(werkzeug("shellcheck"), dateien), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def pwsh_pruefen(dateien: list[Path], analyzer: bool = True) -> None:
    """Parser-Check (+ PSScriptAnalyzer) für alle Dateien in einem pwsh-Aufruf."""
    pwsh = werkzeug("pwsh")
    r = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", pwsh_skript(dateien, analyzer)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    fehler, _ = pwsh_auswerten(r.stdout)
    assert not fehler, "\n".join(f"{f['art']} {f['datei']}:{f['zeile']}: {f['meldung']}" for f in fehler)
