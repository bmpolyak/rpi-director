# Raspberry Pi LED Director (MQTT)

A robust Python system for controlling LEDs and monitoring buttons across multiple Raspberry Pi devices using MQTT messaging. The system supports both server (button monitoring) and client (LED control) modes with bidirectional communication.

## Features

- **Multi-device support**: One server Pi (buttons) can communicate with multiple client Pis (LEDs)
- **MQTT messaging**: Reliable bidirectional communication with QoS 1 delivery guarantees
- **Client presence tracking**: Server can detect which clients are online with heartbeat monitoring
- **Visual status feedback**: LEDs flash to indicate connection problems
  - Server red LED flashes when MQTT broker is unreachable
  - Client yellow LED flashes when MQTT connection is lost
  - Server yellow LED flashes when client heartbeats are lost
- **Robust deployment**: Systemd services, virtual environment, automated setup
- **Dual network interfaces**: DHCP + static IP configuration for reliable networking
- **Advanced GPIO handling**: Per-pin edge detection with polling fallback, flood protection
- **Production logging**: Optional file logging with rotation, disabled by default for SD card protection
- **Industrial reliability**: Thread-safe operations, graceful error handling, 24/7 factory operations
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
- **Buttons**: GPIO 2, 3, 4 (with pull-up resistors, active-low)
- **LEDs**: 
  - Status LEDs: GPIO 10 (red), 9 (green)
  - Client status LEDs: GPIO 11 (client1), 5 (client2), 6 (client3)
- **Network**: Requires static IP for MQTT broker accessibility

### Client Pis (LED Control)  
- **LEDs**: GPIO 10 (red), 9 (green), 11 (yellow)
- **Button**: GPIO 2 (yellow, with pull-up resistor, active-low)
- **Network**: Can use DHCP, but needs access to server's MQTT broker

### Wiring Example
```
Button (GPIO 2) ─── [Button] ─── GND
                 └─ 10kΩ ─── 3.3V

LED (GPIO 10) ─── [220Ω Resistor] ─── [LED] ─── GND
```

**Important**: All buttons are configured as active-low (HIGH=not pressed, LOW=pressed) with internal pull-up resistors enabled.

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
- **Server Pi**: 192.168.5.101 (as configured in settings.json)
- **Client Pis**: 192.168.5.102, 192.168.5.103, etc.

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
sudo python3 install.py --mode server
```

For **client** mode (LED control):
```bash
sudo python3 install.py --mode client --client-id client1
```

Additional client examples:
```bash
sudo python3 install.py --mode client --client-id client2
sudo python3 install.py --mode client --client-id client3 --broker-host 192.168.1.100
```

The installation script will:
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
  "server_buttons": {
    "red": 2,
    "green": 3,
    "clear": 4
  },
  "server_leds": {
    "red": 10,
    "green": 9,
    "yellow_client1": 11,
    "yellow_client2": 5,
    "yellow_client3": 6
  },
  "client_buttons": {
    "yellow": 2
  },
  "client_leds": {
    "red": 10,
    "green": 9,
    "yellow": 11
  },
  "clients": [
    "client1",
    "client2", 
    "client3"
  ],
  "mqtt": {
    "broker_host": "192.168.5.101",
    "broker_port": 1883,
    "keepalive": 60,
    "client_id_prefix": "led_director"
  }
}
```

### MQTT Topics

The system uses the following MQTT topic structure:
- `led-director/server/event/buttons/{color}`: Button press events (published by server)
- `led-director/client/{client_id}/cmd/leds/{color}`: LED control commands (published by server)
- `led-director/client/{client_id}/state/leds/{color}`: LED status confirmations (published by clients)
- `led-director/client/{client_id}/event/buttons/yellow`: Client button events (published by clients)
- `led-director/client/{client_id}/heartbeat`: Client presence heartbeat (published by clients)

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

**🛡️ SD Card Protection: File logging is DISABLED by default** to prevent SD card overflow in factory environments. All logs go to console/systemd journal only.

### Default Logging Behavior

```bash
# By default - no file logging, WARNING level only
python3 -m rpi_director --mode server
# Output: "File logging disabled (default). Set RPI_DIRECTOR_ENABLE_FILE_LOGGING=1 to enable."
```

### Enable File Logging (Optional)

For troubleshooting or development, enable file logging with automatic rotation:

