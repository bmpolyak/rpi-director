"""
Configuration and settings management for LED Director.
"""

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class SettingsManager:
    """Manages loading and validation of LED Director configuration."""
    
    def __init__(self, settings_path="settings.json", mode="client"):
        self.settings_path = Path(settings_path)
        self.mode = mode
        
        # Configuration sections
        self.mqtt_settings = {}
        self.server_buttons = {}
        self.server_leds = {}
        self.client_buttons = {}
        self.client_leds = {}
        self.clients_list = ["client1", "client2", "client3"]  # Default
        
        self.load_settings()
        self.validate_settings()
    
    def load_settings(self):
        """Load configuration from JSON file."""
        try:
            with open(self.settings_path, 'r') as f:
                settings = json.load(f)
            
            # Validate required sections
            if 'mqtt' not in settings:
                raise KeyError("'mqtt' section required in settings")
            
            self.mqtt_settings = settings['mqtt']
            self.server_buttons = settings.get('server_buttons', {})
            self.server_leds = settings.get('server_leds', {})
            self.client_buttons = settings.get('client_buttons', {})
            self.client_leds = settings.get('client_leds', {})
            self.clients_list = settings.get('clients', self.clients_list)
            
            logger.info(f"Settings loaded from {self.settings_path}")
            logger.info(f"MQTT broker: {self.mqtt_settings['broker_host']}:{self.mqtt_settings['broker_port']}")
            
        except FileNotFoundError:
            logger.error(f"Settings file not found: {self.settings_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing settings file: {e}")
            sys.exit(1)
        except KeyError as e:
            logger.error(f"Missing key in settings file: {e}")
            sys.exit(1)
    
    def validate_settings(self):
        """Validate configuration based on mode."""
        # Enforce mode-specific settings requirements
        if self.mode == "server":
            if not self.server_buttons:
                raise KeyError("'server_buttons' section required when running in server mode")
            if not self.server_leds:
                raise KeyError("'server_leds' section required when running in server mode")
        else:  # client mode
            if not self.client_buttons:
                raise KeyError("'client_buttons' section required when running in client mode")
            if not self.client_leds:
                raise KeyError("'client_leds' section required when running in client mode")
        
        # Validate GPIO pin numbers
        self._validate_gpio_pins()
    
    def _validate_gpio_pins(self):
        """Validate GPIO pin numbers for the active mode."""
        if self.mode == "server":
            active_pins = list(self.server_buttons.values()) + list(self.server_leds.values())
        else:
            active_pins = list(self.client_buttons.values()) + list(self.client_leds.values())
        
        # Valid BCM GPIO pins on most Raspberry Pi models
        common_gpio_pins = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]
        extended_gpio_pins = common_gpio_pins + [28, 29, 30, 31]  # Some Pi models have these
        
        for pin in active_pins:
            if not isinstance(pin, int):
                raise ValueError(f"GPIO pin must be an integer: {pin}")
            elif pin not in extended_gpio_pins:
                # Warn about unusual pins but don't fail (user might know better)
                logger.warning(f"Unusual GPIO pin {pin} - valid range is typically 2-27 (some models support 28-31)")
            elif pin not in common_gpio_pins:
                logger.info(f"Using extended GPIO pin {pin} - ensure your Pi model supports it")
    
    def get_button_pins(self):
        """Get button pins for current mode."""
        return self.server_buttons if self.mode == "server" else self.client_buttons
    
    def get_led_pins(self):
        """Get LED pins for current mode."""
        return self.server_leds if self.mode == "server" else self.client_leds
