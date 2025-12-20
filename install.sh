#!/bin/bash
#####################################################################
##  LUMEN Installation Script v2.0
##
##  Interactive installer for LUMEN - LED control for Klipper printers.
##  Handles GPIO proxy service setup for WS281x LED strips.
##
##  Usage:
##    cd ~/lumen
##    ./install.sh
##
##  What this script does:
##    1. Detects and confirms installation paths
##    2. Installs rpi-ws281x library (for GPIO LED support)
##    3. Sets up ws281x-proxy systemd service (runs as root for GPIO access)
##    4. Links LUMEN component to Moonraker
##    5. Creates default configuration
##    6. Configures Moonraker integration
#####################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

LUMEN_VERSION="0.1.0"

# Default paths (will be confirmed interactively)
DEFAULT_USER=$(whoami)
DEFAULT_MOONRAKER_VENV="${HOME}/moonraker-env"
DEFAULT_PRINTER_DATA="${HOME}/printer_data"
DEFAULT_MOONRAKER_COMPONENTS="${HOME}/moonraker/moonraker/components"
LUMEN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Proxy service settings
PROXY_PORT=3769
PROXY_SERVICE_NAME="ws281x-proxy"

#####################################################################
##  Helper Functions
#####################################################################

print_header() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║            LUMEN Installation v${LUMEN_VERSION}                           ║"
    echo "║       Lights Under My Enclosure Now - RPI Edition             ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_section() {
    echo ""
    echo -e "${BOLD}${CYAN}━━━ $1 ━━━${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

prompt_yes_no() {
    local prompt="$1"
    local default="$2"
    local response
    
    if [ "$default" = "y" ]; then
        prompt="${prompt} [Y/n]: "
    else
        prompt="${prompt} [y/N]: "
    fi
    
    read -p "$prompt" response
    response=${response:-$default}
    
    case "$response" in
        [Yy]* ) return 0;;
        * ) return 1;;
    esac
}

prompt_value() {
    local prompt="$1"
    local default="$2"
    local response
    
    read -p "${prompt} [${default}]: " response
    echo "${response:-$default}"
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}

#####################################################################
##  Pre-flight Checks
#####################################################################

preflight_checks() {
    print_section "Pre-flight Checks"
    
    local errors=0
    
    # Check if running as root (we don't want that)
    if [ "$EUID" -eq 0 ]; then
        print_error "Please do not run this script as root."
        print_info "The script will use sudo when needed."
        exit 1
    fi
    
    # Check for required commands
    if check_command python3; then
        print_success "Python3 found: $(python3 --version)"
    else
        print_error "Python3 not found"
        errors=$((errors + 1))
    fi
    
    if check_command systemctl; then
        print_success "systemctl found"
    else
        print_error "systemctl not found (required for service management)"
        errors=$((errors + 1))
    fi
    
    if check_command sudo; then
        print_success "sudo found"
    else
        print_error "sudo not found (required for service installation)"
        errors=$((errors + 1))
    fi
    
    # Check if LUMEN files exist
    if [ -f "${LUMEN_DIR}/moonraker/components/lumen.py" ]; then
        print_success "LUMEN component found"
    else
        print_error "LUMEN component not found at ${LUMEN_DIR}/moonraker/components/lumen.py"
        print_info "Make sure you're running this script from the LUMEN repository directory"
        errors=$((errors + 1))
    fi
    
    if [ $errors -gt 0 ]; then
        echo ""
        print_error "Pre-flight checks failed with $errors error(s). Please fix and retry."
        exit 1
    fi
    
    echo ""
    print_success "All pre-flight checks passed!"
}

#####################################################################
##  Path Detection & Confirmation
#####################################################################

