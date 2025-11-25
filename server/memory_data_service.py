"""
In-memory data service for storing and retrieving processed cost data
Replaces database storage for DL/VC records while keeping authentication in DB
"""

from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import pandas as pd
import io
import uuid
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DLRecord:
    """Direct Labor record in memory"""
    id: str
    project: str
    period: str
    employee: str
    ticket: str
    bucket: str
    dc_hours: Optional[float]
    total_dl_costs: float
    source_file: str
    created_at: datetime
    created_by: int


@dataclass
class VCRecord:
    """Variable Cost record in memory"""
    id: str
    project: str
    period: str
    item: str
    bucket: str
    total_dl_costs: float  # Despite name, this is VC costs
    source_file: str
    created_at: datetime
    created_by: int


@dataclass
class ProcessingLog:
    """Processing log record in memory"""
    id: str
    user_id: int
    filename: str
    period: str
    status: str  # 'success', 'failed', 'partial'
    records_processed: int
    error_message: Optional[str]
    processing_time_seconds: Optional[float]
    created_at: datetime


@dataclass
class InMemoryUserData:
    """Container for all user data in memory"""
    user_id: int
    dl_records: List[DLRecord] = field(default_factory=list)
    vc_records: List[VCRecord] = field(default_factory=list)
    processing_logs: List[ProcessingLog] = field(default_factory=list)
    projects: set = field(default_factory=set)  # Set of unique project names


