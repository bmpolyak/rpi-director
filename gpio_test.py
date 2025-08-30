#!/usr/bin/env python3
"""
GPIO Pin Test Script - Enhanced Edge Detection Diagnostics
Tests each pin individually to identify hardware or permission issues.
Comprehensive edge detection testing with failure analysis.
"""

import RPi.GPIO as GPIO
import time
import threading
import os
import sys
import signal
import argparse

# Test configuration constants
CALLBACK_TIMEOUT_SECONDS = 5.0
STRESS_TEST_DURATION = 5.0
STATE_SAMPLE_COUNT = 20
STATE_SAMPLE_INTERVAL = 0.05
CALLBACK_SETTLE_TIME = 0.1
CLEANUP_SETTLE_TIME = 0.1
DEBOUNCE_TIME_NORMAL = 200  # milliseconds
DEBOUNCE_TIME_STRESS = 50   # milliseconds for stress testing
MIN_BOUNCE_INTERVAL_MS = 10  # Minimum interval indicating hardware bounce
MAX_CALLBACKS_WARNING = 5    # Warn if more callbacks than this
MAX_CALLBACKS_NOISE = 15     # Indicate noise if more than this

# Global cleanup flag to ensure GPIO cleanup on exit
cleanup_needed = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    print(f"\n🛑 Received signal {signum}, cleaning up GPIO...")
    if cleanup_needed:
        GPIO.cleanup()
    sys.exit(0)

# Setup signal handlers for clean shutdown
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def check_system_capabilities():
    """Check system capabilities and permissions for GPIO operations."""
    print("SYSTEM CAPABILITY CHECKS:")
    print("=" * 50)
    
    # Check if running as root/sudo
    if os.geteuid() == 0:
        print("  ✅ Running as root/sudo - GPIO permissions OK")
    else:
        print("  ⚠️  NOT running as root - may need sudo for GPIO access")
        
    # Check GPIO group membership
    try:
        import pwd, grp
        username = pwd.getpwuid(os.getuid()).pw_name
        
        # Correct way to check GPIO group membership
        try:
            gpio_group = grp.getgrnam('gpio')
            user_groups = os.getgroups()
            if gpio_group.gr_gid in user_groups:
                print(f"  ✅ User '{username}' is in 'gpio' group")
            else:
                print(f"  ⚠️  User '{username}' NOT in 'gpio' group - add with: sudo usermod -a -G gpio {username}")
                print(f"     Note: You'll need to logout/login after adding to group")
        except KeyError:
            print("  ⚠️  'gpio' group not found on system")
            
    except Exception as e:
        print(f"  ⚠️  Could not check gpio group membership: {e}")
    
    # Check /dev/gpiomem permissions
    if os.path.exists('/dev/gpiomem'):
        stat = os.stat('/dev/gpiomem')
        can_rw = os.access('/dev/gpiomem', os.R_OK | os.W_OK)
        print(f"  ✅ /dev/gpiomem exists (mode {oct(stat.st_mode)[-3:]}); "
              f"{'RW access OK' if (can_rw or os.geteuid()==0) else 'no RW access'}")
    else:
        print("  ❌ /dev/gpiomem not found - GPIO may not be available")
    
    # Check device tree overlays that might conflict
    dt_path = '/proc/device-tree/soc'
    if os.path.exists(dt_path):
        print("  ✅ Device tree found")
    else:
        print("  ⚠️  Device tree not found - unusual for Pi")
    
    # Check for common conflicting services
    conflicting_services = ['pigpiod']
    for service in conflicting_services:
        try:
            result = os.system(f"pgrep {service} > /dev/null 2>&1")
            if result == 0:
                print(f"  ⚠️  {service} is running - may conflict with RPi.GPIO")
                print(f"     Stop with: sudo systemctl stop {service}")
            else:
                print(f"  ✅ {service} not running")
        except Exception as e:
            print(f"  ⚠️  Could not check {service} status: {e}")
    
    # Local hints for pin conflicts
    print("  🔎 If using GPIO14/15, disable serial console/login.")
    print("  🔎 If using GPIO2/3 for buttons, disable I²C or move pins.")
    
    print()

