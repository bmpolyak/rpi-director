# Raspberry Pi LED Director

A Python script that runs in the background on a Raspberry Pi and manages LED states based on button presses or OSC (Open Sound Control) network commands.

## Features

### Server Mode
- Listens for button presses on configurable GPIO pins
- Controls corresponding LEDs on configurable GPIO pins
- Sends OSC commands to multiple client devices over the network
- Red LED lights up by default on startup
- Automatic fallback to polling if GPIO edge detection fails

### Client Mode
- Listens for OSC commands over the network
- Controls local LEDs based on received commands
- Red LED lights up by default on startup
- LEDs stay lit until another command is received

### Common Features
- Only one LED is lit at a time
- Runs as a background service
- Configurable pin assignments and network settings via JSON settings file
- Robust GPIO handling with automatic polling fallback
- Logging support
- Graceful shutdown handling

## Quick Setup

**🚀 Automated Installation (Recommended)**

Copy the project to your Raspberry Pi and run the setup script:

```bash
# Copy project files to Raspberry Pi
scp -r rpi-director/ your-user@your-pi-ip:/home/your-user/

# SSH to your Pi and run setup
ssh your-user@your-pi-ip
cd ~/rpi-director

# For server mode (listens to buttons, sends OSC)
sudo python3 setup.py --mode server

# For client mode (listens to OSC, controls LEDs)  
sudo python3 setup.py --mode client
```

**The setup script automatically:**
- ✅ Creates virtual environment (`~/rpi-director-venv`)
- ✅ Installs all dependencies from `requirements.txt`
- ✅ Sets up GPIO permissions
- ✅ Installs and starts systemd service
- ✅ Tests the installation

## Hardware Setup

### Default Pin Configuration
- **Buttons:** Red (GPIO 2), Yellow (GPIO 3), Green (GPIO 4)
- **LEDs:** Red (GPIO 10), Yellow (GPIO 9), Green (GPIO 11)

### Physical Pin Mapping
- **Buttons:** Red (Pin 3), Yellow (Pin 5), Green (Pin 7)
- **LEDs:** Red (Pin 19), Yellow (Pin 21), Green (Pin 23)

### Wiring
1. Connect buttons between the configured GPIO pins and GND
2. Connect LEDs with appropriate resistors (typically 330Ω) between the configured GPIO pins and GND
3. Ensure proper grounding for all components

**Note:** If you experience GPIO edge detection issues, the script automatically falls back to reliable button polling.

## Manual Installation (Alternative)

If you prefer manual setup or the automated script doesn't work:

1. **Copy files to Raspberry Pi:**
   ```bash
   scp -r rpi-director/ your-user@your-pi-ip:/home/your-user/
   ```

2. **SSH and create virtual environment:**
   ```bash
   ssh your-user@your-pi-ip
   cd ~/rpi-director
   
   # Install system packages
   sudo apt update
   sudo apt install python3-venv python3-full
   
   # Create virtual environment
   python3 -m venv ~/rpi-director-venv
   source ~/rpi-director-venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Setup GPIO permissions:**
   ```bash
   sudo usermod -a -G gpio $USER
   sudo chown root:gpio /dev/gpiomem
   sudo chmod g+rw /dev/gpiomem
   ```

4. **Test manually:**
   ```bash
   # Activate venv and test
   source ~/rpi-director-venv/bin/activate
   python rpi_director.py --mode server  # or --mode client
   ```

5. **Install systemd service (optional):**
   ```bash
   sudo cp rpi-director.service /etc/systemd/system/        # For server
   sudo cp rpi-director-client.service /etc/systemd/system/ # For client
   
   sudo systemctl daemon-reload
   sudo systemctl enable rpi-director.service    # or rpi-director-client.service
   sudo systemctl start rpi-director.service     # or rpi-director-client.service
   ```

## Configuration

Edit `settings.json` to configure pins and network settings:

```json
{
    "buttons": {
        "red": 2,
        "yellow": 3,
        "green": 4
    },
    "leds": {
        "red": 10,
        "yellow": 9,
        "green": 11
    },
    "osc": {
        "server_port": 8001,
        "client_addresses": [
            "192.168.1.100:8001",
            "192.168.1.101:8001",
            "192.168.1.102:8001"
        ]
    }
}
```

### Configuration Options
- `buttons`: GPIO pin numbers for button inputs (server mode only)
- `leds`: GPIO pin numbers for LED outputs
- `osc.server_port`: Port for OSC server to listen on (client mode)
- `osc.client_addresses`: List of IP:port addresses to send OSC commands to (server mode)

**Note:** If you have GPIO edge detection issues, try alternative pin numbers like 17, 27, 22, or 5, 6, 13.

## Usage

### Using the Setup Script (Recommended)

After running `sudo python3 setup.py --mode <server|client>`, your service is automatically installed and running.

**Useful commands provided by setup script:**
```bash
# Check service status
sudo systemctl status rpi-director.service          # Server
sudo systemctl status rpi-director-client.service   # Client

