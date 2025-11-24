"""
JWT-based Authentication Service for API
Replaces the session-based authentication with stateless JWT tokens
"""

import jwt
import bcrypt
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging
from dotenv import load_dotenv
# Import authentication-only models
from auth_models import User, auth_db_config

logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

class AuthAPIService:
    """JWT-based authentication service for the API"""
    
    def __init__(self):
        # JWT configuration - SECURE: No fallback, require proper secret
        self.secret_key = self._get_secure_jwt_secret()
        self.algorithm = 'HS256'
        self.token_expire_hours = int(os.getenv('JWT_EXPIRE_HOURS', '24'))
    
    def _get_secure_jwt_secret(self) -> str:
        """
        Securely retrieve and validate JWT secret key.
        
        Returns:
            Valid JWT secret key
            
        Raises:
            RuntimeError: If no secure secret is configured
        """
        secret = os.getenv('JWT_SECRET_KEY')
        print(secret)
        # CRITICAL SECURITY: Refuse to start without proper secret
        if not secret:
            raise RuntimeError(
                "SECURITY ERROR: JWT_SECRET_KEY environment variable is required. "
                "Set a cryptographically secure random key (minimum 32 characters)."
            )
        
        # Validate secret strength
        if len(secret) < 32:
            raise RuntimeError(
                "SECURITY ERROR: JWT_SECRET_KEY must be at least 32 characters long. "
                "Generate a secure key using: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        
        # Check for common weak defaults
        weak_defaults = {
            'your-secret-key-change-in-production',
            'secret',
            'jwt-secret',
            'your-super-secret-jwt-key-change-in-production-make-it-long-and-random',
            'change-me',
            'development-key'
        }
        
        if secret.lower() in weak_defaults or secret in weak_defaults:
            raise RuntimeError(
                "SECURITY ERROR: Detected weak/default JWT secret. "
                "Generate a secure key using: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        
        logger.info("JWT secret key validated successfully")
        return secret
    
    def authenticate_user(self, username: str, password: str) -> Tuple[bool, str, Optional[User], Optional[str]]:
        """
        Authenticate user and generate JWT token
        
        Args:
            username: Username or email
            password: Plain text password
            
        Returns:
            Tuple of (success, message, user_object, jwt_token)
        """
        db_session = auth_db_config.get_session()
        if not db_session:
            return False, "Authentication database unavailable", None, None
        try:
            # Find user by username or email
            user = db_session.query(User).filter(
                and_(
                    (User.username == username) | (User.email == username),
                    User.is_active == True
                )
            ).first()
            
            if not user:
                return False, "Invalid username or password", None, None
            
            # Check password
            if not user.check_password(password):
                return False, "Invalid username or password", None, None
            
            # Update last login
            user.last_login = datetime.utcnow()
            db_session.commit()
            
            # Generate JWT token
            token = self.generate_token(user)
            
            logger.info(f"User authenticated: {user.username}")
            return True, "Authentication successful", user, token
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error authenticating user: {str(e)}")
            return False, f"Authentication failed: {str(e)}", None, None
        finally:
            db_session.close()
    
    def generate_token(self, user: User) -> str:
        """
        Generate JWT token for user
        
        Args:
            user: User object
            
        Returns:
            JWT token string
        """
        try:
            # Token payload
            payload = {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'exp': datetime.utcnow() + timedelta(hours=self.token_expire_hours),
                'iat': datetime.utcnow(),
                'iss': 'DirectCostMaster'  # Issuer
            }
            
            # Generate token
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            
            logger.debug(f"Token generated for user: {user.username}")
            return token
            
        except Exception as e:
            logger.error(f"Error generating token: {str(e)}")
            raise
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode JWT token with optimized database access
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            # Decode and validate token first (no DB access needed)
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Extract user_id and validate it exists
            user_id = payload.get('user_id')
            if not user_id:
                logger.warning("Token verification failed: Missing user_id in payload")
                return None
            
            # Optimized: Only check user existence if token is valid and recent
            # For frequently accessed tokens, consider implementing caching here
            db_session = auth_db_config.get_session()
            if not db_session:
                logger.warning("Token verification failed: Authentication database unavailable")
                return None
            try:
                user = db_session.query(User).filter(
                    and_(User.id == user_id, User.is_active == True)
                ).first()
                
                if not user:
                    logger.warning(f"Token verification failed: User {user_id} not found or inactive")
                    return None
                
                # Return verified payload
                return {
                    'id': user_id,
                    'username': payload.get('username'),
                    'email': payload.get('email'),
                    'first_name': payload.get('first_name'),
                    'last_name': payload.get('last_name')
                }
                
            except Exception as db_error:
                logger.error(f"Database error during token verification: {str(db_error)}")
                return None
            finally:
                # CRITICAL: Always close the session
                db_session.close()
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token verification failed: Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token verification failed: Invalid token - {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            return None
    
    def refresh_token(self, token: str) -> Optional[str]:
        """
        Refresh JWT token (generate new token from valid token)
        
        Args:
            token: Current valid JWT token
            
        Returns:
            New JWT token or None if refresh failed
        """
        try:
            # Verify current token
            payload = self.verify_token(token)
            if not payload:
                return None
            
            # Get user from database
            db_session = auth_db_config.get_session()
            if not db_session:
                return None
            try:
                user = db_session.query(User).filter(
                    and_(User.id == payload['id'], User.is_active == True)
                ).first()
                
                if not user:
                    return None
                
                # Generate new token
                new_token = self.generate_token(user)
                return new_token
                
            finally:
                db_session.close()
                
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID (same as before)"""
        db_session = auth_db_config.get_session()
        if not db_session:
            return None
        try:
            return db_session.query(User).filter(
                and_(User.id == user_id, User.is_active == True)
            ).first()
        except Exception as e:
            logger.error(f"Error getting user by ID: {str(e)}")
            return None
        finally:
            db_session.close()
    
    def validate_token_format(self, token: str) -> bool:
        """
        Basic token format validation
        
        Args:
            token: JWT token string
            
        Returns:
            True if format is valid, False otherwise
        """
        try:
            # JWT tokens have 3 parts separated by dots
            parts = token.split('.')
            return len(parts) == 3
        except:
            return False


# Global auth service instance for API
auth_api_service = AuthAPIService()
