#!/bin/bash
#####################################################################
##  LUMEN Uninstallation Script v2.0
##
##  Interactive uninstaller for LUMEN - removes all components cleanly.
##
##  Usage:
##    cd ~/lumen
##    ./uninstall.sh
##
##  What this script does:
##    1. Stops and removes ws281x-proxy systemd service
##    2. Removes LUMEN component symlinks from Moonraker
##    3. Optionally removes lumen.cfg configuration
##    4. Optionally unmasks pigpiod (if you want to use it again)
##    5. Reminds you to clean up moonraker.conf manually
#####################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Service settings
PROXY_SERVICE_NAME="ws281x-proxy"

#####################################################################
##  Helper Functions
#####################################################################

print_header() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                   LUMEN Uninstallation                        ║"
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

#####################################################################
##  Path Detection
#####################################################################

detect_paths() {
    print_section "Detecting Installation"
    
    # Detect Moonraker components directory
    MOONRAKER_COMPONENTS=""
    for path in "${HOME}/moonraker/moonraker/components" "/home/*/moonraker/moonraker/components"; do
        if [ -d "$path" ]; then
            MOONRAKER_COMPONENTS="$path"
            break
        fi
    done
    
    if [ -n "$MOONRAKER_COMPONENTS" ]; then
        print_info "Found Moonraker components at: $MOONRAKER_COMPONENTS"
    else
        print_warning "Moonraker components directory not found"
        MOONRAKER_COMPONENTS=$(prompt_value "Enter Moonraker components path" "${HOME}/moonraker/moonraker/components")
    fi
    
    # Detect printer_data directory
    PRINTER_DATA=""
    for path in "${HOME}/printer_data" "/home/*/printer_data"; do
        if [ -d "$path" ]; then
            PRINTER_DATA="$path"
            break
        fi
    done
    
    if [ -n "$PRINTER_DATA" ]; then
        print_info "Found printer_data at: $PRINTER_DATA"
    else
        print_warning "printer_data directory not found"
        PRINTER_DATA=$(prompt_value "Enter printer_data path" "${HOME}/printer_data")
    fi
}

#####################################################################
##  Remove Proxy Service
#####################################################################

remove_proxy_service() {
    print_section "Removing WS281x Proxy Service"
    
    local SERVICE_FILE="/etc/systemd/system/${PROXY_SERVICE_NAME}.service"
    
    if [ -f "$SERVICE_FILE" ]; then
        print_info "Proxy service found"
        
        if prompt_yes_no "Remove ws281x-proxy service?" "y"; then
            echo "Stopping service..."
            sudo systemctl stop ${PROXY_SERVICE_NAME} 2>/dev/null || true
            
            echo "Disabling service..."
            sudo systemctl disable ${PROXY_SERVICE_NAME} 2>/dev/null || true
            
            echo "Removing service file..."
            sudo rm -f "$SERVICE_FILE"
            
            echo "Reloading systemd..."
            sudo systemctl daemon-reload
            
            print_success "Proxy service removed"
        else
            print_info "Keeping proxy service"
        fi
    else
        print_info "Proxy service not found, skipping..."
    fi
}

#####################################################################
##  Remove Component Symlinks
#####################################################################

remove_component() {
    print_section "Removing Moonraker Component"
    
    local COMPONENT_LINK="${MOONRAKER_COMPONENTS}/lumen.py"
    local LIB_LINK="${MOONRAKER_COMPONENTS}/lumen_lib"
    
    # Remove main component
    if [ -L "$COMPONENT_LINK" ]; then
        echo "Removing lumen.py symlink..."
        rm "$COMPONENT_LINK"
        print_success "Component symlink removed"
    elif [ -f "$COMPONENT_LINK" ]; then
        print_warning "lumen.py is a file, not a symlink"
        if prompt_yes_no "Remove it anyway?" "y"; then
            rm "$COMPONENT_LINK"
            print_success "Component file removed"
        fi
    else
        print_info "Component not found, skipping..."
    fi
    
    # Remove library directory
    if [ -L "$LIB_LINK" ]; then
        echo "Removing lumen_lib symlink..."
        rm "$LIB_LINK"
        print_success "Library symlink removed"
    elif [ -d "$LIB_LINK" ]; then
        print_warning "lumen_lib is a directory, not a symlink"
        if prompt_yes_no "Remove it anyway?" "y"; then
            rm -rf "$LIB_LINK"
            print_success "Library directory removed"
        fi
    else
        print_info "Library not found, skipping..."
    fi
}

