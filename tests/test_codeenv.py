"""Die Code-Template-Umgebung darf ausschließlich escapte Werte ausgeben."""

from __future__ import annotations

import pytest

from app.codeenv import RohwertError, code_umgebung
from app.escaping import Escaped, sh_literal


@pytest.mark.parametrize(
    "quelle",
    [
        "{{ 'konstante' }}",
        "{{ 42 }}",
        "{{ x ~ 'a' }}",
        "{{ x.wert }}",
        "{{ x[1:] }}",
        "{{ x + x }}",
        "{{ roh }}",
        "{{ x.replace('a', 'b') }}",
    ],
)
def test_nur_escapte_ausgabe(quelle: str) -> None:
    env = code_umgebung()
    with pytest.raises(Exception) as e:
        env.from_string(quelle).render(x=sh_literal("a'b"), roh="$(id)")
    assert isinstance(e.value, RohwertError | TypeError) or "unsafe" in str(e.value).lower()


def test_escapter_wert_und_bedingung() -> None:
    env = code_umgebung()
    x = sh_literal("apt")
    assert env.from_string("{% if x.wert == 'apt' %}ok {{ x }}{% endif %}").render(x=x) == "ok 'apt'"


def test_keine_filter() -> None:
    env = code_umgebung()
    with pytest.raises(Exception):
        env.from_string("{{ x | safe }}").render(x=Escaped("a"))


def test_undefinierte_variable() -> None:
    with pytest.raises(Exception):
        code_umgebung().from_string("{{ fehlt }}").render()
