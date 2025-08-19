"""
Pydantic schemas for API request and response models
"""

from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime


# User-related schemas
class UserInfo(BaseModel):
    id: int
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserRegistrationRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)


class UserRegistrationResponse(BaseModel):
    success: bool
    message: str
    user: Optional[UserInfo] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    user: Optional[UserInfo] = None
    expires_in: Optional[int] = None


class TokenRefreshResponse(BaseModel):
    success: bool
    token: str
    expires_in: int


# File processing schemas
class UploadedFileInfo(BaseModel):
    filename: str
    file_id: str
    sheets_count: int
    status: str


class FileUploadResponse(BaseModel):
    success: bool
    message: str
    uploaded_files: List[UploadedFileInfo]


class ProcessingRequest(BaseModel):
    file_ids: List[str]
    month: str
    year: str


class ProcessingStartResponse(BaseModel):
    success: bool
    message: str
    job_id: str
    estimated_duration: int


class ProcessingResults(BaseModel):
    total_records: int
    dl_records: int
    vc_records: int
    projects: int
    successful_files: int
    failed_files: int
    error_details: Optional[List[str]] = None


class ProcessingStatusResponse(BaseModel):
    job_id: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    progress: int  # 0-100
    results: Optional[ProcessingResults] = None
    error_message: Optional[str] = None


# Data retrieval schemas
class DataSummary(BaseModel):
    total_records: int
    dl_records: int
    vc_records: int
    unique_projects: int
    unique_employees: int


class DataSummaryResponse(BaseModel):
    summary: DataSummary
    periods: List[str]
    projects: List[str]


class DLCostRecord(BaseModel):
    employee: str
    project: str
    month: str
    bucket: str
    dc_hours: Optional[float]
    total_dl_costs: float
    source_file: Optional[str] = None
    created_at: Optional[datetime] = None


class VCCostRecord(BaseModel):
    item: str
    project: str
    month: str
    bucket: str
    total_dl_costs: float  # Note: despite name, this is VC costs
    source_file: Optional[str] = None
    created_at: Optional[datetime] = None


class PaginationInfo(BaseModel):
    page: int
    limit: int
    total: int
    pages: int


class DLCostDataResponse(BaseModel):
    records: List[DLCostRecord]
    pagination: PaginationInfo


class VCCostDataResponse(BaseModel):
    records: List[VCCostRecord]
    pagination: PaginationInfo


# Export schemas
class ExportRequest(BaseModel):
    period: Optional[str] = None
    project: Optional[str] = None
    include_dl: bool = True
    include_vc: bool = True


class ExportResponse(BaseModel):
    success: bool
    download_url: str
    expires_at: datetime
    filename: str


# Utility schemas
class ClearDataRequest(BaseModel):
    period: Optional[str] = None
    project: Optional[str] = None


class ClearDataResponse(BaseModel):
    success: bool
    message: str


# Reconciliation schemas
class ProposedAddition(BaseModel):
    project: str
    type: str  # 'DL' or 'VC'
    employee: Optional[str] = None
    item: Optional[str] = None
    bucket: str
    dc_hours: Optional[float] = None
    total_dl_costs: float
    source_file: Optional[str] = None


class ReconcileProgramRequest(BaseModel):
    file_id: str
    month: str
    year: str


class ReconcileReportResponse(BaseModel):
    program_name: str
    period: str
    proposed_additions: List[ProposedAddition]
    total_proposed_amount: float
    proposed_count: int


class ApplyReconcileRequest(BaseModel):
    file_id: str
    month: str
    year: str
    additions: List[ProposedAddition]


class ApplyReconcileResponse(BaseModel):
    success: bool
    message: str
    applied_dl: int
    applied_vc: int


class ProjectInfo(BaseModel):
    id: int
    name: str
    dl_records: int
    vc_records: int
    created_at: datetime


class UserProjectsResponse(BaseModel):
    projects: List[ProjectInfo]


# Error response schema
class ErrorResponse(BaseModel):
    detail: str
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Generic API response wrapper
class APIResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
