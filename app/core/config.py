from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Zabbix Advisor Pro", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    request_timeout: int = Field(default=30, alias="REQUEST_TIMEOUT")
    verify_ssl: bool = Field(default=True, alias="VERIFY_SSL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
