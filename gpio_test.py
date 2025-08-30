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
        gpio_group = grp.getgrnam('gpio')
        if username in [user.pw_name for user in pwd.getpwall() if gpio_group.gr_gid in os.getgroups()]:
            print(f"  ✅ User '{username}' is in 'gpio' group")
        else:
            print(f"  ⚠️  User '{username}' NOT in 'gpio' group - add with: sudo usermod -a -G gpio {username}")
    except Exception as e:
        print(f"  ⚠️  Could not check gpio group membership: {e}")
    
    # Check /dev/gpiomem permissions
    if os.path.exists('/dev/gpiomem'):
        stat = os.stat('/dev/gpiomem')
        print(f"  ✅ /dev/gpiomem exists (permissions: {oct(stat.st_mode)[-3:]})")
    else:
        print("  ❌ /dev/gpiomem not found - GPIO may not be available")
    
    # Check device tree overlays that might conflict
    dt_path = '/proc/device-tree/soc'
    if os.path.exists(dt_path):
        print("  ✅ Device tree found")
    else:
        print("  ⚠️  Device tree not found - unusual for Pi")
    
    # Check for common conflicting services
    conflicting_services = ['pigpiod', 'gpiozero', 'wiringpi']
    for service in conflicting_services:
        if os.system(f"pgrep {service} > /dev/null 2>&1") == 0:
            print(f"  ⚠️  {service} is running - may conflict with RPi.GPIO")
        else:
            print(f"  ✅ {service} not running")
    
    print()

def test_edge_detection_comprehensive(pin, color):
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
        'cleanup_test': False
    }
    
    try:
        # Clean slate
        try:
            GPIO.cleanup(pin)
        except:
            pass
        
        # Basic setup test
        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            edge_results['basic_setup'] = True
            print("  ✅ Basic input setup with pull-up")
        except Exception as e:
            print(f"  ❌ Basic setup failed: {e}")
            return edge_results
        
        # Test 1: Falling edge detection
        try:
            GPIO.add_event_detect(pin, GPIO.FALLING, bouncetime=200)
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
            GPIO.add_event_detect(pin, GPIO.RISING, bouncetime=200)
            edge_results['rising_edge'] = True
            print("  ✅ Rising edge detection setup")
            GPIO.remove_event_detect(pin)
        except Exception as e:
            print(f"  ❌ Rising edge detection failed: {e}")
        
        # Test 3: Both edges
        try:
            GPIO.add_event_detect(pin, GPIO.BOTH, bouncetime=200)
            edge_results['both_edges'] = True
            print("  ✅ Both edges detection setup")
            GPIO.remove_event_detect(pin)
        except Exception as e:
            print(f"  ❌ Both edges detection failed: {e}")
        
        # Test 4: Callback function test
        callback_triggered = threading.Event()
        
        def test_callback(channel):
            callback_triggered.set()
            print(f"    📞 Callback triggered for GPIO {channel}")
        
        try:
            GPIO.add_event_detect(pin, GPIO.FALLING, callback=test_callback, bouncetime=200)
            edge_results['callback_test'] = True
            print("  ✅ Callback-based edge detection setup")
            print("  ℹ️  Press the button now to test callback (5 second timeout)...")
            
            if callback_triggered.wait(timeout=5.0):
                print("  ✅ Callback function executed successfully!")
            else:
                print("  ⚠️  No button press detected (or button not connected)")
                
            GPIO.remove_event_detect(pin)
        except Exception as e:
            print(f"  ❌ Callback edge detection failed: {e}")
            print(f"     Possible causes:")
            print(f"     - Interrupt system not available")
            print(f"     - Kernel GPIO driver issues")
        
        # Test 5: Multiple callback stress test
        callback_count = [0]
        
        def counting_callback(channel):
            callback_count[0] += 1
            if callback_count[0] <= 3:  # Only print first few
                print(f"    📞 Callback #{callback_count[0]} for GPIO {channel}")
        
        try:
            GPIO.add_event_detect(pin, GPIO.FALLING, callback=counting_callback, bouncetime=100)
            edge_results['multiple_callbacks'] = True
            print("  ✅ Multiple callback test setup (100ms debounce)")
            print("  ℹ️  Press button multiple times quickly (5 second timeout)...")
            
            time.sleep(5.0)
            if callback_count[0] > 0:
                print(f"  ✅ Detected {callback_count[0]} button presses")
                if callback_count[0] > 10:
                    print("  ⚠️  Very high callback count - check for bouncing or noise")
            else:
                print("  ⚠️  No button presses detected")
                
            GPIO.remove_event_detect(pin)
        except Exception as e:
            print(f"  ❌ Multiple callback test failed: {e}")
        
        # Test 6: Cleanup test
        try:
            GPIO.add_event_detect(pin, GPIO.FALLING, bouncetime=200)
            GPIO.remove_event_detect(pin)
            GPIO.add_event_detect(pin, GPIO.FALLING, bouncetime=200)  # Should work again
            GPIO.remove_event_detect(pin)
            edge_results['cleanup_test'] = True
            print("  ✅ Edge detection cleanup/re-setup works")
        except Exception as e:
            print(f"  ❌ Cleanup test failed: {e}")
            print(f"     Possible causes:")
            print(f"     - GPIO cleanup not working properly")
            print(f"     - System state corruption")
        
        # Final cleanup
        try:
            GPIO.cleanup(pin)
        except:
            pass
            
    except Exception as e:
        print(f"  ❌ Comprehensive test failed: {e}")
    
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

