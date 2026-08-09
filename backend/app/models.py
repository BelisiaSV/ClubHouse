import uuid
from datetime import date, datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def uuid_pk():
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )


# =========================================================
# ENUMS
# =========================================================
class UserRole(str, PyEnum):
    ADMIN = "admin"
    HEAD_COACH = "head_coach"
    ASSISTANT_COACH = "assistant_coach"
    PHYSIO = "physio"
    ANALYST = "analyst"
    PLAYER = "player"


class PlayerPosition(str, PyEnum):
    GK = "GK"
    CB = "CB"
    FB = "FB"
    DM = "DM"
    CM = "CM"
    AM = "AM"
    WNG = "WNG"
    ST = "ST"


class MatchStatus(str, PyEnum):
    SCHEDULED = "scheduled"
    PLAYED = "played"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class CycleLength(str, PyEnum):
    FOUR_WEEKS = "4_weeks"
    SIX_WEEKS = "6_weeks"
    EIGHT_WEEKS = "8_weeks"


class WeekFocus(str, PyEnum):
    ACCUMULATION = "accumulation"
    INTENSIFICATION = "intensification"
    REALIZATION = "realization"
    DELOAD = "deload"
    RECOVERY = "recovery"


def _values(enum_cls):
    return [member.value for member in enum_cls]


user_role_enum = PGEnum(UserRole, name="user_role", values_callable=_values)
player_position_enum = PGEnum(PlayerPosition, name="player_position", values_callable=_values)
match_status_enum = PGEnum(MatchStatus, name="match_status", values_callable=_values)
cycle_length_enum = PGEnum(CycleLength, name="cycle_length", values_callable=_values)
week_focus_enum = PGEnum(WeekFocus, name="week_focus", values_callable=_values)


# =========================================================
# CLUBS (tenant root)
# =========================================================
class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text)
    primary_color: Mapped[str | None] = mapped_column(Text)
    secondary_color: Mapped[str | None] = mapped_column(Text)
    competition_level: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    users: Mapped[list["User"]] = relationship(back_populates="club", cascade="all, delete-orphan")
    players: Mapped[list["Player"]] = relationship(back_populates="club", cascade="all, delete-orphan")


