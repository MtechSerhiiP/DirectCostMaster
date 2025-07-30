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
        self.processed_data = []
    
    def extract_project_name_from_filename(self, filename: str) -> str:
        """
        Extract project name from the P&L filename.
        
        Args:
            filename: The original filename of the P&L file
            
        Returns:
            str: Extracted project name
        """
        # Remove file extension and clean up the name
        project_name = filename.replace('.xlsx', '').replace('.xls', '')
        
        # Remove common prefixes/suffixes that might be in P&L files
        project_name = re.sub(r'^P&L[\s_-]*', '', project_name, flags=re.IGNORECASE)
        project_name = re.sub(r'[\s_-]*P&L$', '', project_name, flags=re.IGNORECASE)
        
        return project_name.strip()
    
    def process_dl_costs_direct(self, df: pd.DataFrame, project_name: str) -> List[Dict]:
        """
        Process data from 'DL Costs (Direct)' tab.
        
        Args:
            df: DataFrame containing the DL Costs data
            project_name: Name of the project
            
        Returns:
            List of dictionaries containing processed DC records
        """
        processed_records = []
        
        if df.empty:
            logger.warning("DL Costs (Direct) data is empty")
            return processed_records
        
        # Expected columns based on process description
        required_columns = [
            'Employee/Ticket', 'Total hours direct', 'Sick leave', 
            'Unconditional bonus', 'Total DL', 'Medical insurance'
        ]
        
        # Check if required columns exist
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.warning(f"Missing columns in DL Costs: {missing_columns}")
        
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
                    'Total hours direct': row.get('Total hours direct', 0),
                    'Sick leave': row.get('Sick leave', 0),
                    'Unconditional bonus': row.get('Unconditional bonus', 0),
                    'Total DL': row.get('Total DL', 0),
                    'Medical insurance': row.get('Medical insurance', 0),
                    'Bucket': self._determine_bucket_dl(row),
                    'Source': 'DL Costs (Direct)'
                }
                
                # Copy other columns that might be present
                for col in df.columns:
                    if col not in record and col != 'Employee/Ticket':
                        record[col] = row.get(col, '')
                
                processed_records.append(record)
                
            except Exception as e:
                logger.error(f"Error processing DL row {index}: {str(e)}")
                continue
        
        logger.info(f"Processed {len(processed_records)} DL Cost records")
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
    
    def _determine_bucket_dl(self, row: pd.Series) -> str:
        """
        Determine the bucket classification for DL Costs records.
        
        Args:
            row: DataFrame row containing employee data
            
        Returns:
            str: Bucket classification
        """
        employee_ticket = str(row.get('Employee/Ticket', '')).strip()
        total_hours_direct = row.get('Total hours direct', 0)
        sick_leave = row.get('Sick leave', 0)
        unconditional_bonus = row.get('Unconditional bonus', 0)
        total_dl = row.get('Total DL', 0)
        
        # Rule 1: PM role charge entries
        if 'PM role charge' in employee_ticket:
            return 'PM role charge'
        
        # Rule 2: Sick leave - hours in "Sick leave" match hours in "Total hours direct"
        try:
            if (total_hours_direct > 0 and sick_leave > 0 and 
                abs(float(total_hours_direct) - float(sick_leave)) < 0.01):
                return 'Sick leave'
        except (ValueError, TypeError):
            pass
        
        # Rule 3: Bonus - amount in "Unconditional bonus" matches amount in "Total DL"
        try:
            if (unconditional_bonus > 0 and total_dl > 0 and 
                abs(float(unconditional_bonus) - float(total_dl)) < 0.01):
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
        Process a complete P&L file with both DL and VC costs.
        
        Args:
            sheets_data: Dictionary of sheet names to DataFrames
            filename: Original filename for project name extraction
            
        Returns:
            List of all processed records
        """
        project_name = self.extract_project_name_from_filename(filename)
        all_records = []
        
        # Process DL Costs (Direct) tab
        dl_sheet_name = self._find_sheet_by_pattern(sheets_data.keys(), ['DL Costs (Direct)', 'DL Costs', 'Direct Labor'])
        if dl_sheet_name:
            dl_records = self.process_dl_costs_direct(sheets_data[dl_sheet_name], project_name)
            all_records.extend(dl_records)
        else:
            logger.warning("DL Costs (Direct) sheet not found")
        
        # Process VC Costs (Direct) tab
        vc_sheet_name = self._find_sheet_by_pattern(sheets_data.keys(), ['VC Costs (Direct)', 'VC Costs', 'Variable Costs'])
        if vc_sheet_name:
            vc_records = self.process_vc_costs_direct(sheets_data[vc_sheet_name], project_name)
            all_records.extend(vc_records)
        else:
            logger.warning("VC Costs (Direct) sheet not found")
        
        logger.info(f"Processed complete file '{filename}': {len(all_records)} total records")
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
