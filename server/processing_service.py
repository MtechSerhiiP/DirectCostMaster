"""
Processing API Service
Handles file upload storage and asynchronous processing for the API
"""

import os
import io
import uuid
import json
import re
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
        self.comparison_exports: Dict[str, Dict[str, Any]] = {}
        
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

    def start_previous_month_comparison_placeholder(self, job_id: str, file_ids: List[str], user_id: int) -> Dict[str, Any]:
        """Stub handler for previous-month comparison until logic is implemented."""
        now = datetime.utcnow()
        self.processing_jobs[job_id] = {
            'job_id': job_id,
            'status': 'failed',  # mark failed to short-circuit polling
            'progress': 0,
            'user_id': user_id,
            'started_at': now,
            'completed_at': now,
            'file_ids': file_ids,
            'results': None,
            'error_message': 'Previous-month comparison is not implemented yet.'
        }
        return self.processing_jobs[job_id]

    async def process_previous_month_comparison(self, job_id: str, file_ids: List[str], user_id: int):
        """Process multiple files with raw cell-by-cell comparison, automatically pairing by name and month."""
        if len(file_ids) < 2:
            raise ValueError("Comparison requires at least 2 files.")

        # Initialize job
        self.processing_jobs[job_id] = {
            'job_id': job_id,
            'status': 'processing',
            'progress': 0,
            'user_id': user_id,
            'started_at': datetime.utcnow(),
            'file_ids': file_ids,
            'results': None,
            'error_message': None,
            'mode': 'prev_month'
        }

        try:
            # Fetch all files
            file_infos = []
            for file_id in file_ids:
                file_info = self.get_uploaded_file(file_id, user_id)
                if not file_info:
                    raise ValueError(f"File {file_id} not found or unauthorized")
                file_infos.append(file_info)

            # Helper function to convert column index to Excel-style letter (A, B, C, ... Z, AA, AB, etc.)
            def col_index_to_letter(col_idx: int) -> str:
                """Convert 0-based column index to Excel column letter."""
                result = ""
                col_idx += 1  # Excel columns are 1-based
                while col_idx > 0:
                    col_idx -= 1
                    result = chr(col_idx % 26 + ord('A')) + result
                    col_idx //= 26
                return result

            # Parse Excel to JSON (raw data, no processing)
            def excel_to_json(file_info: Dict[str, Any]) -> Dict[str, Any]:
                month, year = self._parse_month_year_from_filename(file_info['filename'])
                file_io = io.BytesIO(file_info['content'])
                excel_data = pd.read_excel(file_io, sheet_name=None, engine='openpyxl', header=None)
                
                sheets_json = {}
                for sheet_name, df in excel_data.items():
                    # Convert DataFrame to dict of dicts with Excel-style addressing
                    rows = {}
                    for pandas_row_idx, row in df.iterrows():
                        excel_row = pandas_row_idx + 1  # Excel rows are 1-based
                        row_dict = {}
                        for pandas_col_idx, val in enumerate(row):
                            excel_col = col_index_to_letter(pandas_col_idx)
                            # Preserve value as-is (handles None, numbers, strings, etc.)
                            row_dict[excel_col] = val if pd.notna(val) else None
                        rows[excel_row] = row_dict
                    sheets_json[sheet_name] = rows
                
                return {
                    'filename': file_info['filename'],
                    'month': month,
                    'year': year,
                    'sheets': sheets_json,
                    'project_name': self._normalize_filename(file_info['filename'])
                }

            # Parse all files
            parsed_files = [excel_to_json(fi) for fi in file_infos]

            # Group files by project name
            projects = {}
            for parsed in parsed_files:
                project = parsed['project_name']
                if project not in projects:
                    projects[project] = []
                projects[project].append(parsed)

            # Helper function to filter comparison data
            def filter_comparison_data(parsed_data: Dict[str, Any], is_previous: bool) -> Dict[str, Any]:
                """
                Filter sheets to only include relevant cost sheets.
                For previous month file: also remove data after last "Total" row.
                """
                allowed_sheets = {
                    'dl costs (direct)',
                    'dl costs (variable)', 
                    'vc costs (direct)',
                    'vc costs (variable)'
                }
                
                filtered_sheets = {}
                for sheet_name, rows in parsed_data['sheets'].items():
                    sheet_lower = sheet_name.lower().strip()
                    
                    if sheet_lower not in allowed_sheets:
                        continue
                    
                    # If this is previous month file, find last "Total" row
                    if is_previous:
                        last_total_row = -1
                        for row_idx in sorted(rows.keys(), reverse=True):
                            row_data = rows[row_idx]
                            for col, val in row_data.items():
                                if val and isinstance(val, str) and 'total' in val.lower():
                                    last_total_row = row_idx
                                    break
                            if last_total_row != -1:
                                break
                        
                        if last_total_row != -1:
                            filtered_rows = {idx: row for idx, row in rows.items() if idx <= last_total_row}
                            filtered_sheets[sheet_name] = filtered_rows
                        else:
                            filtered_sheets[sheet_name] = rows
                    else:
                        filtered_sheets[sheet_name] = rows
                
                return {
                    'filename': parsed_data['filename'],
                    'month': parsed_data['month'],
                    'year': parsed_data['year'],
                    'sheets': filtered_sheets,
                    'project_name': parsed_data['project_name']
                }

            # Helper function to compare two files
            def compare_two_files(current: Dict[str, Any], previous: Dict[str, Any]) -> List[Dict[str, Any]]:
                """Compare two files and return list of mismatches."""
                mismatches = []
                all_sheets = set(current['sheets'].keys()) | set(previous['sheets'].keys())
                
                for sheet_name in sorted(all_sheets):
                    cur_sheet = current['sheets'].get(sheet_name, {})
                    prev_sheet = previous['sheets'].get(sheet_name, {})
                    
                    all_rows = set(cur_sheet.keys()) | set(prev_sheet.keys())
                    
                    for row_idx in sorted(all_rows):
                        cur_row = cur_sheet.get(row_idx, {})
                        prev_row = prev_sheet.get(row_idx, {})
                        
                        all_cols = set(cur_row.keys()) | set(prev_row.keys())
                        
                        for col in sorted(all_cols):
                            cur_val = cur_row.get(col)
                            prev_val = prev_row.get(col)
                            
                            if cur_val == prev_val:
                                continue
                            
                            if prev_val is None:
                                continue
                            
                            if cur_val is not None and prev_val is not None:
                                try:
                                    cur_num = float(cur_val)
                                    prev_num = float(prev_val)
                                    if round(cur_num - prev_num, 2) == 0:
                                        continue
                                except (ValueError, TypeError):
                                    pass
                            
                            mismatches.append({
                                'sheet': sheet_name,
                                'row': row_idx,
                                'column': col,
                                'current_value': str(cur_val) if cur_val is not None else 'EMPTY',
                                'previous_value': str(prev_val) if prev_val is not None else 'EMPTY',
                                'current_file': current['filename'],
                                'previous_file': previous['filename'],
                                'project': current['project_name'],
                                'current_period': f"{current['month']} {current['year']}" if current['month'] else 'Current',
                                'previous_period': f"{previous['month']} {previous['year']}" if previous['month'] else 'Previous'
                            })
                
                return mismatches

            # Collect all mismatches from all projects
            all_mismatches = []
            comparison_pairs = []

            for project, files in projects.items():
                # Sort files by month within project
                files_by_month = [(f, self._month_index(f['month'])) for f in files]
                files_by_month.sort(key=lambda x: (x[1], x[0]['year']))

                # Pair consecutive months and apply filtering
                for i in range(len(files_by_month) - 1):
                    previous_file = filter_comparison_data(files_by_month[i][0], is_previous=True)
                    current_file = filter_comparison_data(files_by_month[i + 1][0], is_previous=False)
                    
                    # Compare pair
                    pair_mismatches = compare_two_files(current_file, previous_file)
                    all_mismatches.extend(pair_mismatches)
                    
                    comparison_pairs.append({
                        'project': project,
                        'previous': previous_file['filename'],
                        'current': current_file['filename'],
                        'mismatches_count': len(pair_mismatches)
                    })

            # Build Excel report with multiple sheets
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Summary sheet
                summary_rows = []
                for pair in comparison_pairs:
                    summary_rows.append({
                        'Project': pair['project'],
                        'Previous File': pair['previous'],
                        'Current File': pair['current'],
                        'Mismatches': pair['mismatches_count']
                    })
                summary_rows.append({
                    'Project': 'TOTAL',
                    'Previous File': '',
                    'Current File': '',
                    'Mismatches': len(all_mismatches)
                })
                
                summary_df = pd.DataFrame(summary_rows)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)

                # Mismatches sheet
                if all_mismatches:
                    mismatch_df = pd.DataFrame(all_mismatches)
                    mismatch_df.to_excel(writer, sheet_name='Mismatches', index=False)
                else:
                    pd.DataFrame([{'Info': 'No cell mismatches found between all files.'}]).to_excel(
                        writer, sheet_name='Mismatches', index=False
                    )

            output.seek(0)
            excel_bytes = output.getvalue()
            expires_at = datetime.utcnow() + timedelta(hours=1)
            self.comparison_exports[job_id] = {
                'content': excel_bytes,
                'filename': f"MultiFileComparison_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx",
                'user_id': user_id,
                'created_at': datetime.utcnow(),
                'expires_at': expires_at
            }

            results = {
                # Base fields for schema
                'total_records': 0,
                'dl_records': 0,
                'vc_records': 0,
                'projects': len(projects),
                'successful_files': len(file_ids),
                'failed_files': 0,
                'error_details': None,
                # Comparison-specific fields
                'total_mismatches': len(all_mismatches),
                'dl_mismatches': 0,
                'vc_mismatches': 0,
                'download_url': f"/api/v1/files/compare-previous/{job_id}/download",
                'current_file': 'Multiple files',
                'previous_file': 'Multiple files'
            }

            self.processing_jobs[job_id].update({
                'status': 'completed',
                'progress': 100,
                'completed_at': datetime.utcnow(),
                'results': results,
                'error_message': None
            })

            logger.info(f"Multi-file comparison job {job_id} completed: {len(all_mismatches)} cell mismatches found across {len(projects)} project(s)")

        except Exception as e:
            self.processing_jobs[job_id].update({
                'status': 'failed',
                'progress': 0,
                'completed_at': datetime.utcnow(),
                'error_message': str(e)
            })
            logger.error(f"Multi-file comparison job {job_id} failed: {str(e)}")
            raise

    def get_comparison_download(self, job_id: str, user_id: int) -> Tuple[bytes, str]:
        export = self.comparison_exports.get(job_id)
        if not export:
            raise ValueError("Comparison report not found or expired")
        if export['user_id'] != user_id:
            raise ValueError("Unauthorized access to download")
        if datetime.utcnow() > export['expires_at']:
            del self.comparison_exports[job_id]
            raise ValueError("Comparison report expired")
        return export['content'], export['filename']
    
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

    # ------------------ Previous-month comparison helpers ------------------
    @staticmethod
    def _normalize_filename(name: str) -> str:
        base = os.path.splitext(name)[0]
        months = r"january|february|march|april|may|june|july|august|september|october|november|december"
        # remove month + optional year tokens to get stable project name
        cleaned = re.sub(rf"\b({months})\b\s*\d{{0,4}}", "", base, flags=re.IGNORECASE)
        return cleaned.strip().lower()

    @staticmethod
    def _parse_month_year_from_filename(name: str) -> Tuple[Optional[str], Optional[str]]:
        months = [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december"
        ]
        lower = name.lower()
        found_month = None
        for m in months:
            if m in lower:
                found_month = m.capitalize()
                break
        year_match = re.search(r"(20\d{2})", lower)
        found_year = year_match.group(1) if year_match else None
        return found_month, found_year

    @staticmethod
    def _month_index(month: Optional[str]) -> int:
        if not month:
            return -1
        order = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        try:
            return order.index(month)
        except ValueError:
            return -1


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
