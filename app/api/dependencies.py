"""
API dependencies for dependency injection.
"""
from typing import Generator
from sqlalchemy.orm import Session
from app.services.database_service import db_service


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = db_service.get_db_session()
    try:
        yield db
    finally:
        db.close()
