"""
GPIO management for LED Director - buttons and LEDs.
"""

import logging
import threading
import time

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    # Mock GPIO for development/testing
    HAS_GPIO = False
    class MockGPIO:
        BCM = "BCM"
        IN = "IN"
        OUT = "OUT"
        HIGH = 1
        LOW = 0
        PUD_UP = "PUD_UP"
        FALLING = "FALLING"
        
        @staticmethod
        def setmode(mode): pass
        @staticmethod
        def setwarnings(enabled): pass
        @staticmethod
        def setup(pin, mode, **kwargs): pass
        @staticmethod
        def input(pin): return 1
        @staticmethod
        def output(pin, value): pass
        @staticmethod
        def add_event_detect(pin, edge, **kwargs): 
            raise Exception("Mock GPIO: Edge detection not available")
        @staticmethod
        def remove_event_detect(pin): pass
        @staticmethod
        def cleanup(*args): pass
    
    GPIO = MockGPIO()

logger = logging.getLogger(__name__)


class GPIOManager:
    """Manages GPIO operations for buttons and LEDs with thread safety."""
    
    def __init__(self, button_pins, led_pins, use_edge_detection=True):
        """Initialize GPIO handler."""
        if not HAS_GPIO:
            use_edge_detection = False  # Force polling mode for mock
            
        self.button_pins = button_pins
        self.led_pins = led_pins
        self.use_edge_detection = use_edge_detection and HAS_GPIO
        self.edge_pins = set()  # Track which pins successfully use edge detection
        
        # State tracking
        self.button_states = {}
        self.led_states = {}
        self.last_button_press = {}  # For debouncing
        self.button_press_callback = None
        self.gpio_lock = threading.Lock()  # Thread safety for state access
        
        # Setup GPIO
        self.setup_gpio()
    
    def setup_gpio(self):
        """Setup GPIO pins for buttons and LEDs."""
        try:
            # Suppress GPIO warnings for cleaner output
            GPIO.setwarnings(False)
            
            # Clean up any existing GPIO state first (critical for edge detection)
            try:
                GPIO.cleanup()
            except Exception as e:
                logger.debug(f"GPIO cleanup during init: {e}")
            
            # Ensure clean GPIO state
            GPIO.setmode(GPIO.BCM)
            
            # Log hardware summary
            logger.info("=== Hardware Configuration Summary ===")
            logger.info(f"Button pins: {self.button_pins}")
            logger.info(f"LED pins: {self.led_pins}")
            logger.info(f"Edge detection enabled: {self.use_edge_detection}")
            logger.info(f"GPIO available: {HAS_GPIO}")
            logger.info(f"RPi.GPIO module: {GPIO}")
            if not HAS_GPIO:
                logger.warning("Running in MOCK GPIO mode - no actual hardware control")
            
            # Check for pin conflicts
            all_pins = list(self.button_pins.values()) + list(self.led_pins.values())
            used_pins = set()
            for pin in all_pins:
                if pin in used_pins:
                    raise ValueError(f"Pin {pin} is used multiple times in configuration")
                used_pins.add(pin)
            
            logger.info(f"Total pins in use: {len(all_pins)} (buttons: {len(self.button_pins)}, LEDs: {len(self.led_pins)})")
            logger.info("Pin assignments validated - no conflicts detected")
            
            # Setup button pins
            self._setup_button_pins()
            
            # Setup LED pins
            self._setup_led_pins()
            
            # Log setup summary
            logger.info("=== GPIO Setup Complete ===")
            logger.info(f"Edge detection pins: {len(self.edge_pins)}/{len(self.button_pins)} buttons")
            if self.edge_pins:
                edge_colors = [color for color, pin in self.button_pins.items() if pin in self.edge_pins]
                logger.info(f"Edge detection active for: {edge_colors}")
            
            poll_pins = {color: pin for color, pin in self.button_pins.items() if pin not in self.edge_pins}
            if poll_pins:
                logger.info(f"Polling required for: {list(poll_pins.keys())}")
            else:
                logger.info("All buttons using edge detection (optimal)")
                
        except Exception as e:
            logger.error(f"Failed to setup GPIO: {e}")
            raise
    
    def _setup_button_pins(self):
        """Setup button pins as inputs with pull-up resistors.
        
        ASSUMPTION: Buttons are wired active-low (normally HIGH, LOW when pressed).
        - Pull-up enabled: pin reads HIGH when button not pressed
        - Button press connects pin to ground: pin reads LOW when pressed  
        - Edge detection triggers on FALLING edge (HIGH -> LOW)
        """
        logger.info("Setting up buttons with active-low assumption (HIGH=not pressed, LOW=pressed)")
        
        for color, pin in self.button_pins.items():
            # Clean up any existing state for this pin (critical for edge detection)
            logger.debug(f"Cleaning up GPIO pin {pin} ({color}) before setup")
            try:
                GPIO.remove_event_detect(pin)
                logger.debug(f"Removed existing event detection for pin {pin}")
            except RuntimeError:
                logger.debug(f"No existing event detection for pin {pin}")
                pass  # No event detection was active
            except Exception as e:
                logger.debug(f"Warning during pin {pin} event cleanup: {e}")
            
            try:
                GPIO.cleanup(pin)
                logger.debug(f"Cleaned up pin {pin}")
            except RuntimeWarning:
                logger.debug(f"Normal cleanup warning for pin {pin}")
                pass  # Normal cleanup warning, not an error
            except Exception as e:
                logger.debug(f"Warning during pin {pin} cleanup: {e}")
            
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.button_states[color] = GPIO.HIGH  # Not pressed initially (active low)
            self.last_button_press[color] = 0  # For debouncing
            
            # Try to set up edge detection with debounce for this specific pin
            if self.use_edge_detection:
                try:
                    GPIO.add_event_detect(pin, GPIO.FALLING, 
                                        callback=lambda channel, color=color: self._button_callback(color),
                                        bouncetime=200)  # Increased debounce for better reliability
                    self.edge_pins.add(pin)
                    logger.info(f"Setup button {color} on GPIO pin {pin} with edge detection")
                except Exception as e:
                    logger.warning(f"Edge detection failed for pin {pin} ({color}): {type(e).__name__}: {e}, will use polling for this pin")
                    # Don't disable global edge detection, just exclude this pin
                    try:
                        GPIO.remove_event_detect(pin)
                    except:
                        pass
                    
            if pin not in self.edge_pins:
                logger.info(f"Setup button {color} on GPIO pin {pin} with polling fallback")
    
    def _setup_led_pins(self):
        """Setup LED pins as outputs."""
        for color, pin in self.led_pins.items():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)  # Start with all LEDs off
            self.led_states[color] = False
            logger.info(f"Setup LED {color} on GPIO pin {pin}")
    
    def set_led(self, color, state):
        """Set LED state with thread safety and state caching."""
        with self.gpio_lock:  # Thread-safe GPIO and state access
            if color in self.led_pins:
                # Short-circuit if LED is already in the requested state
                current_state = self.led_states.get(color, None)
                if current_state == state:
                    logger.debug(f"LED {color} already {'ON' if state else 'OFF'}, skipping")
                    return False  # No change made
                
                pin = self.led_pins[color]
                try:
                    GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
                    self.led_states[color] = state
                    logger.info(f"Set LED {color} {'ON' if state else 'OFF'}")
                    return True  # Change made
                except Exception as e:
                    logger.error(f"Failed to set LED {color} on pin {pin}: {e}")
                    return False
            else:
                logger.warning(f"LED color '{color}' not found in configuration")
                return False
    
    def get_led_state(self, color):
        """Get current LED state."""
        with self.gpio_lock:
            return self.led_states.get(color, False)
    
    def _button_callback(self, color):
        """Edge detection callback for button presses with software debounce."""
        current_time = time.time()
        
        with self.gpio_lock:  # Thread-safe access to button state
            last_press = self.last_button_press.get(color, 0)
            
            # Software debounce: ignore presses within 200ms of last press (matches hardware debounce)
            if current_time - last_press < 0.2:
                logger.debug(f"Button {color} debounced (too soon after last press)")
                return
                
            self.last_button_press[color] = current_time
        
        logger.info(f"Button {color} pressed (edge detection)")
        # Trigger callback if set
        if hasattr(self, 'button_press_callback'):
            self.button_press_callback(color)
    
    def set_button_callback(self, callback):
        """Set callback function for button presses."""
        self.button_press_callback = callback
    
    def monitor_buttons_polling(self, shutdown_flag):
        """Monitor button presses using polling for pins without edge detection."""
        non_edge_pins = {color: pin for color, pin in self.button_pins.items() 
                        if pin not in self.edge_pins}
        
        if not non_edge_pins:
            logger.info("All buttons using edge detection, no polling needed")
            # Still run the loop but just wait for shutdown
            while not shutdown_flag.is_set():
                shutdown_flag.wait(1.0)  # Check every second
            return
            
        logger.info(f"Polling {len(non_edge_pins)} buttons without edge detection: {list(non_edge_pins.keys())}")
        
        while not shutdown_flag.is_set():
            try:
                current_time = time.time()
                for color, pin in non_edge_pins.items():
                    with self.gpio_lock:  # Thread-safe access to GPIO and state
                        current_state = GPIO.input(pin)
                        previous_state = self.button_states[color]
                        
                        # Button pressed (falling edge: HIGH -> LOW) with debounce
                        if (previous_state == GPIO.HIGH and current_state == GPIO.LOW):
                            last_press = self.last_button_press.get(color, 0)
                            if current_time - last_press >= 0.2:  # 200ms debounce (matches edge detection)
                                self.last_button_press[color] = current_time
                                # Don't hold the lock during button processing
                                should_process = True
                            else:
                                should_process = False
                                logger.debug(f"Button {color} debounced (polling)")
                        else:
                            should_process = False
                        
                        self.button_states[color] = current_state
                    
                    # Process button outside the lock to avoid holding it too long
                    if should_process:
                        logger.info(f"Button {color} pressed (polling)")
                        if hasattr(self, 'button_press_callback'):
                            self.button_press_callback(color)
                
                time.sleep(0.02)  # Poll every 20ms for better responsiveness while still being efficient
                
            except Exception as e:
                logger.error(f"Error monitoring buttons: {e}")
                time.sleep(1)
    
    def cleanup(self):
        """Clean up GPIO resources."""
        try:
            GPIO.cleanup()
        except:
            pass