detect_and_confirm_paths() {
    print_section "Path Configuration"
    
    echo "LUMEN needs to know where your Klipper/Moonraker installation is located."
    echo "Auto-detected values are shown in brackets. Press Enter to accept or type a new value."
    echo ""
    
    # Detect username
    INSTALL_USER=$(prompt_value "Username for service" "$DEFAULT_USER")
    
    # Detect Moonraker venv
    if [ -d "$DEFAULT_MOONRAKER_VENV" ]; then
        print_info "Found Moonraker venv at: $DEFAULT_MOONRAKER_VENV"
    else
        print_warning "Moonraker venv not found at default location"
    fi
    MOONRAKER_VENV=$(prompt_value "Moonraker virtual environment path" "$DEFAULT_MOONRAKER_VENV")
    
    # Validate venv
    if [ ! -f "${MOONRAKER_VENV}/bin/python" ]; then
        print_error "Python not found in venv at ${MOONRAKER_VENV}/bin/python"
        print_info "Please verify the Moonraker virtual environment path"
        exit 1
    fi
    print_success "Moonraker venv validated: ${MOONRAKER_VENV}"
    
    # Detect printer_data
    if [ -d "$DEFAULT_PRINTER_DATA" ]; then
        print_info "Found printer_data at: $DEFAULT_PRINTER_DATA"
    else
        print_warning "printer_data not found at default location"
    fi
    PRINTER_DATA=$(prompt_value "Printer data path" "$DEFAULT_PRINTER_DATA")
    
    # Validate printer_data
    if [ ! -d "${PRINTER_DATA}/config" ]; then
        print_error "Config directory not found at ${PRINTER_DATA}/config"
        exit 1
    fi
    print_success "Printer data validated: ${PRINTER_DATA}"
    
    # Detect Moonraker components directory
    # Try common locations
    if [ -d "${HOME}/moonraker/moonraker/components" ]; then
        DEFAULT_MOONRAKER_COMPONENTS="${HOME}/moonraker/moonraker/components"
    elif [ -d "/home/${INSTALL_USER}/moonraker/moonraker/components" ]; then
        DEFAULT_MOONRAKER_COMPONENTS="/home/${INSTALL_USER}/moonraker/moonraker/components"
    fi
    
    if [ -d "$DEFAULT_MOONRAKER_COMPONENTS" ]; then
        print_info "Found Moonraker components at: $DEFAULT_MOONRAKER_COMPONENTS"
    else
        print_warning "Moonraker components directory not found at default location"
    fi
    MOONRAKER_COMPONENTS=$(prompt_value "Moonraker components path" "$DEFAULT_MOONRAKER_COMPONENTS")
    
    # Validate components directory
    if [ ! -d "$MOONRAKER_COMPONENTS" ]; then
        print_error "Moonraker components directory not found at ${MOONRAKER_COMPONENTS}"
        exit 1
    fi
    print_success "Moonraker components validated: ${MOONRAKER_COMPONENTS}"
    
    # Summary
    echo ""
    print_section "Configuration Summary"
    echo "  Username:              ${INSTALL_USER}"
    echo "  LUMEN directory:       ${LUMEN_DIR}"
    echo "  Moonraker venv:        ${MOONRAKER_VENV}"
    echo "  Printer data:          ${PRINTER_DATA}"
    echo "  Moonraker components:  ${MOONRAKER_COMPONENTS}"
    echo ""
    
    if ! prompt_yes_no "Is this configuration correct?" "y"; then
        print_info "Please re-run the installer with correct paths"
        exit 0
    fi
}

#####################################################################
##  pigpiod Handling
#####################################################################

handle_pigpiod() {
    print_section "Checking for pigpiod"
    
    # pigpiod conflicts with rpi_ws281x because both try to access /dev/mem
    if systemctl is-active --quiet pigpiod 2>/dev/null; then
        print_warning "pigpiod is currently running"
        echo ""
        echo "pigpiod conflicts with rpi_ws281x (both need /dev/mem access)."
        echo "LUMEN needs pigpiod to be stopped for GPIO LED control to work."
        echo ""
        
        if prompt_yes_no "Stop and disable pigpiod?" "y"; then
            echo "Stopping pigpiod..."
            sudo systemctl stop pigpiod
            sudo systemctl disable pigpiod
            sudo systemctl mask pigpiod
            print_success "pigpiod stopped, disabled, and masked"
            print_info "To restore pigpiod later, run: sudo systemctl unmask pigpiod && sudo systemctl enable pigpiod"
        else
            print_warning "pigpiod left running - GPIO LEDs may not work!"
            print_info "You can use the 'klipper' driver for MCU-attached LEDs instead"
        fi
    elif systemctl is-enabled --quiet pigpiod 2>/dev/null; then
        print_warning "pigpiod is enabled but not running"
        
        if prompt_yes_no "Disable and mask pigpiod to prevent future conflicts?" "y"; then
            sudo systemctl disable pigpiod
            sudo systemctl mask pigpiod
            print_success "pigpiod disabled and masked"
        fi
    else
        print_success "pigpiod not detected or already disabled"
    fi
}