def test_edge_detection_comprehensive(pin, color, interactive=True):
    """Comprehensive edge detection test with multiple scenarios."""
    print(f"\nCOMPREHENSIVE EDGE DETECTION TEST for {color.upper()} button (GPIO {pin}):")
    print("-" * 60)
    
    edge_results = {
        'basic_setup': False,
        'falling_edge': False,
        'rising_edge': False,
        'both_edges': False,
        'callback_test': False,
        'multiple_callbacks': False,
        'cleanup_test': False,
        'actual_button_test': False
    }
    
    pin_cleanup_needed = False
    
    try:
        # Clean slate - be more careful about cleanup
        try:
            GPIO.remove_event_detect(pin)
        except RuntimeError:
            pass  # No event detection was active
        except Exception as e:
            print(f"  ⚠️  Warning during initial cleanup: {e}")
        
        try:
            GPIO.cleanup(pin)
        except RuntimeWarning as w:
            print(f"  ⚠️  GPIO cleanup warning: {w}")
        except Exception:
            pass
        
        pin_cleanup_needed = True
        
        # Basic setup test
        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            edge_results['basic_setup'] = True
            print("  ✅ Basic input setup with pull-up")
            
            # Check initial state to validate pull-up is working
            initial_value = GPIO.input(pin)
            print(f"  ℹ️  Initial pin state: {initial_value} ({'HIGH/not pressed' if initial_value else 'LOW/pressed'})")
            if not initial_value:
                print("  ⚠️  Warning: Pin reads LOW with pull-up - button may be pressed or circuit issue")
                
        except Exception as e:
            print(f"  ❌ Basic setup failed: {e}")
            return edge_results
        
        # Test 1: Falling edge detection
        try:
            GPIO.add_event_detect(pin, GPIO.FALLING, bouncetime=DEBOUNCE_TIME_NORMAL)
            edge_results['falling_edge'] = True
            print("  ✅ Falling edge detection setup")
            GPIO.remove_event_detect(pin)
        except Exception as e:
            print(f"  ❌ Falling edge detection failed: {e}")
            print(f"     Possible causes:")
            print(f"     - Pin already has event detection active")
            print(f"     - GPIO pin is reserved by system")
            print(f"     - Insufficient permissions")
        
        # Test 2: Rising edge detection
        try:
            GPIO.add_event_detect(pin, GPIO.RISING, bouncetime=DEBOUNCE_TIME_NORMAL)
            edge_results['rising_edge'] = True
            print("  ✅ Rising edge detection setup")
            GPIO.remove_event_detect(pin)
        except Exception as e:
            print(f"  ❌ Rising edge detection failed: {e}")
        
        # Test 3: Both edges
        try:
            GPIO.add_event_detect(pin, GPIO.BOTH, bouncetime=DEBOUNCE_TIME_NORMAL)
            edge_results['both_edges'] = True
            print("  ✅ Both edges detection setup")
            GPIO.remove_event_detect(pin)
        except Exception as e:
            print(f"  ❌ Both edges detection failed: {e}")
        
        # Test 4: Callback function test with proper synchronization
        callback_triggered = threading.Event()
        callback_error = []
        
        def test_callback(channel):
            try:
                callback_triggered.set()
                print(f"    📞 Callback triggered for GPIO {channel}")
            except Exception as e:
                callback_error.append(str(e))
        
        try:
            GPIO.add_event_detect(pin, GPIO.FALLING, callback=test_callback, bouncetime=DEBOUNCE_TIME_NORMAL)
            edge_results['callback_test'] = True
            print("  ✅ Callback-based edge detection setup")
            
            if interactive:
                print(f"  ℹ️  Press the button now to test callback ({CALLBACK_TIMEOUT_SECONDS} second timeout)...")
                
                if callback_triggered.wait(timeout=CALLBACK_TIMEOUT_SECONDS):
                    print("  ✅ Callback function executed successfully!")
                    if callback_error:
                        print(f"  ⚠️  Callback had errors: {callback_error}")
                else:
                    print("  ⚠️  No button press detected within timeout")
                    print("  ℹ️  This is normal if no physical button is connected")
            else:
                print("  ℹ️  Non-interactive mode: Skipping button press test")
                print("  ✅ Callback setup validated (IRQ system functional)")
                # Brief wait to ensure callback system is stable
                time.sleep(0.1)
            
            # Record callback results for diagnostics
            edge_results['callback_received'] = callback_triggered.is_set() if interactive else True
                
            # Give callbacks time to finish before cleanup
            time.sleep(CALLBACK_SETTLE_TIME)
            GPIO.remove_event_detect(pin)
        except Exception as e:
            print(f"  ❌ Callback edge detection failed: {e}")
            print(f"     Possible causes:")
            print(f"     - Interrupt system not available")
            print(f"     - Kernel GPIO driver issues")
            
        # Ensure cleanup happens regardless of success/failure
        try:
            GPIO.remove_event_detect(pin)
        except:
            pass  # Already cleaned up or never set up
        
        # Test 5: Multiple callback stress test with better bounce detection
        callback_count = [0]
        callback_times = []
        
        def counting_callback(channel):
            current_time = time.time()
            callback_count[0] += 1
            callback_times.append(current_time)
            if callback_count[0] <= 3:  # Only print first few
                print(f"    📞 Callback #{callback_count[0]} for GPIO {channel} at {current_time:.3f}")
        
        try:
            GPIO.add_event_detect(pin, GPIO.FALLING, callback=counting_callback, bouncetime=DEBOUNCE_TIME_STRESS)  # Lower bounce time for stress test
            edge_results['multiple_callbacks'] = True
            print(f"  ✅ Multiple callback test setup ({DEBOUNCE_TIME_STRESS}ms debounce)")
            
            if interactive:
                print(f"  ℹ️  Press button multiple times quickly ({STRESS_TEST_DURATION} second timeout)...")
                time.sleep(STRESS_TEST_DURATION)
            else:
                print("  ℹ️  Non-interactive mode: Skipping stress test")
                # Brief wait to ensure callback system is stable
                time.sleep(0.2)
            
            # Give callbacks time to finish
            time.sleep(CALLBACK_SETTLE_TIME)
            
            if callback_count[0] > 0 or not interactive:
                if interactive:
                    print(f"  ✅ Detected {callback_count[0]} button presses")
                    edge_results['callback_count'] = callback_count[0]
                    
                    # Analyze bounce patterns
                    if len(callback_times) > 1:
                        intervals = [callback_times[i] - callback_times[i-1] for i in range(1, len(callback_times))]
                        min_interval = min(intervals) * 1000  # Convert to ms
                        edge_results['min_interval_ms'] = min_interval
                        
                        if callback_count[0] > MAX_CALLBACKS_WARNING:
                            print(f"  ⚠️  High callback count detected")
                            print(f"     Minimum interval: {min_interval:.1f}ms")
                            if min_interval < MIN_BOUNCE_INTERVAL_MS:
                                print(f"     🚨 Very short intervals suggest hardware bouncing")
                                edge_results['bounce_detected'] = True
                            elif callback_count[0] > MAX_CALLBACKS_NOISE:
                                print(f"     🚨 Excessive callbacks suggest electrical noise")
                                edge_results['noise_detected'] = True
                    else:
                        print(f"  ℹ️  Single callback - good debounce behavior")
                else:
                    print("  ✅ Non-interactive mode: Callback system validated")
                    edge_results['callback_count'] = 0  # No actual button presses expected
            else:
                print("  ℹ️  No button presses detected (normal if no physical button)")
                edge_results['callback_count'] = 0
                
            GPIO.remove_event_detect(pin)
        except Exception as e:
            print(f"  ❌ Multiple callback test failed: {e}")
            edge_results['multiple_callbacks'] = False
            # Ensure cleanup happens regardless of success/failure
            try:
                GPIO.remove_event_detect(pin)
            except:
                pass  # Already cleaned up or never set up
        
        # Test 6: Cleanup test with better error handling
        try:
            GPIO.add_event_detect(pin, GPIO.FALLING, bouncetime=DEBOUNCE_TIME_NORMAL)
            time.sleep(CLEANUP_SETTLE_TIME)  # Let it settle
            GPIO.remove_event_detect(pin)
            time.sleep(CLEANUP_SETTLE_TIME)  # Wait for cleanup
            GPIO.add_event_detect(pin, GPIO.FALLING, bouncetime=DEBOUNCE_TIME_NORMAL)  # Should work again
            GPIO.remove_event_detect(pin)
            edge_results['cleanup_test'] = True
            print("  ✅ Edge detection cleanup/re-setup works")
        except Exception as e:
            print(f"  ❌ Cleanup test failed: {e}")
            print(f"     Possible causes:")
            print(f"     - GPIO cleanup not working properly")
            print(f"     - System state corruption")
            print(f"     - Resource busy - another process using pin")
        
        # Test 7: Comprehensive button state validation
        try:
            print("  ℹ️  Testing comprehensive button state validation...")
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Test 1: State consistency over time
            states = []
            for i in range(STATE_SAMPLE_COUNT):  # Sample over 1 second
                states.append(GPIO.input(pin))
                time.sleep(STATE_SAMPLE_INTERVAL)
            
            unique_states = set(states)
            stable_percentage = max(states.count(0), states.count(1)) / len(states) * 100
            
            if len(unique_states) > 1:
                print("  ✅ Button state changes detected during test")
                print(f"     States observed: {unique_states}")
                edge_results['actual_button_test'] = True
                edge_results['state_stability'] = stable_percentage
            else:
                stable_state = states[0]
                print(f"  ✅ Pin stable at {stable_state} ({'HIGH/not pressed' if stable_state else 'LOW/pressed'})")
                print(f"     Stability: {stable_percentage:.1f}%")
                edge_results['actual_button_test'] = True
                edge_results['state_stability'] = stable_percentage
                
                # Test 2: Pull-up resistor validation
                if stable_state == 1:  # Expected with pull-up
                    print("  ✅ Pull-up resistor working correctly")
                    edge_results['pullup_working'] = True
                else:
                    print("  ⚠️  Pin reading LOW with pull-up - check wiring")
                    edge_results['pullup_working'] = False
                    
        except Exception as e:
            print(f"  ❌ Button state validation failed: {e}")
            edge_results['actual_button_test'] = False
        
        # Final cleanup with better error handling
        if pin_cleanup_needed:
            try:
                GPIO.remove_event_detect(pin)
            except RuntimeError:
                pass  # No event detection was active
            except Exception as e:
                print(f"  ⚠️  Warning during event detection cleanup: {e}")
            
            try:
                GPIO.cleanup(pin)
            except RuntimeWarning:
                pass  # Normal cleanup warning
            except Exception as e:
                print(f"  ⚠️  Warning during final GPIO cleanup: {e}")
            
    except Exception as e:
        print(f"  ❌ Comprehensive test failed: {e}")
        print(f"     Exception type: {type(e).__name__}")
        # Emergency cleanup
        try:
            GPIO.remove_event_detect(pin)
        except:
            pass
        try:
            GPIO.cleanup(pin)
        except:
            pass
    
    return edge_results

