from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Financial Document Intelligence API"
    debug: bool = True

    database_url: str = "sqlite:///./documents.db"

    google_api_key: str = ""
    groq_api_key: str = ""
    qwen_api_key: str = ""
    openrouter_api_key: str = ""
    ocr_space_api_key: str = ""

    groq_model: str = "qwen/qwen3.8-27b"
    openrouter_model: str = "openrouter/free"
    gemini_model: str = "gemma-4-31b-it"
    max_file_size_mb: int = 10

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()