#####################################################################
##  rpi-ws281x Installation
#####################################################################

install_rpi_ws281x() {
    print_section "Installing rpi-ws281x Library"
    
    echo "rpi-ws281x is required for GPIO LED control."
    echo "This will be installed in the Moonraker virtual environment."
    echo ""
    
    # Check if already installed
    if "${MOONRAKER_VENV}/bin/python" -c "import rpi_ws281x" 2>/dev/null; then
        print_success "rpi-ws281x already installed"
        
        if prompt_yes_no "Reinstall/upgrade rpi-ws281x?" "n"; then
            echo "Installing rpi-ws281x..."
            "${MOONRAKER_VENV}/bin/pip" install --upgrade rpi-ws281x
            print_success "rpi-ws281x upgraded"
        fi
    else
        if prompt_yes_no "Install rpi-ws281x?" "y"; then
            echo "Installing rpi-ws281x..."
            "${MOONRAKER_VENV}/bin/pip" install rpi-ws281x
            
            # Verify installation
            if "${MOONRAKER_VENV}/bin/python" -c "import rpi_ws281x" 2>/dev/null; then
                print_success "rpi-ws281x installed successfully"
            else
                print_error "rpi-ws281x installation failed"
                print_info "GPIO LED control will not work, but Klipper driver will still function"
            fi
        else
            print_warning "Skipping rpi-ws281x installation"
            print_info "GPIO LED control will not be available"
        fi
    fi
}

#####################################################################
##  WS281x Proxy Service Setup
#####################################################################

setup_proxy_service() {
    print_section "Setting up WS281x Proxy Service"
    
    echo "The WS281x proxy runs as root to access GPIO hardware."
    echo "It provides a localhost HTTP API for LUMEN to control LEDs."
    echo ""
    
    local SERVICE_FILE="/etc/systemd/system/${PROXY_SERVICE_NAME}.service"
    local PROXY_SCRIPT="${LUMEN_DIR}/ws281x_proxy.py"
    local LUMEN_CFG="${PRINTER_DATA}/config/lumen.cfg"
    
    # Check if service already exists
    if [ -f "$SERVICE_FILE" ]; then
        print_warning "Proxy service already exists"
        
        if prompt_yes_no "Overwrite existing service configuration?" "y"; then
            sudo systemctl stop ${PROXY_SERVICE_NAME} 2>/dev/null || true
        else
            print_info "Keeping existing service configuration"
            return
        fi
    fi
    
    if ! prompt_yes_no "Install WS281x proxy service?" "y"; then
        print_warning "Skipping proxy service installation"
        print_info "Use 'driver: klipper' in lumen.cfg instead of 'driver: proxy'"
        return
    fi
    
    echo "Creating systemd service..."
    
    # Create the service file
    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=LUMEN WS281x Proxy
Documentation=https://github.com/Lumen-RPI/lumen
After=network.target
Before=moonraker.service

[Service]
Type=simple
User=root
ExecStart=${MOONRAKER_VENV}/bin/python ${PROXY_SCRIPT} --port ${PROXY_PORT} --lumen-cfg ${LUMEN_CFG}
Restart=always
RestartSec=5

# Security hardening (proxy only needs network and /dev/mem)
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
NoNewPrivileges=false

[Install]
WantedBy=multi-user.target
EOF
    
    print_success "Service file created: ${SERVICE_FILE}"
    
    # Reload systemd
    echo "Reloading systemd..."
    sudo systemctl daemon-reload
    
    # Enable the service
    echo "Enabling service..."
    sudo systemctl enable ${PROXY_SERVICE_NAME}
    print_success "Service enabled"
    
    # Start the service
    echo "Starting service..."
    sudo systemctl start ${PROXY_SERVICE_NAME}
    
    # Check if it started successfully
    sleep 2
    if systemctl is-active --quiet ${PROXY_SERVICE_NAME}; then
        print_success "Proxy service started successfully"
        
        # Test the proxy
        echo "Testing proxy connection..."
        if curl -s "http://127.0.0.1:${PROXY_PORT}/status" > /dev/null 2>&1; then
            print_success "Proxy responding on port ${PROXY_PORT}"
        else
            print_warning "Proxy not responding yet (may still be initializing)"
        fi
    else
        print_error "Proxy service failed to start"
        echo ""
        echo "Check the logs with: sudo journalctl -u ${PROXY_SERVICE_NAME} -n 50"
        echo ""
    fi
}

