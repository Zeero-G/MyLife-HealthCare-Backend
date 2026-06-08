import os
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "MYLIFE Medical Records Service"
    PORT: int = 8002
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

    JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"

    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "https://mylife.vercel.app"]

    # Inter-service URLs
    AUTH_SERVICE_URL: str = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
    NOTIFICATION_SERVICE_URL: str = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8005")
    AI_SERVICE_URL: str = os.getenv("AI_SERVICE_URL", "http://localhost:8004")

    # Supabase storage bucket (kept for fallback/QR features)
    STORAGE_BUCKET: str = "medical-docs"

    # AWS S3 configuration
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "")
    # How long (seconds) a presigned PUT URL is valid
    S3_PRESIGN_EXPIRY: int = int(os.getenv("S3_PRESIGN_EXPIRY", "900"))

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