# View live logs  
sudo journalctl -u rpi-director.service -f          # Server
sudo journalctl -u rpi-director-client.service -f   # Client

# Control services
sudo systemctl stop rpi-director.service            # Stop server
sudo systemctl start rpi-director.service           # Start server
sudo systemctl restart rpi-director.service         # Restart server
```

### Manual Testing

**Server Mode** (listens to buttons, sends OSC commands):
```bash
# Activate virtual environment first
source ~/rpi-director-venv/bin/activate
python rpi_director.py --mode server
```

**Client Mode** (listens to OSC commands):
```bash
# Activate virtual environment first
source ~/rpi-director-venv/bin/activate
python rpi_director.py --mode client
```

### Manual Service Installation (if not using setup script)

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

## Network Communication

The system uses OSC (Open Sound Control) protocol for network communication:

### OSC Messages
- `/led/red` - Switch to red LED
- `/led/yellow` - Switch to yellow LED  
- `/led/green` - Switch to green LED

### Network Setup
1. Ensure all devices are on the same network
2. Configure firewall to allow OSC traffic on the specified port (default: 8001)
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

### Common Issues

**"Failed to add edge detection" Error:**
- This is automatically handled by the script with polling fallback
- If you see this warning, button polling is being used instead
- Buttons will still work, just with slightly higher CPU usage

**Buttons Not Working:**
- Check wiring connections
- Verify pin numbers in `settings.json` match your hardware
- Try alternative GPIO pins (2, 3, 4 work reliably)
- Ensure you're in the `gpio` group: `groups $USER`

**Permission Errors:**
- Run setup script with sudo: `sudo python3 setup.py --mode server`
- Or manually: `sudo usermod -a -G gpio $USER` then logout/login

**OSC Network Issues:**
- Check network connectivity between devices
- Verify firewall settings allow UDP traffic on port 8001
- Ensure IP addresses in `settings.json` are correct and reachable
- Test with: `ping target-ip-address`

**Service Won't Start:**
- Check service status: `sudo systemctl status rpi-director.service`
- View detailed logs: `sudo journalctl -u rpi-director.service -n 50`
- Verify virtual environment exists: `ls ~/rpi-director-venv/bin/python`
- Test manually first: `~/rpi-director-venv/bin/python ~/rpi-director/rpi_director.py --mode server`

**Python Package Installation Errors:**
- If `RPi.GPIO` compilation fails during setup, the script automatically tries system packages
- Missing `Python.h` error means development headers weren't installed
- The setup script automatically installs required packages: `python3-dev`, `build-essential`
- If issues persist, manually install: `sudo apt install python3-rpi.gpio python3-osc`

**GPIO Already In Use:**
- Stop other GPIO services: `sudo systemctl list-units | grep -i gpio`
- Kill processes using GPIO: `sudo fuser -k /dev/gpiomem`
- Reboot if necessary

### Debug Commands

```bash
# Test GPIO pin directly
sudo python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
print('Pin 2 value:', GPIO.input(2))
GPIO.cleanup()
"

# Test OSC client
sudo python3 -c "
from pythonosc import udp_client
client = udp_client.SimpleUDPClient('127.0.0.1', 8001)
client.send_message('/led/yellow', 1)
print('OSC message sent')
"

# Check virtual environment
~/rpi-director-venv/bin/python --version
~/rpi-director-venv/bin/pip list | grep -E "(osc|GPIO)"
```

## File Structure

```
rpi-director/
├── rpi_director.py              # Main Python script
├── settings.json               # Pin and network configuration
├── requirements.txt            # Python dependencies
├── setup.py                   # Automated setup script
├── gpio_test.py               # GPIO pin testing utility
├── rpi-director.service       # Systemd service file (server mode)
├── rpi-director-client.service # Systemd service file (client mode)
└── README.md                  # This file
```

## Development

### Testing GPIO Pins
Use the included test utility to verify GPIO pins work:
```bash
source ~/rpi-director-venv/bin/activate
sudo python gpio_test.py
```

This will test each configured pin individually and suggest alternatives if any fail.

### Logging
- **Service logs**: `sudo journalctl -u rpi-director.service -f`
- **Manual run**: Logs appear in console and `./rpi-director.log`
- **Systemd service**: Logs to systemd journal

### Virtual Environment
All Python dependencies are isolated in `~/rpi-director-venv/`:
```bash
# Activate environment
source ~/rpi-director-venv/bin/activate

# Install additional packages
pip install package-name

# Deactivate
deactivate
```