#####################################################################
##  LUMEN Component Installation
#####################################################################

install_lumen_component() {
    print_section "Installing LUMEN Moonraker Component"
    
    local COMPONENT_LINK="${MOONRAKER_COMPONENTS}/lumen.py"
    local LIB_LINK="${MOONRAKER_COMPONENTS}/lumen_lib"
    
    # Link main component
    if [ -L "$COMPONENT_LINK" ] || [ -f "$COMPONENT_LINK" ]; then
        print_warning "lumen.py already exists in Moonraker components"
        if prompt_yes_no "Overwrite existing component?" "y"; then
            rm -f "$COMPONENT_LINK"
        else
            print_info "Keeping existing component"
        fi
    fi
    
    if [ ! -e "$COMPONENT_LINK" ]; then
        echo "Linking lumen.py..."
        ln -sf "${LUMEN_DIR}/moonraker/components/lumen.py" "$COMPONENT_LINK"
        print_success "Component linked: ${COMPONENT_LINK}"
    fi
    
    # Link library directory
    if [ -L "$LIB_LINK" ] || [ -d "$LIB_LINK" ]; then
        print_warning "lumen_lib already exists in Moonraker components"
        if prompt_yes_no "Overwrite existing library?" "y"; then
            rm -rf "$LIB_LINK"
        else
            print_info "Keeping existing library"
        fi
    fi
    
    if [ ! -e "$LIB_LINK" ]; then
        echo "Linking lumen_lib..."
        ln -sf "${LUMEN_DIR}/moonraker/components/lumen_lib" "$LIB_LINK"
        print_success "Library linked: ${LIB_LINK}"
    fi
}

#####################################################################
##  Configuration Setup
#####################################################################

setup_configuration() {
    print_section "Configuration Setup"
    
    local LUMEN_CFG="${PRINTER_DATA}/config/lumen.cfg"
    local MOONRAKER_CONF="${PRINTER_DATA}/config/moonraker.conf"
    
    # Create lumen.cfg if it doesn't exist
    if [ ! -f "$LUMEN_CFG" ]; then
        echo "Creating default lumen.cfg..."
        cp "${LUMEN_DIR}/config/lumen.cfg.example" "$LUMEN_CFG"
        print_success "Config created: ${LUMEN_CFG}"
        print_info "Edit this file to configure your LED groups"
    else
        print_info "lumen.cfg already exists, skipping..."
    fi
    
    # Check moonraker.conf for [lumen] section
    echo ""
    echo "Checking moonraker.conf..."
    
    if grep -q "^\[lumen\]" "$MOONRAKER_CONF" 2>/dev/null; then
        print_success "[lumen] section found in moonraker.conf"
    else
        print_warning "[lumen] section not found in moonraker.conf"
        echo ""
        echo "You need to add the following to moonraker.conf:"
        echo ""
        echo -e "${GREEN}[lumen]"
        echo "config_path: ${PRINTER_DATA}/config/lumen.cfg"
        echo "# debug: True              # Enable for troubleshooting"
        echo -e "# debug: console          # Also log to Mainsail console${NC}"
        echo ""
        
        if prompt_yes_no "Add [lumen] section to moonraker.conf automatically?" "y"; then
            echo "" >> "$MOONRAKER_CONF"
            echo "[lumen]" >> "$MOONRAKER_CONF"
            echo "config_path: ${PRINTER_DATA}/config/lumen.cfg" >> "$MOONRAKER_CONF"
            echo "# debug: True" >> "$MOONRAKER_CONF"
            print_success "[lumen] section added to moonraker.conf"
        fi
    fi
    
    # Check for update_manager section
    if grep -q "^\[update_manager lumen\]" "$MOONRAKER_CONF" 2>/dev/null; then
        print_success "[update_manager lumen] section found"
    else
        print_warning "[update_manager lumen] section not found"
        echo ""
        echo "For automatic updates, add to moonraker.conf:"
        echo ""
        echo -e "${GREEN}[update_manager lumen]"
        echo "type: git_repo"
        echo "path: ${LUMEN_DIR}"
        echo "origin: https://github.com/MakesBadDecisions/Lumen_RPI.git"
        echo "managed_services: moonraker"
        echo -e "primary_branch: main${NC}"
        echo ""

        if prompt_yes_no "Add [update_manager lumen] section automatically?" "y"; then
            # Try to detect git remote origin
            GITHUB_ORIGIN=$(cd "${LUMEN_DIR}" && git remote get-url origin 2>/dev/null || echo "")

            if [ -z "$GITHUB_ORIGIN" ]; then
                print_warning "Could not detect git origin. Using default."
                GITHUB_ORIGIN="https://github.com/MakesBadDecisions/Lumen_RPI.git"
            fi

            echo "" >> "$MOONRAKER_CONF"
            echo "[update_manager lumen]" >> "$MOONRAKER_CONF"
            echo "type: git_repo" >> "$MOONRAKER_CONF"
            echo "path: ${LUMEN_DIR}" >> "$MOONRAKER_CONF"
            echo "origin: ${GITHUB_ORIGIN}" >> "$MOONRAKER_CONF"
            echo "managed_services: moonraker" >> "$MOONRAKER_CONF"
            echo "primary_branch: main" >> "$MOONRAKER_CONF"
            print_success "[update_manager lumen] section added"
        fi
    fi
}

