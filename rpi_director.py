#!/usr/bin/env python3
"""
Raspberry Pi LED Director Script

This script can run in two modes:
- Server mode: Listens to button presses, controls local LEDs, and sends OSC commands to clients
- Client mode: Listens to OSC commands and controls local LEDs accordingly

The red LED is lit by default on startup in both modes.
"""

import json
import time
import signal
import sys
import logging
import argparse
import threading
from pathlib import Path

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("Error: RPi.GPIO not available. This script must be run on a Raspberry Pi.")
    print("Please ensure you are running this on a Raspberry Pi with RPi.GPIO installed.")
    sys.exit(1)

try:
    from pythonosc import udp_client, dispatcher
    from pythonosc.osc_server import ThreadingOSCUDPServer
except ImportError:
    print("python-osc not available. Install with: pip install python-osc")
    sys.exit(1)

# Configure logging with better error handling
log_file = './rpi-director.log'  # Default to local log file
try:
    # Try to write to system log directory (on Raspberry Pi with proper permissions)
    import os
    if os.path.exists('/var/log') and os.access('/var/log', os.W_OK):
        system_log_file = '/var/log/rpi-director.log'
        test_handler = logging.FileHandler(system_log_file)
        test_handler.close()
        log_file = system_log_file
except (PermissionError, FileNotFoundError):
    # Fall back to local log file for development/testing
    pass

try:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
except Exception as e:
    # If file logging fails, fall back to console only
    print(f"Warning: Could not setup file logging: {e}")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
logger = logging.getLogger(__name__)


class LEDDirectorBase:
    """Base class with common functionality for both server and client modes."""
    
    def __init__(self, settings_file='settings.json'):
        """Initialize the LED Director with settings from file."""
        self.settings_file = Path(settings_file)
        self._shutdown_requested = False
        self.load_settings()
        self.current_led = 'red'  # Default to red LED on startup
        self.setup_gpio()
        self.setup_signal_handlers()
        
    def load_settings(self):
        """Load pin configurations from settings file."""
        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
                self.button_pins = settings['buttons']
                self.led_pins = settings['leds']
                self.osc_settings = settings.get('osc', {})
                
                # Validate GPIO pin numbers
                all_pins = list(self.button_pins.values()) + list(self.led_pins.values())
                for pin in all_pins:
                    if not isinstance(pin, int) or pin < 0 or pin > 40:
                        raise ValueError(f"Invalid GPIO pin number: {pin}. Must be between 0-40.")
                
                logger.info(f"Settings loaded: {settings}")
        except FileNotFoundError:
            logger.error(f"Settings file {self.settings_file} not found!")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing settings file: {e}")
            sys.exit(1)
        except KeyError as e:
            logger.error(f"Missing key in settings file: {e}")
            sys.exit(1)
        except ValueError as e:
            logger.error(f"Invalid setting: {e}")
            sys.exit(1)
    
    def setup_gpio(self):
        """Setup GPIO pins for LEDs."""
        try:
            # Ensure clean GPIO state
            GPIO.setmode(GPIO.BCM)
            
            # Clean up any existing GPIO state for our pins
            all_pins = list(self.button_pins.values()) + list(self.led_pins.values())
            for pin in all_pins:
                try:
                    GPIO.cleanup(pin)
                except RuntimeWarning:
                    pass  # Pin wasn't set up, ignore warning
            
            # Setup LED pins as outputs
            for color, pin in self.led_pins.items():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)  # Start with all LEDs off
                logger.info(f"Setup LED {color} on GPIO pin {pin}")
            
            # Light up the red LED initially
            self.switch_led('red')
        except Exception as e:
            logger.error(f"Failed to setup GPIO: {e}")
            raise
    
    def switch_led(self, color):
        """Switch to the specified LED and turn off others."""
        if color not in self.led_pins:
            logger.error(f"Unknown LED color: {color}")
            return
        
        # Turn off current LED
        if self.current_led in self.led_pins:
            GPIO.output(self.led_pins[self.current_led], GPIO.LOW)
        
        # Turn on new LED
        GPIO.output(self.led_pins[color], GPIO.HIGH)
        self.current_led = color
        logger.info(f"Switched to {color} LED on GPIO pin {self.led_pins[color]}")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {sig}, shutting down gracefully...")
        # Set a flag to indicate shutdown was requested
        self._shutdown_requested = True
    
    def cleanup(self):
        """Cleanup GPIO resources."""
        logger.info("Cleaning up GPIO...")
        try:
            GPIO.cleanup()
        except Exception as e:
            logger.error(f"Error during GPIO cleanup: {e}")


