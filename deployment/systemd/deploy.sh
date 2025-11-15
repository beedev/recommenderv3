#!/bin/bash
#
# ESAB Recommender - Production Deployment Script
#
# This script automates the deployment of the ESAB Recommender application
# on a Linux production server.
#
# Usage:
#   ./deploy.sh [install|update|restart|status|logs|stop]
#

set -e  # Exit on error

# Auto-detect installation directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Configuration
APP_NAME="esab-recommender"
# Auto-detect user: Use current sudo user if available, otherwise current user
APP_USER="${SUDO_USER:-$(whoami)}"
APP_GROUP="$APP_USER"
# Use detected repository root as installation directory
INSTALL_DIR="$REPO_ROOT"
BACKEND_SERVICE="esab-recommender.service"
FRONTEND_SERVICE="esab-recommender-frontend.service"
TARGET_FILE="esab-recommender.target"
VENV_DIR="$INSTALL_DIR/src/backend/venv"
BACKEND_DIR="$INSTALL_DIR/src/backend"
LOG_DIR="$INSTALL_DIR/logs"

# Display detected configuration
echo ""
echo "=== Detected Configuration ==="
echo "Repository Root: $REPO_ROOT"
echo "Installation Directory: $INSTALL_DIR"
echo "Application User: $APP_USER"
echo "Application Group: $APP_GROUP"
echo "Backend Directory: $BACKEND_DIR"
echo "Log Directory: $LOG_DIR"
echo "=============================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Generate systemd service files dynamically
generate_service_files() {
    log_info "Generating systemd service files with detected paths..."

    # Generate backend service file
    cat > /tmp/$BACKEND_SERVICE <<EOF
[Unit]
Description=ESAB Recommender Backend API (FastAPI)
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service
PartOf=esab-recommender.target

[Service]
Type=exec
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$BACKEND_DIR/venv/bin"
Environment="PYTHONPATH=$BACKEND_DIR"
EnvironmentFile=$BACKEND_DIR/.env

# Uvicorn command with production settings
ExecStart=$BACKEND_DIR/venv/bin/uvicorn app.main:app \\
    --host 0.0.0.0 \\
    --port 8000 \\
    --workers 4 \\
    --log-level info \\
    --access-log

# Startup timeout (allow time for all workers to initialize)
TimeoutStartSec=120

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=5min
StartLimitBurst=5

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$LOG_DIR

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

# Logging - Write to both journal AND files
StandardOutput=append:$LOG_DIR/esab-recommender.log
StandardError=append:$LOG_DIR/esab-recommender-error.log
SyslogIdentifier=esab-recommender

# Graceful shutdown
TimeoutStopSec=30
KillMode=mixed
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
WantedBy=esab-recommender.target
EOF

    # Generate frontend service file
    cat > /tmp/$FRONTEND_SERVICE <<EOF
[Unit]
Description=ESAB Recommender Frontend HTTP Server
After=network.target
PartOf=esab-recommender.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$INSTALL_DIR/src

# Python HTTP server for static frontend
ExecStart=/usr/bin/python3 -m http.server 3000 --bind 0.0.0.0

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=5min
StartLimitBurst=5

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only

# Resource limits
LimitNOFILE=1024
LimitNPROC=512

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=esab-frontend

# Graceful shutdown
TimeoutStopSec=10
KillMode=mixed
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
WantedBy=esab-recommender.target
EOF

    log_info "Service files generated successfully"
}

# Detect OS and package manager
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    else
        log_error "Cannot detect OS. /etc/os-release not found."
        exit 1
    fi
    
    log_info "Detected OS: $OS $OS_VERSION"
}

# Get Python version
get_python_version() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        log_info "Detected Python version: $PYTHON_VERSION"
    else
        PYTHON_VERSION=""
        PYTHON_MAJOR=0
        PYTHON_MINOR=0
    fi
}

