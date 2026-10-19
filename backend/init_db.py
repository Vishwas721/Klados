"""Test the database connection and create all tables directly (no migration)."""

from sqlalchemy import text

from app.core.config import settings
from app.db.models import Base
from app.db.session import engine


def main() -> None:
    print(f"Connecting to {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB} ...")
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("Connection OK.")

    print("Creating tables ...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")


if __name__ == "__main__":
    main()
