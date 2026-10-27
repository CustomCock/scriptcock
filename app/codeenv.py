"""Jinja-Umgebungen für Code-Templates.

Die Code-Umgebung ist bewusst *nicht* die HTML-Umgebung:

* ``autoescape=False`` – HTML-Escaping wäre für Shell-Code falsch.
* ``finalize`` lässt ausschließlich :class:`~app.escaping.Escaped` durch.
  Jeder andere Wert in ``{{ … }}`` – ein roher String, eine Zahl, das Ergebnis
  eines Filters oder einer Verkettung – führt zu einem Fehler. Ein vergessenes
  Escaping ist damit unmöglich.
* ``StrictUndefined`` – Tippfehler in Platzhaltern fallen sofort auf.
* Sandbox, keine Filter.
* ``trim_blocks`` entfernt den Zeilenumbruch nur nach Zeilen, die *allein* aus einem Block-Tag
  bestehen. Steht vor dem Tag am Zeilenende noch Code (``reg add … {% endif %}``), bleibt der
  Umbruch erhalten – sonst klebte die nächste Zeile daran (siehe :class:`_ZeilenendeBehalten`).
"""

from __future__ import annotations

import re
from typing import Any

from jinja2 import StrictUndefined
from jinja2.ext import Extension
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


# Zeile mit Code vor einem Block-Tag am Zeilenende, z. B. „net use X: /persistent:{% if d %}yes{% endif %}“
_TAG_AM_ZEILENENDE = re.compile(r"^(?P<vorher>[^\n]*\S[^\n]*?\{%(?:(?!%\}).)*?)(?<![+-])%\}$", re.MULTILINE)
_NUR_TAG = re.compile(r"^\s*\{%(?:(?!%\}).)*%\}\s*$")


class _ZeilenendeBehalten(Extension):
    """Setzt ``+%}`` (trim_blocks aus) an Block-Tags, hinter denen nur noch der Zeilenumbruch kommt,
    wenn davor auf derselben Zeile noch etwas anderes steht."""

    def preprocess(self, source: str, name: str | None, filename: str | None = None) -> str:
        def ersetzen(m: re.Match[str]) -> str:
            zeile = m.group(0)
            return zeile if _NUR_TAG.match(zeile) else m.group("vorher") + "+%}"

        return _TAG_AM_ZEILENENDE.sub(ersetzen, source)


def code_umgebung() -> SandboxedEnvironment:
    env = SandboxedEnvironment(
        extensions=[_ZeilenendeBehalten],
        autoescape=False,
        undefined=StrictUndefined,
        finalize=_nur_escaped,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters.clear()
    return env


def text_umgebung() -> SandboxedEnvironment:
    """Für Fortschrittstexte: rendert Klartext, der danach als Ganzes escaped wird."""
    env = SandboxedEnvironment(autoescape=False, undefined=StrictUndefined)
    env.filters.clear()
    return env
