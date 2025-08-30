from datetime import datetime, timezone
from sqlmodel import SQLModel, Field


class Note(SQLModel, table=True):
    __tablename__ = "notes"

    id: int = Field(default=None, primary_key=True)
    note: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
