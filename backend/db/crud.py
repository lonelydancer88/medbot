import json
from datetime import datetime, timezone
from sqlmodel import select
from backend.db.database import get_session
from backend.db.models import Session as SessionModel, Message, Diagnosis
from backend.langgraph.state import ConsultationState


def create_session_in_db() -> SessionModel:
    with get_session() as db:
        s = SessionModel()
        db.add(s)
        db.commit()
        db.refresh(s)
        return s


def get_session_from_db(session_id: str) -> SessionModel | None:
    with get_session() as db:
        return db.get(SessionModel, session_id)


def list_sessions_db(skip: int = 0, limit: int = 20) -> list[SessionModel]:
    with get_session() as db:
        stmt = select(SessionModel).order_by(SessionModel.updated_at.desc()).offset(skip).limit(limit)
        return list(db.exec(stmt).all())


def save_state(state: ConsultationState):
    with get_session() as db:
        s = db.get(SessionModel, state["session_id"])
        if not s:
            return
        s.state_json = json.dumps(state, default=str, ensure_ascii=False)
        s.phase = state["phase"]
        s.updated_at = datetime.now(timezone.utc)
        s.status = "completed" if state["phase"] == "complete" else "active"
        db.commit()


def add_message_to_db(session_id: str, role: str, content: str):
    with get_session() as db:
        msg = Message(session_id=session_id, role=role, content=content)
        db.add(msg)
        db.commit()


def get_messages_from_db(session_id: str) -> list[Message]:
    with get_session() as db:
        stmt = select(Message).where(Message.session_id == session_id).order_by(Message.id)
        return list(db.exec(stmt).all())


def save_diagnoses(session_id: str, diagnoses: list[dict]):
    with get_session() as db:
        for d in diagnoses:
            obj = Diagnosis(
                session_id=session_id,
                disease=d.get("disease", ""),
                probability=d.get("probability", ""),
                reason=d.get("reason", ""),
            )
            db.add(obj)
        db.commit()


def get_diagnoses_from_db(session_id: str) -> list[Diagnosis]:
    with get_session() as db:
        stmt = select(Diagnosis).where(Diagnosis.session_id == session_id)
        return list(db.exec(stmt).all())
