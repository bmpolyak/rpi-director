#!/usr/bin/env python3
"""
GPIO Pin Test Script
Tests each pin individually to identify hardware or permission issues.
"""

import RPi.GPIO as GPIO
import time

def test_pin(pin, pin_type="input"):
    """Test a specific GPIO pin"""
    try:
        print(f"Testing GPIO pin {pin} as {pin_type}...")
        
        # Clean up any existing state
        try:
            GPIO.cleanup(pin)
        except RuntimeWarning:
            pass
        
        if pin_type == "input":
            # Test as input with pull-up
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            value = GPIO.input(pin)
            print(f"  ✅ Pin {pin} input setup OK, value: {value}")
            
            # Test edge detection
            GPIO.add_event_detect(pin, GPIO.FALLING, bouncetime=200)
            print(f"  ✅ Pin {pin} edge detection OK")
            GPIO.remove_event_detect(pin)
            
        elif pin_type == "output":
            # Test as output
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
            print(f"  ✅ Pin {pin} output setup OK")
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(pin, GPIO.LOW)
        
        GPIO.cleanup(pin)
        return True
        
    except Exception as e:
        print(f"  ❌ Pin {pin} FAILED: {e}")
        try:
            GPIO.cleanup(pin)
        except:
            pass
        return False

def main():
    print("GPIO Pin Test - Starting...")
    print("=" * 50)
    
    # Updated pin configuration to match new settings.json
    button_pins = {"red": 2, "yellow": 3, "green": 4}
    led_pins = {"red": 10, "yellow": 9, "green": 11}
    
    GPIO.setmode(GPIO.BCM)
    
    print("\nTesting BUTTON pins (inputs with edge detection):")
    button_results = {}
    for color, pin in button_pins.items():
        button_results[color] = test_pin(pin, "input")
    
    print("\nTesting LED pins (outputs):")
    led_results = {}
    for color, pin in led_pins.items():
        led_results[color] = test_pin(pin, "output")
    
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print("Button pins:")
    for color, result in button_results.items():
        status = "✅ OK" if result else "❌ FAILED"
        print(f"  {color} (GPIO {button_pins[color]}): {status}")
    
    print("LED pins:")
    for color, result in led_results.items():
        status = "✅ OK" if result else "❌ FAILED"
        print(f"  {color} (GPIO {led_pins[color]}): {status}")
    
    # Suggest alternative pins if any failed
    failed_buttons = [color for color, result in button_results.items() if not result]
    if failed_buttons:
        print(f"\nSUGGESTED ALTERNATIVE BUTTON PINS:")
        alternative_pins = [2, 3, 4, 17, 27, 22, 5, 6, 13, 19, 26]
        for i, color in enumerate(failed_buttons[:len(alternative_pins)]):
            print(f"  {color}: GPIO {alternative_pins[i]} (instead of {button_pins[color]})")
    
    GPIO.cleanup()

if __name__ == "__main__":
    main()
