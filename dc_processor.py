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
        logger.info(f"Initial DataFrame columns: {list(df.columns)}")
        
        # Find the section for the target month
        month_header_row, month_end_row = self._find_month_section(df, target_month)
        
        if month_header_row is None:
            logger.warning(f"Month section '{target_month}' not found in DL Costs data")
            return processed_records
        
        logger.info(f"Processing month '{target_month}' from rows {month_header_row} to {month_end_row}")
        
        # The actual headers are in the row immediately following the month header
        header_row_index = month_header_row
        # header_row_index = month_header_row + 1
        
        # Extract the headers for this specific month section
        month_headers = self._extract_headers_from_row(df.iloc[header_row_index])
        
        # The data starts on the row after the headers
        data_start_row = header_row_index + 1
        
        # Create a temporary DataFrame for this month's data with correct headers
        month_data = df.iloc[data_start_row:month_end_row].copy()
        month_data.columns = month_headers
        month_data = month_data.reset_index(drop=True)
        
        logger.info(f"Processing month '{target_month}' with headers: {month_headers}")
        
        # Process each row of data for this month
        for index, row in month_data.iterrows():
            try:
                # Skip empty rows - check first column (Employee/Ticket)
                first_col_value = row.iloc[0] if len(row) > 0 else None
                if pd.isna(first_col_value) or str(first_col_value).strip() == '':
                    continue
                    
                # Skip total rows within the month data
                first_col_str = str(first_col_value).strip()
                logger.debug(f"Processing row {index}: {first_col_str}")
                
                if 'total' in first_col_str.lower():
                    logger.debug(f"Skipping total row: {first_col_str}")
                    continue
                
                employee_ticket = first_col_str
                
                # Base info for all generated records from this row
                base_record_info = {
                    'Employee': employee_ticket,
                    'Project': project_name,
                    'Month': target_month,
                }
                
                # Map original column names to standard names
                column_mapping = self._create_column_mapping(month_data.columns)
                reverse_column_mapping = {v: k for k, v in column_mapping.items()}

                def get_cost(standard_name):
                    col = reverse_column_mapping.get(standard_name)
                    value = float(row.get(col, 0) or 0) if col else 0
                    # Round Total DL Costs to 2 decimal places
                    if standard_name == 'Total DL Costs':
                        return round(value, 2)
                    return value

                # Get all potential cost values
                total_hours_direct_val = get_cost('Total Hours Direct')
                total_dl_costs_val = get_cost('Total DL Costs')
                paid_overtime_val = get_cost('Paid Overtime')
                base_salary_val = get_cost('Base Salary')
                payroll_taxes_val = get_cost('Payroll Taxes')
                vacation_liability_val = get_cost('Accrued Vacation Liability')
                paid_vacation_val = get_cost('Paid Vacation')
                sick_leave_val = get_cost('Sick Leave Paid')
                medical_insurance_val = get_cost('Medical Insurance')
                bonus_val = get_cost('Unconditional Bonus')

                # Get associated hours
                direct_hours_val = get_cost('Hours Direct')
                sick_hours_val = get_cost('Sick Leave Hours')

                # New Rule: Discrepancies & corrections from previous month
                if total_hours_direct_val < 0:
                    record = base_record_info.copy()
                    record.update({
                        'Bucket': 'Discrepancies & corrections from previous month',
                        'DC Hours': total_hours_direct_val,
                        'Total DL costs': round(total_dl_costs_val, 2)
                    })
                    processed_records.append(record)
                    continue # Skip all other bucketing for this row

                # Handle PM role charge as a special case
                if 'pm role charge' in employee_ticket.lower():
                    if total_dl_costs_val != 0:
                        record = base_record_info.copy()
                        record.update({
                            'Bucket': 'PM role charge',
                            'DC Hours': 0,
                            'Total DL costs': round(total_dl_costs_val, 2)
                        })
                        processed_records.append(record)
                    continue

                # Rule 5: Paid Overtime (must be checked first as it includes base salary components)
                if paid_overtime_val > 0:
                    total_cost = paid_overtime_val + base_salary_val + payroll_taxes_val + vacation_liability_val + paid_vacation_val
                    total_cost = round(total_cost, 2)  # Round to 2 decimal places
                    if total_cost > 0:
                        record = base_record_info.copy()
                        record.update({
                            'Bucket': 'Paid overtime',
                            'DC Hours': direct_hours_val,
                            'Total DL costs': total_cost
                        })
                        processed_records.append(record)
                else:
                    # Rule 1: Need clarification (only if not overtime)
                    total_cost = base_salary_val + payroll_taxes_val + vacation_liability_val + paid_vacation_val
                    total_cost = round(total_cost, 2)  # Round to 2 decimal places
                    if total_cost > 0:
                        record = base_record_info.copy()
                        record.update({
                            'Bucket': 'Need clarification',
                            'DC Hours': direct_hours_val,
                            'Total DL costs': total_cost
                        })
                        processed_records.append(record)

                # Rule 2: Sick leave (independent)
                if sick_leave_val > 0:
                    record = base_record_info.copy()
                    record.update({
                        'Bucket': 'Sick leave',
                        'DC Hours': sick_hours_val,
                        'Total DL costs': round(sick_leave_val, 2)
                    })
                    processed_records.append(record)

                # Rule 3: Medical Insurance (independent)
                if medical_insurance_val > 0:
                    record = base_record_info.copy()
                    record.update({
                        'Bucket': 'Medical Insurance',
                        'DC Hours': 0,
                        'Total DL costs': round(medical_insurance_val, 2)
                    })
                    processed_records.append(record)

                # Rule 4: Bonus (independent)
                if bonus_val > 0:
                    record = base_record_info.copy()
                    record.update({
                        'Bucket': 'Bonus',
                        'DC Hours': 0,
                        'Total DL costs': round(bonus_val, 2)
                    })
                    processed_records.append(record)

            except Exception as e:
                logger.error(f"Error processing DL row {index}: {str(e)}")
                continue
        
        logger.info(f"Processed {len(processed_records)} DL Cost records for {target_month}")
        return processed_records
    
    def _extract_headers_from_row(self, header_row: pd.Series) -> List[str]:
        """
        Extracts and cleans column headers from a pandas Series.
        
        Args:
            header_row: The pandas Series representing the header row.
            
        Returns:
            A list of cleaned header strings.
        """
        new_columns = []
        for i, val in enumerate(header_row.values):
            if pd.notna(val) and str(val).strip():
                new_columns.append(str(val).strip())
            else:
                # Fallback for empty or NaN headers
                new_columns.append(f"Unnamed: {i}")
        return new_columns
    
    def process_vc_costs_direct(self, df: pd.DataFrame, project_name: str, target_month: str = None) -> List[Dict]:
        """
        Process data from 'VC Costs (Direct)' tab for a specific month.
        
        Args:
            df: DataFrame containing the VC Costs data
            project_name: Name of the project
            target_month: Month to process (e.g., 'June 2025')
            
        Returns:
            List of dictionaries containing processed VC records
        """
        processed_records = []
        
        if df.empty:
            logger.warning("VC Costs (Direct) data is empty")
            return processed_records
        
        # Log the actual columns found in the data
        logger.info(f"Initial VC DataFrame columns: {list(df.columns)}")
        
        # Find the section for the target month
        month_header_row, month_end_row = self._find_month_section(df, target_month)
        
        if month_header_row is None:
            logger.warning(f"Month section '{target_month}' not found in VC Costs data")
            return processed_records
        
        logger.info(f"Processing VC month '{target_month}' from rows {month_header_row} to {month_end_row}")
        
        # The actual headers are in the row immediately following the month header
        header_row_index = month_header_row
        
        # Extract the headers for this specific month section
        month_headers = self._extract_headers_from_row(df.iloc[header_row_index])
        
        # The data starts on the row after the headers
        data_start_row = header_row_index + 1
        
        # Create a temporary DataFrame for this month's data with correct headers
        month_data = df.iloc[data_start_row:month_end_row].copy()
        month_data.columns = month_headers
        month_data = month_data.reset_index(drop=True)
        
        logger.info(f"Processing VC month '{target_month}' with headers: {month_headers}")
        
        # Process each row of data for this month
        for index, row in month_data.iterrows():
            try:
                # Skip empty rows - check first column (Items)
                first_col_value = row.iloc[0] if len(row) > 0 else None
                if pd.isna(first_col_value) or str(first_col_value).strip() == '':
                    continue
                    
                # Skip total rows within the month data
                first_col_str = str(first_col_value).strip()
                logger.debug(f"Processing VC row {index}: {first_col_str}")
                
                if 'total' in first_col_str.lower():
                    logger.debug(f"Skipping total row: {first_col_str}")
                    continue
                
                item_name = first_col_str
                
                # Base info for all generated records from this row
                base_record_info = {
                    'Item': item_name,
                    'Project': project_name,
                    'Month': target_month,
                    'DC Hours': 0  # Always 0 for VC costs
                }
                
                # Map original column names to standard names for VC
                column_mapping = self._create_vc_column_mapping(month_data.columns)
                reverse_column_mapping = {v: k for k, v in column_mapping.items()}

                def get_vc_cost(standard_name):
                    col = reverse_column_mapping.get(standard_name)
                    value = float(row.get(col, 0) or 0) if col else 0
                    # Round all VC cost values to 2 decimal places
                    return round(value, 2)

                # Get all potential cost values
                recruiting_costs_val = get_vc_cost('VC.Recruiting Costs')
                hw_nonresellable_val = get_vc_cost('VC.HW-Nonresellable')
                sw_nonresellable_val = get_vc_cost('VC.SW-Nonresellable')
                travel_val = get_vc_cost('VC.Travel')
                communications_val = get_vc_cost('VC.Communications')
                other_direct_val = get_vc_cost('VC.Other.Direct')

                # Check for negative values (Discrepancies & corrections)
                all_values = [recruiting_costs_val, hw_nonresellable_val, sw_nonresellable_val, 
                             travel_val, communications_val, other_direct_val]
                
                if any(val < 0 for val in all_values):
                    total_cost = sum(all_values)
                    total_cost = round(total_cost, 2)  # Round to 2 decimal places
                    record = base_record_info.copy()
                    record.update({
                        'Bucket': 'Discrepancies & corrections from previous month',
                        'Total DL costs': total_cost
                    })
                    processed_records.append(record)
                    continue

                # Rule 1: Recruiting cost
                if recruiting_costs_val > 0:
                    record = base_record_info.copy()
                    record.update({
                        'Bucket': 'Recruiting cost',
                        'Total DL costs': round(recruiting_costs_val, 2)
                    })
                    processed_records.append(record)

                # Rule 2: DC - other DC (combine all other direct costs)
                other_dc_total = hw_nonresellable_val + sw_nonresellable_val + travel_val + communications_val + other_direct_val
                other_dc_total = round(other_dc_total, 2)  # Round to 2 decimal places
                if other_dc_total > 0:
                    record = base_record_info.copy()
                    record.update({
                        'Bucket': 'DC - other DC',
                        'Total DL costs': other_dc_total
                    })
                    processed_records.append(record)

            except Exception as e:
                logger.error(f"Error processing VC row {index}: {str(e)}")
                continue
        
        logger.info(f"Processed {len(processed_records)} VC Cost records for {target_month}")
        return processed_records
    
    def _create_column_mapping(self, columns: List[str]) -> Dict[str, str]:
        """
        Create a mapping from actual column names to standardized names.
        Uses position-based mapping for Unnamed columns based on typical Excel structure.
        
        Args:
            columns: List of actual column names from the DataFrame
            
        Returns:
            Dict mapping original column names to standard names
        """
        mapping = {}
        
        # Expected column positions based on the Excel structure you showed
        expected_positions = {
            0: 'Employee/Ticket',  # First column is always Employee/Ticket
            1: 'TOTAL Hours direct',
            2: 'Hours direct', 
            3: 'Hours sick leave paid by project',
            4: 'Man-months direct',
            5: 'TOTAL DL costs',
            6: 'Base salary',
            7: 'Sick leave Paid by Project',
            8: 'Paid overtime',
            9: 'Unconditional Bonus',
            10: 'Payroll taxes',
            11: 'Accrued Vacation Liability',
            12: 'Paid vacation',
            13: 'VC.Medical Insurance'
        }
        
        for i, col in enumerate(columns):
            col_str = str(col).strip()
            col_lower = col_str.lower()
            
            # Skip the first column (Employee/Ticket) as it's handled separately
            if i == 0:
                continue
            
            # Handle Unnamed columns by position
            if 'unnamed' in col_lower or col_str.startswith('Unnamed'):
                if i in expected_positions:
                    standard_name = self._get_standard_name_for_position(i)
                    if standard_name:
                        mapping[col] = standard_name
                continue
            
            # Handle named columns
            standard_name = self._map_named_column(col_str)
            if standard_name:
                mapping[col] = standard_name
            else:
                # Keep original column name for unmapped columns
                mapping[col] = col
        
        return mapping
    
    def _create_vc_column_mapping(self, columns: List[str]) -> Dict[str, str]:
        """
        Create a mapping from actual VC column names to standardized names.
        
        Args:
            columns: List of actual column names from the VC DataFrame
            
        Returns:
            Dict mapping original column names to standard names
        """
        mapping = {}
        
        # Expected VC column positions
        expected_vc_positions = {
            0: 'Items',
            1: 'TicketID', 
            2: 'TOTAL',
            3: 'VC.HW-Nonresellable',
            4: 'VC.SW-Nonresellable',
            5: 'VC.Travel',
            6: 'VC.Communications',
            7: 'VC.Recruiting Costs',
            8: 'VC.Other.Direct'
        }
        
        for i, col in enumerate(columns):
            col_str = str(col).strip()
            col_lower = col_str.lower()
            
            # Skip the first column (Items) as it's handled separately
            if i == 0:
                continue
            
            # Handle Unnamed columns by position
            if 'unnamed' in col_lower or col_str.startswith('Unnamed'):
                if i in expected_vc_positions:
                    standard_name = expected_vc_positions[i]
                    mapping[col] = standard_name
                continue
            
            # Handle named columns
            standard_name = self._map_vc_named_column(col_str)
            if standard_name:
                mapping[col] = standard_name
            else:
                # Keep original column name for unmapped columns
                mapping[col] = col
        
        return mapping
    
    def _map_vc_named_column(self, col_name: str) -> Optional[str]:
        """
        Map a VC named column to its standard name.
        
        Args:
            col_name: Original VC column name
            
        Returns:
            Standard column name or None if not recognized
        """
        col_lower = col_name.lower().strip()
        
        if 'items' in col_lower:
            return None  # Skip items column as it's handled separately
        elif 'ticketid' in col_lower or 'ticket id' in col_lower:
            return 'TicketID'
        elif col_lower == 'total':
            return 'TOTAL'
        elif 'vc.hw-nonresellable' in col_lower or 'hw-nonresellable' in col_lower:
            return 'VC.HW-Nonresellable'
        elif 'vc.sw-nonresellable' in col_lower or 'sw-nonresellable' in col_lower:
            return 'VC.SW-Nonresellable'
        elif 'vc.travel' in col_lower or col_lower == 'travel':
            return 'VC.Travel'
        elif 'vc.communications' in col_lower or 'communications' in col_lower:
            return 'VC.Communications'
        elif 'vc.recruiting costs' in col_lower or 'recruiting costs' in col_lower:
            return 'VC.Recruiting Costs'
        elif 'vc.other.direct' in col_lower or 'other.direct' in col_lower:
            return 'VC.Other.Direct'
        else:
            return None
    
    def _get_standard_name_for_position(self, position: int) -> Optional[str]:
        """
        Get standardized column name based on position in Excel sheet.
        
        Args:
            position: 0-based column position
            
        Returns:
            Standard column name or None if position not recognized
        """
        position_mapping = {
            1: 'Total Hours Direct',
            2: 'Hours Direct',
            3: 'Sick Leave Hours', 
            4: 'Man-Months Direct',
            5: 'Total DL Costs',
            6: 'Base Salary',
            7: 'Sick Leave Paid',
            8: 'Paid Overtime',
            9: 'Unconditional Bonus',
            10: 'Payroll Taxes',
            11: 'Accrued Vacation Liability',
            12: 'Paid Vacation',
            13: 'Medical Insurance'
        }
        
        return position_mapping.get(position)
    
    def _map_named_column(self, col_name: str) -> Optional[str]:
        """
        Map a named column to its standard name.
        
        Args:
            col_name: Original column name
            
        Returns:
            Standard column name or None if not recognized
        """
        col_lower = col_name.lower().strip()
        
        # Map based on the actual structure you provided
        if 'employee' in col_lower or 'ticket' in col_lower:
            return None  # Skip employee/ticket column as it's handled separately
        elif 'total hours direct' in col_lower:
            return 'Total Hours Direct'
        elif 'hours direct' in col_lower and 'total' not in col_lower:
            return 'Hours Direct'
        elif 'hours sick leave' in col_lower or ('sick leave' in col_lower and 'hours' in col_lower):
            return 'Sick Leave Hours'
        elif 'man-months' in col_lower or 'man months' in col_lower:
            return 'Man-Months Direct'
        elif 'total dl costs' in col_lower:
            return 'Total DL Costs'
        elif 'base salary' in col_lower:
            return 'Base Salary'
        elif 'sick leave paid' in col_lower:
            return 'Sick Leave Paid'
        elif 'paid overtime' in col_lower:
            return 'Paid Overtime'
        elif 'unconditional bonus' in col_lower:
            return 'Unconditional Bonus'
        elif 'payroll tax' in col_lower:
            return 'Payroll Taxes'
        elif 'vacation liability' in col_lower:
            return 'Accrued Vacation Liability'
        elif 'paid vacation' in col_lower:
            return 'Paid Vacation'
        elif 'medical insurance' in col_lower or 'vc.medical' in col_lower:
            return 'Medical Insurance'
        else:
            return None
    
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
        # month_name = target_month.split()[0] if ' ' in target_month else target_month
        # target_variations.append(month_name.lower())
        target_variations.append(target_month.lower())
        
        # Add year variations if not already included
        # current_year = "2025"  # You can make this dynamic if needed
        # if current_year not in target_month:
        #     target_variations.append(f"{month_name.lower()} {current_year}")
        
        start_row = None
        end_row = None

        # Search through the DataFrame for month headers
        for index, row in df.iterrows():
            # Check first column for month names
            first_col_value = str(row.iloc[0] if len(row) > 0 else '').strip().lower()
            print(f"Checking row {index}: {first_col_value}")
            
            # Check if this row contains our target month
            for variation in target_variations:
                if variation in first_col_value:
                    start_row = index + 1  # Start from the row AFTER the month header
                    logger.info(f"Found month section '{target_month}' starting at row {start_row}")
                    break
        
        # If we found a start but no end, process until the end of the data
        if start_row is not None:
            # Look for a TOTAL row to end the section
            for index in range(start_row, len(df)):
                first_col_value = str(df.iloc[index, 0] if len(df.iloc[index]) > 0 else '').strip().lower()
                if 'total' in first_col_value:
                    logger.debug(f"Found TOTAL row at index {index}, ending month section")
                    end_row = index
                    break

        return start_row, end_row

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
        
        # Process VC Costs (Direct) tab
        vc_sheet_name = self._find_sheet_by_pattern(sheets_data.keys(), ['VC Costs (Direct)', 'VC Costs', 'Variable Costs'])
        if vc_sheet_name:
            vc_records = self.process_vc_costs_direct(sheets_data[vc_sheet_name], project_name, target_month)
            all_records.extend(vc_records)
        else:
            logger.warning("VC Costs (Direct) sheet not found")
        
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

        # Process VC Costs (Direct) tab
        vc_sheet_name = self._find_sheet_by_pattern(sheets_data.keys(), ['VC Costs (Direct)', 'VC Costs', 'Variable Costs'])
        if vc_sheet_name:
            vc_records = self.process_vc_costs_direct(sheets_data[vc_sheet_name], project_name, target_month)
            all_records.extend(vc_records)
        else:
            logger.warning("VC Costs (Direct) sheet not found")
        
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
    
    def export_to_dataframe(self, records: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Convert processed records to pandas DataFrames for export, separating DL and VC data.
        
        Args:
            records: List of processed record dictionaries
            
        Returns:
            Tuple of (DL DataFrame, VC DataFrame)
        """
        if not records:
            return pd.DataFrame(), pd.DataFrame()
        
        # Separate DL and VC records based on presence of 'Employee' vs 'Item' field
        dl_records = [r for r in records if 'Employee' in r]
        vc_records = [r for r in records if 'Item' in r]
        
        # Create DL DataFrame
        dl_df = pd.DataFrame()
        if dl_records:
            dl_df = pd.DataFrame(dl_records)
            dl_preferred_order = ['Employee', 'Project', 'Month', 'Bucket', 'DC Hours', 'Total DL costs']
            dl_df = dl_df.reindex(columns=dl_preferred_order)
        
        # Create VC DataFrame  
        vc_df = pd.DataFrame()
        if vc_records:
            vc_df = pd.DataFrame(vc_records)
            vc_preferred_order = ['Item', 'Project', 'Month', 'Bucket', 'DC Hours', 'Total DL costs']
            vc_df = vc_df.reindex(columns=vc_preferred_order)
        
        return dl_df, vc_df


class DCMasterFileManager:
    """
    Manages the creation and updating of the master DC file
    that consolidates data from multiple projects.
    """
    
    def __init__(self):
        self.master_dl_data = pd.DataFrame()
        self.master_vc_data = pd.DataFrame()
    
    def add_project_data(self, project_records: List[Dict]):
        """
        Add data from a single project to the master file.
        
        Args:
            project_records: List of processed records from one project
        """
        if not project_records:
            return
        
        # Separate DL and VC records
        dl_records = [r for r in project_records if 'Employee' in r]
        vc_records = [r for r in project_records if 'Item' in r]
        
        # Add DL records
        if dl_records:
            project_dl_df = pd.DataFrame(dl_records)
            if self.master_dl_data.empty:
                self.master_dl_data = project_dl_df
            else:
                self.master_dl_data = pd.concat([self.master_dl_data, project_dl_df], ignore_index=True)
        
        # Add VC records
        if vc_records:
            project_vc_df = pd.DataFrame(vc_records)
            if self.master_vc_data.empty:
                self.master_vc_data = project_vc_df
            else:
                self.master_vc_data = pd.concat([self.master_vc_data, project_vc_df], ignore_index=True)
        
        logger.info(f"Added {len(dl_records)} DL and {len(vc_records)} VC records to master file. Total: {len(self.master_dl_data)} DL, {len(self.master_vc_data)} VC")
    
    def get_master_dataframes(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Get the current master DataFrames."""
        return self.master_dl_data.copy(), self.master_vc_data.copy()
    
    def get_master_dataframe(self) -> pd.DataFrame:
        """Get the current master DataFrame (legacy method - returns combined data)."""
        if self.master_dl_data.empty and self.master_vc_data.empty:
            return pd.DataFrame()
        elif self.master_dl_data.empty:
            return self.master_vc_data.copy()
        elif self.master_vc_data.empty:
            return self.master_dl_data.copy()
        else:
            # Combine both datasets
            return pd.concat([self.master_dl_data, self.master_vc_data], ignore_index=True)
    
    def clear_master_data(self):
        """Clear all data from the master file."""
        self.master_dl_data = pd.DataFrame()
        self.master_vc_data = pd.DataFrame()
        logger.info("Master data cleared")
    
    def export_to_excel(self, output_path: str = None) -> bytes:
        """
        Export master data to Excel format with separate sheets for DL and VC data.
        
        Args:
            output_path: Optional file path to save to disk
            
        Returns:
            bytes: Excel file content as bytes (for download)
        """
        if self.master_dl_data.empty and self.master_vc_data.empty:
            raise ValueError("No data to export")
        
        # Create Excel file in memory
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Export DL data if available
            if not self.master_dl_data.empty:
                self.master_dl_data.to_excel(writer, sheet_name='DL Costs Master Data', index=False)
                
                # Auto-adjust column widths for DL sheet
                dl_worksheet = writer.sheets['DL Costs Master Data']
                for column in dl_worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    dl_worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Export VC data if available
            if not self.master_vc_data.empty:
                self.master_vc_data.to_excel(writer, sheet_name='VC Costs Master Data', index=False)
                
                # Auto-adjust column widths for VC sheet
                vc_worksheet = writer.sheets['VC Costs Master Data']
                for column in vc_worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    vc_worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        excel_bytes = output.getvalue()
        
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(excel_bytes)
            logger.info(f"Master data exported to {output_path}")
        
        return excel_bytes
