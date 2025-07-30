"""
Direct Cost Processing Module
Implements the specific business logic for processing P&L files
according to the requirements in process_description.txt
"""

import pandas as pd
import logging
import io
from typing import Dict, List, Optional, Tuple
import re

logger = logging.getLogger(__name__)


class DirectCostProcessor:
    """
    Processes Direct Cost data from P&L Excel files according to specific business rules.
    Handles both DL Costs (Direct) and VC Costs (Direct) tabs.
    """
    
    def __init__(self):
        self.dl_costs_data = None
        self.vc_costs_data = None
        self.project_name = ""
        self.current_month = "June"
        self.processed_data = []
        self.sheet_index_offset = 2
    
    def extract_project_name_from_filename(self, filename: str) -> str:
        """
        Extract project name from the P&L filename.
        
        Args:
            filename: The original filename of the P&L file (e.g., "Strategic.UHG.NICE.TAM - June 2025.XLSX")
            
        Returns:
            str: Extracted project name
        """
        # Remove file extension
        project_name = filename.replace('.xlsx', '').replace('.xls', '').replace('.XLSX', '').replace('.XLS', '')
        
        # Split by dash and take the first part (project name)
        if ' - ' in project_name:
            project_name = project_name.split(' - ')[0]
        elif '-' in project_name:
            project_name = project_name.split('-')[0]
        
        # Clean up any trailing/leading whitespace
        return project_name.strip()
    
    def extract_month_from_filename(self, filename: str) -> Optional[str]:
        """
        Extract month from the P&L filename.
        
        Args:
            filename: The original filename of the P&L file
            
        Returns:
            str or None: Extracted month name or None if not found
        """
        months = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        
        filename_lower = filename.lower()
        
        for month in months:
            if month.lower() in filename_lower:
                return month
        
        # Try short month names
        short_months = {
            'jan': 'January', 'feb': 'February', 'mar': 'March', 'apr': 'April',
            'may': 'May', 'jun': 'June', 'jul': 'July', 'aug': 'August',
            'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December'
        }
        
        for short, full in short_months.items():
            if short in filename_lower:
                return full
        
        return None
    
    def process_dl_costs_direct(self, df: pd.DataFrame, project_name: str, target_month: str = None) -> List[Dict]:
        """
        Process data from 'DL Costs (Direct)' tab for a specific month.
        
        Args:
            df: DataFrame containing the DL Costs data
            project_name: Name of the project
            target_month: Month to process (e.g., 'June 2025')
            
        Returns:
            List of dictionaries containing processed DC records
        """
        processed_records = []
        
        if df.empty:
            logger.warning("DL Costs (Direct) data is empty")
            return processed_records
        
        # Log the actual columns found in the data
        logger.info(f"Available columns in DL Costs sheet: {list(df.columns)}")
        
        # Find the section for the target month
        month_start_row, month_end_row = self._find_month_section(df, target_month)
        month_start_row += self.sheet_index_offset  # Adjust for sheet index offset
        month_end_row += self.sheet_index_offset  # Adjust for sheet index offset
        print(f"Month start row: {month_start_row}, Month end row: {month_end_row}")
        if month_start_row is None:
            logger.warning(f"Month section '{target_month}' not found in DL Costs data")
            return processed_records
        
        logger.info(f"Processing month '{target_month}' from rows {month_start_row} to {month_end_row}")
        
        # Get the subset of data for this month
        month_data = df.iloc[month_start_row:month_end_row] if month_end_row else df.iloc[month_start_row:]
        
        # Process each row of data for this month
        for index, row in month_data.iterrows():
            try:
                # Skip empty rows - check first column (Employee/Ticket)
                first_col_value = row.iloc[0] if len(row) > 0 else None
                if pd.isna(first_col_value) or str(first_col_value).strip() == '':
                    continue
                
                # Skip header rows and total rows
                first_col_str = str(first_col_value).strip()
                if (first_col_str.lower() in ['employee/ticket', 'total'] or 
                    first_col_str == '' or 
                    'total' in first_col_str.lower()):
                    continue
                
                # Extract employee/ticket name from first column
                employee_ticket = first_col_str
                
                # Create base record with the data structure we have
                record = {
                    'Employee': employee_ticket,
                    'Project': project_name,
                    'Month': target_month,
                    'Bucket': self._determine_bucket_dl(row, df.columns),
                    'Source': 'DL Costs (Direct)'
                }
                
                # Map actual columns to our standard names based on position and content
                column_mapping = self._create_column_mapping(df.columns)
                
                # Add data from mapped columns
                for original_col, standard_col in column_mapping.items():
                    if original_col in df.columns:
                        value = row.get(original_col, 0)
                        # Convert to numeric if possible, otherwise keep as string
                        try:
                            if pd.notna(value) and str(value).strip() != '':
                                record[standard_col] = float(value)
                            else:
                                record[standard_col] = 0
                        except (ValueError, TypeError):
                            record[standard_col] = str(value) if pd.notna(value) else ''
                
                # Copy any additional columns that weren't mapped
                for col in df.columns:
                    if col not in column_mapping and col not in record:
                        record[col] = row.get(col, '')
                
                processed_records.append(record)
                
            except Exception as e:
                logger.error(f"Error processing DL row {index}: {str(e)}")
                continue
        
        logger.info(f"Processed {len(processed_records)} DL Cost records for {target_month}")
        return processed_records
    
    def process_vc_costs_direct(self, df: pd.DataFrame, project_name: str) -> List[Dict]:
        """
        Process data from 'VC Costs (Direct)' tab.
        
        Args:
            df: DataFrame containing the VC Costs data
            project_name: Name of the project
            
        Returns:
            List of dictionaries containing processed DC records
        """
        processed_records = []
        
        if df.empty:
            logger.warning("VC Costs (Direct) data is empty")
            return processed_records
        
        # Expected columns based on process description
        required_columns = ['Employee/Ticket', 'TOTAL']
        
        # Check if required columns exist
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.warning(f"Missing columns in VC Costs: {missing_columns}")
        
        for index, row in df.iterrows():
            try:
                # Skip empty rows
                if pd.isna(row.get('Employee/Ticket', '')):
                    continue
                
                employee_ticket = str(row['Employee/Ticket']).strip()
                
                # Create base record
                record = {
                    'Employee': employee_ticket,
                    'Project': project_name,
                    'TOTAL DL costs': row.get('TOTAL', 0),
                    'Bucket': self._determine_bucket_vc(employee_ticket),
                    'Source': 'VC Costs (Direct)'
                }
                
                # Copy other columns that might be present
                for col in df.columns:
                    if col not in record and col != 'Employee/Ticket':
                        record[col] = row.get(col, '')
                
                processed_records.append(record)
                
            except Exception as e:
                logger.error(f"Error processing VC row {index}: {str(e)}")
                continue
        
        logger.info(f"Processed {len(processed_records)} VC Cost records")
        return processed_records
    
    def _create_column_mapping(self, columns: List[str]) -> Dict[str, str]:
        """
        Create a mapping from actual column names to standardized names.
        
        Args:
            columns: List of actual column names from the DataFrame
            
        Returns:
            Dict mapping original column names to standard names
        """
        mapping = {}
        
        for col in columns:
            col_lower = str(col).lower().strip()
            
            # Map based on the actual structure you provided
            if 'employee' in col_lower or 'ticket' in col_lower:
                continue  # Skip employee/ticket column as it's handled separately
            elif 'total hours direct' in col_lower or col_lower == 'total hours direct':
                mapping[col] = 'Total Hours Direct'
            elif 'hours direct' in col_lower and 'total' not in col_lower:
                mapping[col] = 'Hours Direct'
            elif 'hours sick leave' in col_lower or 'sick leave' in col_lower:
                mapping[col] = 'Sick Leave Hours'
            elif 'man-months' in col_lower or 'man months' in col_lower:
                mapping[col] = 'Man-Months Direct'
            elif 'total dl costs' in col_lower or col_lower == 'total dl costs':
                mapping[col] = 'Total DL Costs'
            elif 'base salary' in col_lower:
                mapping[col] = 'Base Salary'
            elif 'sick leave paid' in col_lower:
                mapping[col] = 'Sick Leave Paid'
            elif 'paid overtime' in col_lower:
                mapping[col] = 'Paid Overtime'
            elif 'unconditional bonus' in col_lower:
                mapping[col] = 'Unconditional Bonus'
            elif 'payroll tax' in col_lower:
                mapping[col] = 'Payroll Taxes'
            elif 'vacation liability' in col_lower:
                mapping[col] = 'Accrued Vacation Liability'
            elif 'paid vacation' in col_lower:
                mapping[col] = 'Paid Vacation'
            elif 'medical insurance' in col_lower:
                mapping[col] = 'Medical Insurance'
            else:
                # Keep original column name for unmapped columns
                mapping[col] = col
        
        return mapping
    
    def _find_month_section(self, df: pd.DataFrame, target_month: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Find the start and end row indices for a specific month section in the DataFrame.
        
        Args:
            df: DataFrame containing the monthly data
            target_month: Month to find (e.g., 'June', 'June 2025')
            
        Returns:
            Tuple of (start_row, end_row) indices, or (None, None) if not found
        """
        if not target_month:
            return None, None
        
        # Convert target month to different possible formats
        target_variations = []
        
        # Extract just the month name if year is included
        month_name = target_month.split()[0] if ' ' in target_month else target_month
        target_variations.append(month_name.lower())
        target_variations.append(target_month.lower())
        
        # Add year variations if not already included
        current_year = "2025"  # You can make this dynamic if needed
        if current_year not in target_month:
            target_variations.append(f"{month_name.lower()} {current_year}")
        
        start_row = None
        end_row = None

        print(df)
        # Search through the DataFrame for month headers
        for index, row in df.iterrows():
            # Check first column for month names
            first_col_value = str(row.iloc[0] if len(row) > 0 else '').strip().lower()
            print(f"Checking row {index}: {first_col_value}")
            # Check if this row contains our target month
            for variation in target_variations:
                if variation in first_col_value:
                    start_row = index  # Start from the next row (after the month header)
                    logger.info(f"Found month section '{target_month}' starting at row {start_row}")
                    break
            
            # If we found the start and this is a new month header, set end_row
            if start_row is not None and index > start_row:
                # Check if this is another month header
                months = ['january', 'february', 'march', 'april', 'may', 'june',
                         'july', 'august', 'september', 'october', 'november', 'december']
                
                for month in months:
                    if month in first_col_value and month not in target_variations:
                        end_row = index + 1
                        logger.info(f"Month section '{target_month}' ends at row {end_row}")
                        return start_row, end_row
        
        # If we found a start but no end, process until the end of the data
        if start_row is not None:
            # Look for a TOTAL row to end the section
            for index in range(start_row, len(df)):
                first_col_value = str(df.iloc[index, 0] if len(df.iloc[index]) > 0 else '').strip().lower()
                if 'total' in first_col_value:
                    print(f"Found TOTAL row at index {index}, ending month section")
                    end_row = index
                    break

        return start_row, end_row

    def _determine_bucket_dl(self, row: pd.Series, columns: List[str]) -> str:
        """
        Determine the bucket classification for DL Costs records.
        
        Args:
            row: DataFrame row containing employee data
            columns: List of column names to help identify data
            
        Returns:
            str: Bucket classification
        """
        # Get employee/ticket name from first column
        employee_ticket = str(row.iloc[0] if len(row) > 0 else '').strip()
        
        # Rule 1: PM role charge entries
        if 'PM role charge' in employee_ticket:
            return 'PM role charge'

        # Try to find relevant columns for other rules
        total_hours_col = None
        sick_hours_col = None
        bonus_col = None
        total_dl_col = None
        
        for col in columns:
            col_lower = str(col).lower()
            if 'total hours direct' in col_lower:
                total_hours_col = col
            elif 'hours sick leave' in col_lower or ('sick leave' in col_lower and 'hours' in col_lower):
                sick_hours_col = col
            elif 'unconditional bonus' in col_lower:
                bonus_col = col
            elif 'total dl costs' in col_lower:
                total_dl_col = col
                bonus_col = col
            elif 'total dl costs' in col_lower:
                total_dl_col = col
        
        # Rule 2: Sick leave - hours in sick leave match hours in total direct
        if total_hours_col and sick_hours_col:
            try:
                total_hours = float(row.get(total_hours_col, 0) or 0)
                sick_hours = float(row.get(sick_hours_col, 0) or 0)
                if total_hours > 0 and sick_hours > 0 and abs(total_hours - sick_hours) < 0.01:
                    return 'Sick leave'
            except (ValueError, TypeError):
                pass
        
        # Rule 3: Bonus - amount in unconditional bonus matches amount in total DL
        if bonus_col and total_dl_col:
            try:
                bonus_amount = float(row.get(bonus_col, 0) or 0)
                total_dl_amount = float(row.get(total_dl_col, 0) or 0)
                if bonus_amount > 0 and total_dl_amount > 0 and abs(bonus_amount - total_dl_amount) < 0.01:
                    return 'Bonus'
            except (ValueError, TypeError):
                pass
        
        # Default bucket for regular employees
        return 'Regular DL'
    
    def _determine_bucket_vc(self, employee_ticket: str) -> str:
        """
        Determine the bucket classification for VC Costs records.
        
        Args:
            employee_ticket: The employee/ticket identifier
            
        Returns:
            str: Bucket classification
        """
        employee_ticket = str(employee_ticket).strip()
        
        # Rule: If DC name starts with "Recruiting costs"
        if employee_ticket.startswith('Recruiting costs'):
            return 'Recruiting costs'
        
        # Default bucket for other VC costs
        return 'DC-other DC'
    
    def process_complete_file(self, sheets_data: Dict[str, pd.DataFrame], filename: str) -> List[Dict]:
        """
        Process a complete P&L file with both DL and VC costs for a specific month.
        
        Args:
            sheets_data: Dictionary of sheet names to DataFrames
            filename: Original filename for project name and month extraction
            
        Returns:
            List of all processed records
        """
        project_name = self.extract_project_name_from_filename(filename)
        target_month = self.extract_month_from_filename(filename)
        
        if not target_month:
            logger.warning(f"Could not extract month from filename: {filename}")
            target_month = "June"  # Default fallback
        
        logger.info(f"Processing file '{filename}' for project '{project_name}' and month '{target_month}'")
        
        all_records = []
        
        # Process DL Costs (Direct) tab
        dl_sheet_name = self._find_sheet_by_pattern(sheets_data.keys(), ['DL costs (direct)', 'DL costs breakdown'])
        if dl_sheet_name:
            dl_records = self.process_dl_costs_direct(sheets_data[dl_sheet_name], project_name, target_month)
            all_records.extend(dl_records)
        else:
            logger.warning("DL Costs (Direct) sheet not found")
        
        # # Process VC Costs (Direct) tab
        # vc_sheet_name = self._find_sheet_by_pattern(sheets_data.keys(), ['VC Costs (Direct)', 'VC Costs', 'Variable Costs'])
        # if vc_sheet_name:
        #     vc_records = self.process_vc_costs_direct(sheets_data[vc_sheet_name], project_name)
        #     all_records.extend(vc_records)
        # else:
        #     logger.warning("VC Costs (Direct) sheet not found")
        
        logger.info(f"Processed complete file '{filename}': {len(all_records)} total records for {target_month}")
        return all_records
    
    def process_file_for_month(self, sheets_data: Dict[str, pd.DataFrame], filename: str, selected_month: str) -> List[Dict]:
        """
        Process a P&L file for a manually selected month.
        
        Args:
            sheets_data: Dictionary of sheet names to DataFrames
            filename: Original filename for project name extraction
            selected_month: Manually selected month to process
            
        Returns:
            List of all processed records
        """
        project_name = self.extract_project_name_from_filename(filename)
        target_month = selected_month
        
        logger.info(f"Processing file '{filename}' for project '{project_name}' and selected month '{target_month}'")
        
        all_records = []
        
        # Process DL Costs (Direct) tab
        dl_sheet_name = self._find_sheet_by_pattern(sheets_data.keys(), ['DL costs (direct)', 'DL costs breakdown'])
        if dl_sheet_name:
            dl_records = self.process_dl_costs_direct(sheets_data[dl_sheet_name], project_name, target_month)
            all_records.extend(dl_records)
        else:
            logger.warning("DL Costs (Direct) sheet not found")
        
        logger.info(f"Processed file '{filename}': {len(all_records)} total records for {target_month}")
        return all_records
    
    def _find_sheet_by_pattern(self, sheet_names: List[str], patterns: List[str]) -> Optional[str]:
        """
        Find a sheet name that matches one of the given patterns.
        
        Args:
            sheet_names: List of available sheet names
            patterns: List of patterns to match against
            
        Returns:
            str or None: First matching sheet name or None if no match
        """
        for pattern in patterns:
            for sheet_name in sheet_names:
                if pattern.lower() in sheet_name.lower():
                    return sheet_name
        return None
    
    def export_to_dataframe(self, records: List[Dict]) -> pd.DataFrame:
        """
        Convert processed records to a pandas DataFrame for export.
        
        Args:
            records: List of processed record dictionaries
            
        Returns:
            pd.DataFrame: Consolidated DataFrame with all records
        """
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        
        # Reorder columns for better readability
        preferred_order = [
            'Employee', 'Project', 'Bucket', 'Source',
            'Total hours direct', 'Sick leave', 'Unconditional bonus',
            'Total DL', 'TOTAL DL costs', 'Medical insurance'
        ]
        
        # Include only columns that exist in the data
        columns = [col for col in preferred_order if col in df.columns]
        remaining_columns = [col for col in df.columns if col not in columns]
        final_columns = columns + remaining_columns
        
        return df[final_columns]


class DCMasterFileManager:
    """
    Manages the creation and updating of the master DC file
    that consolidates data from multiple projects.
    """
    
    def __init__(self):
        self.master_data = pd.DataFrame()
    
    def add_project_data(self, project_records: List[Dict]):
        """
        Add data from a single project to the master file.
        
        Args:
            project_records: List of processed records from one project
        """
        if not project_records:
            return
        
        project_df = pd.DataFrame(project_records)
        
        if self.master_data.empty:
            self.master_data = project_df
        else:
            self.master_data = pd.concat([self.master_data, project_df], ignore_index=True)
        
        logger.info(f"Added {len(project_records)} records to master file. Total records: {len(self.master_data)}")
    
    def get_master_dataframe(self) -> pd.DataFrame:
        """Get the current master DataFrame."""
        return self.master_data.copy()
    
    def clear_master_data(self):
        """Clear all data from the master file."""
        self.master_data = pd.DataFrame()
        logger.info("Master data cleared")
    
    def export_to_excel(self, output_path: str = None) -> bytes:
        """
        Export master data to Excel format.
        
        Args:
            output_path: Optional file path to save to disk
            
        Returns:
            bytes: Excel file content as bytes (for download)
        """
        if self.master_data.empty:
            raise ValueError("No data to export")
        
        # Create Excel file in memory
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            self.master_data.to_excel(writer, sheet_name='DC Master Data', index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['DC Master Data']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        excel_bytes = output.getvalue()
        
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(excel_bytes)
            logger.info(f"Master data exported to {output_path}")
        
        return excel_bytes
