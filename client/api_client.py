"""
API Client Service for Direct Cost Master
Handles all HTTP communication with the FastAPI server
"""

import requests
import json
import io
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class APIClientService:
    """Service for communicating with the Direct Cost Master API server"""
    
    def __init__(self):
        # API configuration
<<<<<<< HEAD
        self.api_host = os.getenv('API_HOST', '127.0.0.1')
=======
        # Default to 'server' for Docker, '127.0.0.1' for local dev
        self.api_host = os.getenv('API_HOST', 'server')
>>>>>>> 25e7f39 (Made docker-compose up start all application)
        self.api_port = os.getenv('API_PORT', '8000')
        self.base_url = f"http://{self.api_host}:{self.api_port}"
        
        # Authentication state
        self.auth_token = None
        self.current_user = None
        
        # Session for connection pooling
        self.session = requests.Session()
        
        logger.info(f"API Client initialized for {self.base_url}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication if available"""
        headers = {'Content-Type': 'application/json'}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        return headers
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and check for errors"""
        try:
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                # Clear invalid token
                self.auth_token = None
                self.current_user = None
                raise Exception("Authentication required or token expired")
            else:
                error_data = response.json() if response.content else {"detail": "Unknown error"}
                raise Exception(f"API Error ({response.status_code}): {error_data.get('detail', 'Unknown error')}")
        except requests.exceptions.JSONDecodeError:
            raise Exception(f"Invalid response from server ({response.status_code})")
    
    # Authentication methods
    def login(self, username: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """Login user and store authentication token"""
        try:
            data = {
                'username': username,
                'password': password
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/login",
                json=data,
                headers={'Content-Type': 'application/json'}
            )
            
            result = self._handle_response(response)
            
            if result.get('success') and result.get('token'):
                self.auth_token = result['token']
                self.current_user = result.get('user')
                return True, result.get('message', 'Login successful'), self.current_user
            else:
                return False, result.get('message', 'Login failed'), None
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return False, str(e), None
    
    def refresh_token(self) -> bool:
        """Refresh authentication token"""
        try:
            if not self.auth_token:
                return False
            
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/refresh",
                headers=self._get_headers()
            )
            
            result = self._handle_response(response)
            
            if result.get('success') and result.get('token'):
                self.auth_token = result['token']
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            return False
    
    def logout(self):
        """Logout user (clear local state)"""
        self.auth_token = None
        self.current_user = None
    
    # File processing methods
    def upload_files(self, file_list: List[Tuple[str, bytes]]) -> Tuple[bool, str, List[Dict]]:
        """
        Upload multiple files to the server
        
        Args:
            file_list: List of (filename, file_content) tuples
            
        Returns:
            Tuple of (success, message, uploaded_files_info)
        """
        try:
            if not self.auth_token:
                return False, "Authentication required", []
            
            # Prepare files for upload
            files = []
            for filename, content in file_list:
                files.append(('files', (filename, io.BytesIO(content), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')))
            
            # Remove Content-Type header for multipart upload
            headers = {'Authorization': f'Bearer {self.auth_token}'}
            
            response = self.session.post(
                f"{self.base_url}/api/v1/files/upload",
                files=files,
                headers=headers
            )
            
            result = self._handle_response(response)
            
            if result.get('success'):
                return True, result.get('message', 'Files uploaded'), result.get('uploaded_files', [])
            else:
                return False, result.get('message', 'Upload failed'), []
                
        except Exception as e:
            logger.error(f"File upload error: {str(e)}")
            return False, str(e), []
    
    def start_processing(self, file_ids: List[str], month: str, year: str, 
                         analysis_mode: str = "single") -> Tuple[bool, str, Optional[str]]:
        """
        Start file processing and return job ID
        
        Args:
            file_ids: List of file IDs to process
            month: Target month name
            year: Target year
            analysis_mode: 'single' for single month, 'ytd' for Year-to-Date
            
        Returns:
            Tuple of (success, message, job_id)
        """
        try:
            if not self.auth_token:
                return False, "Authentication required", None
            
            data = {
                'file_ids': file_ids,
                'month': month,
                'year': year,
                'analysis_mode': analysis_mode
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/files/process",
                json=data,
                headers=self._get_headers()
            )
            
            result = self._handle_response(response)
            
            if result.get('success'):
                return True, result.get('message', 'Processing started'), result.get('job_id')
            else:
                return False, result.get('message', 'Processing failed'), None
                
        except Exception as e:
            logger.error(f"Processing start error: {str(e)}")
            return False, str(e), None
    
    def get_processing_status(self, job_id: str) -> Tuple[bool, Dict[str, Any]]:
        """Get processing job status"""
        try:
            if not self.auth_token:
                return False, {"error": "Authentication required"}
            
            response = self.session.get(
                f"{self.base_url}/api/v1/files/process/{job_id}/status",
                headers=self._get_headers()
            )
            
            result = self._handle_response(response)
            return True, result
                
        except Exception as e:
            logger.error(f"Status check error: {str(e)}")
            return False, {"error": str(e)}
    
    # Data retrieval methods
    def get_data_summary(self, period: str = None, project: str = None) -> Tuple[bool, Dict[str, Any]]:
        """Get data summary"""
        try:
            if not self.auth_token:
                return False, {"error": "Authentication required"}
            
            params = {}
            if period:
                params['period'] = period
            if project:
                params['project'] = project
            
            response = self.session.get(
                f"{self.base_url}/api/v1/data/summary",
                params=params,
                headers=self._get_headers()
            )
            
            result = self._handle_response(response)
            return True, result
                
        except Exception as e:
            logger.error(f"Data summary error: {str(e)}")
            return False, {"error": str(e)}
    
    def get_dl_costs(self, period: str = None, project: str = None, page: int = 1, limit: int = 50) -> Tuple[bool, Dict[str, Any]]:
        """Get DL cost records"""
        try:
            if not self.auth_token:
                return False, {"error": "Authentication required"}
            
            params = {'page': page, 'limit': limit}
            if period:
                params['period'] = period
            if project:
                params['project'] = project
            
            response = self.session.get(
                f"{self.base_url}/api/v1/data/dl-costs",
                params=params,
                headers=self._get_headers()
            )
            
            result = self._handle_response(response)
            return True, result
                
        except Exception as e:
            logger.error(f"DL costs error: {str(e)}")
            return False, {"error": str(e)}
    
    def get_vc_costs(self, period: str = None, project: str = None, page: int = 1, limit: int = 50) -> Tuple[bool, Dict[str, Any]]:
        """Get VC cost records"""
        try:
            if not self.auth_token:
                return False, {"error": "Authentication required"}
            
            params = {'page': page, 'limit': limit}
            if period:
                params['period'] = period
            if project:
                params['project'] = project
            
            response = self.session.get(
                f"{self.base_url}/api/v1/data/vc-costs",
                params=params,
                headers=self._get_headers()
            )
            
            result = self._handle_response(response)
            return True, result
                
        except Exception as e:
            logger.error(f"VC costs error: {str(e)}")
            return False, {"error": str(e)}
    
    def get_user_projects(self) -> Tuple[bool, List[Dict]]:
        """Get user's projects"""
        try:
            if not self.auth_token:
                return False, []
            
            response = self.session.get(
                f"{self.base_url}/api/v1/user/projects",
                headers=self._get_headers()
            )
            
            result = self._handle_response(response)
            return True, result.get('projects', [])
                
        except Exception as e:
            logger.error(f"Projects error: {str(e)}")
            return False, []
    
    # Export methods
    def create_excel_export(self, period: str = None, project: str = None, 
                           include_dl: bool = True, include_vc: bool = True) -> Tuple[bool, Dict[str, Any]]:
        """Create Excel export"""
        try:
            if not self.auth_token:
                return False, {"error": "Authentication required"}
            
            data = {
                'include_dl': include_dl,
                'include_vc': include_vc
            }
            if period:
                data['period'] = period
            if project:
                data['project'] = project
            
            response = self.session.post(
                f"{self.base_url}/api/v1/export/excel",
                json=data,
                headers=self._get_headers()
            )
            
            result = self._handle_response(response)
            return True, result
                
        except Exception as e:
            logger.error(f"Export creation error: {str(e)}")
            return False, {"error": str(e)}
    
    def download_file(self, download_id: str) -> Tuple[bool, bytes, str]:
        """Download file by ID"""
        try:
            if not self.auth_token:
                return False, b"", "error.txt"
            
            response = self.session.get(
                f"{self.base_url}/api/v1/downloads/{download_id}",
                headers={'Authorization': f'Bearer {self.auth_token}'}
            )
            
            if response.status_code == 200:
                # Extract filename from Content-Disposition header
                content_disposition = response.headers.get('Content-Disposition', '')
                filename = 'DirectCostMaster.xlsx'
                if 'filename=' in content_disposition:
                    filename = content_disposition.split('filename=')[1].strip('"')
                
                return True, response.content, filename
            else:
                return False, b"", "error.txt"
                
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            return False, b"", "error.txt"
    
    # Utility methods
    def clear_data(self, period: str = None, project: str = None) -> Tuple[bool, str]:
        """Clear user data"""
        try:
            if not self.auth_token:
                return False, "Authentication required"
            
            data = {}
            if period:
                data['period'] = period
            if project:
                data['project'] = project
            
            response = self.session.delete(
                f"{self.base_url}/api/v1/data/clear",
                json=data,
                headers=self._get_headers()
            )
            
            result = self._handle_response(response)
            
            if result.get('success'):
                return True, result.get('message', 'Data cleared')
            else:
                return False, result.get('message', 'Clear failed')
                
        except Exception as e:
            logger.error(f"Clear data error: {str(e)}")
            return False, str(e)
    
    def check_server_health(self) -> bool:
        """Check if server is available"""
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

    # Reconciliation client methods
    def propose_reconcile_program(self, file_id: str, month: str, year: str) -> Tuple[bool, Dict[str, Any]]:
        """Request a reconciliation proposal for a program-level P&L file."""
        try:
            if not self.auth_token:
                return False, {"error": "Authentication required"}

            data = {'file_id': file_id, 'month': month, 'year': year}
            response = self.session.post(
                f"{self.base_url}/api/v1/reconcile/program/propose",
                json=data,
                headers=self._get_headers()
            )

            result = self._handle_response(response)
            return True, result
        except Exception as e:
            logger.error(f"Propose reconcile error: {str(e)}")
            return False, {"error": str(e)}

    def apply_reconcile_program(self, file_id: str, month: str, year: str, additions: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        """Apply reconciliation additions approved by the user."""
        try:
            if not self.auth_token:
                return False, {"error": "Authentication required"}

            data = {'file_id': file_id, 'month': month, 'year': year, 'additions': additions}
            response = self.session.post(
                f"{self.base_url}/api/v1/reconcile/program/apply",
                json=data,
                headers=self._get_headers()
            )

            result = self._handle_response(response)
            return True, result
        except Exception as e:
            logger.error(f"Apply reconcile error: {str(e)}")
            return False, {"error": str(e)}
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.auth_token is not None
    
    def get_current_user(self) -> Optional[Dict]:
        """Get current user info"""
        return self.current_user


# Global API client instance
api_client = APIClientService()
