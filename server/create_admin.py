"""
One-time script to create a default admin user in the SQLite database.
"""

import os
import sys
from sqlalchemy.orm import Session

# Add the server directory to the Python path to allow module imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from auth_models import User, auth_db_config

# --- Admin User Configuration ---
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"
ADMIN_EMAIL = "admin@example.com"
# --------------------------------

def create_admin_user():
    """
    Connects to the database and creates the admin user if it doesn't exist.
    """
    print("Attempting to create admin user...")
    
    # Ensure tables are created
    if not auth_db_config.create_tables():
        print("Could not ensure database tables exist. Aborting.")
        return

    # Get a database session
    db_session = auth_db_config.get_session()
    if not db_session:
        print("Failed to get a database session. Aborting.")
        return

    try:
        # Check if the admin user already exists
        existing_user = db_session.query(User).filter(User.username == ADMIN_USERNAME).first()
        
        if existing_user:
            print(f"User '{ADMIN_USERNAME}' already exists. No action taken.")
            return

        # Create the new admin user
        print(f"Creating new admin user: '{ADMIN_USERNAME}'")
        admin_user = User(
            username=ADMIN_USERNAME,
            email=ADMIN_EMAIL,
            first_name="Admin",
            last_name="User",
            is_active=True
        )
        
        # Set the password
        admin_user.set_password(ADMIN_PASSWORD)
        
        # Add to session and commit
        db_session.add(admin_user)
        db_session.commit()
        
        print("\n" + "="*40)
        print("✅ Admin user created successfully!")
        print(f"   Username: {ADMIN_USERNAME}")
        print(f"   Password: {ADMIN_PASSWORD}")
        print("="*40)
        print("\n⚠️ IMPORTANT: Please change this default password after your first login.")

    except Exception as e:
        db_session.rollback()
        print(f"❌ An error occurred: {e}")
    finally:
        db_session.close()
        print("Database session closed.")

if __name__ == "__main__":
    create_admin_user()
