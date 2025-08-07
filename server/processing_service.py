"""
Processing API Service
Handles file upload storage and asynchronous processing for the API
"""

import os
import io
import uuid
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import logging
from pathlib import Path

# Import existing processing logic
from dc_processor import DirectCostProcessor
from database_service import db_service

logger = logging.getLogger(__name__)


class ProcessingAPIService:
    """Service for handling file processing in API context"""
    
    def __init__(self):
        # Temporary file storage (in production, use Redis or database)
        self.uploaded_files: Dict[str, Dict[str, Any]] = {}
        self.processing_jobs: Dict[str, Dict[str, Any]] = {}
        
        # Create processor instance
        self.dc_processor = DirectCostProcessor()
        
        # Temporary storage directory
        self.temp_dir = Path(os.getenv('TEMP_FILE_DIR', './temp_files'))
        self.temp_dir.mkdir(exist_ok=True)
    
    def store_uploaded_file(self, file_id: str, filename: str, content: bytes, user_id: int) -> Dict[str, Any]:
        """
        Store uploaded file temporarily
        
        Args:
            file_id: Unique file identifier
            filename: Original filename
            content: File content as bytes
            user_id: User ID who uploaded the file
            
        Returns:
            Dictionary with file information
        """
        try:
            # Validate Excel file by trying to read it
            file_io = io.BytesIO(content)
            excel_data = pd.read_excel(file_io, sheet_name=None, engine='openpyxl')
            sheets_count = len(excel_data)
            
            # Store file info
            file_info = {
                'file_id': file_id,
                'filename': filename,
                'content': content,
                'user_id': user_id,
                'sheets_count': sheets_count,
                'uploaded_at': datetime.utcnow(),
                'status': 'uploaded'
            }
            
            self.uploaded_files[file_id] = file_info
            
            logger.info(f"File stored: {filename} (ID: {file_id}, Sheets: {sheets_count})")
            
            return {
                'filename': filename,
                'file_id': file_id,
                'sheets_count': sheets_count,
                'status': 'uploaded'
            }
            
        except Exception as e:
            logger.error(f"Error storing file {filename}: {str(e)}")
            raise ValueError(f"Invalid Excel file: {str(e)}")
    
    def get_uploaded_file(self, file_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get uploaded file by ID (with user validation)
        
        Args:
            file_id: File identifier
            user_id: User ID for validation
            
        Returns:
            File info or None if not found/unauthorized
        """
        file_info = self.uploaded_files.get(file_id)
        if file_info and file_info['user_id'] == user_id:
            return file_info
        return None
    
    async def process_files_async(self, job_id: str, file_ids: List[str], month: str, year: str, user_id: int):
        """
        Asynchronously process multiple files
        
        Args:
            job_id: Processing job identifier
            file_ids: List of file IDs to process
            month: Target month
            year: Target year
            user_id: User ID
        """
        # Initialize job status
        self.processing_jobs[job_id] = {
            'job_id': job_id,
            'status': 'processing',
            'progress': 0,
            'user_id': user_id,
            'started_at': datetime.utcnow(),
            'file_ids': file_ids,
            'period': f"{month} {year}",
            'results': None,
            'error_message': None
        }
        
        try:
            total_files = len(file_ids)
            processed_files = 0
            successful_files = 0
            failed_files = []
            all_records = []
            
            for i, file_id in enumerate(file_ids):
                try:
                    # Update progress
                    progress = int((i / total_files) * 100)
                    self.processing_jobs[job_id]['progress'] = progress
                    
                    # Get file
                    file_info = self.get_uploaded_file(file_id, user_id)
                    if not file_info:
                        failed_files.append(f"File {file_id} not found")
                        continue
                    
                    # Process file
                    file_content = file_info['content']
                    filename = file_info['filename']
                    
                    # Create BytesIO object and read Excel data
                    file_io = io.BytesIO(file_content)
                    excel_data = pd.read_excel(file_io, sheet_name=None, engine='openpyxl')
                    
                    # Process using existing DC processor
                    selected_period = f"{month} {year}"
                    processed_records = self.dc_processor.process_file_for_month(
                        excel_data, 
                        filename,
                        selected_period
                    )
                    
                    if processed_records:
                        all_records.extend(processed_records)
                        successful_files += 1
                        
                        # Save to database
                        db_success, db_message, db_dl_count, db_vc_count = db_service.save_processed_data(
                            processed_records, 
                            user_id, 
                            filename, 
                            selected_period
                        )
                        
                        if not db_success:
                            logger.error(f"Database save failed for {filename}: {db_message}")
                        
                        logger.info(f"Successfully processed {len(processed_records)} records from {filename}")
                    else:
                        failed_files.append(f"{filename} (no data for {selected_period})")
                    
                    processed_files += 1
                    
                    # Small delay to allow other tasks
                    await asyncio.sleep(0.1)
                    
                except Exception as file_error:
                    error_msg = f"{file_info.get('filename', file_id)}: {str(file_error)}"
                    failed_files.append(error_msg)
                    logger.error(f"Error processing file {file_id}: {str(file_error)}")
                    continue
            
            # Calculate results
            dl_records = len([r for r in all_records if 'Employee' in r])
            vc_records = len([r for r in all_records if 'Item' in r])
            
            # Update job with final results
            self.processing_jobs[job_id].update({
                'status': 'completed',
                'progress': 100,
                'completed_at': datetime.utcnow(),
                'results': {
                    'total_records': len(all_records),
                    'dl_records': dl_records,
                    'vc_records': vc_records,
                    'projects': len(set(r.get('Project', '') for r in all_records)),
                    'successful_files': successful_files,
                    'failed_files': len(failed_files),
                    'error_details': failed_files if failed_files else None
                }
            })
            
            logger.info(f"Processing job {job_id} completed: {successful_files}/{total_files} files successful")
            
        except Exception as e:
            # Update job with error
            self.processing_jobs[job_id].update({
                'status': 'failed',
                'progress': 0,
                'completed_at': datetime.utcnow(),
                'error_message': str(e)
            })
            logger.error(f"Processing job {job_id} failed: {str(e)}")
    
    def get_job_status(self, job_id: str, user_id: int) -> Dict[str, Any]:
        """
        Get processing job status
        
        Args:
            job_id: Job identifier
            user_id: User ID for validation
            
        Returns:
            Job status dictionary
        """
        job = self.processing_jobs.get(job_id)
        
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        if job['user_id'] != user_id:
            raise ValueError("Unauthorized access to job")
        
        return {
            'job_id': job['job_id'],
            'status': job['status'],
            'progress': job['progress'],
            'results': job.get('results'),
            'error_message': job.get('error_message')
        }
    
    def cleanup_expired_files(self, hours: int = 24):
        """
        Clean up expired uploaded files
        
        Args:
            hours: Hours after which files are considered expired
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            expired_files = []
            
            for file_id, file_info in self.uploaded_files.items():
                if file_info['uploaded_at'] < cutoff_time:
                    expired_files.append(file_id)
            
            for file_id in expired_files:
                del self.uploaded_files[file_id]
                logger.info(f"Cleaned up expired file: {file_id}")
            
            logger.info(f"Cleaned up {len(expired_files)} expired files")
            
        except Exception as e:
            logger.error(f"Error cleaning up files: {str(e)}")
    
    def cleanup_expired_jobs(self, hours: int = 48):
        """
        Clean up expired processing jobs
        
        Args:
            hours: Hours after which jobs are considered expired
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            expired_jobs = []
            
            for job_id, job_info in self.processing_jobs.items():
                completed_at = job_info.get('completed_at', job_info.get('started_at'))
                if completed_at and completed_at < cutoff_time:
                    expired_jobs.append(job_id)
            
            for job_id in expired_jobs:
                del self.processing_jobs[job_id]
                logger.info(f"Cleaned up expired job: {job_id}")
            
            logger.info(f"Cleaned up {len(expired_jobs)} expired jobs")
            
        except Exception as e:
            logger.error(f"Error cleaning up jobs: {str(e)}")
    
    def get_user_files(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all files uploaded by user
        
        Args:
            user_id: User ID
            
        Returns:
            List of file information dictionaries
        """
        user_files = []
        for file_id, file_info in self.uploaded_files.items():
            if file_info['user_id'] == user_id:
                user_files.append({
                    'file_id': file_id,
                    'filename': file_info['filename'],
                    'sheets_count': file_info['sheets_count'],
                    'uploaded_at': file_info['uploaded_at'],
                    'status': file_info['status']
                })
        
        return sorted(user_files, key=lambda x: x['uploaded_at'], reverse=True)


# Global processing service instance
processing_api_service = ProcessingAPIService()
