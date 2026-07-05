import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from .models import Base, ScannedFile

# Defaults to local SQLite for local/daily use. Set DATABASE_URL to a
# Postgres connection string (e.g. via the Docker Compose setup) to use
# Postgres instead — no code changes needed either way.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./drive_cleaner.db")
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _migrate_missing_columns():
    """
    Base.metadata.create_all() only creates tables that don't exist yet — it
    never adds columns to a table that's already there. If drive_cleaner.db
    was created by an earlier version of this app (e.g. before the Phase 2
    columns like subcategory/blur_score/pdf_page_count existed), every query
    that touches those columns fails silently on the frontend. This adds any
    columns the model defines but the actual table is missing.

    SQLite-only: a fresh Postgres deployment always starts from create_all()
    with the full current schema, so there's nothing to migrate there.
    """
    if not IS_SQLITE:
        return

    inspector = inspect(engine)
    if "scanned_files" not in inspector.get_table_names():
        return  # fresh DB, create_all() below handles it

    existing_columns = {col["name"] for col in inspector.get_columns("scanned_files")}
    with engine.begin() as conn:
        for column in ScannedFile.__table__.columns:
            if column.name in existing_columns:
                continue
            col_type = column.type.compile(engine.dialect)
            conn.execute(text(f"ALTER TABLE scanned_files ADD COLUMN {column.name} {col_type}"))


def init_db():
    _migrate_missing_columns()
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
