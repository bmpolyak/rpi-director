"""
LED Director Client implementation.
"""

import logging

from .base import LEDDirectorBase

logger = logging.getLogger(__name__)


class LEDDirectorClient(LEDDirectorBase):
    """Client mode: monitors client buttons, controls client LEDs."""
    
    def __init__(self, settings_path="settings.json", client_id="client1"):
        super().__init__(settings_path, mode="client", client_id=client_id)
        
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