# Install system dependencies
install_system_dependencies() {
    log_info "Installing system dependencies..."
    
    detect_os
    get_python_version
    
    # Determine Python version string for package names
    if [ ! -z "$PYTHON_VERSION" ]; then
        PYTHON_PKG_VERSION="${PYTHON_MAJOR}.${PYTHON_MINOR}"
    else
        PYTHON_PKG_VERSION="3"
    fi
    
    case $OS in
        ubuntu|debian)
            log_info "Installing packages for Debian/Ubuntu..."
            apt-get update
            
            # Install Python if not present
            if ! command -v python3 &> /dev/null; then
                log_info "Installing Python 3..."
                apt-get install -y python3
                get_python_version
                PYTHON_PKG_VERSION="${PYTHON_MAJOR}.${PYTHON_MINOR}"
            fi
            
            # Install required packages
            PACKAGES=(
                "python${PYTHON_PKG_VERSION}-venv"
                "python3-pip"
                "python${PYTHON_PKG_VERSION}-dev"
                "build-essential"
                "curl"
                "git"
            )
            
            for package in "${PACKAGES[@]}"; do
                if ! dpkg -l | grep -q "^ii  $package"; then
                    log_info "Installing $package..."
                    apt-get install -y "$package" || log_warn "Failed to install $package, continuing..."
                else
                    log_info "$package is already installed"
                fi
            done
            ;;
            
        rhel|centos|fedora|rocky|almalinux)
            log_info "Installing packages for RHEL/CentOS/Fedora..."
            
            # Determine package manager
            if command -v dnf &> /dev/null; then
                PKG_MGR="dnf"
            else
                PKG_MGR="yum"
            fi
            
            # Install Python if not present
            if ! command -v python3 &> /dev/null; then
                log_info "Installing Python 3..."
                $PKG_MGR install -y python3
                get_python_version
            fi
            
            # Install required packages
            PACKAGES=(
                "python3-devel"
                "python3-pip"
                "gcc"
                "gcc-c++"
                "make"
                "curl"
                "git"
            )
            
            for package in "${PACKAGES[@]}"; do
                log_info "Installing $package..."
                $PKG_MGR install -y "$package" || log_warn "Failed to install $package, continuing..."
            done
            ;;
            
        *)
            log_warn "Unsupported OS: $OS. Please install dependencies manually:"
            log_warn "  - Python 3.11 or higher"
            log_warn "  - python3-venv (or equivalent)"
            log_warn "  - python3-pip"
            log_warn "  - python3-dev (or python3-devel)"
            log_warn "  - build-essential (or gcc, gcc-c++, make)"
            read -p "Press Enter to continue or Ctrl+C to abort..."
            ;;
    esac
    
    log_info "System dependencies installation complete"
}

