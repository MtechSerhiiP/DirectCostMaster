"""
In-memory data service for storing and retrieving processed cost data
Replaces database storage for DL/VC records while keeping authentication in DB
"""

from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import pandas as pd
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
class InMemoryUserData:
    """Container for all user data in memory"""
    user_id: int
    dl_records: List[DLRecord] = field(default_factory=list)
    vc_records: List[VCRecord] = field(default_factory=list)
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

            message = f"Successfully saved {dl_count} DL records and {vc_count} VC records in memory"
            logger.info(f"Data saved to memory: {message}")
            return True, message, dl_count, vc_count

        except Exception as e:
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


# Global memory data service instance
memory_data_service = MemoryDataService()
