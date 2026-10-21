"""Jinja-Umgebungen für Code-Templates.

Die Code-Umgebung ist bewusst *nicht* die HTML-Umgebung:

* ``autoescape=False`` – HTML-Escaping wäre für Shell-Code falsch.
* ``finalize`` lässt ausschließlich :class:`~app.escaping.Escaped` durch.
  Jeder andere Wert in ``{{ … }}`` – ein roher String, eine Zahl, das Ergebnis
  eines Filters oder einer Verkettung – führt zu einem Fehler. Ein vergessenes
  Escaping ist damit unmöglich.
* ``StrictUndefined`` – Tippfehler in Platzhaltern fallen sofort auf.
* Sandbox, keine Filter.
"""

from __future__ import annotations

from typing import Any

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from app.escaping import Escaped


class RohwertError(TypeError):
    """Ein Code-Template wollte einen nicht escapten Wert ausgeben."""


def _nur_escaped(wert: Any) -> Escaped:
    if isinstance(wert, Escaped):
        return wert
    raise RohwertError(
        f"Code-Templates dürfen nur escapte Parameter ausgeben, nicht {type(wert).__name__} "
        "(keine Filter, Verkettungen oder Konstanten in {{ … }})."
    )


def code_umgebung() -> SandboxedEnvironment:
    env = SandboxedEnvironment(
        autoescape=False,
        undefined=StrictUndefined,
        finalize=_nur_escaped,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
    )
    env.filters.clear()
    return env


def text_umgebung() -> SandboxedEnvironment:
    """Für Fortschrittstexte: rendert Klartext, der danach als Ganzes escaped wird."""
    env = SandboxedEnvironment(autoescape=False, undefined=StrictUndefined)
    env.filters.clear()
    return env