class MemoryDataService:
    """Service for handling in-memory data operations for cost data"""
    
    def __init__(self):
        # In-memory storage: user_id -> InMemoryUserData
        self.user_data: Dict[int, InMemoryUserData] = {}
        
    def _get_user_data(self, user_id: int) -> InMemoryUserData:
        """Get or create user data container"""
        if user_id not in self.user_data:
            self.user_data[user_id] = InMemoryUserData(user_id=user_id)
        return self.user_data[user_id]
    
    def save_processed_data(self, processed_records: List[Dict], user_id: int, 
                           filename: str, period: str) -> Tuple[bool, str, int, int]:
        """
        Save processed records to memory
        
        Args:
            processed_records: List of processed record dictionaries
            user_id: ID of the user saving the data
            filename: Source filename
            period: Processing period (e.g., "June 2025")
            
        Returns:
            Tuple of (success, message, dl_count, vc_count)
        """
        start_time = datetime.utcnow()
        dl_count = 0
        vc_count = 0

        try:
            user_data = self._get_user_data(user_id)
            
            # Process records
            for record in processed_records:
                project_name = record.get('Project', 'Unknown')
                user_data.projects.add(project_name)
                
                # Determine record type based on presence of 'Employee' vs 'Item'
                # Use record-specific month if available (important for YTD processing)
                record_period = record.get('Month') or period

                if 'Employee' in record:
                    # Create DL record
                    dl_record = DLRecord(
                        id=str(uuid.uuid4()),
                        project=project_name,
                        period=record_period,
                        employee=record.get('Employee', ''),
                        ticket=record.get('Ticket', ''),
                        bucket=record.get('Bucket', ''),
                        dc_hours=record.get('DC Hours'),
                        total_dl_costs=record.get('Total DL costs', 0),
                        source_file=filename,
                        created_at=datetime.utcnow(),
                        created_by=user_id
                    )
                    user_data.dl_records.append(dl_record)
                    dl_count += 1
                    
                elif 'Item' in record:
                    # Create VC record
                    vc_record = VCRecord(
                        id=str(uuid.uuid4()),
                        project=project_name,
                        period=record_period,
                        item=record.get('Item', ''),
                        bucket=record.get('Bucket', ''),
                        total_dl_costs=record.get('Total DL costs', 0),  # Note: despite name, this is VC costs
                        source_file=filename,
                        created_at=datetime.utcnow(),
                        created_by=user_id
                    )
                    user_data.vc_records.append(vc_record)
                    vc_count += 1

            # Create processing log
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            log_entry = ProcessingLog(
                id=str(uuid.uuid4()),
                user_id=user_id,
                filename=filename,
                period=period,
                status='success',
                records_processed=dl_count + vc_count,
                error_message=None,
                processing_time_seconds=processing_time,
                created_at=datetime.utcnow()
            )
            user_data.processing_logs.append(log_entry)

            message = f"Successfully saved {dl_count} DL records and {vc_count} VC records in memory"
            logger.info(f"Data saved to memory: {message}")
            return True, message, dl_count, vc_count

        except Exception as e:
            # Create error log
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            try:
                user_data = self._get_user_data(user_id)
                log_entry = ProcessingLog(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    filename=filename,
                    period=period,
                    status='failed',
                    records_processed=0,
                    error_message=str(e),
                    processing_time_seconds=processing_time,
                    created_at=datetime.utcnow()
                )
                user_data.processing_logs.append(log_entry)
            except:
                pass

            logger.error(f"Error saving data to memory: {str(e)}")
            return False, f"Failed to save data: {str(e)}", 0, 0
    
    def get_user_data(self, user_id: int, period: str = None, 
                      project_name: str = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Get user's processed data as DataFrames
        
        Args:
            user_id: User ID
            period: Optional period filter
            project_name: Optional project name filter
            
        Returns:
            Tuple of (dl_dataframe, vc_dataframe)
        """
        try:
            user_data = self._get_user_data(user_id)
            
            # Filter DL records
            dl_data = []
            for record in user_data.dl_records:
                # Apply filters
                if period and record.period != period:
                    continue
                if project_name and record.project != project_name:
                    continue
                    
                dl_data.append({
                    'Project': record.project,
                    'Period': record.period,
                    'Employee': record.employee,
                    'Ticket': record.ticket,
                    'Bucket': record.bucket,
                    'DC Hours': record.dc_hours,
                    'Total DL costs': record.total_dl_costs,
                    'Source File': record.source_file,
                    'Created At': record.created_at
                })
            
            # Filter VC records
            vc_data = []
            for record in user_data.vc_records:
                # Apply filters
                if period and record.period != period:
                    continue
                if project_name and record.project != project_name:
                    continue
                    
                vc_data.append({
                    'Project': record.project,
                    'Period': record.period,
                    'Item': record.item,
                    'Bucket': record.bucket,
                    'Total DL costs': record.total_dl_costs,  # Note: despite name, this is VC costs
                    'Source File': record.source_file,
                    'Created At': record.created_at
                })
            
            # Convert to DataFrames
            dl_df = pd.DataFrame(dl_data) if dl_data else pd.DataFrame()
            vc_df = pd.DataFrame(vc_data) if vc_data else pd.DataFrame()
            
            return dl_df, vc_df
            
        except Exception as e:
            logger.error(f"Error retrieving user data from memory: {str(e)}")
            return pd.DataFrame(), pd.DataFrame()
    
    def get_user_projects(self, user_id: int) -> List[Dict]:
        """
        Get list of user's projects
        
        Args:
            user_id: User ID
            
        Returns:
            List of project dictionaries
        """
        try:
            user_data = self._get_user_data(user_id)
            
            project_list = []
            for project_name in user_data.projects:
                # Count records for this project
                dl_count = len([r for r in user_data.dl_records if r.project == project_name])
                vc_count = len([r for r in user_data.vc_records if r.project == project_name])
                
                # Get creation date (earliest record for this project)
                creation_dates = []
                for r in user_data.dl_records:
                    if r.project == project_name:
                        creation_dates.append(r.created_at)
                for r in user_data.vc_records:
                    if r.project == project_name:
                        creation_dates.append(r.created_at)
                
                created_at = min(creation_dates) if creation_dates else datetime.utcnow()
                
                project_list.append({
                    'id': hash(project_name),  # Use hash as fake ID
                    'name': project_name,
                    'description': f"In-memory project for {project_name}",
                    'created_at': created_at,
                    'dl_records': dl_count,
                    'vc_records': vc_count,
                    'total_records': dl_count + vc_count
                })
            
            # Sort by creation date
            project_list.sort(key=lambda x: x['created_at'], reverse=True)
            return project_list
            
        except Exception as e:
            logger.error(f"Error retrieving user projects from memory: {str(e)}")
            return []
    
    def get_processing_history(self, user_id: int, limit: int = 50) -> List[Dict]:
        """
        Get user's processing history
        
        Args:
            user_id: User ID
            limit: Maximum number of records to return
            
        Returns:
            List of processing log dictionaries
        """
        try:
            user_data = self._get_user_data(user_id)
            
            # Sort by creation date (newest first) and apply limit
            sorted_logs = sorted(user_data.processing_logs, 
                               key=lambda x: x.created_at, reverse=True)[:limit]
            
            history = []
            for log in sorted_logs:
                history.append({
                    'id': log.id,
                    'filename': log.filename,
                    'period': log.period,
                    'status': log.status,
                    'records_processed': log.records_processed,
                    'error_message': log.error_message,
                    'processing_time_seconds': log.processing_time_seconds,
                    'created_at': log.created_at
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error retrieving processing history from memory: {str(e)}")
            return []
    
    def clear_user_data(self, user_id: int, period: str = None, project_name: str = None) -> Tuple[bool, str]:
        """
        Clear user's data (with optional filters)
        
        Args:
            user_id: User ID
            period: Optional period filter
            project_name: Optional project name filter
            
        Returns:
            Tuple of (success, message)
        """
        try:
            user_data = self._get_user_data(user_id)
            
            dl_deleted = 0
            vc_deleted = 0
            
            # Filter and remove DL records
            new_dl_records = []
            for record in user_data.dl_records:
                should_delete = True
                if period and record.period != period:
                    should_delete = False
                if project_name and record.project != project_name:
                    should_delete = False
                    
                if should_delete:
                    dl_deleted += 1
                else:
                    new_dl_records.append(record)
            
            # Filter and remove VC records
            new_vc_records = []
            for record in user_data.vc_records:
                should_delete = True
                if period and record.period != period:
                    should_delete = False
                if project_name and record.project != project_name:
                    should_delete = False
                    
                if should_delete:
                    vc_deleted += 1
                else:
                    new_vc_records.append(record)
            
            # Update records
            user_data.dl_records = new_dl_records
            user_data.vc_records = new_vc_records
            
            # Update projects set (remove projects with no records)
            remaining_projects = set()
            for record in user_data.dl_records + user_data.vc_records:
                remaining_projects.add(record.project)
            user_data.projects = remaining_projects
            
            message = f"Deleted {dl_deleted} DL records and {vc_deleted} VC records from memory"
            logger.info(f"User data cleared from memory: {message}")
            return True, message
            
        except Exception as e:
            logger.error(f"Error clearing user data from memory: {str(e)}")
            return False, f"Failed to clear data: {str(e)}"
    
    def export_user_data_to_excel(self, user_id: int, period: str = None, 
                                  project_name: str = None) -> Optional[bytes]:
        """
        Export user's data to Excel format
        
        Args:
            user_id: User ID
            period: Optional period filter
            project_name: Optional project name filter
            
        Returns:
            Excel file as bytes or None if failed
        """
        try:
            dl_df, vc_df = self.get_user_data(user_id, period, project_name)
            
            if dl_df.empty and vc_df.empty:
                return None
            
            # Create Excel file in memory
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                if not dl_df.empty:
                    dl_df.to_excel(writer, sheet_name='DL Costs', index=False)
                if not vc_df.empty:
                    vc_df.to_excel(writer, sheet_name='VC Costs', index=False)
            
            output.seek(0)
            return output.read()
            
        except Exception as e:
            logger.error(f"Error exporting user data to Excel from memory: {str(e)}")
            return None
    
    def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive statistics about user's data
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with statistics
        """
        try:
            user_data = self._get_user_data(user_id)
            
            # Basic counts
            total_dl = len(user_data.dl_records)
            total_vc = len(user_data.vc_records)
            total_records = total_dl + total_vc
            
            # Unique periods
            periods = set()
            for record in user_data.dl_records + user_data.vc_records:
                periods.add(record.period)
            
            # Cost totals
            total_dl_costs = sum(r.total_dl_costs for r in user_data.dl_records)
            total_vc_costs = sum(r.total_dl_costs for r in user_data.vc_records)
            
            # Bucket distribution
            dl_buckets = {}
            for record in user_data.dl_records:
                dl_buckets[record.bucket] = dl_buckets.get(record.bucket, 0) + 1
                
            vc_buckets = {}
            for record in user_data.vc_records:
                vc_buckets[record.bucket] = vc_buckets.get(record.bucket, 0) + 1
            
            return {
                'total_records': total_records,
                'dl_records': total_dl,
                'vc_records': total_vc,
                'unique_projects': len(user_data.projects),
                'unique_periods': len(periods),
                'total_dl_costs': round(total_dl_costs, 2),
                'total_vc_costs': round(total_vc_costs, 2),
                'periods': sorted(list(periods)),
                'projects': sorted(list(user_data.projects)),
                'dl_bucket_distribution': dl_buckets,
                'vc_bucket_distribution': vc_buckets
            }
            
        except Exception as e:
            logger.error(f"Error getting user statistics from memory: {str(e)}")
            return {
                'total_records': 0,
                'dl_records': 0,
                'vc_records': 0,
                'unique_projects': 0,
                'unique_periods': 0,
                'total_dl_costs': 0.0,
                'total_vc_costs': 0.0,
                'periods': [],
                'projects': [],
                'dl_bucket_distribution': {},
                'vc_bucket_distribution': {}
            }
    
    def clear_all_user_data(self, user_id: int) -> bool:
        """
        Clear all data for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Success status
        """
        try:
            if user_id in self.user_data:
                del self.user_data[user_id]
                logger.info(f"Cleared all data for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing all user data: {str(e)}")
            return False
    
    def get_memory_usage_stats(self) -> Dict[str, Any]:
        """
        Get statistics about memory usage
        
        Returns:
            Dictionary with memory usage statistics
        """
        try:
            total_users = len(self.user_data)
            total_dl_records = 0
            total_vc_records = 0
            total_projects = set()
            
            for user_data in self.user_data.values():
                total_dl_records += len(user_data.dl_records)
                total_vc_records += len(user_data.vc_records)
                total_projects.update(user_data.projects)
            
            return {
                'total_users': total_users,
                'total_dl_records': total_dl_records,
                'total_vc_records': total_vc_records,
                'total_records': total_dl_records + total_vc_records,
                'unique_projects': len(total_projects),
                'average_records_per_user': (total_dl_records + total_vc_records) / max(total_users, 1)
            }
        except Exception as e:
            logger.error(f"Error getting memory usage stats: {str(e)}")
            return {}


# Global memory data service instance
memory_data_service = MemoryDataService()
