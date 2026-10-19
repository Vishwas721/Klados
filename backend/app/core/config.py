from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "klados"

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgrespassword"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "leads_db"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # JSON list when set via env, e.g. CORS_ORIGINS='["http://localhost:3000"]'
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    QUEUE_NAME: str = "lead_tasks"

    # Safe IP limits: cap leads per cell, pace audits, and cap leads per day
    MAX_LEADS_PER_CELL: int = 20
    AUDIT_DELAY_MIN_S: int = 3
    AUDIT_DELAY_MAX_S: int = 7
    DAILY_LIMIT: int = 40

    OLLAMA_URL: str = "http://localhost:11434/api/generate"
    OLLAMA_MODEL: str = "llama3:8b"
    OLLAMA_TIMEOUT_S: float = 30.0

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"


settings = Settings()
