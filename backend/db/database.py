from sqlmodel import SQLModel, create_engine, Session as DBSession
from backend.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session() -> DBSession:
    return DBSession(engine)
