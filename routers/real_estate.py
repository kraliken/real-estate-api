from fastapi import APIRouter
from sqlmodel import func, select

from database.connection import SessionDep
from database.models import Note
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

router = APIRouter(prefix="/real-estate", tags=["real-estate"])
TZ = ZoneInfo("Europe/Budapest")


@router.post("/create")
async def save_real_estate(session: SessionDep):

    count = session.exec(select(func.count()).select_from(Note)).one()
    note_text = f"note from server {count + 1}"

    note = Note(note=note_text, created_at=datetime.now(timezone.utc))

    session.add(note)
    session.commit()
    session.refresh(note)
    return {
        **note.dict(),
        "created_at_utc": note.created_at.isoformat().replace("+00:00", "Z"),
        "created_at_local": note.created_at.astimezone(TZ).isoformat(),
    }


@router.get("/all")
async def save_real_estate(session: SessionDep):

    statement = select(Note)
    notes = session.exec(statement).all()

    return notes
