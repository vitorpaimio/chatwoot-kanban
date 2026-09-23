from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    chatwoot_base_url: str = "http://127.0.0.1:3001"
    public_url: str = "http://localhost:3000"
    database_url: str
    encryption_key: str = ""
    env: str = "development"
    webhook_tolerance: int = 300
    session_recheck_seconds: int = 30


settings = Settings()
