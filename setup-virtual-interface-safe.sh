#!/bin/bash
#
# Safe Virtual Interface Setup Script
# This version uses dhcpcd.conf method which is safer for Raspberry Pi OS
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

echo "🌐 Setting up safe virtual interface with IP: $STATIC_IP"

# Backup dhcpcd.conf
cp /etc/dhcpcd.conf /etc/dhcpcd.conf.backup.$(date +%Y%m%d_%H%M%S)

# Remove any existing static IP configuration for eth0:0
sed -i '/^interface eth0:0/,/^$/d' /etc/dhcpcd.conf

# Add static IP configuration for alias interface
cat >> /etc/dhcpcd.conf << EOF

# Static IP for LED Director OSC communication
interface eth0:0
static ip_address=$STATIC_IP/24
EOF

# Restart dhcpcd to apply changes
systemctl restart dhcpcd

# Give it time to apply
sleep 3

print_success "Safe virtual interface configured!"
print_warning "The Pi will keep its DHCP IP on eth0 and add $STATIC_IP on eth0:0"

# Show current status
echo ""
echo "Current network status:"
ip addr show eth0 | grep -E "(inet |eth0)"

echo ""
print_success "Setup complete! Both DHCP and static IP should now work."
echo "DHCP IP: $(ip route get 8.8.8.8 | grep -oE 'src [0-9.]+' | cut -d' ' -f2)"
echo "Static IP: $STATIC_IP"
