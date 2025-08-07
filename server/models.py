"""
Database models for Direct Cost Master application
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
import bcrypt
import os
from typing import Optional

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
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="created_by_user")
    
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


class UserSession(Base):
    """User session model for session management"""
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    ip_address = Column(String(45), nullable=True)  # Support both IPv4 and IPv6
    user_agent = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<UserSession(user_id={self.user_id}, token='{self.session_token[:10]}...', active={self.is_active})>"


class Project(Base):
    """Project model to store project information"""
    __tablename__ = 'projects'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    created_by_user = relationship("User", back_populates="projects")
    dl_records = relationship("DLCostRecord", back_populates="project", cascade="all, delete-orphan")
    vc_records = relationship("VCCostRecord", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project(name='{self.name}', created_by={self.created_by})>"


class DLCostRecord(Base):
    """Direct Labor Cost record model"""
    __tablename__ = 'dl_cost_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    
    # Core fields from DC processing
    period = Column(String(50), nullable=False, index=True)  # e.g., "June 2025"
    employee = Column(String(200), nullable=False, index=True)
    ticket = Column(String(200), nullable=True)
    bucket = Column(String(100), nullable=False, index=True)
    dc_hours = Column(Float, nullable=True)
    total_dl_costs = Column(Float, nullable=False)
    
    # Metadata
    source_file = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="dl_records")
    created_by_user = relationship("User")
    
    def __repr__(self):
        return f"<DLCostRecord(project_id={self.project_id}, employee='{self.employee}', bucket='{self.bucket}', costs={self.total_dl_costs})>"


class VCCostRecord(Base):
    """Variable Cost record model"""
    __tablename__ = 'vc_cost_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    
    # Core fields from VC processing
    period = Column(String(50), nullable=False, index=True)  # e.g., "June 2025"
    item = Column(String(200), nullable=False, index=True)
    bucket = Column(String(100), nullable=False, index=True)
    total_dl_costs = Column(Float, nullable=False)  # Note: despite name, this is VC costs
    
    # Metadata
    source_file = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="vc_records")
    created_by_user = relationship("User")
    
    def __repr__(self):
        return f"<VCCostRecord(project_id={self.project_id}, item='{self.item}', bucket='{self.bucket}', costs={self.total_dl_costs})>"


class ProcessingLog(Base):
    """Log of file processing operations"""
    __tablename__ = 'processing_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    filename = Column(String(500), nullable=False)
    period = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)  # 'success', 'failed', 'partial'
    records_processed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f"<ProcessingLog(filename='{self.filename}', status='{self.status}', records={self.records_processed})>"


# Database configuration and utilities
class DatabaseConfig:
    """Database configuration and connection management"""
    
    def __init__(self):
        # Get database URL from environment variables
        self.db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:Betta&Gamma123d@localhost:5432/directcostmaster')
        self.engine = None
        self.SessionLocal = None
    
    def create_engine(self):
        """Create SQLAlchemy engine"""
        if not self.engine:
            self.engine = create_engine(
                self.db_url,
                echo=False,  # Set to True for SQL debugging
                pool_size=10,
                max_overflow=20
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
        engine = self.create_engine()
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully!")
    
    def get_session(self):
        """Get database session"""
        SessionLocal = self.create_session_factory()
        return SessionLocal()


# Global database configuration instance
db_config = DatabaseConfig()
