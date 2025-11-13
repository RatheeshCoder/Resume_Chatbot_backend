import os
from typing import ClassVar
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Loads all environment variables from the .env file."""

    MONGO_URI: str
    GROQ_API_KEY: str
    GOOGLE_API_KEY: str
    GROQ_MODEL: str = "llama3-70b-8192"
    RECURSION_LIMIT: int = 12          # ← NEW
    MAX_FIELD_RETRIES: int = 2

    # Define path to `.env` (ensure it always resolves correctly)
    env_file_path: ClassVar[str] = str(Path(__file__).resolve().parent.parent / ".env")

    model_config = SettingsConfigDict(
        env_file=env_file_path,
        env_file_encoding="utf-8"
    )


# Create a single instance for global use
try:
    settings = Settings()
    print("✅ INFO: Configuration loaded successfully.")
except Exception as e:
    print(f"❌ ERROR: Failed to load settings from .env file: {e}")
    print("⚠️ CRITICAL: Ensure `.env` exists in the project root and contains required keys:")
    print("  - MONGO_URI")
    print("  - GROQ_API_KEY")
