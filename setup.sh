#!/bin/bash

###############################################################################
# DWbot - Full Setup & Health Check Script
# Usage: chmod +x setup.sh && sudo ./setup.sh
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_NAME="dwbot"
SERVICE_FILE="/etc/systemd/system/${BOT_NAME}.service"
VENV_DIR="${SCRIPT_DIR}/venv"
LOG_FILE="${SCRIPT_DIR}/setup_report.log"
PYTHON_CMD="python3"
PIP_CMD="pip3"

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

###############################################################################
# Helper Functions
###############################################################################

log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

print_header() {
    log ""
    log "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log "${CYAN}  $1${NC}"
    log "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log ""
}

print_success() {
    log "${GREEN}✓ $1${NC}"
    ((CHECKS_PASSED++))
}

print_fail() {
    log "${RED}✗ $1${NC}"
    ((CHECKS_FAILED++))
}

print_warning() {
    log "${YELLOW}⚠ $1${NC}"
    ((WARNINGS++))
}

print_info() {
    log "${BLUE}ℹ $1${NC}"
}

run_cmd() {
    if eval "$1" >> "$LOG_FILE" 2>&1; then
        return 0
    else
        return 1
    fi
}

check_root() {
    if [ "$EUID" -ne 0 ]; then 
        log "${RED}✗ This script must be run as root (use sudo)${NC}"
        exit 1
    fi
}

###############################################################################
# System Checks
###############################################################################

