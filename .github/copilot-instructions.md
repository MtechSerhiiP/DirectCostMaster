# Direct Cost Master - AI Coding Instructions

## Project Overview
Direct Cost Master is a modern Client-Server web application for processing Excel P&L files. It extracts and categorizes Direct Labor (DL) and Variable Cost (VC) data according to specific business rules. The application features a FastAPI backend with JWT authentication, PostgreSQL persistence, and a NiceGUI frontend client.

## Architecture & Key Components

### **Client-Server Architecture**
- **Server** (`/server/`): FastAPI REST API handling business logic, authentication, and data processing
- **Client** (`main.py`): NiceGUI presentation layer making HTTP requests to the server
- **Communication**: Stateless RESTful API with JWT token-based authentication

### Core Processing Pipeline
1. **File Upload**: Client uploads files via API → Server stores temporarily → Returns file IDs
2. **Processing**: Client requests processing → Server processes asynchronously → Returns job ID
3. **Status Polling**: Client polls processing status → Server returns progress/results
4. **Data Retrieval**: Client fetches processed data via paginated API endpoints
5. **Export**: Client requests export → Server generates Excel → Client downloads

### Critical Files & Responsibilities

#### **Server Components** (`/server/`)
- `main.py`: FastAPI application with all REST endpoints
- `auth_service.py`: JWT-based authentication (stateless)
- `processing_service.py`: Async file processing and job management
- `data_service.py`: Data retrieval, pagination, and export generation
- `schemas.py`: Pydantic models for API request/response validation
- `dc_processor.py`: Core business logic for DL/VC cost categorization
- `models.py`: SQLAlchemy schema with user isolation patterns
- `database_service.py`: Data persistence and retrieval operations

#### **Client Components**
- `main.py`: NiceGUI UI making HTTP requests to server API
- Client-side state management and user interaction handling

## API Endpoint Patterns

### Authentication Flow
```python
# JWT Token Authentication
POST /api/v1/auth/login → {token, user_info}
POST /api/v1/auth/refresh → {new_token}
Headers: Authorization: Bearer <token>
```

### Async Processing Pattern
```python
# File processing workflow
POST /api/v1/files/upload → {file_ids}
POST /api/v1/files/process → {job_id}
GET /api/v1/files/process/{job_id}/status → {status, progress, results}
```

### Data Retrieval with Pagination
```python
GET /api/v1/data/dl-costs?page=1&limit=50&period=June%202025
GET /api/v1/data/vc-costs?page=1&limit=50&project=Strategic.UHG
```

## Business Logic Patterns

### DL Cost Processing Rules (Priority Order)
```python
# Negative hours = "Discrepancies & corrections from previous month"
if total_hours_direct_val < 0:
    # Process and skip other rules

# PM role charges have special handling
if 'pm role charge' in employee_ticket.lower():
    bucket = 'PM role charge'

# Paid overtime INCLUDES base salary components
if paid_overtime_val > 0:
    total_cost = paid_overtime_val + base_salary_val + payroll_taxes_val + vacation_liability_val + paid_vacation_val
    bucket = 'Paid overtime'
else:
    # Regular classification (base + taxes + vacation)
    bucket = 'Need clarification'

# Independent buckets (can coexist)
# - 'Sick leave' if sick_leave_val > 0
# - 'Medical Insurance' if medical_insurance_val > 0  
# - 'Bonus' if bonus_val > 0
```

### VC Cost Processing Rules
```python
# Negative values = corrections
if any(val < 0 for val in all_values):
    bucket = 'Discrepancies & corrections from previous month'

# Recruiting costs are separate
if recruiting_costs_val > 0:
    bucket = 'Recruiting cost'

# All other costs combined
other_dc_total = hw_nonresellable + sw_nonresellable + travel + communications + other_direct
if other_dc_total > 0:
    bucket = 'DC - other DC'
```

## Data Flow & File Structure

### Month Section Detection
Excel files contain multiple months. The processor finds target month sections by:
1. Scanning first column for month names (e.g., "June 2025")
2. Headers are in the row immediately following month header
3. Data continues until next "total" row or end of sheet

### Column Mapping Strategy
Uses position-based mapping for "Unnamed" columns from merged Excel cells:
```python
expected_positions = {
    1: 'Total Hours Direct',
    2: 'Hours Direct', 
    5: 'Total DL Costs',
    6: 'Base Salary',
    # ... specific to Excel structure
}
```

## Database Patterns

### User Isolation
All records have `created_by` foreign key. Users only see their own data:
```python
# Always filter by user_id
dl_filters = [DLCostRecord.created_by == user_id]
```

### Session Management
- JWT tokens with 24-hour expiry and refresh capability
- Stateless authentication - no server-side sessions
- User isolation enforced at API level with token validation

## Development Workflows

### Running the Application
```powershell
# Database setup (one-time)
python init_db.py

# Start server (Terminal 1)
cd server
python main.py  
# Runs on http://127.0.0.1:8000

# Start client (Terminal 2)
python main.py
# Runs on http://127.0.0.1:8080
```

### Key Testing Patterns
- Use test P&L files from `files/` directory
- Test with multi-month Excel files
- Verify bucket classifications match business rules
- Test negative value handling (corrections)

### Error Handling Approach
- Database initialization gracefully degrades to read-only mode
- File processing continues on individual failures, logs errors
- UI shows specific error messages while continuing workflow

## Common Implementation Patterns

### File Processing Pattern
```python
# Always use in-memory processing
file_io = io.BytesIO(file_content)
excel_data = pd.read_excel(file_io, sheet_name=None, engine='openpyxl')
```

### Database Transaction Pattern
```python
db_session = db_config.get_session()
try:
    # operations
    db_session.commit()
except Exception as e:
    db_session.rollback()
    # error handling
finally:
    db_session.close()
```

### API Request Pattern
```python
# Client making API requests
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(f"{API_BASE_URL}/api/v1/files/upload", 
                        files=files, headers=headers)
```

### Background Job Pattern
```python
# Server: Start async processing
background_tasks.add_task(processing_service.process_files_async, 
                         job_id, file_ids, month, year, user_id)

# Client: Poll for status
while status != 'completed':
    response = requests.get(f"{API_BASE_URL}/api/v1/files/process/{job_id}/status")
    status = response.json()['status']
```

## Integration Points

### External Dependencies
- PostgreSQL (with graceful degradation)
- Environment variables via `.env` file
- NiceGUI for web interface (single-page app)

### Project-Specific Conventions
- Round all DL/VC costs to 2 decimal places
- Project names extracted from filename before " - "
- Sheet names found by pattern matching (case-insensitive)
- Multiple files processed sequentially (not parallel)

When working with this codebase, focus on the business logic in `dc_processor.py` for rule changes, `main.py` for UI flow, and always maintain user isolation in database operations.
