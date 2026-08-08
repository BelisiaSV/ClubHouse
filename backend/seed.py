"""Dev convenience: seed a demo club + player + MAS test so /mas/compensation
has data to work against.

Usage: python seed.py
"""
from datetime import date, timedelta

from app.database import SessionLocal
from app.models import Club, MasTest, Player, PlayerPosition

db = SessionLocal()
try:
    club = db.query(Club).filter_by(slug="demo-fc").first()
    if club is None:
        club = Club(name="Demo FC", slug="demo-fc", competition_level="1e Provinciale")
        db.add(club)
        db.commit()
        db.refresh(club)

    player = db.query(Player).filter_by(club_id=club.id, first_name="J.", last_name="Peeters").first()
    if player is None:
        player = Player(
            club_id=club.id,
            first_name="J.",
            last_name="Peeters",
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
    print(f"Seeded player id={player.id} (club={club.slug})")
finally:
    db.close()