#####################################################################
##  Final Steps
#####################################################################

final_steps() {
    print_section "Installation Complete!"
    
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗"
    echo "║                    LUMEN is installed!                        ║"
    echo -e "╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${YELLOW}Next steps:${NC}"
    echo ""
    echo "1. Edit your LED configuration:"
    echo "   nano ${PRINTER_DATA}/config/lumen.cfg"
    echo ""
    echo "2. Restart Moonraker to load LUMEN:"
    echo "   sudo systemctl restart moonraker"
    echo ""
    echo "3. Check LUMEN status:"
    echo "   curl http://localhost:7125/server/lumen/status | python3 -m json.tool"
    echo ""
    echo "4. Monitor LED updates (useful for debugging):"
    echo "   watch -n 2 'curl -s http://localhost:7125/server/lumen/status | python3 -m json.tool'"
    echo ""
    
    if systemctl is-active --quiet ${PROXY_SERVICE_NAME} 2>/dev/null; then
        echo "5. Check proxy service:"
        echo "   sudo systemctl status ${PROXY_SERVICE_NAME}"
        echo "   curl http://127.0.0.1:${PROXY_PORT}/status"
        echo ""
    fi
    
    echo -e "${CYAN}Useful commands:${NC}"
    echo "  View LUMEN logs:    sudo journalctl -u moonraker | grep LUMEN"
    echo "  View proxy logs:    sudo journalctl -u ${PROXY_SERVICE_NAME}"
    echo "  Test LED event:     curl -X POST 'http://localhost:7125/server/lumen/test_event?event=heating'"
    echo "  Reload config:      curl -X POST 'http://localhost:7125/server/lumen/reload'"
    echo "  List colors:        curl http://localhost:7125/server/lumen/colors"
    echo ""
    
    if prompt_yes_no "Restart Moonraker now?" "y"; then
        echo "Restarting Moonraker..."
        sudo systemctl restart moonraker
        print_success "Moonraker restarted"
        echo ""
        echo "Wait a few seconds, then check status with:"
        echo "  curl http://localhost:7125/server/lumen/status | python3 -m json.tool"
    fi
    
    echo ""
    echo -e "${GREEN}Enjoy your lights! 💡${NC}"
}

#####################################################################
##  Main Installation Flow
#####################################################################

main() {
    print_header
    
    preflight_checks
    detect_and_confirm_paths
    handle_pigpiod
    install_rpi_ws281x
    setup_proxy_service
    install_lumen_component
    setup_configuration
    final_steps
}

# Run main function
main "$@"
