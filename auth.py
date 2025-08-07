"""
Authentication and session management module
"""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_
from models import User, UserSession, db_config
import logging

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling authentication and session management"""
    
    def __init__(self):
        self.session_duration_hours = 24  # Session valid for 24 hours
    
    def register_user(self, username: str, email: str, password: str, 
                     first_name: str = None, last_name: str = None) -> Tuple[bool, str, Optional[User]]:
        """
        Register a new user
        
        Args:
            username: Unique username
            email: User email
            password: Plain text password
            first_name: Optional first name
            last_name: Optional last name
            
        Returns:
            Tuple of (success, message, user_object)
        """
        db_session = db_config.get_session()
        try:
            # Check if username or email already exists
            existing_user = db_session.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                if existing_user.username == username:
                    return False, "Username already exists", None
                else:
                    return False, "Email already exists", None
            
            # Create new user
            new_user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            new_user.set_password(password)
            
            db_session.add(new_user)
            db_session.commit()
            
            logger.info(f"New user registered: {username}")
            return True, "User registered successfully", new_user
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error registering user: {str(e)}")
            return False, f"Registration failed: {str(e)}", None
        finally:
            db_session.close()
    
    def authenticate_user(self, username: str, password: str) -> Tuple[bool, str, Optional[User]]:
        """
        Authenticate user with username and password
        
        Args:
            username: Username or email
            password: Plain text password
            
        Returns:
            Tuple of (success, message, user_object)
        """
        db_session = db_config.get_session()
        try:
            # Find user by username or email
            user = db_session.query(User).filter(
                and_(
                    (User.username == username) | (User.email == username),
                    User.is_active == True
                )
            ).first()
            
            if not user:
                return False, "Invalid username or password", None
            
            # Check password
            if not user.check_password(password):
                return False, "Invalid username or password", None
            
            # Update last login
            user.last_login = datetime.utcnow()
            db_session.commit()
            
            logger.info(f"User authenticated: {user.username}")
            return True, "Authentication successful", user
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error authenticating user: {str(e)}")
            return False, f"Authentication failed: {str(e)}", None
        finally:
            db_session.close()
    
    def create_session(self, user: User, ip_address: str = None, user_agent: str = None) -> Optional[str]:
        """
        Create a new session for user
        
        Args:
            user: User object
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Session token or None if failed
        """
        db_session = db_config.get_session()
        try:
            # Generate unique session token
            session_token = self._generate_session_token()
            
            # Create session
            expires_at = datetime.utcnow() + timedelta(hours=self.session_duration_hours)
            
            user_session = UserSession(
                user_id=user.id,
                session_token=session_token,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            db_session.add(user_session)
            db_session.commit()
            
            logger.info(f"Session created for user {user.username}: {session_token[:10]}...")
            return session_token
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error creating session: {str(e)}")
            return None
        finally:
            db_session.close()
    
    def validate_session(self, session_token: str) -> Tuple[bool, Optional[User]]:
        """
        Validate session token and return user if valid
        
        Args:
            session_token: Session token to validate
            
        Returns:
            Tuple of (is_valid, user_object)
        """
        db_session = db_config.get_session()
        try:
            # Find active session
            session = db_session.query(UserSession).filter(
                and_(
                    UserSession.session_token == session_token,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.utcnow()
                )
            ).first()
            
            if not session:
                return False, None
            
            # Get user
            user = db_session.query(User).filter(
                and_(
                    User.id == session.user_id,
                    User.is_active == True
                )
            ).first()
            
            if not user:
                # Deactivate session if user is not active
                session.is_active = False
                db_session.commit()
                return False, None
            
            return True, user
            
        except Exception as e:
            logger.error(f"Error validating session: {str(e)}")
            return False, None
        finally:
            db_session.close()
    
    def logout_session(self, session_token: str) -> bool:
        """
        Logout specific session
        
        Args:
            session_token: Session token to logout
            
        Returns:
            True if successful, False otherwise
        """
        db_session = db_config.get_session()
        try:
            # Find and deactivate session
            session = db_session.query(UserSession).filter(
                UserSession.session_token == session_token
            ).first()
            
            if session:
                session.is_active = False
                db_session.commit()
                logger.info(f"Session logged out: {session_token[:10]}...")
                return True
            
            return False
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error logging out session: {str(e)}")
            return False
        finally:
            db_session.close()
    
    def logout_all_user_sessions(self, user_id: int) -> bool:
        """
        Logout all sessions for a user
        
        Args:
            user_id: User ID
            
        Returns:
            True if successful, False otherwise
        """
        db_session = db_config.get_session()
        try:
            # Deactivate all user sessions
            db_session.query(UserSession).filter(
                UserSession.user_id == user_id
            ).update({UserSession.is_active: False})
            
            db_session.commit()
            logger.info(f"All sessions logged out for user ID: {user_id}")
            return True
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error logging out all sessions: {str(e)}")
            return False
        finally:
            db_session.close()
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions
        
        Returns:
            Number of sessions cleaned up
        """
        db_session = db_config.get_session()
        try:
            # Deactivate expired sessions
            result = db_session.query(UserSession).filter(
                and_(
                    UserSession.is_active == True,
                    UserSession.expires_at <= datetime.utcnow()
                )
            ).update({UserSession.is_active: False})
            
            db_session.commit()
            logger.info(f"Cleaned up {result} expired sessions")
            return result
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error cleaning up sessions: {str(e)}")
            return 0
        finally:
            db_session.close()
    
    def _generate_session_token(self) -> str:
        """Generate a secure session token"""
        return f"{uuid.uuid4().hex}{secrets.token_hex(32)}"
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        db_session = db_config.get_session()
        try:
            return db_session.query(User).filter(
                and_(User.id == user_id, User.is_active == True)
            ).first()
        except Exception as e:
            logger.error(f"Error getting user by ID: {str(e)}")
            return None
        finally:
            db_session.close()


# Global auth service instance
auth_service = AuthService()
