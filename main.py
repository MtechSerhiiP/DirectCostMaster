"""
Direct Cost Master - Excel File Processing Application
A modern, minimalist web interface for processing Excel files with Direct Cost data.
Built with NiceGUI for a clean and responsive user experience.
"""

import io
from pdb import run
import pandas as pd
from nicegui import ui, app
from typing import Optional, Dict, Any
import logging

# Import our custom processor
from dc_processor import DirectCostProcessor, DCMasterFileManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ExcelProcessor:
    """
    Excel file processor for Direct Cost Master application.
    Handles Excel file operations using in-memory processing (IOBytes approach).
    Supports multiple file processing.
    """
    
    def __init__(self):
        self.current_file: Optional[io.BytesIO] = None
        self.file_name: str = ""
        self.sheets_data: Dict[str, pd.DataFrame] = {}
        # Multiple files support
        self.loaded_files: Dict[str, Dict[str, pd.DataFrame]] = {}  # filename -> sheets_data
        self.file_processing_status: Dict[str, str] = {}  # filename -> status
        
    def load_excel_from_bytes(self, file_content: bytes, filename: str) -> bool:
        """
        Load Excel file from bytes into memory without saving to disk.
        
        Args:
            file_content: Raw bytes of the Excel file
            filename: Original filename for reference
            
        Returns:
            bool: True if successfully loaded, False otherwise
        """
        try:
            # Create BytesIO object to work with file in memory
            file_io = io.BytesIO(file_content)
            
            # Read Excel file and all sheets
            excel_data = pd.read_excel(file_io, sheet_name=None, engine='openpyxl')
            
            # Store in loaded files collection
            self.loaded_files[filename] = excel_data
            self.file_processing_status[filename] = 'loaded'
            
            # Keep compatibility - set as current file if it's the first one
            if not self.current_file:
                self.current_file = file_io
                self.file_name = filename
                self.sheets_data = excel_data
            
            logger.info(f"Successfully loaded Excel file: {filename}")
            logger.info(f"Available sheets: {list(excel_data.keys())}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading Excel file {filename}: {str(e)}")
            self.file_processing_status[filename] = f'error: {str(e)}'
            return False
    
    def get_sheet_names(self) -> list:
        """Get list of available sheet names from the loaded Excel file."""
        return list(self.sheets_data.keys()) if self.sheets_data else []
    
    def get_sheet_data(self, sheet_name: str) -> Optional[pd.DataFrame]:
        """Get data from a specific sheet."""
        return self.sheets_data.get(sheet_name)
    
    def get_sheet_preview(self, sheet_name: str, rows: int = 10) -> Optional[pd.DataFrame]:
        """Get a preview of the first few rows from a sheet."""
        sheet_data = self.get_sheet_data(sheet_name)
        return sheet_data.head(rows) if sheet_data is not None else None
    
    def get_loaded_files(self) -> Dict[str, str]:
        """Get dictionary of loaded files and their status."""
        return self.file_processing_status.copy()
    
    def get_file_sheets_data(self, filename: str) -> Optional[Dict[str, pd.DataFrame]]:
        """Get sheets data for specific file."""
        return self.loaded_files.get(filename)
    
    def clear_all_files(self):
        """Clear all loaded files."""
        self.loaded_files.clear()
        self.file_processing_status.clear()
        self.current_file = None
        self.file_name = ""
        self.sheets_data = {}
    
    def get_files_count(self) -> int:
        """Get count of loaded files."""
        return len(self.loaded_files)


