#!/bin/bash
#
# Simple Virtual Interface Setup Script
# Creates or updates a virtual ethernet interface with static IP
#

set -e

# Configuration
PHYSICAL_INTERFACE="eth0"
VIRTUAL_INTERFACE="eth0:0"
STATIC_IP="$1"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Check arguments
if [[ -z "$STATIC_IP" ]]; then
    print_error "Usage: sudo $0 <static_ip>"
    echo "Example: sudo $0 192.168.1.100"
    exit 1
fi

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root"
    echo "Usage: sudo $0 <static_ip>"
    exit 1
fi

# Validate IP format
if ! [[ "$STATIC_IP" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
    print_error "Invalid IP address format: $STATIC_IP"
    exit 1
fi

echo "🌐 Setting up virtual interface with IP: $STATIC_IP"

# Check if virtual interface already exists
if ip link show "$VIRTUAL_INTERFACE" &>/dev/null; then
    print_warning "Virtual interface $VIRTUAL_INTERFACE already exists"
    
    # Remove existing IP addresses
    ip addr flush dev "$VIRTUAL_INTERFACE" 2>/dev/null || true
    
    # Add new IP
    ip addr add "$STATIC_IP/24" dev "$VIRTUAL_INTERFACE"
    ip link set "$VIRTUAL_INTERFACE" up
    
    print_success "Updated virtual interface $VIRTUAL_INTERFACE with IP $STATIC_IP"
else
    # Create new virtual interface
    ip link add link "$PHYSICAL_INTERFACE" name "$VIRTUAL_INTERFACE" type dummy
    ip addr add "$STATIC_IP/24" dev "$VIRTUAL_INTERFACE"
    ip link set "$VIRTUAL_INTERFACE" up
    
    print_success "Created virtual interface $VIRTUAL_INTERFACE with IP $STATIC_IP"
fi

# Create/update systemd service for persistence
cat > /etc/systemd/system/virtual-eth.service << EOF
[Unit]
Description=Virtual Ethernet Interface
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c 'ip link add link $PHYSICAL_INTERFACE name $VIRTUAL_INTERFACE type dummy 2>/dev/null || true; ip addr flush dev $VIRTUAL_INTERFACE 2>/dev/null || true; ip addr add $STATIC_IP/24 dev $VIRTUAL_INTERFACE; ip link set $VIRTUAL_INTERFACE up'
ExecStop=/bin/bash -c 'ip link delete $VIRTUAL_INTERFACE 2>/dev/null || true'

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable virtual-eth.service >/dev/null 2>&1

print_success "Virtual interface will persist across reboots"

# Show current status
echo
echo "Current network interfaces:"
ip addr show "$PHYSICAL_INTERFACE" | grep -E "(inet |state)" | head -2
ip addr show "$VIRTUAL_INTERFACE" | grep -E "(inet |state)" | head -2

echo
print_success "Setup complete! Virtual interface $VIRTUAL_INTERFACE configured with IP $STATIC_IP"
