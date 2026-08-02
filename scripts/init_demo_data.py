from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.data.seed import reset_demo_data  # noqa: E402


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    database = SessionLocal()
    try:
        reset_demo_data(database)
        print("Demo database initialized successfully.")
    finally:
        database.close()

