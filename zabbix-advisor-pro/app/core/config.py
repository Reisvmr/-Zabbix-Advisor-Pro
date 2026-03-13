from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Zabbix Advisor Pro"
    debug: bool = True
    request_timeout: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
