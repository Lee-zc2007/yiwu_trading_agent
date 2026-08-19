import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_DATABASE = PROJECT_ROOT / "tradeguard_test.db"
if TEST_DATABASE.exists():
    TEST_DATABASE.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"
os.environ["AGENT_MODE"] = "deterministic"

from backend.app.core.database import engine  # noqa: E402
from backend.app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
    if TEST_DATABASE.exists():
        TEST_DATABASE.unlink()
