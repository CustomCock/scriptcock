"""SQLite-Datenbank (SQLAlchemy). Speichert jedes erzeugte Script mit Hash und IR."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


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
    # Editor: im Browser geänderter Text (ohne Kopf-Markierung) – None = unverändert generiert
    editor_text: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    manuell_bearbeitet: Mapped[bool] = mapped_column(Boolean, default=False)


class GespeichertesRezept(Basis):
    """Rezepte, die im Baukasten erstellt wurden (zusätzlich zu ``recipes/*.yaml``)."""

    __tablename__ = "rezepte"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rezept_id: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    daten_json: Mapped[str] = mapped_column(Text)
    autor: Mapped[str] = mapped_column(String(200))
    erstellt_am: Mapped[datetime] = mapped_column(DateTime)
    freigegeben: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class Bewertung(Basis):
    """„Hat funktioniert ✓“ – höchstens eine Stimme pro Benutzer und Script."""

    __tablename__ = "bewertungen"
    __table_args__ = (UniqueConstraint("skript_id", "benutzer", name="eine_stimme_pro_benutzer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skript_id: Mapped[int] = mapped_column(ForeignKey("skripte.id", ondelete="CASCADE"), index=True)
    benutzer: Mapped[str] = mapped_column(String(200))
    erstellt_am: Mapped[datetime] = mapped_column(DateTime)


class Datenbank:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite:///"):
            pfad = url.removeprefix("sqlite:///")
            if pfad and pfad != ":memory:":
                Path(pfad).parent.mkdir(parents=True, exist_ok=True)
        im_speicher = url in ("sqlite://", "sqlite:///:memory:")
        self.engine: Engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            # In-Memory-SQLite: alle Sitzungen müssen dieselbe Verbindung nutzen.
            poolclass=StaticPool if im_speicher else None,
        )
        self._sitzung = sessionmaker(bind=self.engine, expire_on_commit=False)
        Basis.metadata.create_all(self.engine)
        self._migrieren()

    # Spalten, die nach dem ersten Release dazukamen: (Tabelle, Spalte, SQL-Definition)
    NACHTRAEGLICHE_SPALTEN = (
        ("skripte", "editor_text", "TEXT"),
        ("skripte", "manuell_bearbeitet", "BOOLEAN NOT NULL DEFAULT 0"),
    )

    def _migrieren(self) -> None:
        """Mini-Migration für bestehende Datenbanken: fehlende Spalten per ALTER TABLE ergänzen."""
        vorhanden = {
            (tabelle, s["name"])
            for tabelle in {t for t, _, _ in self.NACHTRAEGLICHE_SPALTEN}
            for s in inspect(self.engine).get_columns(tabelle)
        }
        with self.engine.begin() as con:
            for tabelle, spalte, definition in self.NACHTRAEGLICHE_SPALTEN:
                if (tabelle, spalte) not in vorhanden:
                    con.execute(text(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {definition}"))

    def sitzung(self) -> Iterator[Session]:
        with self._sitzung() as s:
            yield s

    def neue_sitzung(self) -> Session:
        return self._sitzung()