# Installation function
install_app() {
    log_info "Starting ESAB Recommender installation..."

    # Install system dependencies
    install_system_dependencies

    # Verify required commands are available
    log_info "Verifying required commands..."
    get_python_version
    
    if [ -z "$PYTHON_VERSION" ] || [ $PYTHON_MAJOR -lt 3 ] || [ $PYTHON_MINOR -lt 8 ]; then
        log_error "Python 3.8 or higher is required. Found: $PYTHON_VERSION"
        exit 1
    fi

    if ! command -v pip3 &> /dev/null; then
        log_error "pip3 is not installed. Please install python3-pip."
        exit 1
    fi

    # Verify user exists
    if ! id "$APP_USER" &>/dev/null; then
        log_error "User $APP_USER does not exist. Please create it first or run with sudo."
        exit 1
    else
        log_info "User $APP_USER exists ✓"
    fi

    # Create log directory with correct ownership
    log_info "Creating log directory..."
    mkdir -p $LOG_DIR
    chown -R $APP_USER:$APP_GROUP $LOG_DIR
    chmod 755 $LOG_DIR

    # Verify source directory exists
    if [ ! -d "$INSTALL_DIR/src" ]; then
        log_error "Source directory not found at $INSTALL_DIR/src"
        log_error "Please run this script from the deployment/systemd directory within your repository"
        exit 1
    fi
    log_info "Source directory exists ✓"

    # Create virtual environment
    log_info "Creating Python virtual environment..."
    cd $BACKEND_DIR
    
    # Remove existing venv if it exists and is broken
    if [ -d "venv" ] && [ ! -f "venv/bin/activate" ]; then
        log_warn "Removing broken virtual environment..."
        rm -rf venv
    fi
    
    # Create new venv
    if [ ! -d "venv" ]; then
        python3 -m venv venv || {
            log_error "Failed to create virtual environment."
            log_error "Please ensure python3-venv is installed:"
            log_error "  Debian/Ubuntu: sudo apt install python3-venv"
            log_error "  RHEL/CentOS: sudo yum install python3-devel"
            exit 1
        }
        log_info "Virtual environment created successfully"
    else
        log_info "Virtual environment already exists"
    fi

    # Install Python dependencies
    log_info "Installing Python dependencies..."
    source $VENV_DIR/bin/activate
    
    # Upgrade pip first
    pip install --upgrade pip
    
    # Install wheel for better package builds
    pip install wheel
    
    # Install requirements
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        log_info "Python dependencies installed successfully"
    else
        log_warn "requirements.txt not found in $BACKEND_DIR"
    fi
    
    deactivate

    # Check if .env file exists
    if [ ! -f "$BACKEND_DIR/.env" ]; then
        log_warn ".env file not found. Creating from template..."
        if [ -f "$BACKEND_DIR/.env.example" ]; then
            cp $BACKEND_DIR/.env.example $BACKEND_DIR/.env
            log_warn "Please edit $BACKEND_DIR/.env with your configuration"
        else
            log_error "No .env or .env.example found. Please create $BACKEND_DIR/.env manually"
        fi
    fi

    # Set permissions on entire installation
    log_info "Setting file permissions..."
    chown -R $APP_USER:$APP_GROUP $INSTALL_DIR
    chmod -R 755 $INSTALL_DIR

    # Ensure logs directory is writable
    if [ -d "$LOG_DIR" ]; then
        chown -R $APP_USER:$APP_GROUP $LOG_DIR
        chmod 755 $LOG_DIR
        log_info "Logs directory permissions set for user $APP_USER"
    fi

    # Secure .env file
    if [ -f "$BACKEND_DIR/.env" ]; then
        chmod 600 $BACKEND_DIR/.env
        chown $APP_USER:$APP_GROUP $BACKEND_DIR/.env
    fi

    # Generate and install systemd services
    log_info "Generating systemd service files with current configuration..."
    generate_service_files

    log_info "Installing systemd services..."
    # Copy generated service files to systemd directory
    cp /tmp/$BACKEND_SERVICE /etc/systemd/system/
    cp /tmp/$FRONTEND_SERVICE /etc/systemd/system/

    # Copy target file from repository (doesn't need path customization)
    if [ -f "$INSTALL_DIR/deployment/$TARGET_FILE" ]; then
        cp $INSTALL_DIR/deployment/$TARGET_FILE /etc/systemd/system/
    elif [ -f "$INSTALL_DIR/deployment/systemd/$TARGET_FILE" ]; then
        cp $INSTALL_DIR/deployment/systemd/$TARGET_FILE /etc/systemd/system/
    else
        log_error "Target file not found"
        exit 1
    fi

    # Clean up temporary files
    rm -f /tmp/$BACKEND_SERVICE /tmp/$FRONTEND_SERVICE

    systemctl daemon-reload
    systemctl enable $BACKEND_SERVICE
    systemctl enable $FRONTEND_SERVICE
    systemctl enable $TARGET_FILE

    log_info "Installation complete!"
    echo ""
    log_info "Next steps:"
    log_info "  1. Edit the configuration: sudo nano $BACKEND_DIR/.env"
    log_info "  2. Start both services: sudo systemctl start $TARGET_FILE"
    log_info "  3. Check status: sudo systemctl status $TARGET_FILE"
    echo ""
    log_info "Individual service controls:"
    log_info "  - Backend (port 8000): sudo systemctl [start|stop|status] $BACKEND_SERVICE"
    log_info "  - Frontend (port 3000): sudo systemctl [start|stop|status] $FRONTEND_SERVICE"
    log_info "  - Both services: sudo systemctl [start|stop|status] $TARGET_FILE"
    echo ""
    log_info "View logs:"
    log_info "  - sudo ./deploy.sh logs"
    log_info "  - sudo journalctl -u $BACKEND_SERVICE -f"
    log_info "  - sudo journalctl -u $FRONTEND_SERVICE -f"
}

