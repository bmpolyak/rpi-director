#!/bin/bash
#
# NetworkManager Safe Virtual Interface Setup Script
# Adds a static IP while keeping DHCP working
#

set -e

STATIC_IP="$1"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root"
    exit 1
fi

if [[ -z "$STATIC_IP" ]]; then
    print_error "Usage: sudo $0 <static_ip>"
    exit 1
fi

# Validate IP format
if ! [[ "$STATIC_IP" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
    print_error "Invalid IP address format: $STATIC_IP"
    exit 1
fi

echo "🌐 Setting up NetworkManager virtual interface with IP: $STATIC_IP"

# Check if NetworkManager is running
if ! systemctl is-active --quiet NetworkManager; then
    print_error "NetworkManager is not running!"
    exit 1
fi

# Get the primary ethernet connection name
CONN_NAME=$(nmcli -t -f NAME,DEVICE connection show --active | grep eth0 | cut -d: -f1)

if [[ -z "$CONN_NAME" ]]; then
    print_warning "No active ethernet connection found, trying to find any ethernet connection"
    CONN_NAME=$(nmcli -t -f NAME,TYPE connection show | grep ethernet | head -1 | cut -d: -f1)
    
    if [[ -z "$CONN_NAME" ]]; then
        print_error "No ethernet connection found. Creating a new one..."
        nmcli connection add type ethernet con-name "Wired connection 1" ifname eth0
        CONN_NAME="Wired connection 1"
    fi
fi

print_success "Found ethernet connection: $CONN_NAME"

# Check if static IP already exists
EXISTING_IPS=$(nmcli -t -f ipv4.addresses connection show "$CONN_NAME" | cut -d: -f2)

if [[ "$EXISTING_IPS" == *"$STATIC_IP"* ]]; then
    print_warning "Static IP $STATIC_IP already configured"
else
    # Add static IP while keeping DHCP
    print_success "Adding static IP $STATIC_IP to connection '$CONN_NAME'"
    nmcli connection modify "$CONN_NAME" +ipv4.addresses "$STATIC_IP/24"
    
    # Make sure DHCP is still enabled (this is the key!)
    nmcli connection modify "$CONN_NAME" ipv4.method auto
fi

# Apply the changes
print_success "Activating connection..."
nmcli connection up "$CONN_NAME"

# Wait for interface to come up
sleep 3

# Show results
echo ""
echo "Network interface status:"
ip addr show eth0 | grep -E "(eth0|inet )" || echo "No eth0 interface found"

echo ""
echo "NetworkManager connection details:"
nmcli connection show "$CONN_NAME" | grep -E "(ipv4.method|ipv4.addresses)"

# Test connectivity
echo ""
DHCP_IP=$(ip route get 8.8.8.8 2>/dev/null | grep -oE 'src [0-9.]+' | cut -d' ' -f2)
if [[ -n "$DHCP_IP" ]]; then
    print_success "DHCP IP: $DHCP_IP"
else
    print_warning "Could not detect DHCP IP"
fi

if ping -c 1 -W 2 "$STATIC_IP" >/dev/null 2>&1; then
    print_success "Static IP $STATIC_IP is reachable"
else
    print_warning "Static IP $STATIC_IP may not be fully configured yet"
fi

echo ""
print_success "Setup complete!"
print_success "Your Pi now has both DHCP and static IP ($STATIC_IP)"
print_warning "Both IPs are on the same interface (eth0), not a virtual interface"
print_warning "This is safer and won't break your networking"

echo ""
echo "Connection will persist across reboots automatically."
