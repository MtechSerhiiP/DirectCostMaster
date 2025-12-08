"""
Direct Cost Master - NiceGUI Client
Modern web interface that communicates with the FastAPI server
"""

import io
import os
import asyncio
import time
from typing import Optional, Dict, Any, List
import logging
from dotenv import load_dotenv
from nicegui import ui, app

# Import API client
from api_client import api_client

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DirectCostMasterClient:
    """
    Client application for Direct Cost Master using NiceGUI.
    Communicates with FastAPI server via REST API.
    """
    
    def __init__(self):
        # Authentication state (managed by api_client)
        self.current_user = None
        self.is_authenticated = False
        
        # UI components references
        self.upload_area = None
        self.file_info_card = None
        self.files_list_card = None
        self.process_button = None
        self.download_button = None
        self.results_card = None
        self.month_select = None
        self.year_select = None
        self.analysis_mode_radio = None  # New: analysis mode selector
        # Comparison mode is now selected via radio (no separate checkbox)
        self.enable_prev_month_comparison = False
        
        # Authentication UI components
        self.login_card = None
        self.user_info_card = None
        self.login_username = None
        self.login_password = None
        
        # Files management
        self.files_list_table = None
        self.clear_files_button = None
        self.uploaded_files = []  # Store uploaded file info
        
        # Results components
        self.results_summary = None
        self.dl_tab = None
        self.vc_tab = None
        self.dl_summary = None
        self.vc_summary = None
        self.dl_results_table = None
        self.vc_results_table = None
        
        # Processing state
        self.current_job_id = None
        self.processing_timer = None
        
        
        # Main content container
        self.main_content = None
        
        # Server connection status
        self.server_status_label = None
    
    def create_header(self):
        """Create the application header with title and server status."""
        with ui.row().classes('w-full justify-between items-center mb-8'):
            with ui.column().classes('text-left'):
                ui.label('Direct Cost Master').classes('text-4xl font-bold text-blue-600 mb-2')
                ui.label('Excel File Processing Application').classes('text-lg text-gray-600')
                # Add memory mode indicator
                ui.label('🧠 Memory Mode: Data stored in memory (faster, but temporary)').classes('text-sm text-orange-600 font-medium mt-1')
            
            with ui.column().classes('text-right'):
                self.server_status_label = ui.label().classes('text-sm')
                self.update_server_status()
        
        ui.separator().classes('w-full mt-4')
    
    def update_server_status(self):
        """Update server connection status"""
        if api_client.check_server_health():
            self.server_status_label.set_text('🟢 Server: Online')
            self.server_status_label.classes(remove='text-red-500')
            self.server_status_label.classes(add='text-green-500')
        else:
            self.server_status_label.set_text('🔴 Server: Offline')
            self.server_status_label.classes(remove='text-green-500')
            self.server_status_label.classes(add='text-red-500')
    
    def create_auth_section(self):
        """Create authentication section with login forms."""
        # Login Card
        self.login_card = ui.card().classes('w-full max-w-md mx-auto p-6 shadow-lg')
        
        with self.login_card:
            ui.label('Login').classes('text-2xl font-bold text-center mb-6')
            
            self.login_username = ui.input('Username or Email').classes('w-full mb-4')
            self.login_password = ui.input('Password', password=True).classes('w-full mb-4')
            
            with ui.row().classes('w-full gap-4'):
                ui.button('Login', on_click=self.handle_login).classes(
                    'flex-1 bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 rounded'
                )
    
    def create_user_info_section(self):
        """Create user information and logout section."""
        self.user_info_card = ui.card().classes('w-full max-w-4xl mx-auto p-4 shadow-lg mb-6 hidden')
        
        with self.user_info_card:
            with ui.row().classes('w-full justify-between items-center'):
                self.user_welcome_label = ui.label().classes('text-lg font-medium')
                ui.button('Logout', on_click=self.handle_logout).classes(
                    'bg-red-500 hover:bg-red-600 text-white font-semibold py-2 px-4 rounded'
                )
    
    async def handle_login(self):
        """Handle user login via API"""
        username = self.login_username.value
        password = self.login_password.value
        
        if not username or not password:
            ui.notify('Please enter both username and password', type='warning')
            return
        
        # Check server connection first
        if not api_client.check_server_health():
            ui.notify('Server is not available. Please try again later.', type='negative')
            return
        
        try:
            success, message, user = api_client.login(username, password)
            
            if success and user:
                self.current_user = user
                self.is_authenticated = True
                
                # Update UI
                self.show_main_application()
                ui.notify(f'Welcome, {user.get("first_name") or user.get("username")}!', type='positive')
                
                # Load user's existing data
                await self.load_user_data()
            else:
                ui.notify(message, type='negative')
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            ui.notify('Login failed. Please try again.', type='negative')
    
    def handle_logout(self):
        """Handle user logout"""
        try:
            api_client.logout()
            
            # Clear state
            self.current_user = None
            self.is_authenticated = False
            self.uploaded_files.clear()
            self.current_job_id = None
            
            # Stop any processing timer
            if self.processing_timer:
                self.processing_timer.cancel()
                self.processing_timer = None
            
            # Show login form
            self.show_login_form()
            ui.notify('Logged out successfully', type='info')
            
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            ui.notify('Logout completed', type='info')
    
    
    def show_login_form(self):
        """Show login form and hide registration form"""
        self.login_card.classes(remove='hidden')
        self.main_content.classes(add='hidden')
        self.user_info_card.classes(add='hidden')
    
    def show_main_application(self):
        """Show main application and hide auth forms"""
        self.login_card.classes(add='hidden')
        self.user_info_card.classes(remove='hidden')
        self.main_content.classes(remove='hidden')
        
        # Update user welcome message
        if self.current_user:
            welcome_text = f"Welcome, {self.current_user.get('first_name') or self.current_user.get('username')}!"
            self.user_welcome_label.set_text(welcome_text)
    
    async def load_user_data(self):
        """Load user's existing data from server"""
        print("🔄 Loading user data...")
        print(f"Authentication status: {self.is_authenticated}")
        
        if not self.is_authenticated:
            print("❌ Not authenticated, skipping data load")
            return
        
        try:
            print("📊 Requesting user data summary...")
            logger.info("Loading user's existing data...")
            success, summary_data = api_client.get_data_summary()
            
            print(f"Data summary response - Success: {success}")
            print(f"Data summary response - Data: {summary_data}")
            
            if success:
                summary = summary_data.get('summary', {})
                total_records = summary.get('total_records', 0)
                
                print(f"📈 Found {total_records} existing records")
                logger.info(f"Found {total_records} existing records")
                
                if total_records > 0:
                    ui.notify(f'Loaded {total_records} existing records', type='info')
                    print("✅ Updating results display with existing data...")
                    # Update results display
                    await self.update_results_display()
                else:
                    print("ℹ️ No existing data found, showing empty results")
                    logger.info("No existing data found")
                    # Still show the results card with "no data" message
                    await self.update_results_display()
            else:
                error_msg = summary_data.get('error', 'Unknown error') if isinstance(summary_data, dict) else str(summary_data)
                print(f"❌ Failed to load user data: {error_msg}")
                logger.error(f"Failed to load user data: {error_msg}")
                ui.notify('Failed to load existing data', type='warning')
                
        except Exception as e:
            print(f"❌ Exception in load_user_data: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            
            logger.error(f"Error loading user data: {str(e)}")
            ui.notify('Failed to load existing data', type='warning')
    
    def create_upload_section(self):
        """Create the file upload section."""
        with ui.card().classes('w-full max-w-2xl mx-auto p-6 shadow-lg'):
            ui.label('Upload Excel Files').classes('text-xl font-semibold mb-4')
            
            # File upload component
            upload = ui.upload(
                on_upload=self.handle_file_upload,
                multiple=True,
                auto_upload=True,
                max_files=20
            ).classes('w-full')
            
            upload.props('accept=".xlsx,.xls" color="primary" flat bordered')
            upload.tooltip('Select Excel files (.xlsx or .xls) - Maximum 20 files')
            
            with ui.row().classes('w-full justify-center mt-4'):
                ui.label('Drag and drop your Excel files here or click to browse (Max: 20 files)').classes('text-gray-500 text-sm')
    
    def create_files_list_section(self):
        """Create the uploaded files list section."""
        self.files_list_card = ui.card().classes('w-full max-w-4xl mx-auto p-6 shadow-lg mt-6 hidden')
        
        with self.files_list_card:
            with ui.row().classes('w-full justify-between items-center mb-4'):
                ui.label('Uploaded Files').classes('text-xl font-semibold')
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

            # Program reconcile button
            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Propose Program Reconcile', on_click=self.handle_propose_program_reconcile).classes(
                    'bg-indigo-500 hover:bg-indigo-600 text-white font-semibold py-2 px-4 rounded'
                )
    
    def create_process_section(self):
        """Create the data processing controls section."""
        with ui.card().classes('w-full max-w-2xl mx-auto p-6 shadow-lg mt-6'):
            ui.label('Process Data').classes('text-xl font-semibold mb-4')
            
            # Month and Year selection row
            with ui.row().classes('w-full gap-4 mb-4'):
                with ui.column().classes('flex-1'):
                    ui.label('Select Month:').classes('text-sm font-medium mb-2')
                    self.month_select = ui.select(
                        options=['January', 'February', 'March', 'April', 'May', 'June',
                                'July', 'August', 'September', 'October', 'November', 'December'],
                        value='July'
                    ).classes('w-full')

                with ui.column().classes('flex-1'):
                    ui.label('Select Year:').classes('text-sm font-medium mb-2')
                    self.year_select = ui.select(
                        options=['2025', '2024', '2023', '2022', '2021', '2020'],
                        value='2025'
                    ).classes('w-full')

            # Analysis mode selection (radio buttons) including previous-month comparison
            ui.label('Analysis Mode:').classes('text-sm font-medium mb-2')
            self.analysis_mode_radio = ui.radio(
                options={
                    'single': 'Single Month - Process only selected month',
                    'ytd': 'YTD (Year-to-Date) - Process January through selected month',
                    'prev_month': 'Compare with previous month (two-file mode)'
                },
                value='single'
            ).classes('w-full mb-4')

            # Info about YTD mode
            with ui.row().classes('w-full mb-4'):
                ui.icon('info', size='sm').classes('text-blue-500')
                ui.label(
                    'YTD mode will process all months from January to the selected month. '
                    'If some months are missing in a file, a warning will be shown.'
                ).classes('text-xs text-gray-500 ml-2')

            with ui.row().classes('w-full gap-4'):
                self.process_button = ui.button(
                    'Process All P&L Files',
                    on_click=self.process_all_files
                ).classes('flex-1 bg-blue-500 hover:bg-blue-600 text-white font-semibold py-3 rounded-lg disabled:opacity-50')

                clear_button = ui.button(
                    'Clear All Data',
                    on_click=self.clear_master_data
                ).classes('bg-red-500 hover:bg-red-600 text-white font-semibold py-3 px-6 rounded-lg')

            self.process_button.set_enabled(False)

            ui.label(
                'This will process all uploaded Excel files for the selected month/period.'
            ).classes('text-sm text-gray-500 mt-2')

    def create_results_section(self):
        """Create the results and download section."""
        self.results_card = ui.card().classes('w-full max-w-6xl mx-auto p-6 shadow-lg mt-6 hidden')
        
        with self.results_card:
            ui.label('Processing Results').classes('text-xl font-semibold mb-4')
            
            # Results summary
            self.results_summary = ui.label().classes('text-sm text-gray-600 mb-4')
            
            # Action buttons row
            with ui.row().classes('w-full gap-4 mb-4'):
                self.download_button = ui.button(
                    'Download Master DC File',
                    on_click=self.download_master_file
                ).classes('bg-green-500 hover:bg-green-600 text-white font-semibold py-3 px-6 rounded-lg')
                
                # Add refresh button
                ui.button(
                    'Refresh Results',
                    on_click=self.refresh_results
                ).classes('bg-blue-500 hover:bg-blue-600 text-white font-semibold py-3 px-6 rounded-lg')
            
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
    
    async def handle_file_upload(self, event):
        """Handle file upload via API"""
        try:
            if not self.is_authenticated:
                ui.notify('Please login first', type='warning')
                return
            
            if len(self.uploaded_files) >= 20:
                ui.notify('Maximum 20 files allowed. Please clear existing files first.', type='warning')
                return
            
            # NiceGUI SmallFileUpload: read() is async, returns bytes
            file_obj = event.file
            filename = file_obj.name
            file_content = await file_obj.read()
            
            # Check if file already uploaded
            if any(f['filename'] == filename for f in self.uploaded_files):
                ui.notify(f'File {filename} is already uploaded.', type='warning')
                return
            
            # Upload to server
            success, message, uploaded_files = api_client.upload_files([(filename, file_content)])
            
            if success and uploaded_files:
                # Store file info locally
                self.uploaded_files.extend(uploaded_files)
                self.update_files_list()
                ui.notify(f'Successfully uploaded: {filename}', type='positive')
            else:
                ui.notify(f'Error uploading {filename}: {message}', type='negative')
                
        except Exception as e:
            logger.error(f"Error in file upload: {str(e)}")
            ui.notify(f'Error uploading file: {str(e)}', type='negative')
    
    def update_files_list(self):
        """Update the files list display."""
        if not self.uploaded_files:
            self.files_list_card.classes(add='hidden')
            self.process_button.set_enabled(False)
            return
        
        # Show files list card
        self.files_list_card.classes(remove='hidden')
        
        # Prepare rows for the table
        rows = []
        for file_info in self.uploaded_files:
            rows.append({
                'filename': file_info['filename'],
                'status': file_info['status'],
                'sheets': file_info['sheets_count']
            })
        
        # Update table
        self.files_list_table.rows = rows
        self.files_list_table.update()
        
        # Enable processing button
        self.process_button.set_enabled(True)
        
        ui.notify(f'Total files uploaded: {len(self.uploaded_files)}', type='info')
    
    def clear_all_files(self):
        """Clear all uploaded files."""
        self.uploaded_files.clear()
        self.files_list_card.classes(add='hidden')
        self.process_button.set_enabled(False)
        ui.notify('All files cleared.', type='info')
    
    async def process_all_files(self):
        """Process files: default analysis OR previous-month comparison."""
        
        # --- Basic validation ---
        if not self.uploaded_files:
            ui.notify('No files to process. Please upload files first.', type='warning')
            return
        
        if not self.is_authenticated:
            ui.notify('Please login first', type='warning')
            return

        try:
            file_ids = [f['file_id'] for f in self.uploaded_files]
            selected_month = self.month_select.value
            selected_year = self.year_select.value
            analysis_mode = self.analysis_mode_radio.value  # 'single', 'ytd', 'prev_month'
            #  NEW FEATURE: PREVIOUS MONTH COMPARISON (radio option)
            if analysis_mode == 'prev_month':

                # Strict validation: need exactly 2 files
                if len(file_ids) != 2:
                    ui.notify(
                        'Previous month comparison requires exactly 2 Excel files:\n'
                        '• current month\n'
                        '• previous month',
                        type='warning',
                    )
                    return

                ui.notify(
                    'Starting previous-month comparison for 2 files...',
                    type='info'
                )

                # Start job via new API route
                success, message, job_id = api_client.start_previous_month_comparison(file_ids)

                if not success or not job_id:
                    ui.notify(f'Failed to start comparison: {message}', type='negative')
                    return

                self.current_job_id = job_id
                await self.poll_processing_status()
                return  # stop here, do NOT run default logic

            #  (Single Month / YTD)

            if analysis_mode == 'ytd':
                mode_text = f"YTD (January - {selected_month}) {selected_year}"
            else:
                mode_text = f"{selected_month} {selected_year}"

            ui.notify(
                f'Starting processing of {len(file_ids)} files for {mode_text}...',
                type='info'
            )

            success, message, job_id = api_client.start_processing(
                file_ids,
                selected_month,
                selected_year,
                analysis_mode
            )

            if success and job_id:
                self.current_job_id = job_id
                ui.notify(
                    f'Processing started ({analysis_mode} mode). Checking progress...',
                    type='info'
                )
                await self.poll_processing_status()
            else:
                ui.notify(f'Failed to start processing: {message}', type='negative')

        except Exception as e:
            logger.error(f"Error starting processing: {str(e)}")
            ui.notify(f'Error starting processing: {str(e)}', type='negative')

    
    async def poll_processing_status(self):
        """Poll processing status until completion"""
        if not self.current_job_id:
            return
        
        try:
            while True:
                success, status_data = api_client.get_processing_status(self.current_job_id)
                
                if not success:
                    ui.notify('Failed to get processing status', type='warning')
                    break
                
                status = status_data.get('status')
                progress = status_data.get('progress', 0)
                
                if status == 'completed':
                    results = status_data.get('results', {})
                    total_records = results.get('total_records', 0)
                    successful_files = results.get('successful_files', 0)
                    failed_files = results.get('failed_files', 0)
                    total_mismatches = results.get('total_mismatches')
                    
                    # Check if this is a comparison job (has total_mismatches)
                    if total_mismatches is not None:
                        # Comparison job
                        current_file = results.get('current_file', 'Unknown')
                        previous_file = results.get('previous_file', 'Unknown')
                        ui.notify(
                            f'Comparison completed! Found {total_mismatches} cell mismatches between {current_file} and {previous_file}',
                            type='positive'
                        )
                        
                        # Show download button for comparison report
                        download_url = results.get('download_url', '')
                        if download_url:
                            
                            async def download_comparison():
                                # Wait a moment for the file to be fully stored on server
                                await asyncio.sleep(0.5)
                                
                                # Retry logic in case of timing issues
                                max_retries = 3
                                for attempt in range(max_retries):
                                    dl_success, file_content, filename = api_client.download_comparison_report(self.current_job_id)
                                    if dl_success:
                                        ui.download(file_content, filename)
                                        ui.notify('Comparison report downloaded successfully!', type='positive')
                                        return
                                    elif attempt < max_retries - 1:
                                        # Retry after delay
                                        await asyncio.sleep(0.5)
                                
                                # All retries failed
                                ui.notify('Failed to download comparison report after multiple attempts', type='negative')
                            
                            ui.notify('📥 Downloading comparison report...', type='info')
                            await download_comparison()
                    else:
                        # Regular processing job
                        ui.notify(f'Processing completed! {total_records} records from {successful_files} files', type='positive')
                        
                        if failed_files > 0:
                            ui.notify(f'Note: {failed_files} files failed to process', type='warning')
                        
                        # Show YTD warnings if any
                        ytd_warnings = results.get('ytd_warnings', [])
                        if ytd_warnings:
                            for warning in ytd_warnings:
                                missing = warning.get('missing_months', [])
                                filename = warning.get('filename', 'Unknown file')
                                if missing:
                                    ui.notify(
                                        f'⚠️ {filename}: Missing months: {", ".join(missing)}',
                                        type='warning',
                                        timeout=10000  # Show for 10 seconds
                                    )
                        
                        # Update results display
                        await self.update_results_display()
                    break
                    
                elif status == 'failed':
                    error_message = status_data.get('error_message', 'Unknown error')
                    ui.notify(f'Processing failed: {error_message}', type='negative')
                    break
                    
                elif status == 'processing':
                    ui.notify(f'Processing... ({progress}%)', type='info')
                    
                # Wait before next check
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"Error polling status: {str(e)}")
            ui.notify(f'Error checking processing status: {str(e)}', type='negative')
        finally:
            self.current_job_id = None
    
    async def update_results_display(self):
        """Update the results display with current data"""
        print("=" * 80)
        print("🔄 STARTING RESULTS DISPLAY UPDATE")
        print(f"Authentication status: {self.is_authenticated}")
        print(f"Current user: {getattr(self, 'current_user', 'Not set')}")
        print(f"Results card classes before: {self.results_card.classes}")
        
        if not self.is_authenticated:
            print("❌ Not authenticated, cannot update results")
            logger.warning("Not authenticated, cannot update results")
            return
        
        try:
            print("📊 Requesting data summary from API...")
            logger.info("Updating results display...")
            
            # Get data summary
            success, summary_data = api_client.get_data_summary()
            
            print(f"API Response - Success: {success}")
            print(f"API Response - Data: {summary_data}")
            
            if not success:
                error_msg = summary_data.get('error', 'Unknown error') if isinstance(summary_data, dict) else str(summary_data)
                print(f"❌ API call failed: {error_msg}")
                logger.error(f"Failed to get data summary: {error_msg}")
                ui.notify(f'Failed to load data: {error_msg}', type='warning')
                return
            
            logger.info(f"Data summary received: {summary_data}")
            
            summary = summary_data.get('summary', {})
            total_records = summary.get('total_records', 0)
            
            print(f"📈 Processing summary data:")
            print(f"  - Total records: {total_records}")
            print(f"  - Full summary: {summary}")
            
            logger.info(f"Total records found: {total_records}")
            
            # Show results card even if no records (to show "no data" message)
            print("🎯 Making results card visible...")
            self.results_card.classes(remove='hidden')
            print(f"Results card classes after removing hidden: {self.results_card.classes}")
            
            # Update summary
            dl_records = summary.get('dl_records', 0)
            vc_records = summary.get('vc_records', 0)
            unique_projects = summary.get('unique_projects', 0)
            
            if total_records > 0:
                summary_text = f"Total Records: {total_records} | DL Records: {dl_records} | VC Records: {vc_records} | Projects: {unique_projects}"
                print(f"✅ Data found - Summary: {summary_text}")
            else:
                summary_text = "No processed data available. Upload and process files to see results."
                print(f"ℹ️ No data - Summary: {summary_text}")
            
            print(f"📝 Updating summary label with: {summary_text}")
            self.results_summary.set_text(summary_text)
            logger.info(f"Summary updated: {summary_text}")
            
            print("✅ RESULTS DISPLAY UPDATE COMPLETED SUCCESSFULLY")
            print("=" * 80)
            
            # Update DL Costs tab
            if dl_records > 0:
                logger.info(f"Loading DL costs data ({dl_records} records)...")
                dl_success, dl_data = api_client.get_dl_costs(limit=50)
                logger.info(f"DL costs API call result: success={dl_success}")
                
                if dl_success:
                    records = dl_data.get('records', [])
                    logger.info(f"DL records received: {len(records)} records")
                    
                    self.dl_summary.set_text(f"DL Records: {dl_records} | Showing first {len(records)} records")
                    
                    # Update DL table
                    if records:
                        dl_columns = [
                            {'name': 'employee', 'label': 'Employee', 'field': 'employee'},
                            {'name': 'project', 'label': 'Project', 'field': 'project'},
                            {'name': 'month', 'label': 'Month', 'field': 'month'},
                            {'name': 'bucket', 'label': 'Bucket', 'field': 'bucket'},
                            {'name': 'dc_hours', 'label': 'DC Hours', 'field': 'dc_hours'},
                            {'name': 'total_dl_costs', 'label': 'Total DL Costs', 'field': 'total_dl_costs'}
                        ]
                        self.dl_results_table.columns = dl_columns
                        self.dl_results_table.rows = records
                        self.dl_results_table.update()
                        logger.info("DL table updated successfully")
                    else:
                        logger.warning("DL records list is empty")
                        self.dl_results_table.rows = []
                        self.dl_results_table.update()
                else:
                    error_msg = dl_data.get('error', 'Unknown error') if isinstance(dl_data, dict) else str(dl_data)
                    logger.error(f"Failed to get DL data: {error_msg}")
                    self.dl_summary.set_text(f"Error loading DL data: {error_msg}")
            else:
                logger.info("No DL records available")
                self.dl_summary.set_text("No DL Cost data available")
                self.dl_results_table.rows = []
                self.dl_results_table.update()
            
            # Update VC Costs tab
            if vc_records > 0:
                logger.info(f"Loading VC costs data ({vc_records} records)...")
                vc_success, vc_data = api_client.get_vc_costs(limit=50)
                logger.info(f"VC costs API call result: success={vc_success}")
                
                if vc_success:
                    records = vc_data.get('records', [])
                    logger.info(f"VC records received: {len(records)} records")
                    
                    self.vc_summary.set_text(f"VC Records: {vc_records} | Showing first {len(records)} records")
                    
                    # Update VC table
                    if records:
                        vc_columns = [
                            {'name': 'item', 'label': 'Item', 'field': 'item'},
                            {'name': 'project', 'label': 'Project', 'field': 'project'},
                            {'name': 'month', 'label': 'Month', 'field': 'month'},
                            {'name': 'bucket', 'label': 'Bucket', 'field': 'bucket'},
                            {'name': 'total_dl_costs', 'label': 'Total VC Costs', 'field': 'total_dl_costs'}
                        ]
                        self.vc_results_table.columns = vc_columns
                        self.vc_results_table.rows = records
                        self.vc_results_table.update()
                        logger.info("VC table updated successfully")
                    else:
                        logger.warning("VC records list is empty")
                        self.vc_results_table.rows = []
                        self.vc_results_table.update()
                else:
                    error_msg = vc_data.get('error', 'Unknown error') if isinstance(vc_data, dict) else str(vc_data)
                    logger.error(f"Failed to get VC data: {error_msg}")
                    self.vc_summary.set_text(f"Error loading VC data: {error_msg}")
            else:
                logger.info("No VC records available")
                self.vc_summary.set_text("No VC Cost data available")
                self.vc_results_table.rows = []
                self.vc_results_table.update()
                
        except Exception as e:
            print("❌ EXCEPTION IN RESULTS DISPLAY UPDATE")
            print(f"Exception type: {type(e)}")
            print(f"Exception message: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            print("=" * 80)
            
            logger.error(f"Error updating results: {str(e)}")
            ui.notify(f'Error updating results: {str(e)}', type='negative')

    async def handle_propose_program_reconcile(self):
        """Initiate propose reconcile flow for a single program file (UI side)."""
        if not self.is_authenticated:
            ui.notify('Please login first', type='warning')
            return

        # Must have at least one file uploaded
        if not self.uploaded_files:
            ui.notify('Please upload at least one P&L file to propose reconciliation', type='warning')
            return
        
        with ui.dialog().classes('w-2/3') as dialog, ui.card().classes('p-4'):
            ui.label('Program P&L Reconciliation').classes('text-lg font-bold mb-4')
            
            # Create dropdown for file selection
            file_options = {f.get('file_id'): f.get('filename', 'Unknown') for f in self.uploaded_files}
            selected_file = ui.select(
                options=file_options,
                label='Select Program P&L file',
                value=None  # Let user explicitly select a file
            ).classes('w-full mb-4')
            
            # Create placeholder for proposal content
            proposal_content = ui.column().classes('w-full p-4')
            
            async def propose_reconcile():
                if not selected_file.value:
                    ui.notify('Please select a file', type='warning')
                    return
                
                # Extract just the file_id from the selected option
                if isinstance(selected_file.value, dict):
                    file_id = selected_file.value.get('value')
                else:
                    file_id = selected_file.value

                if not file_id:
                    ui.notify('Please select a valid file', type='warning')
                    return

                selected_month = self.month_select.value
                selected_year = self.year_select.value
                
                ui.notify('Requesting reconciliation proposal from server...', type='info')
                
                success, result = api_client.propose_reconcile_program(file_id, selected_month, selected_year)
                
                if not success:
                    error = result.get('error', 'Unknown error') if isinstance(result, dict) else str(result)
                    ui.notify(f'Failed to get proposal: {error}', type='negative')
                    return
                
                # Update dialog with proposal results
                program_name = result.get('program_name')
                period = result.get('period')
                proposed = result.get('proposed_additions', [])
                total_amount = result.get('total_proposed_amount', 0)
                                
                with proposal_content:
                    proposal_content.clear()
                    # Show proposal details
                    ui.label(f'Reconciliation proposal for {program_name}').classes('text-lg font-bold')
                    ui.label(f'Period: {period}').classes('text-md text-gray-600')
                    ui.label(f'Proposed additions: {len(proposed)} | Total amount: {total_amount}').classes('text-sm text-gray-600 mb-4')
                    
                    # Show table of proposed additions
                    rows = []
                    for p in proposed:
                        rows.append({
                            'type': p.get('type'),
                            'employee': p.get('employee') or p.get('item'),
                            'bucket': p.get('bucket'),
                            'amount': p.get('total_dl_costs')
                        })
                    
                    if rows:
                        ui.table(
                            columns=[
                                {'name': 'type', 'label': 'Type', 'field': 'type'},
                                {'name': 'employee', 'label': 'Employee/Item', 'field': 'employee'},
                                {'name': 'bucket', 'label': 'Bucket', 'field': 'bucket'},
                                {'name': 'amount', 'label': 'Amount', 'field': 'amount'}
                            ],
                            rows=rows
                        ).classes('w-full mb-4')
                    else:
                        ui.label('No additions proposed - all costs accounted for').classes('text-sm text-gray-600 italic mb-4')
                    
                    with ui.row().classes('w-full justify-end gap-4'):
                        ui.button('Cancel', on_click=lambda: dialog.close()).classes(
                            'bg-gray-400 hover:bg-gray-500 text-white py-2 px-4 rounded'
                        )
                        
                        if rows:  # Only show Apply if there are additions
                            async def apply_and_close():
                                # Call apply endpoint with proposed additions
                                apply_success, apply_result = api_client.apply_reconcile_program(file_id, selected_month, selected_year, proposed)
                                if not apply_success:
                                    err = apply_result.get('error', 'Unknown error') if isinstance(apply_result, dict) else str(apply_result)
                                    ui.notify(f'Failed to apply additions: {err}', type='negative')
                                else:
                                    message = apply_result.get('message', 'Applied')
                                    ui.notify(f'Apply result: {message}', type='positive')
                                    # Refresh results display
                                    await self.update_results_display()
                                dialog.close()
                            
                            ui.button('Apply Additions', on_click=apply_and_close).classes(
                                'bg-green-500 hover:bg-green-600 text-white py-2 px-4 rounded'
                            )
            
            # Initial dialog buttons
            with ui.row().classes('w-full justify-end gap-4 mt-4'):
                ui.button('Cancel', on_click=lambda: dialog.close()).classes(
                    'bg-gray-400 hover:bg-gray-500 text-white py-2 px-4 rounded'
                )
                ui.button('Propose Reconciliation', on_click=propose_reconcile).classes(
                    'bg-blue-500 hover:bg-blue-600 text-white py-2 px-4 rounded'
                )

        dialog.open()
    
    async def refresh_results(self):
        """Manually refresh results display"""
        try:
            ui.notify('Refreshing results...', type='info')
            await self.update_results_display()
            ui.notify('Results refreshed successfully!', type='positive')
        except Exception as e:
            print(f"Error refreshing results: {e}")
            ui.notify(f'Error refreshing results: {str(e)}', type='negative')

    async def download_master_file(self):
        """Generate and download the master DC file via API"""
        if not self.is_authenticated:
            ui.notify('Please login first', type='warning')
            return
        
        try:
            # Create export
            success, export_data = api_client.create_excel_export()
            
            if not success:
                ui.notify('Failed to create export. No data available.', type='warning')
                return
            
            download_url = export_data.get('download_url', '')
            download_id = download_url.split('/')[-1] if download_url else ''
            
            if download_id:
                # Download file
                dl_success, file_content, filename = api_client.download_file(download_id)
                
                if dl_success:
                    # Create download
                    ui.download(file_content, filename)
                    ui.notify('Master file downloaded successfully!', type='positive')
                else:
                    ui.notify('Failed to download file', type='negative')
            else:
                ui.notify('Failed to get download link', type='negative')
                
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            ui.notify(f'Error downloading file: {str(e)}', type='negative')
    
    async def clear_master_data(self):
        """Clear all processed data via API"""
        if not self.is_authenticated:
            ui.notify('Please login first', type='warning')
            return
        
        try:
            success, message = api_client.clear_data()
            
            if success:
                self.results_card.classes(add='hidden')
                ui.notify('All data cleared successfully.', type='info')
            else:
                ui.notify(f'Failed to clear data: {message}', type='negative')
                
        except Exception as e:
            logger.error(f"Error clearing data: {str(e)}")
            ui.notify(f'Error clearing data: {str(e)}', type='negative')
    
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
            
            # Authentication section
            self.create_auth_section()
            self.create_user_info_section()
            
            # Main application content (initially hidden)
            self.main_content = ui.column().classes('w-full items-center space-y-6 hidden')
            
            with self.main_content:
                self.create_upload_section()
                self.create_files_list_section()
                self.create_process_section()
                self.create_results_section()
    
    def run(self, host: str = '0.0.0.0', port: int = 8080):
        """Run the client application"""
        # Check server availability on startup
        if not api_client.check_server_health():
            print("⚠️  API Server is not available. Please start the server first.")
            print("   Run 'cd server && python main.py' to start the server.")
        
        # Create UI
        self.create_ui()
        
        logger.info(f"Starting Direct Cost Master client on {host}:{port}")
        ui.run(host=host, port=port, title='Direct Cost Master', favicon='📊')


# Run the client application
if __name__ in {"__main__", "__mp_main__"}:
    try:
        app = DirectCostMasterClient()
        app.run()
    except Exception as e:
        logger.critical(f"Failed to start client application: {str(e)}")
        print(f"❌ Client startup failed: {str(e)}")
        print("Please check the logs and configuration.")