# Update function
update_app() {
    log_info "Updating ESAB Recommender..."

    # Stop services
    log_info "Stopping services..."
    systemctl stop $TARGET_FILE

    # Backup current installation
    BACKUP_DIR="/tmp/esab-recommender-backup-$(date +%Y%m%d-%H%M%S)"
    log_info "Creating backup at $BACKUP_DIR..."
    mkdir -p $BACKUP_DIR
    cp -r $BACKEND_DIR $BACKUP_DIR

    # Update application files (preserve .env and logs)
    log_info "Updating application files..."
    if [ -d "$(pwd)/src" ]; then
        # Backup .env
        if [ -f "$BACKEND_DIR/.env" ]; then
            cp $BACKEND_DIR/.env /tmp/.env.backup
        fi
        
        # Copy new files
        cp -r $(pwd)/src/backend/app $BACKEND_DIR/ 2>/dev/null || true
        cp $(pwd)/src/backend/requirements.txt $BACKEND_DIR/ 2>/dev/null || true
        
        # Restore .env
        if [ -f "/tmp/.env.backup" ]; then
            cp /tmp/.env.backup $BACKEND_DIR/.env
            rm /tmp/.env.backup
        fi
    else
        log_error "Source directory not found. Please run this script from the repository root."
        log_info "Backup available at: $BACKUP_DIR"
        exit 1
    fi

    # Update Python dependencies
    log_info "Updating Python dependencies..."
    cd $BACKEND_DIR
    
    if [ ! -d "venv" ]; then
        log_error "Virtual environment not found. Please run 'install' first."
        exit 1
    fi
    
    source $VENV_DIR/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt --upgrade
    deactivate

    # Set permissions
    chown -R $APP_USER:$APP_GROUP $INSTALL_DIR

    # Restart services
    log_info "Starting services..."
    systemctl start $TARGET_FILE

    # Check status
    sleep 3
    if systemctl is-active --quiet $BACKEND_SERVICE && systemctl is-active --quiet $FRONTEND_SERVICE; then
        log_info "Update complete! Both services are running."
        log_info "Backend API: http://localhost:8000"
        log_info "Frontend: http://localhost:3000"
        log_info "Backup available at: $BACKUP_DIR"
    else
        log_error "One or more services failed to start."
        log_error "Check backend logs: journalctl -u $BACKEND_SERVICE -n 50"
        log_error "Check frontend logs: journalctl -u $FRONTEND_SERVICE -n 50"
        log_info "Backup available at: $BACKUP_DIR"
        exit 1
    fi
}

# Restart function
restart_app() {
    log_info "Restarting ESAB Recommender..."
    systemctl restart $TARGET_FILE
    sleep 3

    if systemctl is-active --quiet $BACKEND_SERVICE && systemctl is-active --quiet $FRONTEND_SERVICE; then
        log_info "Services restarted successfully"
        log_info "Backend API (port 8000): $(systemctl is-active $BACKEND_SERVICE)"
        log_info "Frontend (port 3000): $(systemctl is-active $FRONTEND_SERVICE)"
    else
        log_error "One or more services failed to start."
        log_error "Backend status: $(systemctl is-active $BACKEND_SERVICE)"
        log_error "Frontend status: $(systemctl is-active $FRONTEND_SERVICE)"
        log_error "Check logs: sudo $0 logs"
        exit 1
    fi
}

# Status function
show_status() {
    log_info "=== ESAB Recommender Status ==="
    echo ""

    log_info "Target Status:"
    systemctl status $TARGET_FILE --no-pager || true

    echo ""
    log_info "Backend Service (port 8000):"
    systemctl status $BACKEND_SERVICE --no-pager || true

    echo ""
    log_info "Frontend Service (port 3000):"
    systemctl status $FRONTEND_SERVICE --no-pager || true

    echo ""
    log_info "Application URLs:"
    if systemctl is-active --quiet $BACKEND_SERVICE; then
        echo "  Backend API: http://localhost:8000"
        echo "  API Docs: http://localhost:8000/docs"
    fi
    if systemctl is-active --quiet $FRONTEND_SERVICE; then
        echo "  Frontend: http://localhost:3000/frontend_prototype.html"
        echo "  Guided Flow: http://localhost:3000/guided_flow.html"
    fi
}

