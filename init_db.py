"""
Database initialization script
Run this script to create database tables and add initial data
"""

import os
from dotenv import load_dotenv
from models import db_config, Base
from auth import auth_service

# Load environment variables
load_dotenv()

def init_database():
    """Initialize database with tables and initial data"""
    try:
        print("Initializing database...")
        
        # Create all tables
        db_config.create_tables()
        print("✓ Database tables created successfully")
        
        # Create default admin user if it doesn't exist
        success, message, user = auth_service.register_user(
            username="admin",
            email="admin@directcostmaster.com",
            password="admin123",  # Change this in production!
            first_name="System",
            last_name="Administrator"
        )
        
        if success:
            print(f"✓ Default admin user created: admin/admin123")
        else:
            print(f"ℹ Default admin user: {message}")
        
        print("\nDatabase initialization completed successfully!")
        print("\nNext steps:")
        print("1. Update your .env file with correct database credentials")
        print("2. Change the default admin password")
        print("3. Start the application with: python main.py")
        
    except Exception as e:
        print(f"✗ Error initializing database: {str(e)}")
        print("\nPlease check:")
        print("1. PostgreSQL is running")
        print("2. Database 'directcostmaster' exists")
        print("3. Connection credentials in .env file are correct")

if __name__ == "__main__":
    init_database()