```bash
# Enable file logging with rotation (10MB files, 3 backups = 30MB max)
export RPI_DIRECTOR_ENABLE_FILE_LOGGING=1
export RPI_DIRECTOR_LOG_LEVEL=INFO

# Run the service
python3 -m rpi_director --mode server
# Output: "File logging enabled: 10MB per file, 3 backups (30MB total)"
```

### Production Log Levels

```bash
# Production (default) - minimal logging
export RPI_DIRECTOR_LOG_LEVEL=WARNING

# Troubleshooting - detailed logging  
export RPI_DIRECTOR_LOG_LEVEL=INFO

# Development - verbose logging
export RPI_DIRECTOR_LOG_LEVEL=DEBUG
```

### Systemd Service Configuration

The systemd services are pre-configured with safe defaults:

```ini
# Current service configuration (safe for production)
Environment=RPI_DIRECTOR_ENABLE_FILE_LOGGING=0
Environment=RPI_DIRECTOR_LOG_LEVEL=WARNING
```

To enable file logging permanently:

```bash
# Edit service file
sudo nano /etc/systemd/system/rpi-director.service

# Change to:
Environment=RPI_DIRECTOR_ENABLE_FILE_LOGGING=1
Environment=RPI_DIRECTOR_LOG_LEVEL=INFO

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart rpi-director.service
```

### View Logs

```bash
# Console logs (always available)
sudo journalctl -u rpi-director.service -f
sudo journalctl -u rpi-director-client.service -f

# File logs (if enabled)
tail -f /home/boston/rpi-director/rpi_director.log
```

## Recent Improvements (August 2025)

### 🔧 Critical Bug Fixes
- **MQTT v2 Compatibility**: Fixed paho-mqtt 2.x constructor to use proper keyword arguments
- **Per-Pin Edge Detection**: Eliminated global failure mode - individual pins fall back to polling if edge detection fails
- **QoS Reliability**: All MQTT subscriptions now use QoS 1 for guaranteed delivery
- **Reconnection Protection**: Prevents conflicts between manual and automatic MQTT reconnection
- **Button Flood Protection**: 300ms cooldown prevents hardware bounce from disrupting factory operations

### 🏭 Industrial Enhancements
- **SD Card Protection**: File logging disabled by default with optional rotation when enabled
- **Hardware Diagnostics**: Comprehensive GPIO testing script with edge detection validation and interactive/non-interactive modes
- **Active-Low Documentation**: Clear documentation of button wiring assumptions (HIGH=not pressed, LOW=pressed)
- **Thread Safety**: Enhanced GPIO operations with proper locking for concurrent access
- **Production Logging**: WARNING level default with configurable verbosity via environment variables

### 📊 Factory Operation Features
- **Hybrid Button Monitoring**: Automatic fallback from edge detection to polling per-pin basis
- **Status Indicator System**: Red/Green/Yellow LED coordination for multi-station factory workflows
- **Client Presence Tracking**: Real-time heartbeat monitoring with 3-second intervals
- **Visual Connection Feedback**: LED status indicators for immediate troubleshooting
  - Server red LED flashes (every 3s) when MQTT broker is unreachable
  - Client yellow LED flashes (every 3s) when MQTT connection is lost  
  - Server yellow LED flashes (every 3s) when client heartbeats are missing

## Status Feedback System

The system provides immediate visual feedback for connection and communication issues:

### Server Status Indicators

**Red LED Flashing**: MQTT broker connection lost
- **Cause**: Mosquitto service stopped, network issues, or broker misconfiguration
- **Pattern**: Quick flash (0.2s on, 2.8s off) every 3 seconds
- **Resolution**: Check `sudo systemctl status mosquitto` and network connectivity

**Yellow LED Flashing**: One or more clients are offline
- **Cause**: Client Pi powered off, network disconnected, or client service stopped
- **Pattern**: Quick flash (0.2s on, 2.8s off) every 3 seconds
- **Resolution**: Check client Pi status and network connectivity

### Client Status Indicators  

**Yellow LED Flashing**: MQTT broker connection lost
- **Cause**: Network issues, server Pi offline, or incorrect broker IP configuration
- **Pattern**: Quick flash (0.2s on, 2.8s off) every 3 seconds
- **Resolution**: Check network connectivity to server Pi and MQTT broker status

