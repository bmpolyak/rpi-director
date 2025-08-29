# Raspberry Pi LED Director

A Python script that runs in the background on a Raspberry Pi and manages LED states based on button presses or OSC (Open Sound Control) network commands.

## Features

### Server Mode
- Listens for button presses on configurable GPIO pins
- Controls corresponding LEDs on configurable GPIO pins
- Sends OSC commands to multiple client devices over the network
- Red LED lights up by default on startup

### Client Mode
- Listens for OSC commands over the network
- Controls local LEDs based on received commands
- Red LED lights up by default on startup
- LEDs stay lit until another command is received

### Common Features
- Only one LED is lit at a time
- Runs as a background service
- Configurable pin assignments and network settings via JSON settings file
- Logging support
- Graceful shutdown handling

## Hardware Setup

### Default Pin Configuration
- **Buttons:** Red (GPIO 25), Yellow (GPIO 8), Green (GPIO 7)
- **LEDs:** Red (GPIO 10), Yellow (GPIO 9), Green (GPIO 11)

### Physical Pin Mapping
- **Buttons:** Red (Pin 22), Yellow (Pin 24), Green (Pin 26)
- **LEDs:** Red (Pin 19), Yellow (Pin 21), Green (Pin 23)

### Wiring
1. Connect buttons between the configured GPIO pins and GND
2. Connect LEDs with appropriate resistors (typically 330Ω) between the configured GPIO pins and GND
3. Ensure proper grounding for all components

## Installation

1. Copy the project files to your Raspberry Pi:
   ```bash
   scp -r rpi-director/ pi@your-pi-ip:/home/pi/
   ```

2. SSH into your Raspberry Pi and navigate to the project directory:
   ```bash
   ssh pi@your-pi-ip
   cd /home/pi/rpi-director
   ```

3. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

4. Make the script executable:
   ```bash
   chmod +x rpi_director.py
   ```

## Configuration

Edit `settings.json` to configure pins and network settings:

```json
{
    "buttons": {
        "red": 25,
        "yellow": 8,
        "green": 7
    },
    "leds": {
        "red": 10,
        "yellow": 9,
        "green": 11
    },
    "osc": {
        "server_port": 8000,
        "client_addresses": [
            "192.168.1.100:8000",
            "192.168.1.101:8000",
            "192.168.1.102:8000"
        ]
    }
}
```

### Configuration Options
- `buttons`: GPIO pin numbers for button inputs (server mode only)
- `leds`: GPIO pin numbers for LED outputs
- `osc.server_port`: Port for OSC server to listen on (client mode)
- `osc.client_addresses`: List of IP:port addresses to send OSC commands to (server mode)

## Usage

### Running Manually

**Server Mode** (listens to buttons, sends OSC commands):
```bash
python3 rpi_director.py --mode server
```

**Client Mode** (listens to OSC commands):
```bash
python3 rpi_director.py --mode client
```

### Running as Services

#### Server Mode Service

1. Copy the server service file:
   ```bash
   sudo cp rpi-director.service /etc/systemd/system/
   ```

2. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable rpi-director.service
   sudo systemctl start rpi-director.service
   ```

#### Client Mode Service

1. Copy the client service file:
   ```bash
   sudo cp rpi-director-client.service /etc/systemd/system/
   ```

2. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable rpi-director-client.service
   sudo systemctl start rpi-director-client.service
   ```

### Service Management

Check status:
```bash
sudo systemctl status rpi-director.service        # Server
sudo systemctl status rpi-director-client.service # Client
```

View logs:
```bash
sudo journalctl -u rpi-director.service -f        # Server
sudo journalctl -u rpi-director-client.service -f # Client
```

Stop services:
```bash
sudo systemctl stop rpi-director.service          # Server
sudo systemctl stop rpi-director-client.service   # Client
```

## Network Communication

The system uses OSC (Open Sound Control) protocol for network communication:

### OSC Messages
- `/led/red` - Switch to red LED
- `/led/yellow` - Switch to yellow LED  
- `/led/green` - Switch to green LED

### Network Setup
1. Ensure all devices are on the same network
2. Configure firewall to allow OSC traffic on the specified port (default: 8000)
3. Update IP addresses in `settings.json` for your network setup

## Operation

### Server Mode
1. On startup, the red LED will be lit by default
2. Press any button (red, yellow, or green) to switch to that color LED
3. The server will also send OSC commands to all configured client addresses
4. Only one LED is active at a time locally

### Client Mode
1. On startup, the red LED will be lit by default
2. The client listens for OSC commands on the configured port
3. When an OSC command is received, it switches to the corresponding LED
4. LEDs stay lit until another OSC command is received
5. Only one LED is active at a time

## Troubleshooting

- Ensure you're running the script with appropriate permissions for GPIO access
- Check wiring connections if buttons or LEDs don't respond
- Review logs for error messages
- Verify pin numbers in `settings.json` match your hardware setup
- Make sure no other processes are using the same GPIO pins
- Check network connectivity if OSC commands aren't working
- Verify firewall settings allow traffic on the OSC port
- Ensure IP addresses in settings are correct and reachable

## File Structure

```
rpi-director/
├── rpi_director.py              # Main Python script
├── settings.json               # Pin and network configuration
├── requirements.txt            # Python dependencies
├── rpi-director.service       # Systemd service file (server mode)
├── rpi-director-client.service # Systemd service file (client mode)
└── README.md                  # This file
```
