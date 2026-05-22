"""pytest fixtures and configuration.

Uses a separate test database to avoid touching production data.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine

# Override database engine BEFORE any backend module imports
import backend.db.database as db_module
_test_engine = create_engine(
    "sqlite:///./test_medbot.db", connect_args={"check_same_thread": False}
)
db_module.engine = _test_engine


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    # Ensure models are imported so SQLModel.metadata is populated
    from backend.db import models  # noqa: F401
    SQLModel.metadata.create_all(_test_engine)
    yield
    SQLModel.metadata.drop_all(_test_engine)


@pytest.fixture
def client():
    from backend.main import app

    return TestClient(app)
