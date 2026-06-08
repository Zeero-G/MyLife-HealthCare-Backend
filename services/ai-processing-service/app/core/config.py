import os
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    PORT: int = 8004
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    NOTIFICATION_SERVICE_URL: str = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8005")
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "https://mylife.vercel.app"]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
