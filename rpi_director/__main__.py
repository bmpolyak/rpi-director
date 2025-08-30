#!/usr/bin/env python3
"""
Raspberry Pi LED Director - MQTT Edition

Command-line interface for the LED Director system.

Usage:
    python3 -m rpi_director --mode server [--client-id server]
    python3 -m rpi_director --mode client [--client-id client1]

Author: GitHub Copilot
Date: August 2025
"""

import argparse
import logging
import logging.handlers
import sys
import os

# Configure logging - file logging is DISABLED by default to prevent SD card overflow
logging_handlers = [logging.StreamHandler(sys.stdout)]

# Determine log level from environment (default to WARNING for production)
log_level = os.environ.get('RPI_DIRECTOR_LOG_LEVEL', 'WARNING').upper()
if log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
    log_level = 'WARNING'

# File logging is OPTIONAL and disabled by default
# Set RPI_DIRECTOR_ENABLE_FILE_LOGGING=1 to enable file logging with rotation
enable_file_logging = os.environ.get('RPI_DIRECTOR_ENABLE_FILE_LOGGING', '0').lower() in ['1', 'true', 'yes']

if enable_file_logging:
    try:
        # Use RotatingFileHandler to prevent SD card overflow when enabled
        file_handler = logging.handlers.RotatingFileHandler(
            'rpi_director.log',
            maxBytes=10*1024*1024,  # 10MB per file
            backupCount=3,          # Keep 3 old files (30MB total max)
            encoding='utf-8'
        )
        logging_handlers.append(file_handler)
        print(f"File logging enabled: 10MB per file, 3 backups (30MB total)")
    except (OSError, IOError) as e:
        print(f"Warning: Cannot create rotating log file 'rpi_director.log': {e}")
        print("Continuing with console logging only...")
else:
    print("File logging disabled (default). Set RPI_DIRECTOR_ENABLE_FILE_LOGGING=1 to enable.")

# Configure logging with production-appropriate level
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=logging_handlers
)
logger = logging.getLogger(__name__)

# Log the configuration for troubleshooting (only to console)
if enable_file_logging:
    logger.info(f"Logging configured at {log_level} level with file rotation enabled")
else:
    logger.info(f"Logging configured at {log_level} level (console only)")


def main():
    """Main function to start the LED Director."""
    parser = argparse.ArgumentParser(description='Raspberry Pi LED Director - MQTT Edition')
    parser.add_argument('--mode', choices=['server', 'client'], required=True,
                       help='Run in server or client mode')
    parser.add_argument('--client-id', type=str, 
                       help='MQTT client ID (default: "server" for server mode, "client1" for client mode)')
    parser.add_argument('--settings', type=str, default='settings.json',
                       help='Path to settings file (default: settings.json)')
    
    args = parser.parse_args()
    
    # Set default client IDs
    if args.client_id is None:
        args.client_id = "server" if args.mode == "server" else "client1"
    
    try:
        # Import here to avoid import errors if RPi.GPIO/paho-mqtt not available
        from .server import LEDDirectorServer
        from .client import LEDDirectorClient
        
        if args.mode == "server":
            director = LEDDirectorServer(args.settings, args.client_id)
        else:
            director = LEDDirectorClient(args.settings, args.client_id)
        
        director.run()
        
    except Exception as e:
        logger.error(f"Error starting LED Director: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