class LEDDirectorServer(LEDDirectorBase):
    """Server mode: Listens to buttons and sends OSC commands to clients."""
    
    def __init__(self, settings_file='settings.json'):
        super().__init__(settings_file)
        self.setup_buttons()
        self.setup_osc_clients()
        
    def setup_buttons(self):
        """Setup button pins as inputs with event detection."""
        # Setup button pins as inputs with pull-up resistors
        for color, pin in self.button_pins.items():
            try:
                # Clean up any existing state for this pin
                try:
                    GPIO.cleanup(pin)
                except RuntimeWarning:
                    pass  # Pin wasn't set up, ignore warning
                
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                
                # Use a proper callback that captures the color correctly
                callback_func = self.create_button_callback(color)
                GPIO.add_event_detect(
                    pin, 
                    GPIO.FALLING, 
                    callback=callback_func,
                    bouncetime=200  # 200ms debounce
                )
                logger.info(f"Setup button {color} on GPIO pin {pin}")
            except RuntimeError as e:
                if "Failed to add edge detection" in str(e):
                    logger.error(f"GPIO pin {pin} conflict for button {color}")
                    logger.error("Possible causes:")
                    logger.error("  1. Pin already in use by another process")
                    logger.error("  2. Hardware issue with the pin")
                    logger.error("  3. Previous GPIO state not cleaned up")
                    logger.error(f"Try: sudo fuser -k /dev/gpiomem")
                else:
                    logger.error(f"Failed to setup button {color} on GPIO pin {pin}: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to setup button {color} on GPIO pin {pin}: {e}")
                raise
    
    def create_button_callback(self, color):
        """Create a proper callback function that captures the color correctly."""
        def callback(channel):
            self.button_callback(channel, color)
        return callback
    
    def setup_osc_clients(self):
        """Setup OSC clients for sending commands."""
        self.osc_clients = []
        client_addresses = self.osc_settings.get('client_addresses', [])
        
        for address in client_addresses:
            try:
                ip, port = address.split(':')
                client = udp_client.SimpleUDPClient(ip, int(port))
                self.osc_clients.append((client, address))
                logger.info(f"Setup OSC client for {address}")
            except ValueError as e:
                logger.error(f"Invalid client address format '{address}': {e}")
    
    def button_callback(self, channel, color):
        """Handle button press events."""
        logger.info(f"{color.capitalize()} button pressed on GPIO pin {channel}")
        self.switch_led(color)
        self.send_osc_command(color)
    
    def send_osc_command(self, color):
        """Send OSC command to all clients."""
        osc_address = f"/led/{color}"
        
        for client, address in self.osc_clients:
            try:
                client.send_message(osc_address, 1)  # Send value 1 to indicate LED on
                logger.info(f"Sent OSC command {osc_address} to {address}")
            except Exception as e:
                logger.error(f"Failed to send OSC command to {address}: {e}")
    
    def run(self):
        """Main loop to keep the server running."""
        logger.info("LED Director Server started. Press buttons or Ctrl+C to stop.")
        try:
            while not self._shutdown_requested:
                time.sleep(0.1)  # Small sleep to prevent high CPU usage
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.cleanup()


