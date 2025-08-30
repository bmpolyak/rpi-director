"""
LED Director Server implementation.
"""

import logging
import threading
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
        
        # Client presence tracking
        self.connected_clients = {}  # client_id -> last_seen_timestamp
        self.CLIENT_TIMEOUT = 12.0   # Consider client offline after 30 seconds
        
        # Status indication threads
        self.mqtt_status_thread = None
        self.mqtt_status_running = False
        self.client_status_thread = None
        self.client_status_running = False
        
        # Start with all LEDs off
        for color in self.settings.get_led_pins():
            self.set_led(color, False)
    
    def setup_mqtt_subscriptions(self):
        """Subscribe to client button presses and heartbeat messages."""
        # Subscribe to all client yellow button events
        self.mqtt.subscribe("led-director/client/+/event/buttons/yellow")
        # Subscribe to client heartbeat/presence messages
        self.mqtt.subscribe("led-director/client/+/heartbeat")
        logger.info("Subscribed to client button event and heartbeat topics")
    
    def handle_mqtt_message(self, topic, payload):
        """Handle MQTT messages from clients."""
        parts = topic.split('/')
        
        if len(parts) >= 3 and parts[0] == "led-director" and parts[1] == "client":
            client_id = parts[2]
            
            # Handle heartbeat messages
            if len(parts) == 4 and parts[3] == "heartbeat":
                self.handle_client_heartbeat(client_id, payload)
                return
            
            # Handle button events
            if len(parts) == 6:
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
    
    def handle_client_heartbeat(self, client_id, payload):
        """Handle heartbeat messages from clients."""
        current_time = time.time()
        
        # Update last seen time
        was_connected = self.is_client_connected(client_id)
        self.connected_clients[client_id] = current_time
        
        # Log new connections
        if not was_connected:
            logger.info(f"Client {client_id} came online")
            
        logger.debug(f"Heartbeat from {client_id}")
    
    def is_client_connected(self, client_id):
        """Check if a client is currently connected (based on recent heartbeat)."""
        if client_id not in self.connected_clients:
            return False
        
        current_time = time.time()
        last_seen = self.connected_clients[client_id]
        return (current_time - last_seen) <= self.CLIENT_TIMEOUT
    
    def get_connected_clients(self):
        """Get list of currently connected client IDs."""
        return [client_id for client_id in self.settings.clients_list 
                if self.is_client_connected(client_id)]
    
    def get_client_connection_info(self):
        """Get detailed connection information for all clients."""
        current_time = time.time()
        info = {}
        
        for client_id in self.settings.clients_list:
            if client_id in self.connected_clients:
                last_seen = self.connected_clients[client_id]
                seconds_ago = current_time - last_seen
                is_connected = seconds_ago <= self.CLIENT_TIMEOUT
                
                info[client_id] = {
                    "connected": is_connected,
                    "last_seen": last_seen,
                    "seconds_ago": seconds_ago
                }
            else:
                info[client_id] = {
                    "connected": False,
                    "last_seen": None,
                    "seconds_ago": None
                }
        
        return info
    
    def log_client_status(self):
        """Log the current status of all clients."""
        connection_info = self.get_client_connection_info()
        connected = []
        disconnected = []
        
        for client_id, info in connection_info.items():
            if info["connected"]:
                connected.append(f"{client_id} ({info['seconds_ago']:.1f}s ago)")
            else:
                disconnected.append(client_id)
        
        logger.info(f"Connected clients ({len(connected)}): {', '.join(connected) if connected else 'none'}")
        if disconnected:
            logger.info(f"Disconnected clients ({len(disconnected)}): {', '.join(disconnected)}")
    
    def cleanup_old_clients(self):
        """Remove old client entries from connected_clients dict."""
        current_time = time.time()
        to_remove = []
        
        for client_id, last_seen in self.connected_clients.items():
            if (current_time - last_seen) > (self.CLIENT_TIMEOUT * 2):  # Keep for 2x timeout
                to_remove.append(client_id)
        
        for client_id in to_remove:
            logger.debug(f"Cleaning up old client entry: {client_id}")
            del self.connected_clients[client_id]
    
    def start_status_monitoring(self):
        """Start status monitoring threads for visual feedback."""
        # Start MQTT connection status monitoring
        if not self.mqtt_status_running:
            self.mqtt_status_running = True
            self.mqtt_status_thread = threading.Thread(target=self._mqtt_status_worker, daemon=True)
            self.mqtt_status_thread.start()
            logger.info("Started MQTT status monitoring thread")
        
        # Start client heartbeat status monitoring
        if not self.client_status_running:
            self.client_status_running = True
            self.client_status_thread = threading.Thread(target=self._client_status_worker, daemon=True)
            self.client_status_thread.start()
            logger.info("Started client status monitoring thread")
    
    def stop_status_monitoring(self):
        """Stop status monitoring threads."""
        if self.mqtt_status_running:
            self.mqtt_status_running = False
            if self.mqtt_status_thread:
                self.mqtt_status_thread.join(timeout=2.0)
            logger.info("Stopped MQTT status monitoring thread")
        
        if self.client_status_running:
            self.client_status_running = False
            if self.client_status_thread:
                self.client_status_thread.join(timeout=2.0)
            logger.info("Stopped client status monitoring thread")
    
    def _mqtt_status_worker(self):
        """Monitor MQTT connection and flash red LED if disconnected."""
        while self.mqtt_status_running:
            try:
                if not self.mqtt.is_connected():
                    # Flash red LED to indicate MQTT disconnection
                    if "red" in self.settings.get_led_pins():
                        # Quick flash: on for 0.2s, off for 2.8s (total 3s cycle)
                        self.gpio.set_led("red", True)
                        time.sleep(0.2)
                        if self.mqtt_status_running:  # Check if we should still be running
                            self.gpio.set_led("red", False)
                            time.sleep(2.8)
                    else:
                        time.sleep(3.0)
                else:
                    # MQTT is connected, wait before next check
                    time.sleep(3.0)
                    
            except Exception as e:
                logger.error(f"Error in MQTT status worker: {e}")
                time.sleep(3.0)
        
        logger.debug("MQTT status worker thread exiting")
    
    def _client_status_worker(self):
        """Monitor client heartbeats and flash yellow LED if any client is disconnected."""
        while self.client_status_running:
            try:
                # Check if any expected clients are disconnected
                disconnected_clients = []
                for client_id in self.settings.clients_list:
                    if not self.is_client_connected(client_id):
                        disconnected_clients.append(client_id)
                
                if disconnected_clients:
                    # Flash yellow LED to indicate missing clients
                    # Use the first yellow LED we can find (could be yellow or yellow_client1, etc.)
                    yellow_led = None
                    for led_name in self.settings.get_led_pins():
                        if led_name.startswith("yellow"):
                            yellow_led = led_name
                            break
                    
                    if yellow_led:
                        # Quick flash: on for 0.2s, off for 2.8s (total 3s cycle)
                        self.gpio.set_led(yellow_led, True)
                        time.sleep(0.2)
                        if self.client_status_running:  # Check if we should still be running
                            self.gpio.set_led(yellow_led, False)
                            time.sleep(2.8)
                    else:
                        time.sleep(3.0)
                else:
                    # All clients connected, wait before next check
                    time.sleep(3.0)
                    
            except Exception as e:
                logger.error(f"Error in client status worker: {e}")
                time.sleep(3.0)
        
        logger.debug("Client status worker thread exiting")
    
    def shutdown(self):
        """Shutdown the server gracefully."""
        logger.info("Shutting down server...")
        self.stop_status_monitoring()
        super().shutdown()
    
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