class DirectCostMasterApp:
    """
    Main application class for Direct Cost Master.
    Handles the user interface and file processing workflow.
    """
    
    def __init__(self):
        self.processor = ExcelProcessor()
        self.dc_processor = DirectCostProcessor()
        self.master_manager = DCMasterFileManager()
        
        # UI components references
        self.upload_area = None
        self.file_info_card = None
        self.files_list_card = None  # New card for multiple files
        self.sheets_select = None
        self.process_button = None
        self.download_button = None
        self.results_card = None
        self.month_select = None
        self.year_select = None
        
        # Files management
        self.files_list_table = None
        self.clear_files_button = None
        
        # Results components for tabs
        self.results_summary = None
        self.dl_tab = None
        self.vc_tab = None
        self.dl_summary = None
        self.vc_summary = None
        self.dl_results_table = None
        self.vc_results_table = None
        
    def create_header(self):
        """Create the application header with title and description."""
        with ui.row().classes('w-full justify-center mb-8'):
            with ui.column().classes('text-center'):
                ui.label('Direct Cost Master').classes('text-4xl font-bold text-blue-600 mb-2')
                ui.label('Excel File Processing Application').classes('text-lg text-gray-600')
                ui.separator().classes('w-24 mx-auto mt-4')
    
    def create_upload_section(self):
        """Create the file upload section with drag-and-drop functionality for multiple files."""
        with ui.card().classes('w-full max-w-2xl mx-auto p-6 shadow-lg'):
            ui.label('Upload Excel Files').classes('text-xl font-semibold mb-4')
            
            # File upload component - now supports multiple files
            upload = ui.upload(
                on_upload=self.handle_file_upload,
                multiple=True,  # Enable multiple file selection
                auto_upload=True,
                max_files=20  # Limit to 20 files
            ).classes('w-full')
            
            # Style the upload area
            upload.props('accept=".xlsx,.xls" color="primary" flat bordered')
            upload.tooltip('Select Excel files (.xlsx or .xls) - Maximum 20 files')
            
            # Upload instructions
            with ui.row().classes('w-full justify-center mt-4'):
                ui.label('Drag and drop your Excel files here or click to browse (Max: 20 files)').classes('text-gray-500 text-sm')
    
    def create_file_info_section(self):
        """Create the file information display section."""
        self.file_info_card = ui.card().classes('w-full max-w-2xl mx-auto p-6 shadow-lg mt-6 hidden')
        
        with self.file_info_card:
            ui.label('File Information').classes('text-xl font-semibold mb-4')
            
            # File details
            self.file_name_label = ui.label().classes('text-sm text-gray-600 mb-2')
            self.sheets_count_label = ui.label().classes('text-sm text-gray-600 mb-4')
    
    def create_files_list_section(self):
        """Create the multiple files list section."""
        self.files_list_card = ui.card().classes('w-full max-w-4xl mx-auto p-6 shadow-lg mt-6 hidden')
        
        with self.files_list_card:
            with ui.row().classes('w-full justify-between items-center mb-4'):
                ui.label('Loaded Files').classes('text-xl font-semibold')
                self.clear_files_button = ui.button(
                    'Clear All Files',
                    on_click=self.clear_all_files
                ).classes('bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded')
            
            # Files list table
            self.files_list_table = ui.table(
                columns=[
                    {'name': 'filename', 'label': 'File Name', 'field': 'filename', 'sortable': True},
                    {'name': 'status', 'label': 'Status', 'field': 'status', 'sortable': True},
                    {'name': 'sheets', 'label': 'Sheets Count', 'field': 'sheets', 'sortable': True}
                ],
                rows=[]
            ).classes('w-full')
    
    def create_process_section(self):
        """Create the data processing controls section."""
        with ui.card().classes('w-full max-w-2xl mx-auto p-6 shadow-lg mt-6'):
            ui.label('Process Data').classes('text-xl font-semibold mb-4')
            
            # Month selection
            ui.label('Select Month to Process:').classes('text-sm font-medium mb-2')
            self.month_select = ui.select(
                options=['January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December'],
                value='June'
            ).classes('w-full mb-4')
            self.month_select.tooltip('Select the month to process from the P&L files')
            # Year selection
            ui.label('Select Year to Process:').classes('text-sm font-medium mb-2')
            self.year_select = ui.select(
                options=['2025', '2024', '2023', '2022', '2021', '2020'],
                value='2025'
            ).classes('w-full mb-4')
            self.year_select.tooltip('Select the year to process from the P&L files')
            
            with ui.row().classes('w-full gap-4'):
                self.process_button = ui.button(
                    'Process All P&L Files',
                    on_click=self.process_all_files
                ).classes('flex-1 bg-blue-500 hover:bg-blue-600 text-white font-semibold py-3 rounded-lg disabled:opacity-50')
                
                # Clear master data button
                clear_button = ui.button(
                    'Clear All Data',
                    on_click=self.clear_master_data
                ).classes('bg-red-500 hover:bg-red-600 text-white font-semibold py-3 px-6 rounded-lg')
            
            # Initially disabled until files are loaded
            self.process_button.set_enabled(False)
            
            ui.label('This will process all loaded Excel files according to the Direct Cost Master workflow for the selected month.').classes('text-sm text-gray-500 mt-2')
    
    def create_results_section(self):
        """Create the results and download section with separate tabs for DL and VC data."""
        self.results_card = ui.card().classes('w-full max-w-6xl mx-auto p-6 shadow-lg mt-6 hidden')
        
        with self.results_card:
            ui.label('Processing Results').classes('text-xl font-semibold mb-4')
            
            # Results summary
            self.results_summary = ui.label().classes('text-sm text-gray-600 mb-4')
            
            # Download button
            self.download_button = ui.button(
                'Download Master DC File',
                on_click=self.download_master_file
            ).classes('bg-green-500 hover:bg-green-600 text-white font-semibold py-3 px-6 rounded-lg mb-4')
            
            # Create tabs for DL and VC data
            with ui.tabs().classes('w-full') as tabs:
                self.dl_tab = ui.tab('DL Costs', icon='people')
                self.vc_tab = ui.tab('VC Costs', icon='inventory')
            
            with ui.tab_panels(tabs, value=self.dl_tab).classes('w-full'):
                # DL Costs tab panel
                with ui.tab_panel(self.dl_tab):
                    ui.label('Direct Labor Costs').classes('text-lg font-medium mb-3')
                    self.dl_summary = ui.label().classes('text-sm text-gray-600 mb-3')
                    self.dl_results_table = ui.table(columns=[], rows=[]).classes('w-full')
                
                # VC Costs tab panel  
                with ui.tab_panel(self.vc_tab):
                    ui.label('Variable Costs').classes('text-lg font-medium mb-3')
                    self.vc_summary = ui.label().classes('text-sm text-gray-600 mb-3')
                    self.vc_results_table = ui.table(columns=[], rows=[]).classes('w-full')
    
    def handle_file_upload(self, event):
        """
        Handle the file upload event for multiple files.
        Process the uploaded Excel files using in-memory operations.
        """
        try:
            # Check file limit
            current_files_count = self.processor.get_files_count()
            if current_files_count >= 20:
                ui.notify('Maximum 20 files allowed. Please clear existing files first.', type='warning')
                return
            
            # Get file content as bytes (IOBytes approach)
            file_content = event.content.read()
            filename = event.name
            
            # Check if file already loaded
            if filename in self.processor.loaded_files:
                ui.notify(f'File {filename} is already loaded.', type='warning')
                return
            
            # Process file in memory
            success = self.processor.load_excel_from_bytes(file_content, filename)
            
            if success:
                # Update UI with file information
                self.update_files_list()
                ui.notify(f'Successfully loaded: {filename}', type='positive')
                logger.info(f"File uploaded and processed: {filename}")
            else:
                ui.notify(f'Error loading Excel file: {filename}. Please check the file format.', type='negative')
                
        except Exception as e:
            logger.error(f"Error in file upload: {str(e)}")
            ui.notify(f'Error uploading file: {str(e)}', type='negative')
    
    def update_file_info(self):
        """Update the file information display after successful upload."""
        # Show file info card
        self.file_info_card.classes(remove='hidden')
        
        # Update file details
        self.file_name_label.set_text(f'File: {self.processor.file_name}')
        sheet_names = self.processor.get_sheet_names()
        self.sheets_count_label.set_text(f'Sheets found: {len(sheet_names)}')
        
        # Enable processing button
        self.process_button.set_enabled(True)
    
    def update_files_list(self):
        """Update the files list display after successful uploads."""
        loaded_files = self.processor.get_loaded_files()
        
        if not loaded_files:
            self.files_list_card.classes(add='hidden')
            self.process_button.set_enabled(False)
            return
        
        # Show files list card
        self.files_list_card.classes(remove='hidden')
        
        # Prepare rows for the table
        rows = []
        for filename, status in loaded_files.items():
            sheets_data = self.processor.get_file_sheets_data(filename)
            sheets_count = len(sheets_data) if sheets_data else 0
            
            rows.append({
                'filename': filename,
                'status': status,
                'sheets': sheets_count
            })
        
        # Update table
        self.files_list_table.rows = rows
        self.files_list_table.update()
        
        # Enable processing button if we have files
        self.process_button.set_enabled(True)
        
        # Update summary
        ui.notify(f'Total files loaded: {len(loaded_files)}', type='info')
    
    def clear_all_files(self):
        """Clear all loaded files."""
        self.processor.clear_all_files()
        self.files_list_card.classes(add='hidden')
        self.process_button.set_enabled(False)
        ui.notify('All files cleared.', type='info')
    
    def process_all_files(self):
        """
        Process all loaded Excel files according to Direct Cost Master requirements.
        Processes files sequentially for the selected month.
        """
        loaded_files = self.processor.get_loaded_files()
        
        if not loaded_files:
            ui.notify('No files to process. Please upload files first.', type='warning')
            return
        
        try:
            selected_month = self.month_select.value
            selected_year = self.year_select.value
            selected_period = f"{selected_month} {selected_year}"
            
            ui.notify(f'Processing {len(loaded_files)} P&L files for {selected_period}...', type='info')
            
            total_processed_records = 0
            successful_files = 0
            failed_files = []
            
            # Process each file sequentially
            for filename, status in loaded_files.items():
                if status != 'loaded':
                    failed_files.append(f"{filename} (not loaded properly)")
                    continue
                
                try:
                    # Get sheets data for this file
                    sheets_data = self.processor.get_file_sheets_data(filename)
                    if not sheets_data:
                        failed_files.append(f"{filename} (no sheets data)")
                        continue
                    
                    # Process this file using our DC processor with selected month
                    processed_records = self.dc_processor.process_file_for_month(
                        sheets_data, 
                        filename,
                        selected_period
                    )
                    
                    if processed_records:
                        # Add processed data to master file
                        self.master_manager.add_project_data(processed_records)
                        total_processed_records += len(processed_records)
                        successful_files += 1
                        logger.info(f"Successfully processed {len(processed_records)} records from {filename}")
                        
                        # Update status
                        self.processor.file_processing_status[filename] = f'processed ({len(processed_records)} records)'
                    else:
                        failed_files.append(f"{filename} (no data for {selected_period})")
                        self.processor.file_processing_status[filename] = f'failed (no data for {selected_period})'
                        
                except Exception as file_error:
                    error_msg = str(file_error)
                    failed_files.append(f"{filename} ({error_msg})")
                    self.processor.file_processing_status[filename] = f'error: {error_msg}'
                    logger.error(f"Error processing file {filename}: {error_msg}")
            
            # Update files list to show processing status
            self.update_files_list()
            
            # Update results display
            if total_processed_records > 0:
                self.update_results_display()
            
            # Show summary notification
            success_msg = f'Successfully processed {successful_files}/{len(loaded_files)} files'
            if total_processed_records > 0:
                success_msg += f' with {total_processed_records} total records for {selected_month}'
            
            if failed_files:
                failed_msg = f'Failed files: {", ".join(failed_files[:3])}'
                if len(failed_files) > 3:
                    failed_msg += f' and {len(failed_files)-3} more...'
                ui.notify(f'{success_msg}. {failed_msg}', type='warning')
            else:
                ui.notify(f'{success_msg}!', type='positive')
            
            logger.info(f"Batch processing completed: {successful_files} successful, {len(failed_files)} failed")
            
        except Exception as e:
            logger.error(f"Error in batch processing: {str(e)}")
            ui.notify(f'Error processing files: {str(e)}', type='negative')
    
    def clear_master_data(self):
        """Clear all processed data from the master file."""
        self.master_manager.clear_master_data()
        self.results_card.classes(add='hidden')
        ui.notify('All master data cleared.', type='info')
    
    def update_results_display(self):
        """Update the results display with current master data."""
        # Get both DL and VC dataframes
        master_dl_df, master_vc_df = self.master_manager.get_master_dataframes()
        
        # Check if we have any data
        if master_dl_df.empty and master_vc_df.empty:
            return
            
        # Show results card
        self.results_card.classes(remove='hidden')
        
        # Update overall summary
        total_dl_records = len(master_dl_df) if not master_dl_df.empty else 0
        total_vc_records = len(master_vc_df) if not master_vc_df.empty else 0
        total_records = total_dl_records + total_vc_records
        
        unique_projects = 0
        if not master_dl_df.empty and 'Project' in master_dl_df.columns:
            unique_projects = max(unique_projects, master_dl_df['Project'].nunique())
        if not master_vc_df.empty and 'Project' in master_vc_df.columns:
            unique_projects = max(unique_projects, master_vc_df['Project'].nunique())
        
        summary_text = f"Total Records: {total_records} | DL Records: {total_dl_records} | VC Records: {total_vc_records} | Projects: {unique_projects}"
        self.results_summary.set_text(summary_text)
        
        # Update DL Costs tab
        if not master_dl_df.empty:
            unique_employees = master_dl_df['Employee'].nunique() if 'Employee' in master_dl_df.columns else 0
            dl_summary_text = f"DL Records: {total_dl_records} | Employees: {unique_employees}"
            self.dl_summary.set_text(dl_summary_text)
            
            # Update DL table (show first 50 rows for preview)
            dl_preview_df = master_dl_df.head(50)
            dl_columns = [{'name': col, 'label': col, 'field': col} for col in dl_preview_df.columns]
            dl_rows = dl_preview_df.fillna('').to_dict('records')
            
            self.dl_results_table.columns = dl_columns
            self.dl_results_table.rows = dl_rows
            self.dl_results_table.update()
        else:
            self.dl_summary.set_text("No DL Cost data available")
            self.dl_results_table.columns = []
            self.dl_results_table.rows = []
            self.dl_results_table.update()
        
        # Update VC Costs tab
        if not master_vc_df.empty:
            unique_items = master_vc_df['Item'].nunique() if 'Item' in master_vc_df.columns else 0
            vc_summary_text = f"VC Records: {total_vc_records} | Items: {unique_items}"
            self.vc_summary.set_text(vc_summary_text)
            
            # Update VC table (show first 50 rows for preview)
            vc_preview_df = master_vc_df.head(50)
            vc_columns = [{'name': col, 'label': col, 'field': col} for col in vc_preview_df.columns]
            vc_rows = vc_preview_df.fillna('').to_dict('records')
            
            self.vc_results_table.columns = vc_columns
            self.vc_results_table.rows = vc_rows
            self.vc_results_table.update()
        else:
            self.vc_summary.set_text("No VC Cost data available")
            self.vc_results_table.columns = []
            self.vc_results_table.rows = []
            self.vc_results_table.update()
    
    def download_master_file(self):
        """Generate and download the master DC file."""
        try:
            master_dl_df, master_vc_df = self.master_manager.get_master_dataframes()
            
            if master_dl_df.empty and master_vc_df.empty:
                ui.notify('No data to download. Process some files first.', type='warning')
                return
            
            # Generate Excel file in memory
            excel_bytes = self.master_manager.export_to_excel()
            
            # Create download
            ui.download(excel_bytes, 'DirectCostMaster.xlsx')
            ui.notify('Master file downloaded successfully!', type='positive')
            
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            ui.notify(f'Error downloading file: {str(e)}', type='negative')
    
    def create_ui(self):
        """Create the complete user interface."""
        # Set page configuration
        ui.page_title('Direct Cost Master')
        
        # Add custom CSS for modern styling
        ui.add_head_html('''
        <style>
            .nicegui-content {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .q-card {
                backdrop-filter: blur(10px);
                background: rgba(255, 255, 255, 0.95);
                border-radius: 12px;
            }
        </style>
        ''')
        
        # Create main container
        with ui.column().classes('w-full items-center space-y-6'):
            self.create_header()
            self.create_upload_section()
            self.create_file_info_section()
            self.create_files_list_section()
            self.create_process_section()
            self.create_results_section()
    
    def run(self, host: str = '127.0.0.1', port: int = 8080):
        """Run the application."""
        self.create_ui()
        
        logger.info(f"Starting Direct Cost Master application on {host}:{port}")
        ui.run(host=host, port=port, title='Direct Cost Master', favicon='📊')

app = DirectCostMasterApp()
app.run()  # Start the application