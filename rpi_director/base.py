"""
Base class for LED Director with common functionality.
"""

import logging
import threading
import time
import signal
import sys

from .config import SettingsManager
from .gpio import GPIOManager
from .mqtt import MQTTManager, create_timestamp

logger = logging.getLogger(__name__)

# Global shutdown flag
shutdown_flag = threading.Event()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    shutdown_flag.set()


# Setup signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class LEDDirectorBase:
    """Base class for LED Director with MQTT communication."""
    
    def __init__(self, settings_path="settings.json", mode="client", client_id=None):
        self.mode = mode
        self.client_id = client_id or f"led_director_{mode}"
        
        # Load configuration
        self.settings = SettingsManager(settings_path, mode)
        
        # Setup GPIO
        self.gpio = GPIOManager(
            self.settings.get_button_pins(),
            self.settings.get_led_pins(),
            use_edge_detection=True
        )
        
        # Setup MQTT
        self.mqtt = MQTTManager(
            self.settings.mqtt_settings,
            self.client_id,
            self.mode
        )
        
        # Set up callbacks
        self.gpio.set_button_callback(self.handle_button_press)
        self.mqtt.set_message_callback(self.handle_mqtt_message)
        self.mqtt.set_connect_callback(self.on_mqtt_connected)
        
        # Button monitoring thread
        self.button_thread = None
        
    def on_mqtt_connected(self):
        """Called when MQTT connection is established."""
        self.setup_mqtt_subscriptions()
        # Republish current LED states to ensure retained topics are seeded
        self.republish_led_states()
    
    def republish_led_states(self):
        """Republish current LED states after MQTT connection to seed retained topics."""
        logger.info("Republishing LED states to seed retained topics")
        for color in self.settings.get_led_pins().keys():
            state = self.gpio.get_led_state(color)
            self._publish_led_state(color, state)
    
    def _publish_led_state(self, color, state):
        """Publish LED state to appropriate MQTT topic."""
        if self.mode == "server":
            if color.startswith("yellow_"):
                client_id = color.replace("yellow_", "")
                topic = f"led-director/server/state/leds/yellow/{client_id}"
            else:
                topic = f"led-director/server/state/leds/{color}"
        else:
            topic = f"led-director/client/{self.client_id}/state/leds/{color}"
        
        payload = {"state": state, "timestamp": create_timestamp()}
        self.mqtt.publish(topic, payload, retain=True, qos=1)
    
    def set_led(self, color, state, publish_state=True):
        """Set LED state and optionally publish state to MQTT."""
        changed = self.gpio.set_led(color, state)
        
        # Only publish if state actually changed and publishing is requested
        if changed and publish_state:
            self._publish_led_state(color, state)
    
    def handle_button_press(self, color):
        """Handle button press event."""
        # Publish button press to MQTT as event (not retained, QoS 1 for reliability)
        if self.mode == "server":
            topic = f"led-director/server/event/buttons/{color}"
        else:
            topic = f"led-director/client/{self.client_id}/event/buttons/{color}"
        
        payload = {"pressed": True, "timestamp": create_timestamp()}
        self.mqtt.publish(topic, payload, retain=False, qos=1)
        
        # Handle button logic (overridden in subclasses)
        self.process_button_press(color)
    
    def setup_mqtt_subscriptions(self):
        """Setup MQTT subscriptions based on mode."""
        # This will be overridden in subclasses
        pass
    
    def handle_mqtt_message(self, topic, payload):
        """Handle received MQTT messages."""
        # This will be overridden in subclasses
        pass
    
    def process_button_press(self, color):
        """Process button press logic (to be overridden)."""
        pass
    
    def cleanup(self):
        """Clean up GPIO and MQTT connections."""
        logger.info("Cleaning up...")
        
        # Signal shutdown to all threads
        shutdown_flag.set()
        
        # Wait for button monitoring thread to finish gracefully
        if self.button_thread and self.button_thread.is_alive():
            logger.info("Waiting for button monitoring thread to finish...")
            self.button_thread.join(timeout=2.0)
            if self.button_thread.is_alive():
                logger.warning("Button monitoring thread did not finish within timeout")
        
        # Cleanup MQTT and GPIO
        self.mqtt.disconnect()
        self.gpio.cleanup()
        
        logger.info("Cleanup complete")
    
    def run(self):
        """Main run loop."""
        logger.info(f"Starting LED Director in {self.mode} mode")
        
        # Log configuration summary  
        logger.info("=== Configuration Summary ===")
        logger.info(f"Client ID: {self.client_id}")
        logger.info(f"MQTT Broker: {self.settings.mqtt_host}:{self.settings.mqtt_port}")
        logger.info(f"Clients configured: {self.settings.clients_list}")
        logger.info(f"Button pins: {self.settings.get_button_pins()}")
        logger.info(f"LED pins: {self.settings.get_led_pins()}")
        logger.info("===============================")
        
        # Wait for MQTT connection using Event (more efficient than busy-wait)
        logger.info("Waiting for MQTT connection...")
        if not self.mqtt.wait_for_connection(timeout=10):
            logger.error("Failed to connect to MQTT broker within 10 seconds")
            return
        
        # Verify we can actually communicate
        if not self.mqtt.is_connected():
            logger.error("MQTT client reports not connected despite connection callback")
            return
        
        logger.info("MQTT connected, starting button monitoring")
        
        # Start button monitoring thread
        if self.gpio.edge_pins:
            logger.info(f"Using GPIO edge detection for {len(self.gpio.edge_pins)} pins (CPU efficient)")
        
        # Always start polling thread for hybrid or full polling mode
        self.button_thread = threading.Thread(
            target=self.gpio.monitor_buttons_polling, 
            args=(shutdown_flag,), 
            daemon=True
        )
        self.button_thread.start()
        
        # Main loop
        try:
            while not shutdown_flag.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self.cleanup()
