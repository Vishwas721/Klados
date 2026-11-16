from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "klados"

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgrespassword"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5434
    POSTGRES_DB: str = "leads_db"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6380

    # JSON list when set via env, e.g. CORS_ORIGINS='["http://localhost:3000"]'
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # When set, every /api request must send it as the X-API-Key header.
    # Give the dashboard the same value via NEXT_PUBLIC_API_KEY.
    API_KEY: str | None = None

    QUEUE_NAME: str = "lead_tasks"

    # Safe IP limits: cap leads per cell, pace audits, and cap leads per day
    MAX_LEADS_PER_CELL: int = 20
    AUDIT_DELAY_MIN_S: int = 3
    AUDIT_DELAY_MAX_S: int = 7
    DAILY_LIMIT: int = 40
    # Pause all Maps scraping this long after Google serves a CAPTCHA/consent wall
    MAPS_BLOCK_COOLDOWN_S: int = 3600

    OLLAMA_URL: str = "http://localhost:11434/api/generate"
    OLLAMA_MODEL: str = "llama3:8b"
    OLLAMA_TIMEOUT_S: float = 30.0

    # ── Request radar: posts where someone asks for a website / automation ──
    # Sent with every request to the public sources; Reddit asks for a
    # descriptive one.
    INTENT_USER_AGENT: str = "klados/0.2 (request radar; small-business lead finder)"
    # Posts older than this are ignored when they come back from a source
    INTENT_MAX_AGE_DAYS: int = 14
    # Posts scoring below this are dropped instead of saved
    INTENT_MIN_SCORE: int = 20
    # Ollama writes the summary and reply only for posts at or above this score
    INTENT_LLM_MIN_SCORE: int = 45

    # How often each source is polled (seconds)
    FREELANCER_POLL_S: int = 600
    REDDIT_POLL_S: int = 900
    HN_POLL_S: int = 3600
    RSS_POLL_S: int = 1800
    WEB_POLL_S: int = 21600

    FREELANCER_QUERIES: list[str] = [
        "website",
        "wordpress",
        "shopify",
        "landing page",
        "web design",
        "website redesign",
        "booking system",
        "whatsapp automation",
        "chatbot",
    ]
    # Fetched as two feeds so busy discussion subs can't push the hiring
    # posts out of the 100-post window.
    REDDIT_HIRING_SUBREDDITS: list[str] = ["forhire", "slavelabour", "freelance_forhire", "hiring"]
    REDDIT_COMMUNITY_SUBREDDITS: list[str] = [
        "smallbusiness",
        "Entrepreneur",
        "indianstartups",
        "bangalore",
        "india",
    ]
    # Optional: a free Reddit "script" app. Without it the public RSS feed is
    # used, which Reddit rate-limits more aggressively.
    REDDIT_CLIENT_ID: str | None = None
    REDDIT_CLIENT_SECRET: str | None = None

    # Extra RSS/Atom feeds of job or request posts, JSON list via env
    INTENT_RSS_FEEDS: list[str] = []

    # Self-hosted SearXNG (docker compose runs one) for open-web search
    SEARXNG_URL: str | None = None
    WEB_SEARCH_QUERIES: list[str] = [
        '"looking for a web developer" small business',
        '"need a website" for my business India',
        '"looking for someone to build" website Bangalore',
        '"recommend a web designer" Bengaluru',
        '"need someone to redesign" my website',
    ]

    # Optional instant alerts for hot posts
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None
    INTENT_ALERT_MIN_SCORE: int = 70

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
