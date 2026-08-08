"""Dev convenience: seed a demo club + coach login + player + MAS test so the
app has data to work against.

Usage: python seed.py
"""
from datetime import date, timedelta

from app.core.security import hash_password
from app.database import SessionLocal
from app.models import Club, MasTest, Player, PlayerPosition, User, UserRole

DEMO_COACH_EMAIL = "coach@demo-fc.be"
DEMO_COACH_PASSWORD = "changeme123"

db = SessionLocal()
try:
    club = db.query(Club).filter_by(slug="demo-fc").first()
    if club is None:
        club = Club(name="Demo FC", slug="demo-fc", competition_level="1e Provinciale")
        db.add(club)
        db.commit()
        db.refresh(club)

    coach = db.query(User).filter_by(email=DEMO_COACH_EMAIL).first()
    if coach is None:
        coach = User(
            club_id=club.id,
            email=DEMO_COACH_EMAIL,
            hashed_password=hash_password(DEMO_COACH_PASSWORD),
            full_name="Demo Coach",
            role=UserRole.HEAD_COACH,
        )
        db.add(coach)
        db.commit()
        db.refresh(coach)

    player = db.query(Player).filter_by(club_id=club.id, first_name="J.", last_name="Peeters").first()
    if player is None:
        player = Player(
            club_id=club.id,
            first_name="J.",
            last_name="Peeters",
            email="j.peeters@example.be",
            phone_number="0470 12 34 56",
            date_of_birth=date(2001, 3, 14),
            position=PlayerPosition.CM,
            dominant_foot="right",
            jersey_number=8,
        )
        db.add(player)
        db.commit()
        db.refresh(player)

    db.add(
        MasTest(
            player_id=player.id,
            club_id=club.id,
            test_date=date.today() - timedelta(days=14),
            protocol="30-15 IFT",
            mas_kmh=16.5,
        )
    )
    db.commit()
    print(f"Seeded club={club.slug} coach_login=({DEMO_COACH_EMAIL} / {DEMO_COACH_PASSWORD}) player_id={player.id}")
finally:
    db.close()