system_checks() {
    print_header "SYSTEM CHECKS"

    # Check OS
    if [ -f /etc/os-release ]; then
        OS_NAME=$(. /etc/os-release && echo "$PRETTY_NAME")
        print_success "OS: $OS_NAME"
    else
        print_warning "Could not detect OS"
    fi

    # Check architecture
    ARCH=$(uname -m)
    print_success "Architecture: $ARCH"

    # Check disk space
    DISK_AVAILABLE=$(df -h "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
    DISK_USAGE=$(df -h "$SCRIPT_DIR" | awk 'NR==2 {print $5}')
    print_success "Disk available: $DISK_AVAILABLE (${DISK_USAGE} used)"

    # Check RAM
    TOTAL_RAM=$(free -h | awk '/^Mem:/ {print $2}')
    AVAILABLE_RAM=$(free -h | awk '/^Mem:/ {print $7}')
    print_success "RAM: $TOTAL_RAM total, $AVAILABLE_RAM available"

    # Check if running inside tmux/screen
    if [ -n "$TMUX" ]; then
        print_info "Running inside tmux session"
    elif [ -n "$STY" ]; then
        print_info "Running inside screen session"
    else
        print_info "Not running inside terminal multiplexer"
    fi
}

###############################################################################
# Dependency Checks
###############################################################################

check_dependencies() {
    print_header "DEPENDENCY CHECKS"

    # Python3
    if command -v python3 &>/dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        print_success "Python3: $PYTHON_VERSION"
    else
        print_fail "Python3 not found"
        print_info "Installing Python3..."
        if run_cmd "apt-get update && apt-get install -y python3 python3-pip python3-venv"; then
            print_success "Python3 installed"
        else
            print_fail "Failed to install Python3"
            exit 1
        fi
    fi

    # pip3
    if command -v pip3 &>/dev/null; then
        PIP_VERSION=$(pip3 --version | awk '{print $2}')
        print_success "pip3: $PIP_VERSION"
    else
        print_fail "pip3 not found"
        print_info "Installing pip3..."
        if run_cmd "apt-get install -y python3-pip"; then
            print_success "pip3 installed"
        else
            print_fail "Failed to install pip3"
            exit 1
        fi
    fi

    # git (optional)
    if command -v git &>/dev/null; then
        GIT_VERSION=$(git --version | awk '{print $3}')
        print_success "Git: $GIT_VERSION"
    else
        print_warning "Git not found (optional)"
    fi

    # wget/curl
    if command -v wget &>/dev/null; then
        print_success "wget: available"
    elif command -v curl &>/dev/null; then
        print_success "curl: available"
    else
        print_warning "Neither wget nor curl found"
    fi

    # systemd
    if command -v systemctl &>/dev/null; then
        SYSTEMD_VERSION=$(systemctl --version | head -1)
        print_success "systemd: $SYSTEMD_VERSION"
    else
        print_warning "systemctl not found (will use alternative methods)"
    fi
}

###############################################################################
# Bot Setup
###############################################################################

setup_bot() {
    print_header "BOT SETUP"

    # Check if we're in the right directory
    if [ ! -f "${SCRIPT_DIR}/main.py" ]; then
        print_fail "main.py not found in $SCRIPT_DIR"
        print_info "Please run this script from the DWbot directory"
        exit 1
    fi
    print_success "Bot files found"

    # Check .env file
    if [ -f "${SCRIPT_DIR}/.env" ]; then
        if grep -q "TG_BOT_TOKEN=" "${SCRIPT_DIR}/.env"; then
            TOKEN=$(grep "TG_BOT_TOKEN=" "${SCRIPT_DIR}/.env" | cut -d'=' -f2)
            if [ ${#TOKEN} -gt 20 ]; then
                print_success ".env file configured (Token: ${TOKEN:0:10}...)"
            else
                print_warning ".env file found but token looks invalid"
            fi
        else
            print_warning ".env file exists but TG_BOT_TOKEN not found"
        fi
    else
        print_warning ".env file not found"
        print_info "You'll need to create it after setup"
    fi

    # Create virtual environment
    if [ -d "$VENV_DIR" ]; then
        print_info "Virtual environment already exists"
        print_success "Using existing virtual environment"
    else
        print_info "Creating virtual environment..."
        if run_cmd "$PYTHON_CMD -m venv $VENV_DIR"; then
            print_success "Virtual environment created"
        else
            print_fail "Failed to create virtual environment"
            exit 1
        fi
    fi

    # Activate venv and set commands
    source "${VENV_DIR}/bin/activate"
    PYTHON_CMD="python"
    PIP_CMD="pip"

    # Install dependencies
    print_info "Checking/installing dependencies..."
    if run_cmd "$PIP_CMD install -r ${SCRIPT_DIR}/requirements.txt"; then
        print_success "All dependencies installed"
    else
        print_fail "Failed to install dependencies"
        exit 1
    fi

    # Verify imports
    print_info "Verifying Python imports..."
    if run_cmd "$PYTHON_CMD -c 'import telegram; import instaloader; import yt_dlp; import sqlite3'"; then
        print_success "All imports successful"
    else
        print_fail "Import verification failed"
        exit 1
    fi

    # Test database creation
    print_info "Testing database initialization..."
    if run_cmd "$PYTHON_CMD -c 'import sys; sys.path.insert(0, \"${SCRIPT_DIR}\"); import database; database.initialize_database()'"; then
        if [ -f "${SCRIPT_DIR}/bot_database.db" ]; then
            DB_SIZE=$(du -h "${SCRIPT_DIR}/bot_database.db" | cut -f1)
            print_success "Database created successfully ($DB_SIZE)"
        else
            print_fail "Database file not created"
        fi
    else
        print_fail "Database initialization failed"
    fi

    # Check file permissions
    if run_cmd "chmod +x ${SCRIPT_DIR}/main.py"; then
        print_success "File permissions set"
    else
        print_warning "Could not set file permissions"
    fi
}

###############################################################################
# Systemd Service Setup
###############################################################################

setup_systemd() {
    if ! command -v systemctl &>/dev/null; then
        print_warning "systemctl not available - skipping service setup"
        print_info "Use tmux/screen/nohup instead (see README)"
        return
    fi

    print_header "SYSTEMD SERVICE SETUP"

    # Get current user
    if [ -n "$SUDO_USER" ]; then
        RUN_USER="$SUDO_USER"
    else
        RUN_USER=$(whoami)
    fi

    # Check if service already exists
    if [ -f "$SERVICE_FILE" ]; then
        print_info "Service file already exists at $SERVICE_FILE"
        
        # Show current status
        if systemctl is-active --quiet "$BOT_NAME"; then
            print_success "Service is currently running"
        else
            print_warning "Service exists but is not running"
        fi
        
        # Ask if user wants to reinstall
        print_info "To reinstall, run: sudo systemctl stop $BOT_NAME && sudo rm $SERVICE_FILE"
        return
    fi

    # Create service file
    print_info "Creating systemd service file..."
    
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=DWbot Telegram Downloader Bot
After=network.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$VENV_DIR/bin/python $SCRIPT_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin

[Install]
WantedBy=multi-user.target
EOF

    if [ -f "$SERVICE_FILE" ]; then
        print_success "Service file created at $SERVICE_FILE"
    else
        print_fail "Failed to create service file"
        return
    fi

    # Enable and start service
    print_info "Reloading systemd daemon..."
    if run_cmd "systemctl daemon-reload"; then
        print_success "Systemd daemon reloaded"
    else
        print_fail "Failed to reload systemd daemon"
        return
    fi

    print_info "Enabling service..."
    if run_cmd "systemctl enable $BOT_NAME"; then
        print_success "Service enabled (will start on boot)"
    else
        print_fail "Failed to enable service"
        return
    fi

    print_info "Starting service..."
    if run_cmd "systemctl start $BOT_NAME"; then
        print_success "Service started"
    else
        print_fail "Failed to start service"
        return
    fi

    # Verify service
    sleep 2
    if systemctl is-active --quiet "$BOT_NAME"; then
        print_success "Service is running and healthy"
    else
        print_fail "Service failed to start"
        print_info "Check logs with: journalctl -u $BOT_NAME -f"
    fi
}

###############################################################################
# Security Checks
###############################################################################

security_checks() {
    print_header "SECURITY CHECKS"

    # Check .env not in git
    if [ -f "${SCRIPT_DIR}/.gitignore" ]; then
        if grep -q ".env" "${SCRIPT_DIR}/.gitignore"; then
            print_success ".env is in .gitignore"
        else
            print_warning ".env not in .gitignore - might be committed!"
        fi
    else
        print_warning ".gitignore not found"
    fi

    # Check database in gitignore
    if [ -f "${SCRIPT_DIR}/.gitignore" ]; then
        if grep -q "bot_database.db" "${SCRIPT_DIR}/.gitignore"; then
            print_success "Database is in .gitignore"
        else
            print_warning "Database not in .gitignore"
        fi
    fi

    # Check file ownership
    if [ -n "$SUDO_USER" ]; then
        print_success "Running as sudo (good for service setup)"
    else
        print_info "Running as current user (may need sudo for service)"
    fi

    # Check if bot token is exposed in code
    if grep -r "TG_BOT_TOKEN\s*=" "${SCRIPT_DIR}/main.py" 2>/dev/null | grep -v "getenv" | grep -v "#" > /dev/null; then
        print_warning "Bot token might be hardcoded in main.py"
    else
        print_success "No hardcoded bot tokens found"
    fi
}

###############################################################################
# Final Report
###############################################################################

generate_report() {
    print_header "SETUP COMPLETE - REPORT"

    log "${BLUE}Summary:${NC}"
    log ""
    log "  ${GREEN}Checks Passed:  $CHECKS_PASSED${NC}"
    log "  ${RED}Checks Failed:  $CHECKS_FAILED${NC}"
    log "  ${YELLOW}Warnings:       $WARNINGS${NC}"
    log ""

    if [ $CHECKS_FAILED -eq 0 ]; then
        log "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        log "${GREEN}  ✓ ALL CHECKS PASSED - Setup Complete!${NC}"
        log "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    else
        log "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        log "${RED}  ✗ $CHECKS_FAILED CHECK(S) FAILED${NC}"
        log "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    fi

    log ""
    print_header "NEXT STEPS"

    # Check service status
    if command -v systemctl &>/dev/null && systemctl is-active --quiet "$BOT_NAME"; then
        log "${GREEN}✓ Bot is running as a service${NC}"
        log ""
        log "Useful commands:"
        log "  ${CYAN}Status:${NC}      sudo systemctl status $BOT_NAME"
        log "  ${CYAN}Stop:${NC}        sudo systemctl stop $BOT_NAME"
        log "  ${CYAN}Restart:${NC}     sudo systemctl restart $BOT_NAME"
        log "  ${CYAN}Logs:${NC}        sudo journalctl -u $BOT_NAME -f"
        log "  ${CYAN}Disable:${NC}     sudo systemctl disable $BOT_NAME"
    else
        log "${YELLOW}Bot service not running or not installed${NC}"
        log ""
        log "To start the bot, use one of these methods:"
        log ""
        log "${BLUE}Option 1: systemd (recommended)${NC}"
        log "  sudo ./setup.sh  (run again to setup service)"
        log ""
        log "${BLUE}Option 2: tmux${NC}"
        log "  tmux new -s dwbot"
        log "  cd $SCRIPT_DIR"
        log "  source venv/bin/activate"
        log "  python main.py"
        log "  # Press Ctrl+B, then D to detach"
        log ""
        log "${BLUE}Option 3: nohup${NC}"
        log "  cd $SCRIPT_DIR"
        log "  source venv/bin/activate"
        log "  nohup python main.py > bot.log 2>&1 &"
    fi

    log ""
    if [ ! -f "${SCRIPT_DIR}/.env" ] || ! grep -q "TG_BOT_TOKEN=" "${SCRIPT_DIR}/.env" 2>/dev/null; then
        log "${YELLOW}⚠ IMPORTANT: Configure your bot token!${NC}"
        log ""
        log "  nano ${SCRIPT_DIR}/.env"
        log ""
        log "  Add this line:"
        log "  TG_BOT_TOKEN=your_token_here"
        log ""
        log "  Get a token from @BotFather on Telegram"
        log ""
    fi

    log "${BLUE}Configuration files:${NC}"
    log "  .env              - Bot token and environment vars"
    log "  admin.py          - Add your user ID to ADMIN_IDS"
    log "  bot_database.db   - Auto-created SQLite database"
    log ""
    log "${BLUE}Log files:${NC}"
    log "  $LOG_FILE"
    if command -v systemctl &>/dev/null; then
        log "  journalctl -u $BOT_NAME -f  (service logs)"
    fi
    log ""
    log "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

###############################################################################
# Main Execution
###############################################################################

main() {
    # Clear log file
    echo "" > "$LOG_FILE"
    
    print_header "DWBOT SETUP SCRIPT"
    print_info "Starting full system check and setup..."
    print_info "Date: $(date)"
    print_info "Directory: $SCRIPT_DIR"
    log ""

    # Run all checks and setup
    check_root
    system_checks
    check_dependencies
    setup_bot
    security_checks
    setup_systemd
    generate_report

    # Save detailed report to file
    REPORT_FILE="${SCRIPT_DIR}/setup_report_$(date +%Y%m%d_%H%M%S).txt"
    cp "$LOG_FILE" "$REPORT_FILE"
    print_info "Detailed report saved to: $REPORT_FILE"
}

# Run main function
main "$@"
