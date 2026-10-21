from __future__ import annotations

import pytest

from app.auth import KeinZugriff, benutzer_aus_claims
from app.config import Einstellungen


def einst(**kw) -> Einstellungen:
    return Einstellungen(
        **{"OIDC_ERLAUBTE_GRUPPE": "baukasten", "OIDC_ADMIN_GRUPPE": "baukasten-admin", **kw}
    )


def test_nutzer() -> None:
    b = benutzer_aus_claims(
        {"preferred_username": "max", "name": "Max M.", "groups": ["/baukasten"]}, einst()
    )
    assert b.name == "max" and b.anzeige == "Max M." and not b.ist_admin


def test_admin_gruppe_reicht() -> None:
    b = benutzer_aus_claims({"preferred_username": "it", "groups": ["baukasten-admin"]}, einst())
    assert b.ist_admin


def test_fremde_gruppe_abgelehnt() -> None:
    with pytest.raises(KeinZugriff):
        benutzer_aus_claims({"preferred_username": "x", "groups": ["/andere"]}, einst())
    with pytest.raises(KeinZugriff):
        benutzer_aus_claims({"preferred_username": "x"}, einst())


def test_ohne_gruppenbeschraenkung() -> None:
    b = benutzer_aus_claims({"sub": "123"}, einst(OIDC_ERLAUBTE_GRUPPE="", OIDC_ADMIN_GRUPPE=""))
    assert b.name == "123" and not b.ist_admin