# =========================================================
# USERS
# =========================================================
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(user_role_enum, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    club: Mapped["Club"] = relationship(back_populates="users")
    player: Mapped["Player | None"] = relationship(back_populates="user")


# =========================================================
# PASSWORD RESET TOKENS
# =========================================================
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    user: Mapped["User"] = relationship()


# =========================================================
# PASSWORD RESET RATE LIMITING
# =========================================================
class PasswordResetAttempt(Base):
    """One row per /forgot-password call, keyed by the normalized email — regardless
    of whether that email belongs to an account. Tracking by raw email (not user_id)
    keeps the rate limit itself from leaking account existence."""

    __tablename__ = "password_reset_attempts"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


# =========================================================
# PLAYERS
# =========================================================
class Player(Base):
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = uuid_pk()
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    phone_number: Mapped[str | None] = mapped_column(Text)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    position: Mapped[PlayerPosition | None] = mapped_column(player_position_enum)
    dominant_foot: Mapped[str | None] = mapped_column(Text)
    jersey_number: Mapped[int | None] = mapped_column(Integer)
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("dominant_foot in ('left','right','both')", name="players_dominant_foot_check"),
    )

    club: Mapped["Club"] = relationship(back_populates="players")
    user: Mapped["User | None"] = relationship(back_populates="player")
    mas_tests: Mapped[list["MasTest"]] = relationship(back_populates="player", cascade="all, delete-orphan")
    match_minutes: Mapped[list["MatchMinutes"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    rpe_wellness_entries: Mapped[list["RpeWellnessData"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )


# =========================================================
# MAS TESTS
# =========================================================
class MasTest(Base):
    __tablename__ = "mas_tests"

    id: Mapped[uuid.UUID] = uuid_pk()
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    test_date: Mapped[date] = mapped_column(Date, nullable=False)
    protocol: Mapped[str] = mapped_column(Text, nullable=False, server_default="30-15 IFT")
    mas_kmh: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    vo2max_estimate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    hr_max_bpm: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    player: Mapped["Player"] = relationship(back_populates="mas_tests")


# =========================================================
# MATCHES
# =========================================================
class Match(Base):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = uuid_pk()
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    opponent: Mapped[str] = mapped_column(Text, nullable=False)
    match_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)
    competition: Mapped[str | None] = mapped_column(Text)
    status: Mapped[MatchStatus] = mapped_column(
        match_status_enum, nullable=False, server_default=MatchStatus.SCHEDULED.value
    )
    postponed_reason: Mapped[str | None] = mapped_column(Text)
    rescheduled_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("matches.id"))
    final_score_for: Mapped[int | None] = mapped_column(Integer)
    final_score_against: Mapped[int | None] = mapped_column(Integer)
    video_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    match_minutes: Mapped[list["MatchMinutes"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )


# =========================================================
# MATCH MINUTES (junction: match <-> player <-> load)
# =========================================================
class MatchMinutes(Base):
    __tablename__ = "match_minutes"

    id: Mapped[uuid.UUID] = uuid_pk()
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    minutes_played: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # UI-facing quick status behind the minutes dropdown on the MAS compensation panel;
    # minutes_played is always the source of truth for compensation math.
    selection_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="basis")
    started_match: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    substituted_in_min: Mapped[int | None] = mapped_column(Integer)
    substituted_out_min: Mapped[int | None] = mapped_column(Integer)
    position_played: Mapped[PlayerPosition | None] = mapped_column(player_position_enum)
    distance_total_m: Mapped[float | None] = mapped_column(Numeric(7, 2))
    distance_hsr_m: Mapped[float | None] = mapped_column(Numeric(7, 2))
    sprints_count: Mapped[int | None] = mapped_column(Integer)
    top_speed_kmh: Mapped[float | None] = mapped_column(Numeric(4, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("match_id", "player_id", name="match_minutes_match_id_player_id_key"),
        CheckConstraint(
            "selection_status in ('basis','bank','niet_geselecteerd')",
            name="match_minutes_selection_status_check",
        ),
    )

    match: Mapped["Match"] = relationship(back_populates="match_minutes")
    player: Mapped["Player"] = relationship(back_populates="match_minutes")


# =========================================================
# RPE / WELLNESS DATA
# =========================================================
class RpeWellnessData(Base):
    __tablename__ = "rpe_wellness_data"

    id: Mapped[uuid.UUID] = uuid_pk()
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    session_type: Mapped[str | None] = mapped_column(Text)
    rpe_score: Mapped[int | None] = mapped_column(Integer)
    session_duration_min: Mapped[int | None] = mapped_column(Integer)
    # Foster's sRPE: generated column, computed by Postgres.
    session_load: Mapped[int | None] = mapped_column(
        Integer, Computed("rpe_score * session_duration_min", persisted=True)
    )
    sleep_quality: Mapped[int | None] = mapped_column(Integer)
    fatigue_level: Mapped[int | None] = mapped_column(Integer)
    muscle_soreness: Mapped[int | None] = mapped_column(Integer)
    stress_level: Mapped[int | None] = mapped_column(Integer)
    mood: Mapped[int | None] = mapped_column(Integer)
    injury_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    injury_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("rpe_score between 1 and 10", name="rpe_wellness_data_rpe_score_check"),
        CheckConstraint("sleep_quality between 1 and 5", name="rpe_wellness_data_sleep_quality_check"),
        CheckConstraint("fatigue_level between 1 and 5", name="rpe_wellness_data_fatigue_level_check"),
        CheckConstraint("muscle_soreness between 1 and 5", name="rpe_wellness_data_muscle_soreness_check"),
        CheckConstraint("stress_level between 1 and 5", name="rpe_wellness_data_stress_level_check"),
        CheckConstraint("mood between 1 and 5", name="rpe_wellness_data_mood_check"),
        UniqueConstraint(
            "player_id", "entry_date", "session_type", name="rpe_wellness_data_player_id_entry_date_session_type_key"
        ),
    )

    player: Mapped["Player"] = relationship(back_populates="rpe_wellness_entries")


# =========================================================
# TRAINING CYCLES (periodization)
# =========================================================
class TrainingCycle(Base):
    __tablename__ = "training_cycles"

    id: Mapped[uuid.UUID] = uuid_pk()
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    length_type: Mapped[CycleLength] = mapped_column(cycle_length_enum, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_match_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("matches.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    shift_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    weeks: Mapped[list["TrainingCycleWeek"]] = relationship(
        back_populates="training_cycle", cascade="all, delete-orphan"
    )


class TrainingCycleWeek(Base):
    __tablename__ = "training_cycle_weeks"

    id: Mapped[uuid.UUID] = uuid_pk()
    training_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("training_cycles.id", ondelete="CASCADE"), nullable=False
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    focus: Mapped[WeekFocus] = mapped_column(week_focus_enum, nullable=False)
    planned_load_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "training_cycle_id", "week_number", name="training_cycle_weeks_training_cycle_id_week_number_key"
        ),
    )

    training_cycle: Mapped["TrainingCycle"] = relationship(back_populates="weeks")
