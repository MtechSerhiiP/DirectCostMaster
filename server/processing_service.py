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
from memory_data_service import memory_data_service

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
    
    async def process_files_async(self, job_id: str, file_ids: List[str], month: str, year: str, 
                                   user_id: int, analysis_mode: str = "single"):
        """
        Asynchronously process multiple files
        
        Args:
            job_id: Processing job identifier
            file_ids: List of file IDs to process
            month: Target month
            year: Target year
            user_id: User ID
            analysis_mode: 'single' for single month, 'ytd' for Year-to-Date
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
            'analysis_mode': analysis_mode,
            'results': None,
            'error_message': None
        }
        
        try:
            total_files = len(file_ids)
            processed_files = 0
            successful_files = 0
            failed_files = []
            all_records = []
            ytd_warnings = []  # Track missing months warnings
            
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
                    
                    if analysis_mode == 'ytd':
                        # YTD mode: process all months from January to selected month
                        processed_records, processed_months, missing_months = self.dc_processor.process_file_for_ytd(
                            excel_data,
                            filename,
                            month,
                            year
                        )
                        
                        # Create warning if some months are missing
                        if missing_months:
                            ytd_warnings.append({
                                'filename': filename,
                                'missing_months': missing_months,
                                'processed_months': processed_months,
                                'message': f"File '{filename}': Missing data for {len(missing_months)} month(s): {', '.join(missing_months)}"
                            })
                            logger.warning(f"YTD processing for {filename}: missing months {missing_months}")
                        
                        selected_period = f"{month} {year}"
                    else:
                        # Single month mode (existing behavior)
                        selected_period = f"{month} {year}"
                        processed_records = self.dc_processor.process_file_for_month(
                            excel_data, 
                            filename,
                            selected_period
                        )
                    
                    if processed_records:
                        all_records.extend(processed_records)
                        successful_files += 1
                        
                        # Save to memory
                        # For YTD mode, we still save individual records with their Month field
                        memory_success, memory_message, memory_dl_count, memory_vc_count = memory_data_service.save_processed_data(
                            processed_records, 
                            user_id, 
                            filename, 
                            selected_period
                        )
                        
                        if not memory_success:
                            logger.error(f"Memory save failed for {filename}: {memory_message}")
                        
                        logger.info(f"Successfully processed {len(processed_records)} records from {filename} ({analysis_mode} mode)")
                    else:
                        if analysis_mode == 'ytd':
                            failed_files.append(f"{filename} (no data for YTD {month} {year})")
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
            
            # Build results with YTD warnings if any
            results = {
                'total_records': len(all_records),
                'dl_records': dl_records,
                'vc_records': vc_records,
                'projects': len(set(r.get('Project', '') for r in all_records)),
                'successful_files': successful_files,
                'failed_files': len(failed_files),
                'error_details': failed_files if failed_files else None
            }
            
            # Add YTD warnings if present
            if ytd_warnings:
                results['ytd_warnings'] = ytd_warnings
            
            # Update job with final results
            self.processing_jobs[job_id].update({
                'status': 'completed',
                'progress': 100,
                'completed_at': datetime.utcnow(),
                'results': results
            })
            
            logger.info(f"Processing job {job_id} completed ({analysis_mode} mode): {successful_files}/{total_files} files successful")
            
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


    # ------------------ Program-level reconciliation ------------------
    def propose_reconcile_program(self, file_id: str, month: str, year: str, user_id: int) -> Dict[str, Any]:
        """
        Propose additions by comparing a program-level P&L file against user's existing saved data.
        Returns a report with proposed additions but does not apply them.
        """
        # Validate file
        file_info = self.get_uploaded_file(file_id, user_id)
        if not file_info:
            raise ValueError("Program file not found or unauthorized")

        # Enforce single program file constraint per user: file must be marked as 'program' or only one allowed per propose
        # (Requirement 8: only one program file may be added via this endpoint)

        # Parse Excel
        file_content = file_info['content']
        file_io = io.BytesIO(file_content)
        excel_data = pd.read_excel(file_io, sheet_name=None, engine='openpyxl')

        # Use DirectCostProcessor to parse program file for the selected month
        program_processor = DirectCostProcessor()
        selected_period = f"{month} {year}"
        program_records = program_processor.process_file_for_month(excel_data, file_info['filename'], selected_period)

        # Load user's existing data for that period from memory
        dl_df, vc_df = memory_data_service.get_user_data(user_id, period=selected_period)

        # Build keys for matching: Employee/Item + Bucket
        existing_dl = {}
        if not dl_df.empty:
            for _, row in dl_df.iterrows():
                key = (str(row.get('Employee')).strip().lower(), str(row.get('Bucket')).strip().lower())
                existing_dl[key] = existing_dl.get(key, 0.0) + float(row.get('Total DL costs') or 0)

        existing_vc = {}
        if not vc_df.empty:
            for _, row in vc_df.iterrows():
                key = (str(row.get('Item')).strip().lower(), str(row.get('Bucket')).strip().lower())
                existing_vc[key] = existing_vc.get(key, 0.0) + float(row.get('Total DL costs') or 0)

        # Compare program_records to master and propose missing entries
        proposed = []
        total_amount = 0.0

        for rec in program_records:
            period = rec.get('Month')
            if period != selected_period:
                continue

            if 'Employee' in rec:
                key = (str(rec.get('Employee', '')).strip().lower(), str(rec.get('Bucket', '')).strip().lower())
                prog_amt = float(rec.get('Total DL costs') or 0)
                existing_amt = existing_dl.get(key, 0.0)
                # If program has amount but master doesn't or less than program (tolerance handled at client)
                if round(prog_amt - existing_amt, 2) > 0:
                    proposed.append({
                        'project': file_info['filename'],
                        'type': 'DL',
                        'employee': rec.get('Employee'),
                        'item': None,
                        'bucket': rec.get('Bucket'),
                        'dc_hours': rec.get('DC Hours'),
                        'total_dl_costs': round(prog_amt - existing_amt, 2),
                        'source_file': file_info['filename']
                    })
                    total_amount += round(prog_amt - existing_amt, 2)

            elif 'Item' in rec:
                key = (str(rec.get('Item', '')).strip().lower(), str(rec.get('Bucket', '')).strip().lower())
                prog_amt = float(rec.get('Total DL costs') or 0)
                existing_amt = existing_vc.get(key, 0.0)
                if round(prog_amt - existing_amt, 2) > 0:
                    proposed.append({
                        'project': file_info['filename'],
                        'type': 'VC',
                        'employee': None,
                        'item': rec.get('Item'),
                        'bucket': rec.get('Bucket'),
                        'dc_hours': 0,
                        'total_dl_costs': round(prog_amt - existing_amt, 2),
                        'source_file': file_info['filename']
                    })
                    total_amount += round(prog_amt - existing_amt, 2)

        report = {
            'program_name': file_info['filename'],
            'period': selected_period,
            'proposed_additions': proposed,
            'total_proposed_amount': round(total_amount, 2),
            'proposed_count': len(proposed)
        }

        return report


    def apply_reconcile_program(self, file_id: str, month: str, year: str, additions: List[Dict[str, Any]], user_id: int) -> Tuple[bool, str, int, int]:
        """
        Apply approved proposed additions to the database as Project = program name.
        Returns counts of applied DL and VC records.
        """
        file_info = self.get_uploaded_file(file_id, user_id)
        if not file_info:
            raise ValueError("Program file not found or unauthorized")

        period = f"{month} {year}"
        applied_dl = 0
        applied_vc = 0

        # Prepare records for saving
        to_save = []
        for add in additions:
            # additions may be Pydantic models (ProposedAddition) or dicts
            if hasattr(add, 'dict'):
                add_dict = add.dict()
            else:
                add_dict = dict(add)

            if add_dict.get('type') == 'DL':
                rec = {
                    'Employee': add_dict.get('employee'),
                    'Project': file_info['filename'],
                    'Month': period,
                    'Bucket': add_dict.get('bucket'),
                    'DC Hours': add_dict.get('dc_hours'),
                    'Total DL costs': add_dict.get('total_dl_costs')
                }
                to_save.append(rec)
                applied_dl += 1
            elif add_dict.get('type') == 'VC':
                rec = {
                    'Item': add_dict.get('item'),
                    'Project': file_info['filename'],
                    'Month': period,
                    'Bucket': add_dict.get('bucket'),
                    'DC Hours': 0,
                    'Total DL costs': add_dict.get('total_dl_costs')
                }
                to_save.append(rec)
                applied_vc += 1

        if to_save:
            # Save using memory_data_service.save_processed_data which expects processed_records list
            success, message, dl_count, vc_count = memory_data_service.save_processed_data(to_save, user_id, file_info['filename'], period)
            if not success:
                raise ValueError(message)

        return True, f"Applied {applied_dl} DL and {applied_vc} VC additions", applied_dl, applied_vc


# Global processing service instance
processing_api_service = ProcessingAPIService()
