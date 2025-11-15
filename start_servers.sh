#!/bin/bash

# Start/Restart Backend and Frontend Servers
# Backend: Port 8000
# Frontend: Port 3000

echo "========================================"
echo "Starting Recommender_v2 Servers"
echo "========================================"

# Kill existing processes
echo ""
echo "Stopping existing servers..."

# Kill backend on port 8000
BACKEND_PID=$(lsof -ti:8000)
if [ ! -z "$BACKEND_PID" ]; then
    echo "  Killing backend process on port 8000 (PID: $BACKEND_PID)"
    kill -9 $BACKEND_PID 2>/dev/null
fi

# Kill frontend on port 3000
FRONTEND_PID=$(lsof -ti:3000)
if [ ! -z "$FRONTEND_PID" ]; then
    echo "  Killing frontend process on port 3000 (PID: $FRONTEND_PID)"
    kill -9 $FRONTEND_PID 2>/dev/null
fi

# Also kill any remaining uvicorn or http.server processes
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "http.server 3000" 2>/dev/null

echo "  ✓ Existing servers stopped"

# Wait a moment for ports to be released
sleep 2

# Get project root (script is in project root)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

# Start backend
echo ""
echo "Starting backend server (port 8000)..."
cd "$PROJECT_ROOT/src/backend"
source venv/bin/activate
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > "$PROJECT_ROOT/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  ✓ Backend started (PID: $BACKEND_PID)"
echo "  Logs: $PROJECT_ROOT/backend.log"

# Wait for backend to initialize
sleep 3

# Start frontend
echo ""
echo "Starting frontend server (port 3000)..."
cd "$PROJECT_ROOT/src/frontend"
nohup python3 -m http.server 3000 > "$PROJECT_ROOT/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "  ✓ Frontend started (PID: $FRONTEND_PID)"
echo "  Logs: $PROJECT_ROOT/frontend.log"

# Display server info
echo ""
echo "========================================"
echo "Servers Started Successfully!"
echo "========================================"
echo ""
echo "Backend API:"
echo "  URL: http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo "  Health: http://localhost:8000/health"
echo "  Static Files: http://localhost:8000/static/"
echo ""
echo "Frontend (if needed):"
echo "  URL: http://localhost:3000"
echo "  Test UI: http://localhost:3000/test_extraction.html"
echo ""
echo "Note: Backend serves static files at /static/"
echo "  Main UI: http://localhost:8000/static/index.html"
echo "  Test Configurator: http://localhost:8000/static/test_configurator.html"
echo "  Test Extraction: http://localhost:8000/static/test_extraction.html"
echo ""
echo "Logs:"
echo "  Backend: tail -f $PROJECT_ROOT/backend.log"
echo "  Frontend: tail -f $PROJECT_ROOT/frontend.log"
echo ""
echo "To stop servers:"
echo "  ./stop_servers.sh"
echo "  (or: ./deployment/local/stop_servers.sh)"
echo ""
