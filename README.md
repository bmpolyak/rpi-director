# Raspberry Pi LED Director (MQTT)

A robust Python system for controlling LEDs and monitoring buttons across multiple Raspberry Pi devices using MQTT messaging. The system supports both server (button monitoring) and client (LED control) modes with bidirectional communication.

## Features

- **Multi-device support**: One server Pi (buttons) can communicate with multiple client Pis (LEDs)
- **MQTT messaging**: Reliable bidirectional communication using MQTT broker
- **Robust deployment**: Systemd services, virtual environment, automated setup
- **Dual network interfaces**: DHCP + static IP configuration for reliable networking
- **Graceful error handling**: GPIO polling fallback, connection resilience
- **Comprehensive logging**: File and systemd journal logging
- **Signal handling**: Clean shutdown on SIGINT/SIGTERM

## Architecture

### Server Mode (Button Monitoring)
- Monitors physical buttons on GPIO pins 2, 3, 4
- Controls corresponding LEDs on GPIO pins 10, 9, 11
- Publishes button press events to MQTT broker
- Runs integrated Mosquitto MQTT broker

### Client Mode (LED Control)
- Subscribes to MQTT button events
- Controls LEDs on GPIO pins 10, 9, 11 based on received commands
- Sends LED status confirmations back to server
- Connects to remote MQTT broker (server Pi)

## Hardware Setup

### Server Pi (Button Monitoring)
- **Buttons**: GPIO 2, 3, 4 (with pull-up resistors)
- **LEDs**: GPIO 10, 9, 11 (with appropriate resistors)
- **Network**: Requires static IP for MQTT broker accessibility

### Client Pis (LED Control)  
- **LEDs**: GPIO 10, 9, 11 (with appropriate resistors)
- **Network**: Can use DHCP, but needs access to server's MQTT broker

### Wiring Example
```
Button (GPIO 2) ─── [Button] ─── GND
                 └─ 10kΩ ─── 3.3V

LED (GPIO 10) ─── [220Ω Resistor] ─── [LED] ─── GND
```

## Network Configuration

The system uses dual network interfaces for reliability:
- **eth0**: DHCP for internet access and general networking
- **eth0:static**: Additional static IP for device-to-device communication

### Setup Static IP (NetworkManager Compatible)

Run the included script on each Pi to add a static IP:

```bash
sudo ./setup-networkmanager-static.sh
```

This will:
- Add a static IP (192.168.1.x) to your existing eth0 interface
- Keep your current DHCP configuration intact
- Use NetworkManager-compatible configuration

### Static IP Assignment
- **Server Pi**: 192.168.1.100
- **Client Pis**: 192.168.1.101, 192.168.1.102, etc.

## Installation

### Prerequisites
```bash
sudo apt update
sudo apt install git python3 python3-pip
```

### Clone Repository
```bash
cd ~
git clone <your-repo-url> rpi-director
cd rpi-director
```

### Automated Setup

For **server** mode (button monitoring + MQTT broker):
```bash
sudo python3 setup.py --mode server
```

For **client** mode (LED control):
```bash
sudo python3 setup.py --mode client
```

The setup script will:
1. Install system dependencies (including Mosquitto for server)
2. Create Python virtual environment
3. Install Python packages (paho-mqtt, RPi.GPIO)
4. Configure GPIO permissions
5. Install and start systemd service
6. Test the installation

## Configuration

### settings.json

The system uses `settings.json` for configuration:

```json
{
  "server": {
    "buttons": [
      {"name": "red", "pin": 2, "led_pin": 10},
      {"name": "yellow", "pin": 3, "led_pin": 9},
      {"name": "green", "pin": 4, "led_pin": 11}
    ]
  },
  "client": {
    "leds": [
      {"name": "red", "pin": 10},
      {"name": "yellow", "pin": 9},
      {"name": "green", "pin": 11}
    ]
  },
  "mqtt": {
    "broker_host": "192.168.1.100",
    "broker_port": 1883,
    "topics": {
      "button_press": "rpi/button/{color}",
      "led_status": "rpi/led/{color}/status",
      "led_command": "rpi/led/{color}/command"
    }
  },
  "logging": {
    "level": "INFO",
    "file": "/var/log/rpi_director.log",
    "max_bytes": 10485760,
    "backup_count": 5
  }
}
```

### MQTT Topics