class LEDDirectorClient(LEDDirectorBase):
    """Client mode: Listens to OSC commands and controls LEDs."""
    
    def __init__(self, settings_file='settings.json'):
        super().__init__(settings_file)
        self.setup_osc_server()
        
    def setup_osc_server(self):
        """Setup OSC server for receiving commands."""
        try:
            self.dispatcher = dispatcher.Dispatcher()
            
            # Map OSC addresses to LED colors
            self.dispatcher.map("/led/red", self.osc_led_handler)
            self.dispatcher.map("/led/yellow", self.osc_led_handler)
            self.dispatcher.map("/led/green", self.osc_led_handler)
            
            # Get server port from settings
            server_port = self.osc_settings.get('server_port', 8000)
            
            # Validate port number
            if not isinstance(server_port, int) or server_port < 1024 or server_port > 65535:
                raise ValueError(f"Invalid server port: {server_port}. Must be between 1024-65535.")
            
            self.osc_server = ThreadingOSCUDPServer(("0.0.0.0", server_port), self.dispatcher)
            logger.info(f"Setup OSC server on port {server_port}")
            
            # Start OSC server in a separate thread
            self.server_thread = threading.Thread(target=self.osc_server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            logger.info("OSC server thread started")
            
        except Exception as e:
            logger.error(f"Failed to setup OSC server: {e}")
            raise
    
    def osc_led_handler(self, unused_addr, *args):
        """Handle incoming OSC LED commands."""
        # Extract color from the OSC address path
        color = unused_addr.split('/')[-1]  # Get the last part of the path (e.g., 'red' from '/led/red')
        logger.info(f"Received OSC command to switch to {color} LED")
        self.switch_led(color)
    
    def cleanup(self):
        """Cleanup resources including OSC server."""
        logger.info("Shutting down OSC server...")
        try:
            if hasattr(self, 'osc_server'):
                # Shutdown the server to stop accepting new requests
                self.osc_server.shutdown()
                # Close the server socket to free the port
                self.osc_server.server_close()
                # Wait for the server thread to finish (with timeout)
                if hasattr(self, 'server_thread') and self.server_thread.is_alive():
                    self.server_thread.join(timeout=5.0)
                    if self.server_thread.is_alive():
                        logger.warning("OSC server thread did not terminate within timeout")
        except Exception as e:
            logger.error(f"Error shutting down OSC server: {e}")
        super().cleanup()
    
    def run(self):
        """Main loop to keep the client running."""
        logger.info("LED Director Client started. Listening for OSC commands. Press Ctrl+C to stop.")
        try:
            while not self._shutdown_requested:
                time.sleep(0.1)  # Small sleep to prevent high CPU usage
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.cleanup()


def main():
    """Main function to start the LED Director in server or client mode."""
    # Check if running on Raspberry Pi and warn about permissions
    try:
        import RPi.GPIO as TestGPIO  # Test if we have real GPIO access
        # Check if we can access GPIO (requires root or gpio group membership)
        try:
            TestGPIO.setmode(TestGPIO.BCM)
            # Only cleanup if we actually set up something, ignore warning if nothing to clean up
            try:
                TestGPIO.cleanup()
            except RuntimeWarning:
                pass  # Ignore "nothing to clean up" warning
        except Exception as e:
            logger.warning("GPIO access may be restricted. You may need to:")
            logger.warning("  1. Run with sudo: sudo python3 rpi_director.py --mode server")
            logger.warning("  2. Or add user to gpio group: sudo usermod -a -G gpio $USER")
            logger.warning(f"  Error: {e}")
    except ImportError:
        pass  # Not on Raspberry Pi, script will exit at import check
    
    parser = argparse.ArgumentParser(description='Raspberry Pi LED Director')
    parser.add_argument('--mode', choices=['server', 'client'], required=True,
                       help='Run in server mode (listens to buttons) or client mode (listens to OSC)')
    parser.add_argument('--settings', default='settings.json',
                       help='Path to settings file (default: settings.json)')
    
    args = parser.parse_args()
    
    # Change to script directory to ensure relative paths work
    script_dir = Path(__file__).parent
    settings_path = script_dir / args.settings
    
    # Check if settings file exists
    if not settings_path.exists():
        print(f"Error: Settings file {settings_path} not found!")
        sys.exit(1)
    
    director = None
    exit_code = 0
    try:
        if args.mode == 'server':
            logger.info("Starting LED Director in SERVER mode")
            director = LEDDirectorServer(settings_path)
        else:
            logger.info("Starting LED Director in CLIENT mode")
            director = LEDDirectorClient(settings_path)
            
        director.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        exit_code = 1
    finally:
        if director:
            try:
                director.cleanup()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                exit_code = 1
        try:
            GPIO.cleanup()
        except Exception:
            pass  # GPIO might not be initialized
        sys.exit(exit_code)


if __name__ == '__main__':
    main()
