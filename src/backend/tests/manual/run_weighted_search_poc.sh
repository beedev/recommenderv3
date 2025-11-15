#!/bin/bash

###############################################################################
# Weighted Lucene Search POC - Quick Start Script
###############################################################################
#
# This script starts the test server and opens the HTML UI for comparing
# full-text vs weighted keyword Lucene searches.
#
# Requirements:
# - Python 3.11+
# - Virtual environment at src/backend/venv/
# - Neo4j running (credentials in src/backend/.env)
# - Dependencies installed (uvicorn, fastapi, neo4j, pydantic)
#
# Usage:
#   cd src/backend/tests/manual
#   chmod +x run_weighted_search_poc.sh
#   ./run_weighted_search_poc.sh
#
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/../.."
VENV_DIR="$BACKEND_DIR/venv"
ENV_FILE="$BACKEND_DIR/.env"
API_FILE="$SCRIPT_DIR/test_api_weighted_search.py"
HTML_FILE="$SCRIPT_DIR/test_weighted_search_ui.html"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  🔬 Weighted Lucene Search POC - Quick Start                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found at $VENV_DIR${NC}"
    echo -e "${BLUE}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✓${NC} Virtual environment activated"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ .env file not found at $ENV_FILE${NC}"
    echo -e "${YELLOW}Please create .env with Neo4j credentials:${NC}"
    echo "  NEO4J_URI=neo4j://localhost:7687"
    echo "  NEO4J_USERNAME=neo4j"
    echo "  NEO4J_PASSWORD=your_password"
    exit 1
fi

echo -e "${GREEN}✓${NC} .env file found"

# Check if required dependencies are installed
echo -e "${BLUE}Checking dependencies...${NC}"
MISSING_DEPS=0

if ! python3 -c "import uvicorn" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  uvicorn not installed${NC}"
    MISSING_DEPS=1
fi

if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  fastapi not installed${NC}"
    MISSING_DEPS=1
fi

if ! python3 -c "import neo4j" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  neo4j not installed${NC}"
    MISSING_DEPS=1
fi

if ! python3 -c "import pydantic" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  pydantic not installed${NC}"
    MISSING_DEPS=1
fi

if [ $MISSING_DEPS -eq 1 ]; then
    echo -e "${BLUE}Installing missing dependencies...${NC}"
    pip install uvicorn fastapi neo4j pydantic python-dotenv
    echo -e "${GREEN}✓${NC} Dependencies installed"
else
    echo -e "${GREEN}✓${NC} All dependencies installed"
fi

# Check if API file exists
if [ ! -f "$API_FILE" ]; then
    echo -e "${RED}❌ API file not found: $API_FILE${NC}"
    exit 1
fi

# Check if HTML file exists
if [ ! -f "$HTML_FILE" ]; then
    echo -e "${RED}❌ HTML file not found: $HTML_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Test files found"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down test server...${NC}"
    kill $SERVER_PID 2>/dev/null || true
    deactivate
    echo -e "${GREEN}✓${NC} Cleanup complete"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start the test server in background
echo -e "${BLUE}Starting test server on port 8001...${NC}"
cd "$BACKEND_DIR"
python3 "$API_FILE" > /tmp/weighted_search_poc.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
echo -e "${BLUE}Waiting for server to be ready...${NC}"
for i in {1..15}; do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Server is ready"
        break
    fi
    if [ $i -eq 15 ]; then
        echo -e "${RED}❌ Server failed to start. Check logs at /tmp/weighted_search_poc.log${NC}"
        cat /tmp/weighted_search_poc.log
        kill $SERVER_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ POC Test Environment is Ready!                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📡 API Server:${NC}       http://localhost:8001"
echo -e "${BLUE}📄 API Docs:${NC}         http://localhost:8001/docs"
echo -e "${BLUE}🌐 HTML Test UI:${NC}     file://$HTML_FILE"
echo -e "${BLUE}📊 Server Logs:${NC}      /tmp/weighted_search_poc.log"
echo ""
echo -e "${YELLOW}Opening HTML test UI in your browser...${NC}"

# Open HTML in default browser
if command -v open &> /dev/null; then
    # macOS
    open "$HTML_FILE"
elif command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open "$HTML_FILE"
elif command -v start &> /dev/null; then
    # Windows (Git Bash)
    start "$HTML_FILE"
else
    echo -e "${YELLOW}⚠️  Could not auto-open browser. Please open manually:${NC}"
    echo -e "   file://$HTML_FILE"
fi

echo ""
echo -e "${BLUE}📝 Sample Queries to Test:${NC}"
echo "   1. I need a machine that can handle MIG/MAG, MMA (Stick), and DC TIG welding."
echo "   2. Show me portable 500A MIG welders for aluminum"
echo "   3. I want a water-cooled multiprocess machine"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"

# Keep script running
tail -f /tmp/weighted_search_poc.log
