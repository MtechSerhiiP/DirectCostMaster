# Direct Cost Master - Client-Server Setup Guide

## Overview
Direct Cost Master now uses a modern Client-Server architecture:
- **Server**: FastAPI REST API (`/server/`) handling business logic and data processing
- **Client**: NiceGUI web interface (`client_main.py`) for user interaction

## Quick Start

### 1. Install Dependencies
```powershell
# Install server dependencies
cd server
pip install -r requirements.txt
cd ..

# Install client dependencies (if different from server)
pip install -r requirements.txt
```

### 2. Database Setup (One-time)
```powershell
python init_db.py
```

### 3. Start the Server
```powershell
# Option 1: Use batch script
start_server.bat

# Option 2: Manual start
cd server
python main.py
```
Server runs on: http://127.0.0.1:8000

### 4. Start the Client (in new terminal)
```powershell
# Option 1: Use batch script  
start_client.bat

# Option 2: Manual start
python client_main.py
```
Client runs on: http://127.0.0.1:8080

## Configuration

### Server Configuration
Copy `server/.env.example` to `server/.env` and update:
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/directcostmaster

# JWT Authentication
JWT_SECRET_KEY=your-super-secret-key-change-in-production

# API Server
API_HOST=127.0.0.1
API_PORT=8000
```

### Client Configuration  
Copy `.env.client.example` to `.env` and update:
```bash
# API Server Connection
API_HOST=127.0.0.1
API_PORT=8000

# Client Settings
CLIENT_HOST=127.0.0.1
CLIENT_PORT=8080
```

## API Documentation

When the server is running, visit:
- **API Docs**: http://127.0.0.1:8000/docs
- **Health Check**: http://127.0.0.1:8000/health

## Architecture Benefits

### **Stateless Design**
- JWT token-based authentication (no server sessions)
- Horizontal scaling capability
- Better security

### **Separation of Concerns**
- **Server**: Business logic, data processing, authentication
- **Client**: Pure presentation layer, user interaction

### **Modern API**
- RESTful design with proper HTTP methods
- Comprehensive error handling
- Background processing for large files
- Paginated data retrieval

## Development Workflow

### Adding New Features
1. **Server**: Add endpoints in `server/main.py`, logic in services
2. **Client**: Add UI components and API calls in `client_main.py`
3. **Schemas**: Update `server/schemas.py` for new data models

### Testing
1. Start server: `cd server && python main.py`
2. Test API: Visit `http://127.0.0.1:8000/docs`
3. Start client: `python client_main.py`
4. Test complete workflow

## Troubleshooting

### Server Won't Start
- Check PostgreSQL is running
- Verify database connection in `server/.env`
- Check port 8000 is not in use

### Client Can't Connect
- Ensure server is running first
- Check API_HOST/API_PORT in client config
- Verify firewall settings

### Authentication Issues
- Check JWT_SECRET_KEY in server config
- Clear browser cookies/local storage
- Verify user exists in database

## File Structure
```
DirectCostMaster/
├── server/                    # FastAPI server
│   ├── main.py               # API endpoints
│   ├── auth_service.py       # JWT authentication
│   ├── processing_service.py # File processing
│   ├── data_service.py       # Data operations
│   ├── schemas.py            # API models
│   └── requirements.txt      # Server dependencies
├── client_main.py            # NiceGUI client
├── api_client.py             # API communication layer
├── dc_processor.py           # Business logic (used by server)
├── database_service.py       # Database operations
├── models.py                 # SQLAlchemy models
├── start_server.bat          # Server startup script
├── start_client.bat          # Client startup script
└── README-ClientServer.md    # This file
```

## Security Notes

### Production Deployment
- Change JWT_SECRET_KEY to a secure random value
- Use HTTPS in production
- Set strong database passwords
- Configure proper CORS origins
- Enable rate limiting

### Development
- Default admin user: `admin` / `admin123`
- Change default passwords immediately
- Don't commit `.env` files to version control
