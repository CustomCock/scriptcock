"""Ein Generator pro Zielsystem."""

from __future__ import annotations

from app.escaping import Ziel
from app.generators.base import GeneratedScript, Generator, GenerierungsFehler
from app.generators.bash import BashGenerator, ZshGenerator
from app.generators.cmd import CmdGenerator
from app.generators.powershell import PowerShellGenerator
from app.registry import Registry

GENERATOREN: dict[Ziel, type[Generator]] = {
    Ziel.POWERSHELL: PowerShellGenerator,
    Ziel.CMD: CmdGenerator,
    Ziel.BASH: BashGenerator,
    Ziel.ZSH: ZshGenerator,
}


def generator_fuer(ziel: Ziel, registry: Registry) -> Generator:
    return GENERATOREN[ziel](registry)


__all__ = ["GENERATOREN", "GeneratedScript", "Generator", "GenerierungsFehler", "generator_fuer"]
