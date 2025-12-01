"""
Authentication-only database models for Direct Cost Master application
Only handles user authentication and sessions
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import bcrypt
import os

Base = declarative_base()


class User(Base):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    def set_password(self, password: str):
        """Hash and set password"""
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    
    def check_password(self, password: str) -> bool:
        """Check if provided password matches the hash"""
        password_bytes = password.encode('utf-8')
        hash_bytes = self.password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"


# Database configuration and utilities
class AuthDatabaseConfig:
    """Authentication database configuration and connection management"""
    
    def __init__(self):
        # Get database URL from environment variables
        self.db_url = os.getenv('DATABASE_URL', 'sqlite:///./auth.db')
        self.engine = None
        self.SessionLocal = None
    
    def create_engine(self):
        """Create SQLAlchemy engine"""
        if not self.engine:
            # Use connect_args for SQLite
            connect_args = {"check_same_thread": False} if self.db_url.startswith("sqlite") else {}
            self.engine = create_engine(
                self.db_url,
                echo=False,  # Set to True for SQL debugging
                pool_size=10,
                max_overflow=20,
                connect_args=connect_args
            )
        return self.engine
    
    def create_session_factory(self):
        """Create session factory"""
        if not self.SessionLocal:
            engine = self.create_engine()
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return self.SessionLocal
    
    def create_tables(self):
        """Create all tables if they don't exist"""
        try:
            engine = self.create_engine()
            Base.metadata.create_all(bind=engine)
            print("Authentication database tables created successfully!")
            return True
        except Exception as e:
            print(f"Warning: Could not create authentication tables: {str(e)}")
            print("Authentication features may not work properly.")
            return False
    
    def get_session(self):
        """Get database session"""
        try:
            SessionLocal = self.create_session_factory()
            return SessionLocal()
        except Exception as e:
            print(f"Warning: Could not connect to authentication database: {str(e)}")
            return None


# Global auth database configuration instance
auth_db_config = AuthDatabaseConfig()
