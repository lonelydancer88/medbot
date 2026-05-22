import uuid
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Column, Text


class Session(SQLModel, table=True):
    __tablename__ = "session"
    id: str = Field(primary_key=True, default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field(default="active")
    state_json: str = Field(default="{}")
    phase: str = Field(default="collecting")


class Message(SQLModel, table=True):
    __tablename__ = "message"
    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="session.id")
    role: str = Field(max_length=16)
    content: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Diagnosis(SQLModel, table=True):
    __tablename__ = "diagnosis"
    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="session.id")
    disease: str = Field(max_length=255)
    probability: str = Field(max_length=16)
    reason: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