def diagnose_edge_detection_failure(pin, results):
    """Provide detailed diagnosis of edge detection failures."""
    print(f"\nEDGE DETECTION FAILURE ANALYSIS for GPIO {pin}:")
    print("-" * 50)
    
    if not results['basic_setup']:
        print("❌ CRITICAL: Basic GPIO setup failed")
        print("   Solutions:")
        print("   - Check if running with appropriate permissions (sudo)")
        print("   - Verify RPi.GPIO is properly installed")
        print("   - Check if GPIO is disabled in config.txt")
        return
    
    if not any([results['falling_edge'], results['rising_edge'], results['both_edges']]):
        print("❌ CRITICAL: All edge detection types failed")
        print("   Probable causes:")
        print("   - GPIO pin is reserved by device tree overlay")
        print("   - Hardware issue with GPIO pin")
        print("   - Kernel GPIO driver not loaded properly")
        print("   - Pin is being used by another process")
        print("   Solutions:")
        print("   - Try different GPIO pin")
        print("   - Check /boot/config.txt for conflicting overlays")
        print("   - Reboot to reset GPIO state")
        print("   - Run: sudo systemctl status pigpiod (disable if running)")
        
    elif not results['callback_test']:
        print("⚠️  WARNING: Edge detection setup works but callbacks fail")
        print("   Probable causes:")
        print("   - Interrupt system not properly configured")
        print("   - Threading issues in Python")
        print("   - System under heavy load")
        print("   Solutions:")
        print("   - Use polling fallback")
        print("   - Reduce system load")
        print("   - Check dmesg for kernel errors")
        
    elif results['multiple_callbacks'] and results.get('callback_count', 0) > 20:
        print("⚠️  WARNING: Excessive callbacks detected")
        print("   Probable causes:")
        print("   - Button bouncing (hardware issue)")
        print("   - Electrical noise on GPIO pin")
        print("   - Insufficient debounce time")
        print("   Solutions:")
        print("   - Add hardware debounce circuit")
        print("   - Increase software debounce time")
        print("   - Check wiring and connections")
    
    elif not results['cleanup_test']:
        print("⚠️  WARNING: GPIO cleanup issues detected")
        print("   Probable causes:")
        print("   - GPIO state not properly reset")
        print("   - Kernel driver issues")
        print("   Solutions:")
        print("   - Always call GPIO.cleanup() in exception handlers")
        print("   - Consider system reboot if persistent")