def test_pin(pin, pin_type="input", color=None):
    """Test a specific GPIO pin with enhanced diagnostics."""
    try:
        print(f"Testing GPIO pin {pin} as {pin_type} ({color})...")
        
        # Clean up any existing state
        try:
            GPIO.cleanup(pin)
        except RuntimeWarning:
            pass
        
        if pin_type == "input":
            # Basic input test
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            value = GPIO.input(pin)
            print(f"  ✅ Pin {pin} input setup OK, value: {value} ({'HIGH/not pressed' if value else 'LOW/pressed'})")
            
            # Read value multiple times to check stability
            values = [GPIO.input(pin) for _ in range(10)]
            if len(set(values)) == 1:
                print(f"  ✅ Pin {pin} stable reading")
            else:
                print(f"  ⚠️  Pin {pin} unstable readings: {values}")
                print(f"     Possible causes: floating pin, bad connection, electrical noise")
            
            # Comprehensive edge detection test
            if color:
                edge_results = test_edge_detection_comprehensive(pin, color)
                
                # Diagnose failures
                if not all(edge_results.values()):
                    diagnose_edge_detection_failure(pin, edge_results)
                
                return all([edge_results['basic_setup'], 
                          any([edge_results['falling_edge'], edge_results['rising_edge']]),
                          edge_results['callback_test']])
            else:
                # Basic edge detection test
                try:
                    GPIO.add_event_detect(pin, GPIO.FALLING, bouncetime=200)
                    print(f"  ✅ Pin {pin} edge detection OK")
                    GPIO.remove_event_detect(pin)
                    return True
                except Exception as e:
                    print(f"  ❌ Pin {pin} edge detection failed: {e}")
                    return False
            
        elif pin_type == "output":
            # Test as output
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
            print(f"  ✅ Pin {pin} output setup OK (set LOW)")
            
            # Test output switching
            for state in [GPIO.HIGH, GPIO.LOW, GPIO.HIGH, GPIO.LOW]:
                GPIO.output(pin, state)
                time.sleep(0.1)
                print(f"    Set pin {pin} to {'HIGH' if state else 'LOW'}")
            
            GPIO.output(pin, GPIO.LOW)  # End in safe state
            print(f"  ✅ Pin {pin} output switching test passed")
        
        GPIO.cleanup(pin)
        return True
        
    except Exception as e:
        print(f"  ❌ Pin {pin} FAILED: {e}")
        print(f"     Exception type: {type(e).__name__}")
        try:
            GPIO.cleanup(pin)
        except:
            pass
        return False

def main():
    print("GPIO Pin Test - Enhanced Edge Detection Diagnostics")
    print("=" * 60)
    
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
    except Exception as e:
        print(f"⚠️  Could not load settings.json: {e}")
        print("Using default pin configuration...")
        # Fallback to default configuration
        server_buttons = {"red": 2, "green": 3, "clear": 4}
        server_leds = {"red": 10, "green": 11, "yellow_client1": 12, "yellow_client2": 13, "yellow_client3": 14}
        client_buttons = {"yellow": 15}
        client_leds = {"red": 16, "green": 17, "yellow": 18}
    
    GPIO.setmode(GPIO.BCM)
    
    print(f"\nTesting SERVER BUTTON pins (inputs with comprehensive edge detection):")
    print("=" * 60)
    server_button_results = {}
    for color, pin in server_buttons.items():
        server_button_results[color] = test_pin(pin, "input", color)
    
    print(f"\nTesting SERVER LED pins (outputs):")
    print("=" * 40)
    server_led_results = {}
    for color, pin in server_leds.items():
        server_led_results[color] = test_pin(pin, "output")
    
    print(f"\nTesting CLIENT BUTTON pins (inputs with comprehensive edge detection):")
    print("=" * 60)
    client_button_results = {}
    for color, pin in client_buttons.items():
        client_button_results[color] = test_pin(pin, "input", color)
    
    print(f"\nTesting CLIENT LED pins (outputs):")
    print("=" * 40)
    client_led_results = {}
    for color, pin in client_leds.items():
        client_led_results[color] = test_pin(pin, "output")
    
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
            safe_pins = [2, 3, 4, 17, 27, 22, 5, 6, 13, 19, 26, 21, 20, 16, 12, 25]
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
    
    # Performance prediction
    print(f"\nPERFORMACE PREDICTION:")
    print("-" * 25)
    if server_buttons_ok and client_buttons_ok:
        print("✅ Edge detection working - CPU usage will be minimal")
        print("   Latency: <1ms, CPU usage: ~0% when idle")
    else:
        print("⚠️  Will use polling fallback - higher CPU usage")
        print("   Latency: ~20ms, CPU usage: ~2-5% continuous")
    
    GPIO.cleanup()
    print(f"\n{'='*60}")
    print("Test complete! Check any failed items above.")
    print("For production deployment, address all FAILED items.")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
