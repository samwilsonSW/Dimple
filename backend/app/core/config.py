from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


# Find the .env file — it's in the backend/ directory
BACKEND_DIR = Path(__file__).parent.parent.parent.resolve()
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    moonshot_api_key: str
    environment: str = "development"

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
