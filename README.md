# Direct Cost Master Application

A modern web-based application for processing P&L Excel files and consolidating Direct Cost data using NiceGUI with PostgreSQL database integration and user authentication.

## Features

- **Modern Web Interface**: Clean, minimalist design with responsive layout
- **User Authentication**: Secure login system with session management
- **PostgreSQL Database**: Persistent storage for processed data and user management
- **Multiple File Processing**: Upload and process up to 20 Excel files simultaneously
- **In-Memory File Processing**: Uses IOBytes approach - no temporary files on disk
- **Excel File Support**: Handles .xlsx and .xls files with multiple sheets
- **Smart Column Mapping**: Automatically handles Unnamed columns from merged Excel cells
- **Month-Specific Processing**: Extracts and processes data for specific months
- **Automated Data Processing**: Implements business rules for DL and VC costs
- **Master File Generation**: Consolidates data from multiple projects
- **Real-time Preview**: View data before processing
- **Data Persistence**: All processed data is saved to PostgreSQL database
- **Download Results**: Export consolidated data as Excel file

## Prerequisites

- Python 3.8 or higher
- PostgreSQL 12 or higher
- Docker
- Git (for cloning the repository)

## Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd DirectCostMaster
```

2. **Run Docker compose**:
```bash
docker compose up --build
```


3. **Open your browser** and navigate to `http://0.0.0.0:8080`

## Default Login:
you can log in with:
- **Username**: admin
- **Password**: admin

## How to Use

### Authentication
1. **Login**: Enter your credentials to access the application

### File Processing
1. **Upload Files**: Drag and drop or click to upload up to 20 Excel P&L files
2. **Review Files**: View the list of uploaded files and their status
3. **Select Period**: Choose the month and year to process
4. **Process Data**: Click "Process All P&L Files" to extract and classify Direct Costs
5. **View Results**: Browse DL and VC costs in separate tabs
6. **Download Results**: Export consolidated data as Excel file

### Data Management
- All processed data is automatically saved to the database
- Data persists between sessions
- Users can only see their own data
- Clear data using "Clear All Data" button when needed

## Database Schema

### Core Tables
- **users**: User accounts and authentication
- **user_sessions**: Session management
- **projects**: Project information extracted from filenames
- **dl_cost_records**: Direct Labor cost records
- **vc_cost_records**: Variable cost records
- **processing_logs**: Processing history and error logs

### Key Features
- User isolation (users only see their own data)
- Session-based authentication
- Audit trail for all processing operations
- Automatic project creation from filenames

## Business Logic

The application processes two types of data according to the requirements:

### DL Costs (Direct) Processing
- Extracts employee data and hours
- Classifies records into buckets:
  - **Need clarification**: Base salary + payroll taxes + vacation + paid vacation
  - **Sick leave**: When sick leave is > 0
  - **Medical Insurance**: When medical insurance > 0
  - **Bonus**: When unconditional bonus > 0
  - **Paid overtime**: When paid overtime > 0 (includes base salary components)
  - **PM role charge**: For PM role charge entries
  - **Discrepancies & corrections**: When total hours < 0

### VC Costs (Direct) Processing
- Extracts variable cost data
- Classifies records into buckets:
  - **Recruiting cost**: For recruiting costs
  - **DC - other DC**: Combined other direct costs
  - **Discrepancies & corrections**: When any value < 0

## Configuration

### Environment Variables (.env)
```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@host:port/database

# Application Configuration
SECRET_KEY=your-secret-key-change-this-in-production
DEBUG=True

# Session Configuration
SESSION_DURATION_HOURS=24

# Logging Configuration
LOG_LEVEL=INFO
```

### Database Configuration
- Connection pooling with 10 connections + 20 overflow
- Automatic table creation on startup
- Migration-ready schema design

## File Structure

```
DirectCostMaster/
├── server/                   # FastAPI backend
│   ├── main.py               # API endpoints
│   ├── auth_service.py       # JWT authentication
│   ├── auth_models.py        # User model and DB config
│   ├── processing_service.py # File processing
│   ├── data_service.py       # Data operations
│   ├── memory_data_service.py # In-memory DL/VC storage
│   ├── dc_processor.py       # Business logic
│   ├── schemas.py            # API models
│   └── requirements.txt      # Server dependencies
├── client/                   # NiceGUI frontend
│   ├── main.py              # Client application
│   └── requirements.txt     # Client dependencies
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
├── .env                    # Environment variables (create from example)
└── README.md              # This file
```

## Security Features

- **Password Hashing**: bcrypt for secure password storage
- **Session Management**: Secure session tokens with expiration
- **User Isolation**: Users can only access their own data
- **SQL Injection Protection**: SQLAlchemy ORM prevents SQL injection
- **Environment Variables**: Sensitive data stored in environment variables

## API Services

### AuthService
- JWT-based authentication
- Token generation and validation
- User management

### MemoryDataService
- In-memory DL/VC record storage
- Project management
- Data retrieval and filtering

### DataAPIService
- Data export to Excel
- Pagination and filtering
- Download management

## Error Handling

Comprehensive error handling and user feedback:
- Database connection errors
- Authentication failures
- File format validation
- Processing error notifications
- Session timeout handling

## Performance Considerations

- **Connection Pooling**: Efficient database connection management
- **In-Memory Processing**: Fast file processing without disk I/O
- **Batch Operations**: Efficient database bulk inserts
- **Session Cleanup**: Automatic cleanup of expired sessions

## Development

### Adding New Features
1. Auth changes: Update `auth_models.py`
2. Business logic: Modify `dc_processor.py`
3. Data storage: Extend `memory_data_service.py`
4. API endpoints: Update `server/main.py`

### Testing
1. Use test database for development
2. Test with sample P&L files
3. Verify authentication flows
4. Check multi-user scenarios

## Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
pg_ctl status

# Test connection
psql -U username -d directcostmaster

# Check logs
tail -f /var/log/postgresql/postgresql.log
```

### Authentication Issues
- Verify user exists in database
- Check session expiration
- Clear browser cookies
- Check server logs

### File Processing Issues
- Verify Excel file format
- Check column structure
- Review processing logs
- Test with smaller files first

## Browser Compatibility

The application works with all modern browsers including Chrome, Firefox, Safari, and Edge.

## Production Deployment

### Environment Setup
1. Use production PostgreSQL instance
2. Set strong SECRET_KEY
3. Disable DEBUG mode
4. Configure proper logging
5. Use HTTPS in production
6. Set up database backups

### Security Checklist
- [ ] Change default admin password
- [ ] Use strong SECRET_KEY
- [ ] Enable HTTPS
- [ ] Configure firewall
- [ ] Set up database backups
- [ ] Monitor logs for suspicious activity

## Support

For issues or questions:
1. Check application logs
2. Review database connection
3. Verify file format requirements
4. Check the process description file for business requirements

## License

[Add your license information here]
