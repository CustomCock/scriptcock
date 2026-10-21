"""SQLite-Datenbank (SQLAlchemy). Speichert jedes erzeugte Script mit Hash und IR."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Basis(DeclarativeBase):
    pass


class GespeichertesScript(Basis):
    __tablename__ = "skripte"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, index=True)
    autor: Mapped[str] = mapped_column(String(200), index=True)
    ziel: Mapped[str] = mapped_column(String(20))
    titel: Mapped[str] = mapped_column(String(200))
    beschreibung: Mapped[str] = mapped_column(Text, default="")
    quelle: Mapped[str] = mapped_column(String(100), default="frei")
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    dateiname: Mapped[str] = mapped_column(String(100))
    inhalt: Mapped[bytes] = mapped_column(LargeBinary)
    ir_json: Mapped[str] = mapped_column(Text)
    # Phase 3: Bibliothek
    in_bibliothek: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    tags: Mapped[str] = mapped_column(String(500), default="")
    funktioniert: Mapped[int] = mapped_column(Integer, default=0)


class Datenbank:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite:///"):
            pfad = url.removeprefix("sqlite:///")
            if pfad and pfad != ":memory:":
                Path(pfad).parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(url, connect_args={"check_same_thread": False})
        self._sitzung = sessionmaker(bind=self.engine, expire_on_commit=False)
        Basis.metadata.create_all(self.engine)

    def sitzung(self) -> Iterator[Session]:
        with self._sitzung() as s:
            yield s

    def neue_sitzung(self) -> Session:
        return self._sitzung()
