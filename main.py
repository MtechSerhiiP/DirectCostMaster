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
    """
    
    def __init__(self):
        self.current_file: Optional[io.BytesIO] = None
        self.file_name: str = ""
        self.sheets_data: Dict[str, pd.DataFrame] = {}
        
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
            self.current_file = io.BytesIO(file_content)
            self.file_name = filename
            
            # Read Excel file and all sheets
            excel_data = pd.read_excel(self.current_file, sheet_name=None, engine='openpyxl')
            self.sheets_data = excel_data
            
            logger.info(f"Successfully loaded Excel file: {filename}")
            logger.info(f"Available sheets: {list(self.sheets_data.keys())}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading Excel file: {str(e)}")
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


class DirectCostMasterApp:
    """
    Main application class for Direct Cost Master.
    Handles the user interface and file processing workflow.
    """
    
    def __init__(self):
        self.processor = ExcelProcessor()
        self.dc_processor = DirectCostProcessor()
        self.master_manager = DCMasterFileManager()
        self.current_sheet = None
        
        # UI components references
        self.upload_area = None
        self.file_info_card = None
        self.sheets_select = None
        self.data_preview = None
        self.process_button = None
        self.download_button = None
        self.results_card = None
        self.month_select = None
        
    def create_header(self):
        """Create the application header with title and description."""
        with ui.row().classes('w-full justify-center mb-8'):
            with ui.column().classes('text-center'):
                ui.label('Direct Cost Master').classes('text-4xl font-bold text-blue-600 mb-2')
                ui.label('Excel File Processing Application').classes('text-lg text-gray-600')
                ui.separator().classes('w-24 mx-auto mt-4')
    
    def create_upload_section(self):
        """Create the file upload section with drag-and-drop functionality."""
        with ui.card().classes('w-full max-w-2xl mx-auto p-6 shadow-lg'):
            ui.label('Upload Excel File').classes('text-xl font-semibold mb-4')
            
            # File upload component
            upload = ui.upload(
                on_upload=self.handle_file_upload,
                multiple=False,
                auto_upload=True
            ).classes('w-full')
            
            # Style the upload area
            upload.props('accept=".xlsx,.xls" color="primary" flat bordered')
            upload.tooltip('Select an Excel file (.xlsx or .xls)')
            
            # Upload instructions
            with ui.row().classes('w-full justify-center mt-4'):
                ui.label('Drag and drop your Excel file here or click to browse').classes('text-gray-500 text-sm')
    
    def create_file_info_section(self):
        """Create the file information display section."""
        self.file_info_card = ui.card().classes('w-full max-w-2xl mx-auto p-6 shadow-lg mt-6 hidden')
        
        with self.file_info_card:
            ui.label('File Information').classes('text-xl font-semibold mb-4')
            
            # File details
            self.file_name_label = ui.label().classes('text-sm text-gray-600 mb-2')
            self.sheets_count_label = ui.label().classes('text-sm text-gray-600 mb-4')
            
            # Sheet selection
            ui.label('Select Sheet to Preview:').classes('text-sm font-medium mb-2')
            self.sheets_select = ui.select(
                options=[],
                on_change=self.on_sheet_selected
            ).classes('w-full mb-4')
    
    def create_data_preview_section(self):
        """Create the data preview section."""
        self.data_preview = ui.card().classes('w-full max-w-6xl mx-auto p-6 shadow-lg mt-6 hidden')
        
        with self.data_preview:
            ui.label('Data Preview').classes('text-xl font-semibold mb-4')
            self.preview_table = ui.table(columns=[], rows=[]).classes('w-full')
    
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
            self.month_select.tooltip('Select the month to process from the P&L file')
            # Year selection
            ui.label('Select Year to Process:').classes('text-sm font-medium mb-2')
            self.year_select = ui.select(
                options=['2025', '2024', '2023', '2022', '2021', '2020'],
                value='2025'
            ).classes('w-full mb-4')
            self.month_select.tooltip('Select the month to process from the P&L file')
            
            with ui.row().classes('w-full gap-4'):
                self.process_button = ui.button(
                    'Process P&L File',
                    on_click=self.process_data
                ).classes('flex-1 bg-blue-500 hover:bg-blue-600 text-white font-semibold py-3 rounded-lg disabled:opacity-50')
                
                # Clear master data button
                clear_button = ui.button(
                    'Clear All Data',
                    on_click=self.clear_master_data
                ).classes('bg-red-500 hover:bg-red-600 text-white font-semibold py-3 px-6 rounded-lg')
            
            # Initially disabled until file is loaded
            self.process_button.set_enabled(False)
            
            ui.label('This will process the Excel data according to the Direct Cost Master workflow for the selected month.').classes('text-sm text-gray-500 mt-2')
    
    def create_results_section(self):
        """Create the results and download section."""
        self.results_card = ui.card().classes('w-full max-w-4xl mx-auto p-6 shadow-lg mt-6 hidden')
        
        with self.results_card:
            ui.label('Processing Results').classes('text-xl font-semibold mb-4')
            
            # Results summary
            self.results_summary = ui.label().classes('text-sm text-gray-600 mb-4')
            
            # Download button
            self.download_button = ui.button(
                'Download Master DC File',
                on_click=self.download_master_file
            ).classes('bg-green-500 hover:bg-green-600 text-white font-semibold py-3 px-6 rounded-lg mb-4')
            
            # Results table
            self.results_table = ui.table(columns=[], rows=[]).classes('w-full')
    
    def handle_file_upload(self, event):
        """
        Handle the file upload event.
        Process the uploaded Excel file using in-memory operations.
        """
        try:
            # Get file content as bytes (IOBytes approach)
            file_content = event.content.read()
            filename = event.name
            
            # Process file in memory
            success = self.processor.load_excel_from_bytes(file_content, filename)
            
            if success:
                # Update UI with file information
                self.update_file_info()
                ui.notify(f'Successfully loaded: {filename}', type='positive')
                logger.info(f"File uploaded and processed: {filename}")
            else:
                ui.notify('Error loading Excel file. Please check the file format.', type='negative')
                
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
        
        # Update sheet selection dropdown
        self.sheets_select.set_options(sheet_names)
        if sheet_names:
            self.sheets_select.set_value(sheet_names[0])
            self.on_sheet_selected()
        
        # Enable processing button
        self.process_button.set_enabled(True)
    
    def on_sheet_selected(self):
        """Handle sheet selection change."""
        if not self.sheets_select.value:
            return
            
        self.current_sheet = self.sheets_select.value
        
        # Get preview data
        preview_data = self.processor.get_sheet_preview(self.current_sheet, rows=5)
        
        if preview_data is not None:
            # Show preview card
            self.data_preview.classes(remove='hidden')
            
            # Update table with preview data
            columns = [{'name': col, 'label': col, 'field': col} for col in preview_data.columns]
            rows = preview_data.fillna('').to_dict('records')
            
            self.preview_table.columns = columns
            self.preview_table.rows = rows
            self.preview_table.update()
            
            logger.info(f"Sheet preview updated: {self.current_sheet}")
    
    def process_data(self):
        """
        Process the Excel data according to Direct Cost Master requirements.
        Implements the business logic from process_description.txt.
        """
        if not self.processor.sheets_data:
            ui.notify('No data to process. Please upload a file first.', type='warning')
            return
        
        try:
            selected_month = self.month_select.value
            selected_year = self.year_select.value
            selected_period = f"{selected_month} {selected_year}"
            ui.notify(f'Processing P&L file for {selected_period}...', type='info')
            print(self.processor.sheets_data['DL costs (direct)'])
            # Process the current file using our DC processor with selected month
            processed_records = self.dc_processor.process_file_for_month(
                self.processor.sheets_data, 
                self.processor.file_name,
                selected_period
            )
            
            if not processed_records:
                ui.notify(f'No data was processed for {selected_period}. Please check the file format and month availability.', type='warning')
                return
            
            # Add processed data to master file
            self.master_manager.add_project_data(processed_records)
            
            # Update results display
            self.update_results_display()
            
            logger.info(f"Successfully processed {len(processed_records)} records for {selected_month}")
            ui.notify(f'Successfully processed {len(processed_records)} records for {selected_month}!', type='positive')
            
        except Exception as e:
            logger.error(f"Error in data processing: {str(e)}")
            ui.notify(f'Error processing data: {str(e)}', type='negative')
    
    def clear_master_data(self):
        """Clear all processed data from the master file."""
        self.master_manager.clear_master_data()
        self.results_card.classes(add='hidden')
        ui.notify('All master data cleared.', type='info')
    
    def update_results_display(self):
        """Update the results display with current master data."""
        # Get both DL and VC dataframes
        master_dl_df, master_vc_df = self.master_manager.get_master_dataframes()
        
        # Combine for display purposes
        combined_dfs = []
        if not master_dl_df.empty:
            combined_dfs.append(master_dl_df)
        if not master_vc_df.empty:
            combined_dfs.append(master_vc_df)
        
        if not combined_dfs:
            return
            
        master_df = pd.concat(combined_dfs, ignore_index=True) if len(combined_dfs) > 1 else combined_dfs[0]
        
        # Show results card
        self.results_card.classes(remove='hidden')
        
        # Update summary
        total_records = len(master_df)
        unique_projects = master_df['Project'].nunique() if 'Project' in master_df.columns else 0
        unique_employees = master_df['Employee'].nunique() if 'Employee' in master_df.columns else 0
        unique_items = master_df['Item'].nunique() if 'Item' in master_df.columns else 0
        
        summary_text = f"Total Records: {total_records} | Projects: {unique_projects} | Employees: {unique_employees} | Items: {unique_items}"
        self.results_summary.set_text(summary_text)
        
        # Update results table (show first 50 rows for preview)
        preview_df = master_df.head(50)
        columns = [{'name': col, 'label': col, 'field': col} for col in preview_df.columns]
        rows = preview_df.fillna('').to_dict('records')
        
        self.results_table.columns = columns
        self.results_table.rows = rows
        self.results_table.update()
    
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
            self.create_data_preview_section()
            self.create_process_section()
            self.create_results_section()
    
    def run(self, host: str = '127.0.0.1', port: int = 8080):
        """Run the application."""
        self.create_ui()
        
        logger.info(f"Starting Direct Cost Master application on {host}:{port}")
        ui.run(host=host, port=port, title='Direct Cost Master', favicon='📊')

app = DirectCostMasterApp()
app.run()  # Start the application