#!/bin/bash
#####################################################################
##  LUMEN v1.4.3 Upgrade Script
##  Optimizes ProxyDriver for true 60 FPS performance
#####################################################################

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "=========================================="
echo "  LUMEN v1.4.3 Upgrade"
echo "  60 FPS Optimization"
echo "=========================================="
echo ""

# Find ws281x-proxy service
SERVICE_NAME=$(systemctl list-units --type=service --all | grep ws281x | awk '{print $1}' | head -1)

if [ -z "$SERVICE_NAME" ]; then
    echo "ERROR: ws281x-proxy service not found"
    echo "This upgrade requires the proxy service to be installed."
    exit 1
fi

SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"

echo "Found service: $SERVICE_NAME"
echo "Service file: $SERVICE_FILE"
echo ""

# Check if quiet mode already enabled
if grep -q "WS281X_QUIET" "$SERVICE_FILE" 2>/dev/null; then
    echo "✓ Quiet mode already enabled in service file"
else
    echo "Adding quiet mode to service file..."

    # Create a temporary file with the updated service (in /tmp with sudo)
    TMP_FILE="/tmp/lumen_upgrade_service_$$"

    # Insert Environment line after User=root
    awk '/^User=root$/ {print; print "Environment=\"WS281X_QUIET=1\""; next}1' "$SERVICE_FILE" | sudo tee "$TMP_FILE" > /dev/null

    # Replace the service file
    sudo cp "$TMP_FILE" "$SERVICE_FILE"
    sudo rm "$TMP_FILE"

    echo "✓ Service file updated with quiet mode"
fi

echo ""
echo "Reloading systemd and restarting services..."
echo ""

# Reload systemd
sudo systemctl daemon-reload

# Restart proxy service
echo "Restarting ws281x-proxy..."
sudo systemctl restart "$SERVICE_NAME"

# Check if it started
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✓ Proxy service restarted successfully"
else
    echo "✗ Proxy service failed to restart"
    echo "Check logs: sudo journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

# Restart Moonraker to load updated drivers.py
echo "Restarting Moonraker..."
sudo systemctl restart moonraker

sleep 3
if systemctl is-active --quiet moonraker; then
    echo "✓ Moonraker restarted successfully"
else
    echo "✗ Moonraker failed to restart"
    echo "Check logs: sudo journalctl -u moonraker -n 50"
    exit 1
fi

echo ""
echo "=========================================="
echo "  v1.4.3 Upgrade Complete!"
echo "=========================================="
echo ""
echo "Changes applied:"
echo "  ✓ ProxyDriver timeout reduced to 10ms (was 100ms)"
echo "  ✓ WS281x proxy quiet mode enabled (reduced logging spam)"
echo ""
echo "Expected performance:"
echo "  • Target: 60 FPS on GPIO/Proxy groups"
echo "  • Previous: ~30 FPS (v1.4.2)"
echo "  • Improvement: 2x faster, should achieve full 60 FPS"
echo ""
echo "Monitor performance:"
echo "  journalctl -u moonraker -f | grep -i 'frame skip\\|fps'"
echo ""
echo "To disable quiet mode (for debugging):"
echo "  1. Edit: $SERVICE_FILE"
echo "  2. Remove line: Environment=\"WS281X_QUIET=1\""
echo "  3. Run: sudo systemctl daemon-reload"
echo "  4. Run: sudo systemctl restart $SERVICE_NAME"
echo ""
