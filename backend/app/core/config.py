from pathlib import Path
import os

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
load_dotenv(PROJECT_DIR / ".env")


class Settings:
    app_name = "Yiwu AI Trade Copilot API"
    ai_provider = os.getenv("AI_PROVIDER", "mock").lower()
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    database_url = os.getenv(
        "DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'data' / 'yiwu_demo.db').as_posix()}"
    )
    frontend_origins = [
        item.strip()
        for item in os.getenv(
            "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if item.strip()
    ]


settings = Settings()

