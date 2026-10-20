from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./timeforge.db"
    redis_url: str = "redis://localhost:6379/0"
    cookie_secure: bool = False
    session_hours: int = 12
    allowed_origin: str = "http://localhost:5173"
    public_url: str = "http://localhost:5173"
    timezone: str = "Asia/Colombo"
    jobs_eager: bool = False
    mail_directory: Path = Path(".mail")
    trusted_hosts: str = "localhost,127.0.0.1,testserver,backend"
    max_import_bytes: int = 2_000_000


@lru_cache
def settings() -> Settings:
    return Settings()
