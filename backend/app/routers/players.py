import io
import uuid

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl.styles import Font
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Player, User
from app.schemas import PlayerCreate, PlayerImportError, PlayerImportResult, PlayerOut, PlayerUpdate

router = APIRouter(prefix="/api/players", tags=["players"])

TEMPLATE_HEADERS = ["Rugnummer", "Naam", "Voornaam", "E-mailadres", "Telefoonnummer"]


@router.get("/import-template")
def download_import_template(current_user: User = Depends(get_current_user)):
    """Downloadable .xlsx template coaches fill in and re-upload via POST /players/import."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Spelers"
    ws.append(TEMPLATE_HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.append([7, "Peeters", "Jan", "jan.peeters@example.be", "0470 12 34 56"])
    for cell in ws[2]:
        cell.font = Font(italic=True, color="999999")
    for col, width in zip("ABCDE", [12, 20, 20, 30, 20]):
        ws.column_dimensions[col].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="spelers_import_sjabloon.xlsx"'},
    )


@router.post("/import", response_model=PlayerImportResult)
def import_players(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Upload een .xlsx-bestand (gebruik het downloadbare sjabloon)")

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file.file.read()), data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Kon het Excel-bestand niet lezen") from exc

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(status_code=400, detail="Bestand is leeg")

    created = 0
    skipped = 0
    errors: list[PlayerImportError] = []

    for row_number, row in enumerate(rows[1:], start=2):  # skip header row
        if row is None or all(cell in (None, "") for cell in row):
            continue  # silently skip fully blank rows

        cells = list(row) + [None] * (5 - len(row))
        rugnummer, naam, voornaam, email, telefoonnummer = cells[:5]

        if not naam or not voornaam:
            skipped += 1
            errors.append(PlayerImportError(row=row_number, message="Naam en voornaam zijn verplicht"))
            continue

        jersey_number = None
        if rugnummer not in (None, ""):
            try:
                jersey_number = int(rugnummer)
            except (TypeError, ValueError):
                skipped += 1
                errors.append(PlayerImportError(row=row_number, message=f"Ongeldig rugnummer: {rugnummer!r}"))
                continue

        player = Player(
            club_id=current_user.club_id,
            first_name=str(voornaam).strip(),
            last_name=str(naam).strip(),
            email=str(email).strip() if email not in (None, "") else None,
            phone_number=str(telefoonnummer).strip() if telefoonnummer not in (None, "") else None,
            jersey_number=jersey_number,
        )
        db.add(player)
        created += 1

    db.commit()
    return PlayerImportResult(created=created, skipped=skipped, errors=errors)


@router.post("", response_model=PlayerOut, status_code=201)
def create_player(
    payload: PlayerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    player = Player(club_id=current_user.club_id, **payload.model_dump())
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@router.get("", response_model=list[PlayerOut])
def list_players(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Player).where(Player.club_id == current_user.club_id).order_by(Player.jersey_number.nulls_last())
    ).all()


@router.get("/{player_id}", response_model=PlayerOut)
def get_player(player_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    player = db.get(Player, player_id)
    if player is None or player.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@router.patch("/{player_id}", response_model=PlayerOut)
def update_player(
    player_id: uuid.UUID,
    payload: PlayerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    player = db.get(Player, player_id)
    if player is None or player.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Player not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(player, field, value)
    db.commit()
    db.refresh(player)
    return player


@router.delete("/{player_id}", status_code=204)
def delete_player(
    player_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    player = db.get(Player, player_id)
    if player is None or player.club_id != current_user.club_id:
        raise HTTPException(status_code=404, detail="Player not found")
    db.delete(player)
    db.commit()
