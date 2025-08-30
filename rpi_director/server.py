"""
LED Director Server implementation.
"""

import logging
import time

from .base import LEDDirectorBase
from .mqtt import create_timestamp

logger = logging.getLogger(__name__)


class LEDDirectorServer(LEDDirectorBase):
    """Server mode: monitors server buttons, controls server LEDs."""
    
    def __init__(self, settings_path="settings.json", client_id="server"):
        super().__init__(settings_path, mode="server", client_id=client_id)
        
        # Initialize server state
        self.current_mode = "idle"  # idle, red_active, green_active
        # Create client states dynamically from settings
        self.client_yellow_states = {client_id: False for client_id in self.settings.clients_list}
        # Flood protection: track last button press time per client
        self.client_last_press = {client_id: 0 for client_id in self.settings.clients_list}
        self.BUTTON_COOLDOWN = 0.3  # 300ms cooldown to prevent button chatter
        
        # Start with all LEDs off
        for color in self.settings.get_led_pins():
            self.set_led(color, False)
    
    def setup_mqtt_subscriptions(self):
        """Subscribe to client button presses."""
        # Subscribe to all client yellow button events
        self.mqtt.subscribe("led-director/client/+/event/buttons/yellow")
        logger.info("Subscribed to client button event topics")
    
    def handle_mqtt_message(self, topic, payload):
        """Handle MQTT messages from clients."""
        parts = topic.split('/')
        
        if len(parts) == 6 and parts[0] == "led-director" and parts[1] == "client":
            client_id = parts[2]
            message_type = parts[3]  # event
            device_type = parts[4]   # buttons
            action = parts[5]        # yellow
            
            if message_type == "event" and device_type == "buttons" and action == "yellow":
                if payload.get("pressed"):
                    self.handle_client_yellow_press(client_id)
    
    def handle_client_yellow_press(self, client_id):
        """Handle yellow button press from a client."""
        current_time = time.time()
        
        # Validate client_id
        if client_id not in self.client_yellow_states:
            logger.warning(f"Unknown client_id: {client_id}, ignoring button press")
            return
        
        # Flood protection: ignore rapid repeats
        last_press = self.client_last_press.get(client_id, 0)
        if current_time - last_press < self.BUTTON_COOLDOWN:
            logger.debug(f"Client {client_id} yellow button press ignored - cooldown active ({current_time - last_press:.3f}s < {self.BUTTON_COOLDOWN}s)")
            return
        
        self.client_last_press[client_id] = current_time
        logger.info(f"Client {client_id} yellow button pressed")
        
        if self.current_mode == "red_active":
            # Toggle client's yellow LED state on server
            current_state = self.client_yellow_states.get(client_id, False)
            new_state = not current_state
            self.client_yellow_states[client_id] = new_state
            
            # Update server's yellow LED for this client
            yellow_led_name = f"yellow_{client_id}"
            if yellow_led_name in self.settings.get_led_pins():
                self.set_led(yellow_led_name, new_state)
            else:
                logger.warning(f"No yellow LED configured for {client_id} (expected: {yellow_led_name})")
            
            # Send LED command to client (use /cmd topic)
            topic = f"led-director/client/{client_id}/cmd/leds/yellow"
            payload = {"state": new_state, "timestamp": create_timestamp()}
            self.mqtt.publish(topic, payload, retain=False, qos=1)  # Commands not retained
            
            logger.info(f"Set {client_id} yellow LED {'ON' if new_state else 'OFF'}")
        else:
            logger.info(f"Client {client_id} yellow button pressed but not in red_active mode (current: {self.current_mode})")
    
    def process_button_press(self, color):
        """Process server button presses."""
        if color == "red":
            # Enter red mode - clients can now press yellow buttons
            self.current_mode = "red_active"
            self.set_led("red", True)
            self.set_led("green", False)
            
            # Turn off all yellow LEDs
            for client_id in self.client_yellow_states:
                self.client_yellow_states[client_id] = False
                yellow_led_name = f"yellow_{client_id}"
                if yellow_led_name in self.settings.get_led_pins():
                    self.set_led(yellow_led_name, False)
            
            # Send red command to all clients (use /cmd topics)
            self.broadcast_to_clients("cmd/leds/red", {"state": True, "timestamp": create_timestamp()})
            self.broadcast_to_clients("cmd/leds/green", {"state": False, "timestamp": create_timestamp()})
            self.broadcast_to_clients("cmd/leds/yellow", {"state": False, "timestamp": create_timestamp()})
            
            logger.info("Entered RED mode - clients can now press yellow buttons")
        
        elif color == "green":
            # Enter green mode
            self.current_mode = "green_active"
            self.set_led("green", True)
            self.set_led("red", False)
            
            # Turn off all server yellow LEDs
            for client_id in self.client_yellow_states:
                self.client_yellow_states[client_id] = False
                yellow_led_name = f"yellow_{client_id}"
                if yellow_led_name in self.settings.get_led_pins():
                    self.set_led(yellow_led_name, False)
            
            # Send green command to all clients (use /cmd topics)
            self.broadcast_to_clients("cmd/leds/green", {"state": True, "timestamp": create_timestamp()})
            self.broadcast_to_clients("cmd/leds/red", {"state": False, "timestamp": create_timestamp()})
            self.broadcast_to_clients("cmd/leds/yellow", {"state": False, "timestamp": create_timestamp()})
            
            logger.info("Entered GREEN mode")
        
        elif color == "clear":
            # Clear all LEDs
            self.current_mode = "idle"
            
            # Turn off all server LEDs
            for led_color in self.settings.get_led_pins():
                self.set_led(led_color, False)
            
            # Reset client states
            for client_id in self.client_yellow_states:
                self.client_yellow_states[client_id] = False
            
            # Send clear command to all clients (use /cmd topics)
            self.broadcast_to_clients("cmd/leds/red", {"state": False, "timestamp": create_timestamp()})
            self.broadcast_to_clients("cmd/leds/green", {"state": False, "timestamp": create_timestamp()})
            self.broadcast_to_clients("cmd/leds/yellow", {"state": False, "timestamp": create_timestamp()})
            
            logger.info("CLEARED all LEDs")
    
    def broadcast_to_clients(self, subtopic, payload):
        """Broadcast message to all configured clients."""
        for client_id in self.settings.clients_list:
            topic = f"led-director/client/{client_id}/{subtopic}"
            self.mqtt.publish(topic, payload, retain=False, qos=1)  # Commands not retained
