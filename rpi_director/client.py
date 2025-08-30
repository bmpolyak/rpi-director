"""
LED Director Client implementation.
"""

import logging
import threading
import time

from .base import LEDDirectorBase
from .mqtt import create_timestamp

logger = logging.getLogger(__name__)


class LEDDirectorClient(LEDDirectorBase):
    """Client mode: monitors client buttons, controls client LEDs."""
    
    def __init__(self, settings_path="settings.json", client_id="client1"):
        super().__init__(settings_path, mode="client", client_id=client_id)
        
        # Heartbeat settings
        self.heartbeat_interval = 3.0  # Send heartbeat every 3 seconds
        self.heartbeat_thread = None
        self.heartbeat_running = False
        
        # MQTT status monitoring
        self.mqtt_status_thread = None
        self.mqtt_status_running = False
        
        # Start with all LEDs off
        for color in self.settings.get_led_pins():
            self.set_led(color, False)
    
    def setup_mqtt_subscriptions(self):
        """Subscribe to server commands and LED control messages."""
        # Subscribe to LED command topics for this client (cmd topics, not state topics to avoid loops)
        self.mqtt.subscribe(f"led-director/client/{self.client_id}/cmd/leds/+")
        logger.info(f"Subscribed to LED command topics for {self.client_id}")
    
    def handle_mqtt_message(self, topic, payload):
        """Handle MQTT messages from server."""
        parts = topic.split('/')
        
        if (len(parts) == 6 and parts[0] == "led-director" and 
            parts[1] == "client" and parts[2] == self.client_id):
            
            message_type = parts[3]  # cmd
            device_type = parts[4]   # leds
            color = parts[5]         # red/green/yellow
            
            if message_type == "cmd" and device_type == "leds":
                # LED control command - apply without publishing (to avoid loop)
                state = payload.get("state", False)
                self.set_led(color, state, publish_state=False)
                logger.info(f"Applied LED command: {color} = {state}")
    
    def process_button_press(self, color):
        """Process client button presses."""
        if color == "yellow":
            # Yellow button pressed - server will handle the logic
            logger.info("Yellow button pressed - sent to server")
    
    def start_heartbeat(self):
        """Start the heartbeat thread."""
        if not self.heartbeat_running:
            self.heartbeat_running = True
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
            self.heartbeat_thread.start()
            logger.info(f"Started heartbeat thread (interval: {self.heartbeat_interval}s)")
    
    def stop_heartbeat(self):
        """Stop the heartbeat thread."""
        if self.heartbeat_running:
            self.heartbeat_running = False
            if self.heartbeat_thread:
                self.heartbeat_thread.join(timeout=2.0)
            logger.info("Stopped heartbeat thread")
    
    def _heartbeat_worker(self):
        """Heartbeat worker thread that sends periodic heartbeat messages."""
        while self.heartbeat_running:
            try:
                if self.mqtt and self.mqtt.is_connected():
                    heartbeat_payload = {
                        "timestamp": create_timestamp(),
                        "client_id": self.client_id,
                        "status": "alive"
                    }
                    topic = f"led-director/client/{self.client_id}/heartbeat"
                    self.mqtt.publish(topic, heartbeat_payload, retain=False, qos=1)
                    logger.debug(f"Sent heartbeat")
                else:
                    logger.debug("Skipping heartbeat - MQTT not connected")
                    
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
            
            # Wait for next heartbeat interval
            time.sleep(self.heartbeat_interval)
        
        logger.debug("Heartbeat worker thread exiting")
    
    def start_mqtt_status_monitoring(self):
        """Start MQTT connection status monitoring."""
        if not self.mqtt_status_running:
            self.mqtt_status_running = True
            self.mqtt_status_thread = threading.Thread(target=self._mqtt_status_worker, daemon=True)
            self.mqtt_status_thread.start()
            logger.info("Started MQTT status monitoring thread")
    
    def stop_mqtt_status_monitoring(self):
        """Stop MQTT connection status monitoring."""
        if self.mqtt_status_running:
            self.mqtt_status_running = False
            if self.mqtt_status_thread:
                self.mqtt_status_thread.join(timeout=2.0)
            logger.info("Stopped MQTT status monitoring thread")
    
    def _mqtt_status_worker(self):
        """Monitor MQTT connection and flash yellow LED if disconnected."""
        while self.mqtt_status_running:
            try:
                if not self.mqtt.is_connected():
                    # Flash yellow LED to indicate MQTT disconnection
                    if "yellow" in self.settings.get_led_pins():
                        # Quick flash: on for 0.2s, off for 2.8s (total 3s cycle)
                        self.gpio.set_led("yellow", True)
                        time.sleep(0.2)
                        if self.mqtt_status_running:  # Check if we should still be running
                            self.gpio.set_led("yellow", False)
                            time.sleep(2.8)
                    else:
                        time.sleep(3.0)
                else:
                    # MQTT is connected - yellow LED state should be controlled by server commands
                    # Don't interfere with LED state here, just wait
                    time.sleep(3.0)
                    
            except Exception as e:
                logger.error(f"Error in MQTT status worker: {e}")
                time.sleep(3.0)
        
        logger.debug("MQTT status worker thread exiting")
    
    def shutdown(self):
        """Shutdown the client gracefully."""
        logger.info("Shutting down client...")
        self.stop_heartbeat()
        self.stop_mqtt_status_monitoring()
        super().shutdown()
