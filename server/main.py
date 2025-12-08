"""
Direct Cost Master - API Server
FastAPI-based REST API server for the Direct Cost Master application
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
import uvicorn
import os
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta
import jwt
import io
import uuid
from contextlib import asynccontextmanager

# Import our existing modules (adapted for API use)
from auth_service import auth_api_service
from processing_service import processing_api_service
from data_service import data_api_service
from auth_models import auth_db_config
from memory_data_service import memory_data_service
from schemas import *

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global services (use the global instances)
auth_service = auth_api_service
processing_service = processing_api_service
data_service = data_api_service

# Security
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    try:
        auth_db_config.create_tables()
        logger.info("Authentication database initialized successfully")
        logger.info("In-memory data service ready - DL/VC records will be stored in memory")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        # Continue without database in development
    
    yield
    
    # Shutdown
    logger.info("Server shutting down")


# Create FastAPI application
app = FastAPI(
    title="Direct Cost Master API",
    description="REST API for Direct Cost Master Excel processing application",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],  # NiceGUI client
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency for getting current user from JWT token
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Extract and validate user from JWT token"""
    try:
        token = credentials.credentials
        user = auth_service.verify_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}


# Authentication endpoints
@app.post("/api/v1/auth/login", response_model=LoginResponse)
async def login_user(login_data: LoginRequest):
    """Authenticate user and receive JWT token"""
    try:
        success, message, user, token = auth_service.authenticate_user(
            username=login_data.username,
            password=login_data.password
        )
        
        if success and user and token:
            return LoginResponse(
                success=True,
                message=message,
                token=token,
                user=UserInfo(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name
                ),
                expires_in=86400  # 24 hours
            )
        else:
            raise HTTPException(status_code=401, detail=message)
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")


@app.post("/api/v1/auth/refresh", response_model=TokenRefreshResponse)
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """Refresh JWT token"""
    try:
        new_token = auth_service.generate_token(current_user)
        return TokenRefreshResponse(
            success=True,
            token=new_token,
            expires_in=86400
        )
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(status_code=500, detail="Token refresh failed")


