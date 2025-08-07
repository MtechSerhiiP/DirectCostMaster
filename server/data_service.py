"""
Data API Service
Handles data retrieval, export, and management for the API
"""

import io
import uuid
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging

# Import existing services
from database_service import db_service

logger = logging.getLogger(__name__)


class DataAPIService:
    """Service for data operations in API context"""
    
    def __init__(self):
        # Temporary storage for export files
        self.export_files: Dict[str, Dict[str, Any]] = {}
        
        # Export file storage directory
        self.export_dir = Path('./temp_exports')
        self.export_dir.mkdir(exist_ok=True)
    
    def get_user_data_summary(self, user_id: int, period: str = None, project: str = None) -> Dict[str, Any]:
        """
        Get comprehensive summary of user's data
        
        Args:
            user_id: User ID
            period: Optional period filter
            project: Optional project filter
            
        Returns:
            Dictionary with summary information
        """
        try:
            # Get data from database service
            dl_df, vc_df = db_service.get_user_data(user_id, period, project)
            
            # Calculate summary statistics
            total_records = len(dl_df) + len(vc_df)
            dl_records = len(dl_df)
            vc_records = len(vc_df)
            
            # Get unique projects and employees
            unique_projects = set()
            unique_employees = set()
            
            if not dl_df.empty:
                if 'Project' in dl_df.columns:
                    unique_projects.update(dl_df['Project'].unique())
                if 'Employee' in dl_df.columns:
                    unique_employees.update(dl_df['Employee'].unique())
            
            if not vc_df.empty:
                if 'Project' in vc_df.columns:
                    unique_projects.update(vc_df['Project'].unique())
            
            # Get all available periods and projects for user
            all_dl_df, all_vc_df = db_service.get_user_data(user_id)
            
            all_periods = set()
            all_projects = set()
            
            if not all_dl_df.empty:
                if 'Period' in all_dl_df.columns:
                    all_periods.update(all_dl_df['Period'].unique())
                if 'Project' in all_dl_df.columns:
                    all_projects.update(all_dl_df['Project'].unique())
            
            if not all_vc_df.empty:
                if 'Period' in all_vc_df.columns:
                    all_periods.update(all_vc_df['Period'].unique())
                if 'Project' in all_vc_df.columns:
                    all_projects.update(all_vc_df['Project'].unique())
            
            return {
                'summary': {
                    'total_records': total_records,
                    'dl_records': dl_records,
                    'vc_records': vc_records,
                    'unique_projects': len(unique_projects),
                    'unique_employees': len(unique_employees)
                },
                'periods': sorted(list(all_periods)),
                'projects': sorted(list(all_projects))
            }
            
        except Exception as e:
            logger.error(f"Error getting data summary: {str(e)}")
            raise
    
    def get_dl_cost_records(self, user_id: int, period: str = None, project: str = None, 
                           page: int = 1, limit: int = 50) -> Dict[str, Any]:
        """
        Get DL cost records with pagination
        
        Args:
            user_id: User ID
            period: Optional period filter
            project: Optional project filter
            page: Page number (1-based)
            limit: Records per page
            
        Returns:
            Dictionary with records and pagination info
        """
        try:
            # Get all matching records
            dl_df, _ = db_service.get_user_data(user_id, period, project)
            
            if dl_df.empty:
                return {
                    'records': [],
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total': 0,
                        'pages': 0
                    }
                }
            
            # Calculate pagination
            total = len(dl_df)
            pages = (total + limit - 1) // limit  # Ceiling division
            offset = (page - 1) * limit
            
            # Get page of records
            page_df = dl_df.iloc[offset:offset + limit]
            
            # Convert to list of dictionaries
            records = []
            for _, row in page_df.iterrows():
                record = {
                    'employee': row.get('Employee', ''),
                    'project': row.get('Project', ''),
                    'month': row.get('Period', ''),
                    'bucket': row.get('Bucket', ''),
                    'dc_hours': row.get('DC Hours'),
                    'total_dl_costs': float(row.get('Total DL costs', 0)),
                    'source_file': row.get('Source File'),
                    'created_at': row.get('Created At')
                }
                records.append(record)
            
            return {
                'records': records,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'pages': pages
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting DL cost records: {str(e)}")
            raise
    
    def get_vc_cost_records(self, user_id: int, period: str = None, project: str = None,
                           page: int = 1, limit: int = 50) -> Dict[str, Any]:
        """
        Get VC cost records with pagination
        
        Args:
            user_id: User ID
            period: Optional period filter
            project: Optional project filter
            page: Page number (1-based)
            limit: Records per page
            
        Returns:
            Dictionary with records and pagination info
        """
        try:
            # Get all matching records
            _, vc_df = db_service.get_user_data(user_id, period, project)
            
            if vc_df.empty:
                return {
                    'records': [],
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total': 0,
                        'pages': 0
                    }
                }
            
            # Calculate pagination
            total = len(vc_df)
            pages = (total + limit - 1) // limit  # Ceiling division
            offset = (page - 1) * limit
            
            # Get page of records
            page_df = vc_df.iloc[offset:offset + limit]
            
            # Convert to list of dictionaries
            records = []
            for _, row in page_df.iterrows():
                record = {
                    'item': row.get('Item', ''),
                    'project': row.get('Project', ''),
                    'month': row.get('Period', ''),
                    'bucket': row.get('Bucket', ''),
                    'total_dl_costs': float(row.get('Total DL costs', 0)),  # Despite name, this is VC costs
                    'source_file': row.get('Source File'),
                    'created_at': row.get('Created At')
                }
                records.append(record)
            
            return {
                'records': records,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'pages': pages
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting VC cost records: {str(e)}")
            raise
    
    def create_excel_export(self, user_id: int, period: str = None, project: str = None,
                           include_dl: bool = True, include_vc: bool = True) -> Dict[str, Any]:
        """
        Create Excel export file
        
        Args:
            user_id: User ID
            period: Optional period filter
            project: Optional project filter
            include_dl: Include DL costs
            include_vc: Include VC costs
            
        Returns:
            Dictionary with download information
        """
        try:
            # Get data
            dl_df, vc_df = db_service.get_user_data(user_id, period, project)
            
            if (dl_df.empty and vc_df.empty) or (not include_dl and not include_vc):
                raise ValueError("No data to export")
            
            # Create Excel file in memory
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Export DL data if requested and available
                if include_dl and not dl_df.empty:
                    # Select and reorder columns for export
                    dl_export_columns = ['Project', 'Period', 'Employee', 'Bucket', 'DC Hours', 'Total DL costs', 'Source File']
                    dl_export_df = dl_df.reindex(columns=dl_export_columns).fillna('')
                    dl_export_df.to_excel(writer, sheet_name='DL Costs', index=False)
                
                # Export VC data if requested and available
                if include_vc and not vc_df.empty:
                    # Select and reorder columns for export
                    vc_export_columns = ['Project', 'Period', 'Item', 'Bucket', 'Total DL costs', 'Source File']
                    vc_export_df = vc_df.reindex(columns=vc_export_columns).fillna('')
                    vc_export_df.to_excel(writer, sheet_name='VC Costs', index=False)
            
            output.seek(0)
            excel_bytes = output.getvalue()
            
            # Generate download info
            download_id = str(uuid.uuid4())
            
            # Create filename
            filename_parts = ['DirectCostMaster']
            if project:
                filename_parts.append(project.replace(' ', '_'))
            if period:
                filename_parts.append(period.replace(' ', '_'))
            filename = '_'.join(filename_parts) + '.xlsx'
            
            # Store export file temporarily
            expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
            
            self.export_files[download_id] = {
                'filename': filename,
                'content': excel_bytes,
                'user_id': user_id,
                'created_at': datetime.utcnow(),
                'expires_at': expires_at
            }
            
            # Clean up expired exports
            self._cleanup_expired_exports()
            
            return {
                'success': True,
                'download_url': f'/api/v1/downloads/{download_id}',
                'expires_at': expires_at,
                'filename': filename
            }
            
        except Exception as e:
            logger.error(f"Error creating Excel export: {str(e)}")
            raise
    
    def get_download_file(self, download_id: str, user_id: int) -> Tuple[bytes, str]:
        """
        Get download file by ID
        
        Args:
            download_id: Download identifier
            user_id: User ID for validation
            
        Returns:
            Tuple of (file_content, filename)
        """
        export_info = self.export_files.get(download_id)
        
        if not export_info:
            raise ValueError("Download not found or expired")
        
        if export_info['user_id'] != user_id:
            raise ValueError("Unauthorized access to download")
        
        if datetime.utcnow() > export_info['expires_at']:
            # Clean up expired file
            del self.export_files[download_id]
            raise ValueError("Download expired")
        
        return export_info['content'], export_info['filename']
    
    def clear_user_data(self, user_id: int, period: str = None, project: str = None) -> Tuple[bool, str]:
        """
        Clear user's data
        
        Args:
            user_id: User ID
            period: Optional period filter
            project: Optional project filter
            
        Returns:
            Tuple of (success, message)
        """
        try:
            return db_service.clear_user_data(user_id, period, project)
        except Exception as e:
            logger.error(f"Error clearing user data: {str(e)}")
            return False, f"Failed to clear data: {str(e)}"
    
    def get_user_projects(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get user's projects
        
        Args:
            user_id: User ID
            
        Returns:
            List of project dictionaries
        """
        try:
            projects = db_service.get_user_projects(user_id)
            
            # Convert to API format
            api_projects = []
            for project in projects:
                api_projects.append({
                    'id': project['id'],
                    'name': project['name'],
                    'dl_records': project['dl_records'],
                    'vc_records': project['vc_records'],
                    'created_at': project['created_at']
                })
            
            return api_projects
            
        except Exception as e:
            logger.error(f"Error getting user projects: {str(e)}")
            raise
    
    def _cleanup_expired_exports(self):
        """Clean up expired export files"""
        try:
            current_time = datetime.utcnow()
            expired_downloads = []
            
            for download_id, export_info in self.export_files.items():
                if current_time > export_info['expires_at']:
                    expired_downloads.append(download_id)
            
            for download_id in expired_downloads:
                del self.export_files[download_id]
                logger.debug(f"Cleaned up expired export: {download_id}")
            
            if expired_downloads:
                logger.info(f"Cleaned up {len(expired_downloads)} expired exports")
                
        except Exception as e:
            logger.error(f"Error cleaning up exports: {str(e)}")
    
    def get_user_data_statistics(self, user_id: int) -> Dict[str, Any]:
        """
        Get detailed statistics about user's data
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with detailed statistics
        """
        try:
            dl_df, vc_df = db_service.get_user_data(user_id)
            
            stats = {
                'total_records': len(dl_df) + len(vc_df),
                'dl_records': len(dl_df),
                'vc_records': len(vc_df),
                'bucket_distribution': {},
                'project_distribution': {},
                'period_distribution': {},
                'cost_summary': {}
            }
            
            # Analyze DL data
            if not dl_df.empty:
                # Bucket distribution
                if 'Bucket' in dl_df.columns:
                    bucket_counts = dl_df['Bucket'].value_counts().to_dict()
                    stats['bucket_distribution']['dl'] = bucket_counts
                
                # Cost summary
                if 'Total DL costs' in dl_df.columns:
                    total_dl_costs = dl_df['Total DL costs'].sum()
                    stats['cost_summary']['total_dl_costs'] = float(total_dl_costs)
            
            # Analyze VC data
            if not vc_df.empty:
                # Bucket distribution
                if 'Bucket' in vc_df.columns:
                    bucket_counts = vc_df['Bucket'].value_counts().to_dict()
                    stats['bucket_distribution']['vc'] = bucket_counts
                
                # Cost summary
                if 'Total DL costs' in vc_df.columns:  # Despite name, this is VC costs
                    total_vc_costs = vc_df['Total DL costs'].sum()
                    stats['cost_summary']['total_vc_costs'] = float(total_vc_costs)
            
            # Combined analysis
            combined_df = pd.concat([dl_df, vc_df], ignore_index=True)
            if not combined_df.empty:
                # Project distribution
                if 'Project' in combined_df.columns:
                    project_counts = combined_df['Project'].value_counts().to_dict()
                    stats['project_distribution'] = project_counts
                
                # Period distribution
                if 'Period' in combined_df.columns:
                    period_counts = combined_df['Period'].value_counts().to_dict()
                    stats['period_distribution'] = period_counts
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting data statistics: {str(e)}")
            raise


# Global data service instance
data_api_service = DataAPIService()