### Normal Operation
- **No flashing LEDs**: All connections healthy
- **Solid LEDs**: Current system state (red/green modes, client yellow states)
- **Heartbeat interval**: Clients send presence updates every 3 seconds
- **Timeout threshold**: Server considers client offline after 30 seconds without heartbeat
- **Reliable Messaging**: QoS 1 ensures critical status updates aren't lost on factory networks
- **24/7 Operation**: Robust error handling and automatic recovery for continuous factory use

## GPIO Hardware Diagnostics

A comprehensive GPIO testing script (`gpio_test.py`) is included to validate hardware setup and diagnose edge detection issues before deployment.

### Quick GPIO Test

```bash
cd ~/rpi-director
sudo python3 gpio_test.py
```

### Non-Interactive Mode (for automated testing)

```bash
# For unattended bench testing or CI/CD pipelines
sudo python3 gpio_test.py --no-interactive
```

### Diagnostic Features

The GPIO test script provides comprehensive validation:

**System Capability Checks**:
- GPIO permissions and group membership
- RPi.GPIO library availability  
- Conflicting services detection (pigpiod, etc.)
- Pin conflict analysis with settings.json

**Per-Pin Testing**:
- Basic GPIO setup validation
- Edge detection capability (FALLING, RISING, BOTH)
- Callback function testing with timeout
- Multiple callback stress testing
- Hardware bounce/noise detection
- Pull-up resistor validation
- Pin stability analysis over time

**Interactive vs Non-Interactive Mode**:
- **Interactive**: Prompts for button presses to test actual hardware
- **Non-Interactive**: Validates IRQ system without user interaction (ideal for bench testing)

### Test Results Interpretation

**✅ PASSED**: Pin fully functional with edge detection
**⚠️ PARTIAL**: Core functionality works but some advanced features failed
**❌ FAILED**: Critical issues detected, will fall back to polling

**System Verdicts**:
- **PRODUCTION READY**: All pins passed, optimal performance expected
- **MOSTLY READY**: 75%+ pins working, some polling fallback
- **NEEDS WORK**: <75% pins working, significant polling required  
- **NOT READY**: No edge detection working, all polling fallback

### Common Issues Detected

The script automatically diagnoses and suggests fixes for:

- **Permission Issues**: Not in gpio group, need sudo
- **Pin Conflicts**: I²C (GPIO 2,3), SPI (GPIO 7-11), UART (GPIO 14,15)  
- **Hardware Bouncing**: Button contacts creating multiple rapid callbacks
- **Electrical Noise**: Excessive callbacks indicating poor signal quality
- **Pull-up Problems**: Internal pull-up resistor not functioning
- **Service Conflicts**: pigpiod or other GPIO services interfering

### Performance Predictions

Based on test results, the script predicts runtime performance:

- **Edge Detection Working**: <1ms latency, ~0% CPU when idle
- **Polling Fallback**: ~20ms latency, ~2-5% continuous CPU usage

## Troubleshooting

### Common Issues

**MQTT Connection Problems**
```bash
# Check if Mosquitto is running on server
sudo systemctl status mosquitto

# Test MQTT connectivity
mosquitto_pub -h 192.168.5.101 -t test/topic -m "hello"
mosquitto_sub -h 192.168.5.101 -t test/topic
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
ping 192.168.5.101  # From client to server
```

### Service Debugging

**View system logs:**
```bash
# Server logs (systemd only - no file logging by default)
sudo journalctl -u rpi-director.service -f

# Client logs  
sudo journalctl -u rpi-director-client.service -f

# MQTT broker logs
sudo journalctl -u mosquitto -f
```

**Enable detailed logging for debugging:**
```bash
# Temporarily enable file logging and debug level
sudo systemctl edit rpi-director.service

# Add these lines in the editor:
[Service]
Environment="RPI_DIRECTOR_ENABLE_FILE_LOGGING=1"
Environment="RPI_DIRECTOR_LOG_LEVEL=DEBUG"

# Restart to apply changes
sudo systemctl restart rpi-director.service

# View the log file
tail -f ~/rpi-director/rpi_director.log
```

**Test manual execution:**
```bash
# Stop service first
sudo systemctl stop rpi-director.service

# Run manually with debug output and logging
cd ~/rpi-director
RPI_DIRECTOR_LOG_LEVEL=DEBUG RPI_DIRECTOR_ENABLE_FILE_LOGGING=1 ~/rpi-director-venv/bin/python rpi_director.py --mode server
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
# After running install.py, restore settings
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
