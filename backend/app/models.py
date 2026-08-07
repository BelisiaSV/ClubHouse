from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Maximal Aerobic Speed, in meters/second. Drives HIT training prescriptions.
    mas_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    matches: Mapped[list["Match"]] = relationship(back_populates="player", cascade="all, delete-orphan")
    rpe_entries: Mapped[list["RPE"]] = relationship(back_populates="player", cascade="all, delete-orphan")
    cycles: Mapped[list["Cycle"]] = relationship(back_populates="player", cascade="all, delete-orphan")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    match_date: Mapped[date] = mapped_column(Date, nullable=False)
    minutes_played: Mapped[int] = mapped_column(Integer, nullable=False)
    opponent: Mapped[str | None] = mapped_column(String(120), nullable=True)
    competition: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship(back_populates="matches")


class RPE(Base):
    """Session-RPE wellness/load entry. load = rpe_value * duration_minutes (session-RPE method)."""

    __tablename__ = "rpe_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    rpe_value: Mapped[int] = mapped_column(Integer, nullable=False)  # Borg CR-10, 0-10
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship(back_populates="rpe_entries")

    @property
    def load(self) -> int:
        return self.rpe_value * self.duration_minutes


class Cycle(Base):
    """Training periodization cycle (e.g. macro/meso/microcycle)."""

    __tablename__ = "cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phase: Mapped[str | None] = mapped_column(String(60), nullable=True)  # e.g. preseason, in-season, taper
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player | None"] = relationship(back_populates="cycles")
