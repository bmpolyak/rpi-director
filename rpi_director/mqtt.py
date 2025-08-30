"""
MQTT communication manager for LED Director.
"""

import json
import logging
import threading
from datetime import datetime, timezone

try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
    # Mock MQTT for development/testing
    class MockMQTTClient:
        MQTT_ERR_SUCCESS = 0
        def __init__(self, *args, **kwargs): pass
        def connect_async(self, *args, **kwargs): pass
        def loop_start(self): pass
        def loop_stop(self): pass
        def disconnect(self): pass
        def subscribe(self, topic): pass
        def publish(self, topic, message, qos=0, retain=False):
            class Result:
                rc = 0
                def wait_for_publish(self, timeout=1.0): pass
            return Result()
        def is_connected(self): return True
        def reconnect_delay_set(self, **kwargs): pass
        def reconnect(self): pass
    
    class MockMQTT:
        CallbackAPIVersion = type('', (), {'VERSION1': 1})()
        Client = MockMQTTClient
        MQTT_ERR_SUCCESS = 0
    
    mqtt = MockMQTT()

logger = logging.getLogger(__name__)


class MQTTManager:
    """Manages MQTT connections and messaging for LED Director."""
    
    def __init__(self, mqtt_settings, client_id, mode):
        if not HAS_MQTT:
            logger.warning("paho-mqtt not available - using mock MQTT (development mode)")
            
        self.mqtt_settings = mqtt_settings
        self.client_id = client_id
        self.mode = mode
        
        # Connection state
        self.mqtt_client = None
        self.mqtt_connected = False
        self.mqtt_connected_event = threading.Event()  # Better than busy-wait
        
        # Callbacks
        self.message_callback = None
        
        self.setup_mqtt()
    
    def setup_mqtt(self):
        """Setup MQTT client and connect to broker."""
        try:
            # Create MQTT client with v1 API compatibility
            try:
                # Try v2 API first (paho-mqtt >= 2.0)
                self.mqtt_client = mqtt.Client(
                    client_id=self.client_id,
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION1
                )
            except AttributeError:
                # Fall back to v1 API (paho-mqtt < 2.0)
                self.mqtt_client = mqtt.Client(client_id=self.client_id)
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.on_message = self._on_message
            
            # Configure authentication if provided
            username = self.mqtt_settings.get('username')
            password = self.mqtt_settings.get('password')
            if username:
                logger.info(f"Using MQTT authentication for user: {username}")
                self.mqtt_client.username_pw_set(username, password)
            else:
                logger.info("Using anonymous MQTT connection (no authentication)")
            
            # Connect to broker
            broker_host = self.mqtt_settings['broker_host']
            broker_port = self.mqtt_settings['broker_port']
            keepalive = self.mqtt_settings.get('keepalive', 60)
            
            # Set up automatic reconnection
            self.mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)
            
            logger.info(f"Connecting to MQTT broker at {broker_host}:{broker_port}")
            # Use async connect for better reconnection handling
            self.mqtt_client.connect_async(broker_host, broker_port, keepalive)
            
            # Start MQTT loop in separate thread
            self.mqtt_client.loop_start()
            
        except Exception as e:
            logger.error(f"Failed to setup MQTT: {e}")
            raise
    
    def _on_connect(self, client, userdata, flags, rc):
        """Called when MQTT client connects to broker."""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            self.mqtt_connected = True
            self.mqtt_connected_event.set()  # Signal connection established
            
            # Trigger connection callback if set
            if hasattr(self, 'connect_callback'):
                self.connect_callback()
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")
            self.mqtt_connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        """Called when MQTT client disconnects from broker."""
        logger.warning(f"Disconnected from MQTT broker: {rc}")
        self.mqtt_connected = False
        
        # Let paho's automatic reconnect handle it (we use loop_start() and reconnect_delay_set())
        # Only attempt manual reconnect for unexpected disconnections and if not already connected
        if rc != mqtt.MQTT_ERR_SUCCESS and not self.mqtt_client.is_connected():
            logger.info("Attempting to reconnect to MQTT broker...")
            try:
                client.reconnect()
            except Exception as e:
                logger.warning(f"Manual reconnect failed: {e}, relying on automatic reconnect")
    
    def _on_message(self, client, userdata, msg):
        """Called when MQTT message is received."""
        try:
            topic = msg.topic
            payload_str = msg.payload.decode('utf-8')
            
            # Handle empty payloads
            if not payload_str.strip():
                logger.warning(f"Received empty MQTT message on topic: {topic}")
                return
                
            payload = json.loads(payload_str)
            logger.info(f"Received MQTT message: {topic} = {payload}")
            
            # Trigger message callback if set
            if self.message_callback:
                self.message_callback(topic, payload)
                
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding MQTT message JSON: {e}, payload: {msg.payload}")
        except UnicodeDecodeError as e:
            logger.error(f"Error decoding MQTT message payload: {e}")
        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}")
    
    def set_message_callback(self, callback):
        """Set callback function for received messages."""
        self.message_callback = callback
    
    def set_connect_callback(self, callback):
        """Set callback function for connection events."""
        self.connect_callback = callback
    
    def subscribe(self, topic, qos=1):
        """Subscribe to MQTT topic with specified QoS (default QoS 1 for reliability)."""
        if self.mqtt_client:
            self.mqtt_client.subscribe(topic, qos=qos)
            logger.info(f"Subscribed to topic: {topic} (QoS {qos})")
    
    def publish(self, topic, payload, retain=True, qos=0):
        """Publish MQTT message with better error handling."""
        if self.mqtt_connected and self.mqtt_client.is_connected():
            try:
                message = json.dumps(payload)
                result = self.mqtt_client.publish(topic, message, qos=qos, retain=retain)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    logger.error(f"Failed to publish MQTT message: {result.rc}")
                else:
                    logger.debug(f"Published MQTT message: {topic} = {payload} (QoS={qos}, retain={retain})")
                    
                # Wait for publish to complete (optional)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    result.wait_for_publish(timeout=1.0)
                    
            except Exception as e:
                logger.error(f"Error publishing MQTT message: {e}")
        else:
            logger.warning(f"Cannot publish MQTT message: not connected (connected={self.mqtt_connected})")
            # Try to reconnect if we think we should be connected
            if self.mqtt_connected and not self.mqtt_client.is_connected():
                logger.warning("MQTT client disconnected unexpectedly, attempting reconnect...")
                try:
                    self.mqtt_client.reconnect()
                except Exception as e:
                    logger.error(f"Failed to reconnect MQTT client: {e}")
                    self.mqtt_connected = False
    
    def wait_for_connection(self, timeout=10):
        """Wait for MQTT connection with timeout."""
        return self.mqtt_connected_event.wait(timeout=timeout)
    
    def is_connected(self):
        """Check if MQTT client is connected."""
        return self.mqtt_connected and self.mqtt_client.is_connected()
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()


def create_timestamp():
    """Create UTC timestamp for MQTT messages."""
    return datetime.now(timezone.utc).isoformat()