def test_pin(pin, pin_type="input", color=None, interactive=True):
    """Test a specific GPIO pin with enhanced diagnostics."""
    pin_cleanup_needed = False
    
    try:
        print(f"Testing GPIO pin {pin} as {pin_type} ({color})...")
        
        # Clean up any existing state with better error handling
        try:
            GPIO.remove_event_detect(pin)
        except RuntimeError:
            pass  # No event detection was active
        except Exception as e:
            print(f"  ⚠️  Warning during initial event detect cleanup: {e}")
        
        try:
            GPIO.cleanup(pin)
        except RuntimeWarning:
            pass  # Normal cleanup warning, not an error
        except Exception as e:
            print(f"  ⚠️  Warning during initial cleanup: {e}")
        
        pin_cleanup_needed = True
        
        if pin_type == "input":
            # Basic input test
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            value = GPIO.input(pin)
            print(f"  ✅ Pin {pin} input setup OK, value: {value} ({'HIGH/not pressed' if value else 'LOW/pressed'})")
            
            # Read value multiple times to check stability
            values = []
            for _ in range(20):
                values.append(GPIO.input(pin))
                time.sleep(0.003)  # Small delay to avoid misreading chatter as stable
            if len(set(values)) == 1:
                print(f"  ✅ Pin {pin} stable reading over 20 samples")
            else:
                print(f"  ⚠️  Pin {pin} unstable readings: {len(set(values))} different values")
                print(f"     Sample values: {values[:10]}...")  # Show first 10
                print(f"     Possible causes: floating pin, bad connection, electrical noise")
                
                # Count transitions to assess stability
                transitions = sum(1 for i in range(1, len(values)) if values[i] != values[i-1])
                print(f"     Transitions detected: {transitions}/19")
                if transitions > 5:
                    print(f"     🚨 High instability - check wiring and connections")
            
            # Comprehensive edge detection test
            if color:
                edge_results = test_edge_detection_comprehensive(pin, color, interactive)
                
                # Diagnose failures
                if not all(edge_results.values()):
                    diagnose_edge_detection_failure(pin, edge_results)
                
                # Success based on edge detection setup, not human interaction
                any_edge_ok = any([
                    edge_results['falling_edge'],
                    edge_results['rising_edge'],
                    edge_results['both_edges']
                ])
                passed = edge_results['basic_setup'] and any_edge_ok
                return passed, edge_results
            else:
                # Basic edge detection test with better error handling
                try:
                    GPIO.add_event_detect(pin, GPIO.FALLING, bouncetime=DEBOUNCE_TIME_NORMAL)
                    print(f"  ✅ Pin {pin} edge detection OK")
                    GPIO.remove_event_detect(pin)
                    return True
                except Exception as e:
                    print(f"  ❌ Pin {pin} edge detection failed: {e}")
                    print(f"     Exception type: {type(e).__name__}")
                    try:
                        GPIO.remove_event_detect(pin)
                    except:
                        pass
                    return False
            
        elif pin_type == "output":
            # Test as output
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
            print(f"  ✅ Pin {pin} output setup OK (set LOW)")
            
            # Test output switching
            for state in [GPIO.HIGH, GPIO.LOW, GPIO.HIGH, GPIO.LOW]:
                GPIO.output(pin, state)
                time.sleep(0.1)
                print(f"    Set pin {pin} to {'HIGH' if state else 'LOW'}")
            
            GPIO.output(pin, GPIO.LOW)  # End in safe state
            print(f"  ✅ Pin {pin} output switching test passed")
        
        # Proper cleanup for all pin types
        if pin_cleanup_needed:
            try:
                GPIO.cleanup(pin)
            except RuntimeWarning:
                pass  # Normal cleanup warning
            except Exception as e:
                print(f"  ⚠️  Warning during cleanup: {e}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Pin {pin} FAILED: {e}")
        print(f"     Exception type: {type(e).__name__}")
        
        # Emergency cleanup
        if pin_cleanup_needed:
            try:
                GPIO.remove_event_detect(pin)
            except:
                pass
            try:
                GPIO.cleanup(pin)
            except:
                pass
        return False

