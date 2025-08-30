#!/usr/bin/env python3
"""
Raspberry Pi LED Director - MQTT Edition

Date: August 2025
"""

import sys
import os

# Add the package to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import and run the main function from the modular implementation
from rpi_director.__main__ import main

if __name__ == "__main__":
    main()
