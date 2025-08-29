#!/usr/bin/env python3
"""
Test script to demonstrate OSC communication between client and a simple OSC sender
"""

import time
import threading
from pythonosc import udp_client

def send_osc_commands():
    """Send OSC commands to the client after a short delay"""
    time.sleep(2)  # Wait for client to start
    
    client = udp_client.SimpleUDPClient('127.0.0.1', 8000)
    
    print("🔴 Sending command to switch to YELLOW LED...")
    client.send_message('/led/yellow', 1)
    time.sleep(1)
    
    print("🟡 Sending command to switch to GREEN LED...")
    client.send_message('/led/green', 1)
    time.sleep(1)
    
    print("🟢 Sending command to switch to RED LED...")
    client.send_message('/led/red', 1)
    time.sleep(1)
    
    print("✅ OSC commands sent successfully!")

if __name__ == '__main__':
    # Start the OSC sender in a separate thread
    sender_thread = threading.Thread(target=send_osc_commands)
    sender_thread.daemon = True
    sender_thread.start()
    
    print("OSC sender started. Commands will be sent in 2 seconds...")
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Test script stopped.")
