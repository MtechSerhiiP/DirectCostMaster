# Direct Cost Master - Client

This folder contains the client-side application for Direct Cost Master.

## Files
- `main.py` - Main NiceGUI client application
- `api_client.py` - API client service for communicating with the server
- `requirements.txt` - Client-specific Python dependencies
- `.env.example` - Environment variables template

## Setup
1. Copy `.env.example` to `.env` and configure your settings
2. Install dependencies: `pip install -r requirements.txt`
3. Run the client: `python main.py`

## Configuration
The client can be configured using environment variables in the `.env` file:
- `API_HOST` - Server host (default: 127.0.0.1)
- `API_PORT` - Server port (default: 8000)
- `CLIENT_HOST` - Client host (default: 127.0.0.1)
- `CLIENT_PORT` - Client port (default: 8080)