#####################################################################
##  Remove Configuration
#####################################################################

remove_configuration() {
    print_section "Configuration Cleanup"
    
    local LUMEN_CFG="${PRINTER_DATA}/config/lumen.cfg"
    
    if [ -f "$LUMEN_CFG" ]; then
        print_warning "Found lumen.cfg at: $LUMEN_CFG"
        echo ""
        echo "This file contains your LED group configuration."
        echo "You may want to keep it for backup or future reinstallation."
        echo ""
        
        if prompt_yes_no "Remove lumen.cfg?" "n"; then
            rm "$LUMEN_CFG"
            print_success "Configuration file removed"
        else
            print_info "Configuration file kept"
        fi
    else
        print_info "lumen.cfg not found, skipping..."
    fi
}

#####################################################################
##  Restore pigpiod
#####################################################################

restore_pigpiod() {
    print_section "pigpiod Restoration"
    
    # Check if pigpiod is masked
    if systemctl is-enabled pigpiod 2>&1 | grep -q "masked"; then
        print_info "pigpiod is currently masked"
        echo ""
        echo "pigpiod was disabled during LUMEN installation to prevent conflicts."
        echo "If you want to use pigpiod again (e.g., for other GPIO projects),"
        echo "you can unmask and enable it now."
        echo ""
        
        if prompt_yes_no "Unmask and enable pigpiod?" "n"; then
            echo "Unmasking pigpiod..."
            sudo systemctl unmask pigpiod
            
            if prompt_yes_no "Also enable pigpiod to start on boot?" "n"; then
                sudo systemctl enable pigpiod
                print_success "pigpiod unmasked and enabled"
            else
                print_success "pigpiod unmasked (but not enabled)"
            fi
        else
            print_info "pigpiod remains masked"
        fi
    else
        print_info "pigpiod is not masked, skipping..."
    fi
}

#####################################################################
##  Final Instructions
#####################################################################

final_instructions() {
    print_section "Uninstallation Complete"
    
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗"
    echo "║                   LUMEN has been removed                      ║"
    echo -e "╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${YELLOW}Manual cleanup required:${NC}"
    echo ""
    echo "1. Edit moonraker.conf and remove the following sections:"
    echo "   - [lumen]"
    echo "   - [update_manager lumen]"
    echo ""
    echo "   nano ${PRINTER_DATA}/config/moonraker.conf"
    echo ""
    echo "2. Restart Moonraker:"
    echo "   sudo systemctl restart moonraker"
    echo ""
    echo "3. Optionally remove the LUMEN repository:"
    echo "   rm -rf ~/lumen"
    echo ""
    
    if prompt_yes_no "Restart Moonraker now?" "y"; then
        echo "Restarting Moonraker..."
        sudo systemctl restart moonraker
        print_success "Moonraker restarted"
    fi
    
    echo ""
    echo -e "${GREEN}Thanks for trying LUMEN! 👋${NC}"
}

#####################################################################
##  Main Uninstallation Flow
#####################################################################

main() {
    print_header
    
    echo "This will remove LUMEN from your system."
    echo ""
    
    if ! prompt_yes_no "Continue with uninstallation?" "n"; then
        print_info "Uninstallation cancelled"
        exit 0
    fi
    
    detect_paths
    remove_proxy_service
    remove_component
    remove_configuration
    restore_pigpiod
    final_instructions
}

# Run main function
main "$@"
