"""
Database service for storing and retrieving processed cost data
"""

from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime
import pandas as pd
import io
from models import (
    Project, DLCostRecord, VCCostRecord, ProcessingLog, 
    User, db_config
)
import logging

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for handling database operations for cost data"""
    
    def __init__(self):
        pass
    
    def create_or_get_project(self, project_name: str, user_id: int, description: str = None, db_session: Session = None) -> Optional[Project]:
        """
        Create a new project or get existing one
        
        Args:
            project_name: Name of the project
            user_id: ID of the user creating the project
            description: Optional project description
            
        Returns:
            Project object or None if failed
        """
        # NOTE: accept an external session in future to avoid detached instances
        external_session = db_session is not None
        if not external_session:
            db_session = db_config.get_session()
        try:
            # Check if project already exists
            existing_project = db_session.query(Project).filter(
                and_(
                    Project.name == project_name,
                    Project.is_active == True
                )
            ).first()

            if existing_project:
                return existing_project

            # Create new project
            new_project = Project(
                name=project_name,
                description=description,
                created_by=user_id
            )

            db_session.add(new_project)
            db_session.commit()

            logger.info(f"Created new project: {project_name}")
            return new_project

        except Exception as e:
            db_session.rollback()
            logger.error(f"Error creating project: {str(e)}")
            return None
        finally:
            if not external_session:
                db_session.close()
    
    def save_processed_data(self, processed_records: List[Dict], user_id: int, 
                           filename: str, period: str) -> Tuple[bool, str, int, int]:
        """
        Save processed records to database
        
        Args:
            processed_records: List of processed record dictionaries
            user_id: ID of the user saving the data
            filename: Source filename
            period: Processing period (e.g., "June 2025")
            
        Returns:
            Tuple of (success, message, dl_count, vc_count)
        """
        db_session = db_config.get_session()
        start_time = datetime.utcnow()
        dl_count = 0
        vc_count = 0

        try:
            # Group records by project
            projects_data = {}
            for record in processed_records:
                project_name = record.get('Project', 'Unknown')
                if project_name not in projects_data:
                    projects_data[project_name] = {'dl': [], 'vc': []}

                # Determine record type based on presence of 'Employee' vs 'Item'
                if 'Employee' in record:
                    projects_data[project_name]['dl'].append(record)
                elif 'Item' in record:
                    projects_data[project_name]['vc'].append(record)

            # Process each project
            for project_name, data in projects_data.items():
                # Create or get project using same session to keep instance bound
                project = self.create_or_get_project(project_name, user_id, db_session=db_session)
                if not project:
                    continue

                # Save DL records
                for dl_record in data['dl']:
                    db_dl_record = DLCostRecord(
                        project_id=project.id,
                        period=period,
                        employee=dl_record.get('Employee', ''),
                        ticket=dl_record.get('Ticket', ''),
                        bucket=dl_record.get('Bucket', ''),
                        dc_hours=dl_record.get('DC Hours'),
                        total_dl_costs=dl_record.get('Total DL costs', 0),
                        source_file=filename,
                        created_by=user_id
                    )
                    db_session.add(db_dl_record)
                    dl_count += 1

                # Save VC records
                for vc_record in data['vc']:
                    db_vc_record = VCCostRecord(
                        project_id=project.id,
                        period=period,
                        item=vc_record.get('Item', ''),
                        bucket=vc_record.get('Bucket', ''),
                        total_dl_costs=vc_record.get('Total DL costs', 0),  # Note: despite name, this is VC costs
                        source_file=filename,
                        created_by=user_id
                    )
                    db_session.add(db_vc_record)
                    vc_count += 1

            # Create processing log
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            log_entry = ProcessingLog(
                user_id=user_id,
                filename=filename,
                period=period,
                status='success',
                records_processed=dl_count + vc_count,
                processing_time_seconds=processing_time
            )
            db_session.add(log_entry)

            db_session.commit()

            message = f"Successfully saved {dl_count} DL records and {vc_count} VC records for {len(projects_data)} projects"
            logger.info(f"Data saved to database: {message}")
            return True, message, dl_count, vc_count

        except Exception as e:
            db_session.rollback()

            # Log the error
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            try:
                log_entry = ProcessingLog(
                    user_id=user_id,
                    filename=filename,
                    period=period,
                    status='failed',
                    records_processed=0,
                    error_message=str(e),
                    processing_time_seconds=processing_time
                )
                db_session.add(log_entry)
                db_session.commit()
            except:
                pass

            logger.error(f"Error saving data to database: {str(e)}")
            return False, f"Failed to save data: {str(e)}", 0, 0

        finally:
            db_session.close()
    
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
        db_session = db_config.get_session()
        try:
            # Build query filters
            dl_filters = [DLCostRecord.created_by == user_id]
            vc_filters = [VCCostRecord.created_by == user_id]
            
            if period:
                dl_filters.append(DLCostRecord.period == period)
                vc_filters.append(VCCostRecord.period == period)
            
            if project_name:
                # Join with Project table for name filtering
                dl_query = db_session.query(DLCostRecord).join(Project).filter(
                    and_(*dl_filters, Project.name == project_name)
                )
                vc_query = db_session.query(VCCostRecord).join(Project).filter(
                    and_(*vc_filters, Project.name == project_name)
                )
            else:
                dl_query = db_session.query(DLCostRecord).filter(and_(*dl_filters))
                vc_query = db_session.query(VCCostRecord).filter(and_(*vc_filters))
            
            # Get DL records
            dl_records = dl_query.all()
            dl_data = []
            for record in dl_records:
                dl_data.append({
                    'Project': record.project.name,
                    'Period': record.period,
                    'Employee': record.employee,
                    'Ticket': record.ticket,
                    'Bucket': record.bucket,
                    'DC Hours': record.dc_hours,
                    'Total DL costs': record.total_dl_costs,
                    'Source File': record.source_file,
                    'Created At': record.created_at
                })
            
            # Get VC records
            vc_records = vc_query.all()
            vc_data = []
            for record in vc_records:
                vc_data.append({
                    'Project': record.project.name,
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
            logger.error(f"Error retrieving user data: {str(e)}")
            return pd.DataFrame(), pd.DataFrame()
        finally:
            db_session.close()
    
    def get_user_projects(self, user_id: int) -> List[Dict]:
        """
        Get list of user's projects
        
        Args:
            user_id: User ID
            
        Returns:
            List of project dictionaries
        """
        db_session = db_config.get_session()
        try:
            projects = db_session.query(Project).filter(
                and_(
                    Project.created_by == user_id,
                    Project.is_active == True
                )
            ).all()
            
            project_list = []
            for project in projects:
                # Count records
                dl_count = db_session.query(DLCostRecord).filter(
                    DLCostRecord.project_id == project.id
                ).count()
                vc_count = db_session.query(VCCostRecord).filter(
                    VCCostRecord.project_id == project.id
                ).count()
                
                project_list.append({
                    'id': project.id,
                    'name': project.name,
                    'description': project.description,
                    'created_at': project.created_at,
                    'dl_records': dl_count,
                    'vc_records': vc_count,
                    'total_records': dl_count + vc_count
                })
            
            return project_list
            
        except Exception as e:
            logger.error(f"Error retrieving user projects: {str(e)}")
            return []
        finally:
            db_session.close()
    
    def get_processing_history(self, user_id: int, limit: int = 50) -> List[Dict]:
        """
        Get user's processing history
        
        Args:
            user_id: User ID
            limit: Maximum number of records to return
            
        Returns:
            List of processing log dictionaries
        """
        db_session = db_config.get_session()
        try:
            logs = db_session.query(ProcessingLog).filter(
                ProcessingLog.user_id == user_id
            ).order_by(ProcessingLog.created_at.desc()).limit(limit).all()
            
            history = []
            for log in logs:
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
            logger.error(f"Error retrieving processing history: {str(e)}")
            return []
        finally:
            db_session.close()
    
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
        db_session = db_config.get_session()
        try:
            dl_deleted = 0
            vc_deleted = 0
            
            # Build filters
            if project_name:
                # Get project ID
                project = db_session.query(Project).filter(
                    and_(
                        Project.name == project_name,
                        Project.created_by == user_id,
                        Project.is_active == True
                    )
                ).first()
                
                if project:
                    dl_filters = [DLCostRecord.project_id == project.id]
                    vc_filters = [VCCostRecord.project_id == project.id]
                else:
                    return True, "No matching project found"
            else:
                dl_filters = [DLCostRecord.created_by == user_id]
                vc_filters = [VCCostRecord.created_by == user_id]
            
            if period:
                dl_filters.append(DLCostRecord.period == period)
                vc_filters.append(VCCostRecord.period == period)
            
            # Delete DL records
            dl_deleted = db_session.query(DLCostRecord).filter(and_(*dl_filters)).delete()
            
            # Delete VC records
            vc_deleted = db_session.query(VCCostRecord).filter(and_(*vc_filters)).delete()
            
            db_session.commit()
            
            message = f"Deleted {dl_deleted} DL records and {vc_deleted} VC records"
            logger.info(f"User data cleared: {message}")
            return True, message
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error clearing user data: {str(e)}")
            return False, f"Failed to clear data: {str(e)}"
        finally:
            db_session.close()
    
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
            logger.error(f"Error exporting user data to Excel: {str(e)}")
            return None


# Global database service instance
db_service = DatabaseService()