# File processing endpoints
@app.post("/api/v1/files/upload", response_model=FileUploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload multiple Excel files for processing"""
    try:
        uploaded_files = []
        
        for file in files:
            if not file.filename.lower().endswith(('.xlsx', '.xls')):
                continue
                
            # Read file content
            content = await file.read()
            
            # Store file temporarily
            file_id = str(uuid.uuid4())
            file_info = processing_service.store_uploaded_file(
                file_id=file_id,
                filename=file.filename,
                content=content,
                user_id=current_user['id']
            )
            
            uploaded_files.append(file_info)
        
        return FileUploadResponse(
            success=True,
            message=f"Successfully uploaded {len(uploaded_files)} files",
            uploaded_files=uploaded_files
        )
        
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="File upload failed")


@app.post("/api/v1/files/process", response_model=ProcessingStartResponse)
async def start_processing(
    process_request: ProcessingRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Start processing uploaded files"""
    try:
        job_id = str(uuid.uuid4())
        
        # Start background processing with analysis mode
        background_tasks.add_task(
            processing_service.process_files_async,
            job_id=job_id,
            file_ids=process_request.file_ids,
            month=process_request.month,
            year=process_request.year,
            user_id=current_user['id'],
            analysis_mode=process_request.analysis_mode
        )
        
        # Estimate duration based on mode
        estimated_duration = 30 if process_request.analysis_mode == 'single' else 60
        
        return ProcessingStartResponse(
            success=True,
            message=f"Processing started ({process_request.analysis_mode} mode)",
            job_id=job_id,
            estimated_duration=estimated_duration
        )
        
    except Exception as e:
        logger.error(f"Processing start error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start processing")


@app.post("/api/v1/files/compare-previous", response_model=ProcessingStartResponse)
async def start_previous_month_comparison(
    request: PreviousMonthComparisonRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Start previous-month comparison (two-file mode)."""
    try:
        if len(request.file_ids) != 2:
            raise HTTPException(status_code=400, detail="Previous-month comparison requires exactly 2 files.")

        job_id = str(uuid.uuid4())
        background_tasks.add_task(
            processing_service.process_previous_month_comparison,
            job_id=job_id,
            file_ids=request.file_ids,
            user_id=current_user['id']
        )

        return ProcessingStartResponse(
            success=True,
            message="Previous-month comparison started",
            job_id=job_id,
            estimated_duration=30
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Previous-month comparison start error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start previous-month comparison")


@app.post('/api/v1/reconcile/program/propose', response_model=ReconcileReportResponse)
async def propose_reconcile_program(
    request: ReconcileProgramRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate a reconciliation proposal for a program-level P&L file (do not apply changes)."""
    try:
        # Only allow one program file per request - processing service enforces single-file policy
        report = processing_service.propose_reconcile_program(
            file_id=request.file_id,
            month=request.month,
            year=request.year,
            user_id=current_user['id']
        )
        return report
    except Exception as e:
        logger.error(f"Propose reconcile error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/v1/reconcile/program/apply', response_model=ApplyReconcileResponse)
async def apply_reconcile_program(
    request: ApplyReconcileRequest,
    current_user: dict = Depends(get_current_user)
):
    """Apply approved reconciliation additions from a program P&L file to the user's data."""
    try:
        success, message, applied_dl, applied_vc = processing_service.apply_reconcile_program(
            file_id=request.file_id,
            month=request.month,
            year=request.year,
            additions=request.additions,
            user_id=current_user['id']
        )
        return ApplyReconcileResponse(
            success=success,
            message=message,
            applied_dl=applied_dl,
            applied_vc=applied_vc
        )
    except Exception as e:
        logger.error(f"Apply reconcile error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/files/compare-previous/{job_id}/download")
async def download_previous_month_comparison(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Download the comparison report Excel for a completed job."""
    try:
        content, filename = processing_service.get_comparison_download(job_id, current_user['id'])
        return StreamingResponse(
            io.BytesIO(content),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Comparison download error: {str(e)}")
        raise HTTPException(status_code=404, detail="Comparison report not found")


@app.get("/api/v1/files/process/{job_id}/status", response_model=ProcessingStatusResponse)
async def get_processing_status(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Check processing status"""
    try:
        status = processing_service.get_job_status(job_id, current_user['id'])
        return ProcessingStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get processing status")


# Data retrieval endpoints
@app.get("/api/v1/data/summary", response_model=DataSummaryResponse)
async def get_data_summary(
    period: Optional[str] = None,
    project: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get user's processed data summary"""
    try:
        summary = data_service.get_user_data_summary(
            user_id=current_user['id'],
            period=period,
            project=project
        )
        return DataSummaryResponse(**summary)
        
    except Exception as e:
        logger.error(f"Data summary error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get data summary")


@app.get("/api/v1/data/dl-costs", response_model=DLCostDataResponse)
async def get_dl_costs(
    period: Optional[str] = None,
    project: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get DL cost records with pagination"""
    try:
        data = data_service.get_dl_cost_records(
            user_id=current_user['id'],
            period=period,
            project=project,
            page=page,
            limit=limit
        )
        return DLCostDataResponse(**data)
        
    except Exception as e:
        logger.error(f"DL costs retrieval error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get DL cost data")


@app.get("/api/v1/data/vc-costs", response_model=VCCostDataResponse)
async def get_vc_costs(
    period: Optional[str] = None,
    project: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get VC cost records with pagination"""
    try:
        data = data_service.get_vc_cost_records(
            user_id=current_user['id'],
            period=period,
            project=project,
            page=page,
            limit=limit
        )
        return VCCostDataResponse(**data)
        
    except Exception as e:
        logger.error(f"VC costs retrieval error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get VC cost data")


# Export endpoints
@app.post("/api/v1/export/excel", response_model=ExportResponse)
async def create_excel_export(
    export_request: ExportRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate Excel export of user's data"""
    try:
        download_info = data_service.create_excel_export(
            user_id=current_user['id'],
            period=export_request.period,
            project=export_request.project,
            include_dl=export_request.include_dl,
            include_vc=export_request.include_vc
        )
        return ExportResponse(**download_info)
        
    except Exception as e:
        logger.error(f"Excel export error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create Excel export")


@app.get("/api/v1/downloads/{download_id}")
async def download_file(
    download_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Download generated Excel file"""
    try:
        file_data, filename = data_service.get_download_file(download_id, current_user['id'])
        
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=404, detail="File not found")


# Utility endpoints
@app.delete("/api/v1/data/clear", response_model=ClearDataResponse)
async def clear_user_data(
    clear_request: ClearDataRequest,
    current_user: dict = Depends(get_current_user)
):
    """Clear user's processed data"""
    try:
        success, message = data_service.clear_user_data(
            user_id=current_user['id'],
            period=clear_request.period,
            project=clear_request.project
        )
        
        if success:
            return ClearDataResponse(success=True, message=message)
        else:
            raise HTTPException(status_code=500, detail=message)
            
    except Exception as e:
        logger.error(f"Clear data error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear data")


@app.get("/api/v1/user/projects", response_model=UserProjectsResponse)
async def get_user_projects(current_user: dict = Depends(get_current_user)):
    """Get user's projects list"""
    try:
        projects = data_service.get_user_projects(current_user['id'])
        return UserProjectsResponse(projects=projects)
        
    except Exception as e:
        logger.error(f"Projects retrieval error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get projects")


if __name__ == "__main__":
    # Configuration - bind to 0.0.0.0 for Docker, can override via env
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    # Run server
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