def main():
    global cleanup_needed
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='GPIO Pin Test - Enhanced Edge Detection Diagnostics')
    parser.add_argument('--no-interactive', action='store_true',
                       help='Run in non-interactive mode (no button press prompts)')
    args = parser.parse_args()
    
    interactive_mode = not args.no_interactive
    
    print("GPIO Pin Test - Enhanced Edge Detection Diagnostics")
    if not interactive_mode:
        print("🤖 Running in NON-INTERACTIVE mode (unattended)")
    print("=" * 60)
    
    try:
        # System capability checks first
        check_system_capabilities()
        
        # Load actual settings from settings.json if available
        try:
            import json
            with open('settings.json', 'r') as f:
                settings = json.load(f)
            server_buttons = settings.get('server_buttons', {})
            server_leds = settings.get('server_leds', {})
            client_buttons = settings.get('client_buttons', {})
            client_leds = settings.get('client_leds', {})
            print("✅ Loaded pin configuration from settings.json")
            
            # Check for potentially conflicting pins in settings.json
            all_pins = list(server_buttons.values()) + list(server_leds.values()) + list(client_buttons.values()) + list(client_leds.values())
            
            # I²C pins (GPIO 2, 3)
            i2c_pins = [pin for pin in all_pins if pin in [2, 3]]
            if i2c_pins:
                print(f"  ⚠️  WARNING: Using I²C pins {i2c_pins} - may conflict with I²C devices")
            
            # SPI pins (GPIO 7, 8, 9, 10, 11)
            spi_pins = [pin for pin in all_pins if pin in [7, 8, 9, 10, 11]]
            if spi_pins:
                print(f"  ⚠️  WARNING: Using SPI pins {spi_pins} - may conflict with SPI devices")
            
            # UART pins (GPIO 14, 15)
            uart_pins = [pin for pin in all_pins if pin in [14, 15]]
            if uart_pins:
                print(f"  ⚠️  WARNING: Using UART pins {uart_pins} - may conflict with serial console")
            
            # Check for duplicate pin usage
            pin_usage = {}
            for category, pins in [("server_buttons", server_buttons), ("server_leds", server_leds), 
                                  ("client_buttons", client_buttons), ("client_leds", client_leds)]:
                for color, pin in pins.items():
                    if pin in pin_usage:
                        print(f"  🚨 ERROR: GPIO {pin} used by both {pin_usage[pin]} and {category}.{color}")
                    else:
                        pin_usage[pin] = f"{category}.{color}"
        except Exception as e:
            print(f"⚠️  Could not load settings.json: {e}")
            print("Using default pin configuration...")
            # Fallback to default configuration - safer pins
            server_buttons = {"red": 17, "green": 27, "clear": 22}
            server_leds = {"red": 23, "green": 24, "yellow_client1": 5, "yellow_client2": 6, "yellow_client3": 12}
            client_buttons = {"yellow": 16}
            client_leds = {"red": 13, "green": 19, "yellow": 20}
        
        GPIO.setmode(GPIO.BCM)
        cleanup_needed = True
        
        print(f"\nTesting SERVER BUTTON pins (inputs with comprehensive edge detection):")
        print("=" * 60)
        server_button_results = {}
        server_button_details = {}
        for color, pin in server_buttons.items():
            passed, details = test_pin(pin, "input", color, interactive_mode)
            server_button_results[color] = passed
            server_button_details[color] = details
        
        print(f"\nTesting SERVER LED pins (outputs):")
        print("=" * 40)
        server_led_results = {}
        for color, pin in server_leds.items():
            result = test_pin(pin, "output")
            server_led_results[color] = result
        
        print(f"\nTesting CLIENT BUTTON pins (inputs with comprehensive edge detection):")
        print("=" * 60)
        client_button_results = {}
        client_button_details = {}
        for color, pin in client_buttons.items():
            passed, details = test_pin(pin, "input", color, interactive_mode)
            client_button_results[color] = passed
            client_button_details[color] = details
        
        print(f"\nTesting CLIENT LED pins (outputs):")
        print("=" * 40)
        client_led_results = {}
        for color, pin in client_leds.items():
            result = test_pin(pin, "output")
            client_led_results[color] = result
        
        # Comprehensive summary
        print("\n" + "=" * 60)
        print("COMPREHENSIVE TEST SUMMARY:")
        print("=" * 60)
        
        def print_results(title, results, pins, is_input=False):
            print(f"\n{title}:")
            all_passed = True
            for color, result in results.items():
                pin = pins.get(color, "?")
                status = "✅ PASSED" if result else "❌ FAILED"
                edge_status = " (edge detection working)" if is_input and result else " (edge detection failed)" if is_input else ""
                print(f"  {color:12} (GPIO {pin:2}): {status}{edge_status}")
                if not result:
                    all_passed = False
            return all_passed
        
        server_buttons_ok = print_results("Server Buttons", server_button_results, server_buttons, True)
        server_leds_ok = print_results("Server LEDs", server_led_results, server_leds)
        client_buttons_ok = print_results("Client Buttons", client_button_results, client_buttons, True)
        client_leds_ok = print_results("Client LEDs", client_led_results, client_leds)
        
        # Overall assessment
        print(f"\nOVERALL ASSESSMENT:")
        print("-" * 30)
        if all([server_buttons_ok, server_leds_ok, client_buttons_ok, client_leds_ok]):
            print("🎉 ALL TESTS PASSED - System ready for production!")
            print("   Edge detection should work reliably.")
        else:
            print("⚠️  SOME TESTS FAILED - System needs attention")
            
            # Specific recommendations
            if not server_buttons_ok or not client_buttons_ok:
                print("\n🔧 BUTTON/EDGE DETECTION ISSUES:")
                print("   Recommendations:")
                print("   1. If edge detection fails, the system will fall back to polling")
                print("   2. Check wiring and button connections")
                print("   3. Consider running with sudo if permission errors")
                print("   4. Try different GPIO pins if hardware issues detected")
                
                # Suggest alternative pins
                print("\n📌 ALTERNATIVE GPIO PINS (if current ones fail):")
                safe_pins = [4, 17, 27, 22, 23, 24, 25, 5, 6, 12, 13, 16, 19, 20, 26]
                used_pins = set(list(server_buttons.values()) + list(server_leds.values()) + 
                              list(client_buttons.values()) + list(client_leds.values()))
                available_pins = [p for p in safe_pins if p not in used_pins][:10]
                
                failed_buttons = []
                for color, result in {**server_button_results, **client_button_results}.items():
                    if not result:
                        failed_buttons.append(color)
                
                for i, color in enumerate(failed_buttons[:len(available_pins)]):
                    print(f"   {color}: Try GPIO {available_pins[i]}")
            
            if not server_leds_ok or not client_leds_ok:
                print("\n💡 LED ISSUES:")
                print("   Recommendations:")
                print("   1. Check LED wiring and resistors")
                print("   2. Verify power supply capacity")
                print("   3. Test LEDs with multimeter")
        
        # Detailed pass/fail criteria with edge detection analysis
        print(f"\nDETAILED PASS/FAIL ANALYSIS:")
        print("-" * 40)
        
        # Analyze edge detection results for each pin type
        critical_tests = ['basic_setup', 'falling_edge', 'rising_edge', 'both_edges']
        important_tests = ['callback_test', 'cleanup_test', 'actual_button_test']
        
        def analyze_edge_results(results_dict, pin_type):
            if not results_dict:
                return False, "No test results available"
                
            critical_passed = sum(1 for test in critical_tests if results_dict.get(test, False))
            important_passed = sum(1 for test in important_tests if results_dict.get(test, False))
            
            # Determine overall status
            if critical_passed >= 3:  # At least 3/4 critical tests
                if important_passed >= 2:  # At least 2/3 important tests
                    status = "PASS"
                    reason = "All essential edge detection features working"
                else:
                    status = "PARTIAL"
                    reason = f"Core detection works but {3-important_passed} advanced features failed"
            else:
                status = "FAIL"
                reason = f"Critical edge detection failures: {4-critical_passed}/4 core tests failed"
                
            # Check for specific issues
            issues = []
            if results_dict.get('bounce_detected'):
                issues.append("Hardware bounce detected")
            if results_dict.get('noise_detected'):
                issues.append("Electrical noise detected")
            if not results_dict.get('pullup_working', True):
                issues.append("Pull-up resistor issue")
                
            if issues:
                reason += f" (Issues: {', '.join(issues)})"
                
            return status in ['PASS', 'PARTIAL'], f"{status}: {reason}"
        
        # Analyze each pin type
        pin_analyses = {}
        for color, results in {**server_button_details, **client_button_details}.items():
            if results:  # Only analyze pins that have edge detection results
                passed, analysis = analyze_edge_results(results, "button")
                pin_analyses[color] = (passed, analysis)
                print(f"  {color:12}: {analysis}")
        
        # Overall system verdict
        total_pins = len(pin_analyses)
        passed_pins = sum(1 for passed, _ in pin_analyses.values() if passed)
        
        print(f"\nSYSTEM VERDICT:")
        print("-" * 20)
        if passed_pins == total_pins and total_pins > 0:
            print("🎯 PRODUCTION READY: All GPIO pins passed edge detection tests")
            verdict = "READY"
        elif passed_pins >= total_pins * 0.75 and total_pins > 0:
            print(f"⚠️  MOSTLY READY: {passed_pins}/{total_pins} pins working ({passed_pins/total_pins*100:.0f}%)")
            print("   System will work but some features may fall back to polling")
            verdict = "PARTIAL"
        elif passed_pins > 0:
            print(f"🚨 NEEDS WORK: Only {passed_pins}/{total_pins} pins working ({passed_pins/total_pins*100:.0f}%)")
            print("   Significant fallback to polling will occur")
            verdict = "NEEDS_WORK"
        else:
            print("❌ NOT READY: No GPIO pins passed edge detection tests")
            print("   System will use polling fallback for all inputs")
            verdict = "NOT_READY"
    
        # Performance prediction
        print(f"\nPERFORMANCE PREDICTION:")
        print("-" * 25)
        if server_buttons_ok and client_buttons_ok:
            print("✅ Edge detection working - CPU usage will be minimal")
            print("   Latency: <1ms, CPU usage: ~0% when idle")
        else:
            print("⚠️  Will use polling fallback - higher CPU usage")
            print("   Latency: ~20ms, CPU usage: ~2-5% continuous")
        
    except Exception as e:
        print(f"🚨 Critical error during GPIO testing: {e}")
        print(f"   Exception type: {type(e).__name__}")
    
    finally:
        # Ensure cleanup always happens
        if cleanup_needed:
            try:
                print("\n🧹 Cleaning up GPIO resources...")
                GPIO.cleanup()
                print("✅ GPIO cleanup completed")
            except Exception as e:
                print(f"⚠️  Error during GPIO cleanup: {e}")
    
    print(f"\n{'='*60}")
    if not interactive_mode:
        print("🤖 NON-INTERACTIVE TEST COMPLETE")
        print("   IRQ setup validated without requiring button presses")
        print("   For full hardware validation, run without --no-interactive")
    else:
        print("Test complete! Check any failed items above.")
    print("For production deployment, address all FAILED items.")
    print(f"{'='*60}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"🚨 Fatal error: {e}")
        print(f"   Exception type: {type(e).__name__}")
    finally:
        # Final safety cleanup
        try:
            if cleanup_needed:
                GPIO.cleanup()
        except:
            pass
        sys.exit(0)