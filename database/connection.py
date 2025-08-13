"""Database connection and session management."""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from database.models import Base
from utils.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Handle database connections and session management."""

    def __init__(self):
        """Initialize database connection."""
        self.engine = None
        self.SessionLocal = None
        self._setup_database()

    def _setup_database(self):
        """Set up database engine and session factory."""

        database_url = settings.database_url

        # Configure engine based on database type
        if database_url.startswith("sqlite"):
            # SQLite configuration for development
            self.engine = create_engine(
                database_url,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False, "timeout": 20},
                echo=settings.debug,
            )
        else:
            # PostgreSQL configuration for production
            self.engine = create_engine(
                database_url,
                pool_size=20,
                max_overflow=30,
                pool_timeout=30,
                pool_recycle=3600,
                echo=settings.debug,
            )

        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        logger.info(
            f"Database configured: {database_url.split('@')[-1] if '@' in database_url else database_url}"
        )

    def create_tables(self):
        """Create all database tables."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {str(e)}")
            raise

    def get_session(self) -> Session:
        """Get a database session."""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
        return self.SessionLocal()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database transaction failed: {str(e)}")
            raise
        finally:
            session.close()

    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {str(e)}")
            return False

    def get_health_status(self) -> dict:
        """Get database health status."""
        try:
            with self.session_scope() as session:
                # Test basic connectivity
                session.execute(text("SELECT 1"))

                # Get connection pool info (if available)
                pool_info = {}
                try:
                    pool = self.engine.pool
                    if hasattr(pool, "size"):
                        pool_info["pool_size"] = pool.size() if callable(pool.size) else pool.size
                    if hasattr(pool, "checked_in_connections"):
                        pool_info["checked_in"] = len(pool.checked_in_connections)
                    if hasattr(pool, "checked_out_connections"):
                        pool_info["checked_out"] = pool.checked_out_connections
                except Exception:
                    # Pool info is optional, don't fail health check
                    pass

                return {
                    "status": "healthy",
                    "connection_active": True,
                    "pool_info": pool_info,
                }

        except Exception as e:
            return {"status": "unhealthy", "connection_active": False, "error": str(e)}


# Global database manager instance
db_manager = DatabaseManager()


# Dependency for FastAPI
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to get database session."""
    with db_manager.session_scope() as session:
        yield session