The system uses the following MQTT topic structure:
- `rpi/button/{color}`: Button press events (published by server)
- `rpi/led/{color}/command`: LED control commands (published by server)
- `rpi/led/{color}/status`: LED status confirmations (published by clients)

## Service Management

### Check Status
```bash
# Server
sudo systemctl status rpi-director.service

# Client  
sudo systemctl status rpi-director-client.service
```

### View Logs
```bash
# Server
sudo journalctl -u rpi-director.service -f

# Client
sudo journalctl -u rpi-director-client.service -f
```

### Control Services
```bash
# Stop
sudo systemctl stop rpi-director.service        # Server
sudo systemctl stop rpi-director-client.service # Client

# Start
sudo systemctl start rpi-director.service        # Server
sudo systemctl start rpi-director-client.service # Client

# Restart
sudo systemctl restart rpi-director.service        # Server
sudo systemctl restart rpi-director-client.service # Client
```

## Manual Usage

Run manually for testing:
```bash
# Server mode
cd ~/rpi-director
~/rpi-director-venv/bin/python rpi_director.py --mode server

# Client mode
cd ~/rpi-director  
~/rpi-director-venv/bin/python rpi_director.py --mode client
```

## Logging Configuration

**File logging is disabled by default** to prevent SD card overflow. All logs go to console/systemd journal only.

### Enable File Logging (Optional)

To enable file logging with automatic rotation:

```bash
# Enable file logging with rotation (10MB files, 3 backups = 30MB max)
export RPI_DIRECTOR_ENABLE_FILE_LOGGING=1

# Run the service
python3 -m rpi_director --mode server
```

### Configure Log Level

```bash
# Set log level (default: WARNING for production)
export RPI_DIRECTOR_LOG_LEVEL=INFO

# Available levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
python3 -m rpi_director --mode server
```

### Systemd Service with Logging

To enable file logging in systemd services, edit the service files:

```bash
sudo systemctl edit rpi-director.service
```

Add:
```ini
[Service]
Environment=RPI_DIRECTOR_ENABLE_FILE_LOGGING=1
Environment=RPI_DIRECTOR_LOG_LEVEL=WARNING
```

## Troubleshooting

### Common Issues

**MQTT Connection Problems**
```bash
# Check if Mosquitto is running on server
sudo systemctl status mosquitto

# Test MQTT connectivity
mosquitto_pub -h 192.168.1.100 -t test/topic -m "hello"
mosquitto_sub -h 192.168.1.100 -t test/topic
```

**GPIO Permission Issues**
```bash
# Check if user is in gpio group
groups $USER

# If not in gpio group, add and reboot
sudo usermod -a -G gpio $USER
```

**Network Connectivity**
```bash
# Check if static IP is configured
ip addr show eth0

# Test connectivity between Pis
ping 192.168.1.100  # From client to server
```

### Service Debugging

**View detailed logs:**
```bash
# Server logs
sudo journalctl -u rpi-director.service -f

# Client logs  
sudo journalctl -u rpi-director-client.service -f

# MQTT broker logs
sudo journalctl -u mosquitto -f
```

**Test manual execution:**
```bash
# Stop service first
sudo systemctl stop rpi-director.service

# Run manually with debug output
cd ~/rpi-director
~/rpi-director-venv/bin/python rpi_director.py --mode server --debug
```

## Firewall Configuration

If using a firewall, ensure MQTT port is open:

```bash
# UFW (if using)
sudo ufw allow 1883/tcp

# Or iptables
sudo iptables -A INPUT -p tcp --dport 1883 -j ACCEPT
```

## Backup and Restore

### Backup Configuration
```bash
tar -czf rpi-director-backup.tar.gz ~/rpi-director/settings.json ~/rpi-director/*.service
```

### Restore on New Pi
```bash
# After running setup.py, restore settings
tar -xzf rpi-director-backup.tar.gz -C /
sudo systemctl restart rpi-director.service  # or rpi-director-client.service
```

## Development

### Adding New Button/LED Colors

1. Update `settings.json` with new pin configurations
2. The system automatically handles new configurations on restart
3. MQTT topics are generated dynamically based on color names

### Extending Functionality

The modular design allows easy extension:
- **MQTTServer**: Handles button monitoring and MQTT publishing
- **MQTTClient**: Handles MQTT subscription and LED control  
- **GPIOManager**: Manages all GPIO operations
- **Settings**: Handles configuration loading and validation

## License

[Add your license here]

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review systemd logs for error details
3. Test components individually (GPIO, MQTT, network)