# Logs function
show_logs() {
    log_info "Select which logs to view:"
    echo "  1) Backend only"
    echo "  2) Frontend only"
    echo "  3) Both (interleaved)"
    echo "  4) Last 50 lines (backend)"
    echo "  5) Last 50 lines (frontend)"
    echo ""

    # Check if running interactively
    if [ -t 0 ]; then
        read -p "Enter choice [1-5] (default: 3): " choice
        choice=${choice:-3}
    else
        choice=3
    fi

    case $choice in
        1)
            log_info "Following backend logs (Ctrl+C to exit)..."
            journalctl -u $BACKEND_SERVICE -f
            ;;
        2)
            log_info "Following frontend logs (Ctrl+C to exit)..."
            journalctl -u $FRONTEND_SERVICE -f
            ;;
        3)
            log_info "Following all service logs (Ctrl+C to exit)..."
            journalctl -u $BACKEND_SERVICE -u $FRONTEND_SERVICE -f
            ;;
        4)
            log_info "Last 50 lines from backend:"
            journalctl -u $BACKEND_SERVICE -n 50 --no-pager
            ;;
        5)
            log_info "Last 50 lines from frontend:"
            journalctl -u $FRONTEND_SERVICE -n 50 --no-pager
            ;;
        *)
            log_error "Invalid choice"
            exit 1
            ;;
    esac
}

# Stop function
stop_app() {
    log_info "Stopping ESAB Recommender..."
    systemctl stop $TARGET_FILE
    sleep 2
    log_info "Backend service: $(systemctl is-active $BACKEND_SERVICE)"
    log_info "Frontend service: $(systemctl is-active $FRONTEND_SERVICE)"
    log_info "All services stopped"
}

# Uninstall function
uninstall_app() {
    log_warn "This will uninstall ESAB Recommender and remove all files."
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "Uninstall cancelled"
        exit 0
    fi
    
    log_info "Uninstalling ESAB Recommender..."
    
    # Stop and disable services
    systemctl stop $TARGET_FILE 2>/dev/null || true
    systemctl disable $BACKEND_SERVICE 2>/dev/null || true
    systemctl disable $FRONTEND_SERVICE 2>/dev/null || true
    systemctl disable $TARGET_FILE 2>/dev/null || true
    
    # Remove systemd files
    rm -f /etc/systemd/system/$BACKEND_SERVICE
    rm -f /etc/systemd/system/$FRONTEND_SERVICE
    rm -f /etc/systemd/system/$TARGET_FILE
    systemctl daemon-reload
    
    # Remove application directory
    read -p "Remove application directory $INSTALL_DIR? (yes/no): " remove_dir
    if [ "$remove_dir" = "yes" ]; then
        rm -rf $INSTALL_DIR
        log_info "Application directory removed"
    fi
    
    # Remove user
    read -p "Remove application user $APP_USER? (yes/no): " remove_user
    if [ "$remove_user" = "yes" ]; then
        userdel $APP_USER 2>/dev/null || true
        log_info "Application user removed"
    fi
    
    log_info "Uninstall complete"
}

# Main script logic
case "${1:-}" in
    install)
        check_root
        install_app
        ;;
    update)
        check_root
        update_app
        ;;
    restart)
        check_root
        restart_app
        ;;
    stop)
        check_root
        stop_app
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    uninstall)
        check_root
        uninstall_app
        ;;
    *)
        echo "ESAB Recommender Deployment Script"
        echo ""
        echo "Usage: $0 {install|update|restart|stop|status|logs|uninstall}"
        echo ""
        echo "Commands:"
        echo "  install    - Initial installation with automatic dependency setup"
        echo "  update     - Update application code and dependencies"
        echo "  restart    - Restart the application services"
        echo "  stop       - Stop the application services"
        echo "  status     - Show service status and information"
        echo "  logs       - View application logs in real-time"
        echo "  uninstall  - Remove the application completely"
        echo ""
        echo "Examples:"
        echo "  sudo ./deploy.sh install      # First-time installation"
        echo "  sudo ./deploy.sh restart      # Restart services"
        echo "  sudo ./deploy.sh logs         # View logs"
        echo "  sudo ./deploy.sh status       # Check status"
        echo ""
        exit 1
        ;;
esac

exit 0
