"""Dev convenience: seed a demo player with match + RPE history so the
compensation and wellness endpoints have data to work against.

Usage: python seed.py
"""
from datetime import date, timedelta

from app.database import Base, SessionLocal, engine
from app.models import RPE, Match, Player

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    player = db.query(Player).filter_by(name="Demo Player").first()
    if player is None:
        player = Player(name="Demo Player", position="Midfielder", mas_score=5.2)
        db.add(player)
        db.commit()
        db.refresh(player)

    db.add(Match(player_id=player.id, match_date=date.today() - timedelta(days=3), minutes_played=35, opponent="Rival FC", competition="League"))

    today = date.today()
    for i in range(28):
        db.add(
            RPE(
                player_id=player.id,
                entry_date=today - timedelta(days=i),
                rpe_value=6 if i % 3 else 8,
                duration_minutes=60,
            )
        )
    db.commit()
    print(f"Seeded player id={player.id}")
finally:
    db.close()
