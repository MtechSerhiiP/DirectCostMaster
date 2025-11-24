"""
Configuration for Direct Cost Master - Memory Mode
This configuration enables in-memory storage for DL/VC records while keeping authentication in database
"""

import os
from typing import Dict, Any

class AppConfig:
    """Application configuration"""
    
    # Storage configuration
    STORAGE_MODE = "MEMORY"  # Use in-memory storage for DL/VC records
    AUTH_STORAGE = "DATABASE"  # Use database for authentication
    
    # Memory storage settings
    MEMORY_CLEANUP_INTERVAL_HOURS = 24  # How often to clean up expired data
    MAX_MEMORY_RECORDS_PER_USER = 50000  # Maximum records per user in memory
    
    # Authentication settings
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_EXPIRE_HOURS = int(os.getenv('JWT_EXPIRE_HOURS', '24'))
    
    # Database settings (only for authentication)
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./auth.db')
    
    # File processing settings
    MAX_FILE_SIZE_MB = 50
    ALLOWED_FILE_TYPES = ['.xlsx', '.xls']
    TEMP_FILE_RETENTION_HOURS = 24
    
    # API settings
    CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
    API_TITLE = "Direct Cost Master API (Memory Mode)"
    API_VERSION = "1.0.0"
    API_DESCRIPTION = """
    Direct Cost Master API with in-memory storage for DL/VC records.
    
    Features:
    - Authentication stored in database
    - DL/VC records stored in memory (faster access, no database overhead)
    - File processing and export capabilities
    - RESTful API with automatic documentation
    """
    
    @classmethod
    def get_summary(cls) -> Dict[str, Any]:
        """Get configuration summary"""
        return {
            "storage_mode": cls.STORAGE_MODE,
            "auth_storage": cls.AUTH_STORAGE,
            "max_records_per_user": cls.MAX_MEMORY_RECORDS_PER_USER,
            "jwt_expire_hours": cls.JWT_EXPIRE_HOURS,
            "max_file_size_mb": cls.MAX_FILE_SIZE_MB,
            "database_for_auth_only": True,
            "memory_for_data": True
        }

# Global configuration instance
app_config = AppConfig()
