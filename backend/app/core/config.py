from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""
    
    # App
    environment: str = "development"
    secret_key: str = "dev-secret-change-me"
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    
    # Optional LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    
    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
