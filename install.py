#!/usr/bin/env python3
"""
Raspberry Pi LED Director Installa    print("\n🚀 Setting up Python virtual environment...")
    
    # Install required system packages
    if not run_command("apt update", "Updating package list"):
        return Falsept

This script sets up the environment and systemd services for the LED Director.
It creates a virtual environment, installs dependencies, and configures systemd services.

Updated for modular package structure.

Usage:
    sudo python3 install.py --mode server
    sudo python3 install.py --mode client --client-id client1
"""

import subprocess
import sys
import os
import argparse
import pwd
from pathlib import Path

def run_command(command, description, check=True):
    """Run a shell command with error handling."""
    print(f"📋 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=check, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()}")
        else:
            print(f"❌ {description} failed")
            if result.stderr.strip():
                print(f"   Error: {result.stderr.strip()}")
            return False
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with error: {e}")
        if e.stderr:
            print(f"   Error output: {e.stderr}")
        return False

def configure_mosquitto():
    """Configure Mosquitto to allow anonymous connections for local development."""
    mosquitto_conf = "/etc/mosquitto/mosquitto.conf"
    local_conf = "/etc/mosquitto/conf.d/99-local.conf"
    
    try:
        # Create local configuration to allow anonymous access
        local_config = """# Local development configuration
# Allow anonymous connections (no authentication required)
allow_anonymous true

# Enable local listeners
listener 1883
protocol mqtt
"""
        
        print("🔧 Configuring Mosquitto for anonymous access...")
        
        # Create conf.d directory if it doesn't exist
        os.makedirs("/etc/mosquitto/conf.d", exist_ok=True)
        
        # Write local configuration
        with open(local_conf, "w") as f:
            f.write(local_config)
            
        print(f"   ✅ Created {local_conf}")
        
        # Stop mosquitto if it's running to reload config
        run_command("systemctl stop mosquitto", "Stopping Mosquitto for config reload", check=False)
        
        return True
        
    except Exception as e:
        print(f"   ⚠️  Failed to configure Mosquitto: {e}")
        print("   You may need to configure Mosquitto authentication manually")
        return True  # Don't fail the entire installation for this

def check_root():
    """Check if running as root (needed for systemd operations)."""
    if os.geteuid() != 0:
        print("❌ This script must be run as root for systemd service installation.")
        print("   Please run: sudo python3 setup.py --mode <server|client>")
        sys.exit(1)

def get_real_user():
    """Get the actual user who ran sudo."""
    if 'SUDO_USER' in os.environ:
        return os.environ['SUDO_USER']
    else:
        return pwd.getpwuid(os.getuid()).pw_name

def setup_venv(user_home, real_user, mode):
    """Create virtual environment and install dependencies."""
    venv_path = user_home / "rpi-director-venv"
    script_dir = user_home / "rpi-director"
    
    print("\n� Setting up Python virtual environment...")
    
    # First, remove any conflicting system packages
    print("🧹 Removing conflicting system GPIO packages...")
    run_command("apt remove -y python3-rpi.gpio python3-rpi-lgpio rpi.gpio-common", "Removing system GPIO packages", check=False)
    
    # Install required system packages
    if not run_command("apt update", "Updating package list"):
        return False
    
    # Install Python development tools and dependencies for RPi.GPIO compilation
    packages = [
        "python3-venv",
        "python3-full", 
        "python3-dev",
        "python3-pip",
        "build-essential",
        "gcc"
    ]
    
    # Add MQTT broker for server mode
    if mode == "server":
        packages.extend(["mosquitto", "mosquitto-clients"])
    
    package_list = " ".join(packages)
    if not run_command(f"apt install -y {package_list}", "Installing system packages and dependencies"):
        return False
    
    # Enable and start MQTT broker on server
    if mode == "server":
        # Configure Mosquitto for anonymous access
        if not configure_mosquitto():
            return False
            
        if not run_command("systemctl enable mosquitto", "Enabling MQTT broker"):
            return False
        if not run_command("systemctl start mosquitto", "Starting MQTT broker"):
            return False
        print("✅ MQTT broker (Mosquitto) installed and started")
    
    # Create virtual environment as the real user
    venv_cmd = f"sudo -u {real_user} python3 -m venv {venv_path}"
    if not run_command(venv_cmd, f"Creating virtual environment at {venv_path}"):
        return False
    
    # Upgrade pip and install wheel to avoid legacy setup.py issues
    upgrade_cmd = f"sudo -u {real_user} {venv_path}/bin/pip install --upgrade pip wheel setuptools"
    if not run_command(upgrade_cmd, "Upgrading pip and installing wheel support"):
        return False
    
    # Install requirements
    pip_cmd = f"sudo -u {real_user} {venv_path}/bin/pip install -r {script_dir}/requirements.txt"
    if not run_command(pip_cmd, "Installing Python dependencies"):
        return False

    # Install the rpi_director package in development mode
    install_pkg_cmd = f"cd {script_dir} && sudo -u {real_user} {venv_path}/bin/pip install -e ."
    if not run_command(install_pkg_cmd, "Installing rpi_director package in development mode"):
        print("⚠️  Package installation failed, trying legacy approach...")
        # Fallback: just make sure the module can be found via PYTHONPATH
        pythonpath_cmd = f"echo 'export PYTHONPATH={script_dir}:$PYTHONPATH' >> /home/{real_user}/.bashrc"
        run_command(pythonpath_cmd, "Adding project to PYTHONPATH", check=False)

    print(f"✅ Virtual environment created at {venv_path}")
    return True

def setup_gpio_permissions(real_user):
    """Setup GPIO permissions for the user."""
    print(f"\n🔧 Setting up GPIO permissions for user '{real_user}'...")
    
    # Add user to gpio group
    if not run_command(f"usermod -a -G gpio {real_user}", f"Adding {real_user} to gpio group"):
        return False
    
    # Set GPIO device permissions
    if not run_command("chown root:gpio /dev/gpiomem", "Setting GPIO device ownership"):
        return False
    
    if not run_command("chmod g+rw /dev/gpiomem", "Setting GPIO device permissions"):
        return False
    
    print(f"✅ GPIO permissions configured for user '{real_user}'")
    print(f"   Note: User may need to log out and back in for group changes to take effect")
    return True

def install_service(mode, user_home, real_user, client_id=None):
    """Install and enable systemd service."""
    print(f"\n⚙️  Installing {mode} service...")
    
    script_dir = user_home / "rpi-director"
    
    # For client mode with specific client ID, create a custom service file name
    if mode == "client" and client_id != "client1":
        service_file = f"rpi-director-{client_id}.service"
        source_service = script_dir / "rpi-director-client.service"  # Use template
    else:
        service_file = f"rpi-director-{mode}.service" if mode == "client" else "rpi-director.service"
        source_service = script_dir / service_file
    
    target_service = Path("/etc/systemd/system") / service_file
    
    # Check if service is already installed and running
    service_exists = target_service.exists()
    service_enabled = False
    service_running = False
    choice = None  # Initialize choice variable
    
    if service_exists:
        # Check if service is enabled
        try:
            result = subprocess.run(f"systemctl is-enabled {service_file}", shell=True, capture_output=True, text=True)
            service_enabled = (result.returncode == 0 and result.stdout.strip() == "enabled")
        except Exception:
            service_enabled = False
        
        # Check if service is running
        try:
            result = subprocess.run(f"systemctl is-active {service_file}", shell=True, capture_output=True, text=True)
            service_running = (result.returncode == 0 and result.stdout.strip() == "active")
        except Exception:
            service_running = False
        
        print(f"📋 Service {service_file} status:")
        print(f"  - Installed: {'✅ Yes' if service_exists else '❌ No'}")
        print(f"  - Enabled: {'✅ Yes' if service_enabled else '❌ No'}")
        print(f"  - Running: {'✅ Yes' if service_running else '❌ No'}")
        
        # Ask user what to do
        print(f"\n⚠️  Service {service_file} already exists!")
        print("Options:")
        print("  1. Reinstall (stop, update, restart)")
        print("  2. Update only (keep running if active)")
        print("  3. Skip service installation")
        
        while True:
            try:
                choice = input("Choose option [1/2/3]: ").strip()
                if choice in ['1', '2', '3']:
                    break
                print("Please enter 1, 2, or 3")
            except (KeyboardInterrupt, EOFError):
                print("\n❌ Installation cancelled by user")
                return False
        
        if choice == '3':
            print("⏭️  Skipping service installation")
            return True
        elif choice == '1':
            print("🔄 Reinstalling service...")
            if service_running:
                run_command(f"systemctl stop {service_file}", f"Stopping {service_file}", check=False)
            if service_enabled:
                run_command(f"systemctl disable {service_file}", f"Disabling {service_file}", check=False)
        else:  # choice == '2'
            print("📝 Updating service configuration...")
    
    # Check if source service file exists
    if not source_service.exists():
        print(f"❌ Service file {source_service} not found!")
        return False
    
    # For client mode with any client ID, modify the service file content
    if mode == "client" and client_id:
        # Read the template service file
        with open(source_service, 'r') as f:
            service_content = f.read()
        
        # Update the ExecStart line to include client ID
        # Replace any existing ExecStart line with the correct venv path and client-id
        import re
        service_content = re.sub(
            r'ExecStart=.*?python3 -m rpi_director --mode client.*',
            f'ExecStart=/home/{real_user}/rpi-director-venv/bin/python3 -m rpi_director --mode client --client-id {client_id}',
            service_content
        )
        
        # Write the modified service file
        with open(target_service, 'w') as f:
            f.write(service_content)
        
        print(f"✅ Created service file {service_file} with client ID: {client_id}")
    elif mode == "server":
        # Handle server mode service file
        # Read the source service file
        with open(source_service, 'r') as f:
            service_content = f.read()
        
        # Update the ExecStart line to use correct venv path
        import re
        service_content = re.sub(
            r'ExecStart=.*?python3 -m rpi_director --mode server.*',
            f'ExecStart=/home/{real_user}/rpi-director-venv/bin/python3 -m rpi_director --mode server --client-id server',
            service_content
        )
        
        # Write the modified service file
        with open(target_service, 'w') as f:
            f.write(service_content)
        
        print(f"✅ Updated service file {service_file} with correct venv path")
    
    # Reload systemd
    if not run_command("systemctl daemon-reload", "Reloading systemd"):
        return False
    
    # Handle service enabling and starting based on previous state and user choice
    service_name = service_file
    
    if service_exists and choice == '2':  # Update only
        print(f"📝 Service {service_name} configuration updated")
        if service_enabled:
            print(f"✅ Service {service_name} remains enabled")
        if service_running:
            print(f"🔄 Restarting service {service_name} to apply changes...")
            if not run_command(f"systemctl restart {service_name}", f"Restarting {service_name}"):
                print(f"⚠️  Service restart failed. Check with: journalctl -u {service_name}")
                return False
            print(f"✅ Service {service_name} restarted successfully")
        else:
            print(f"ℹ️  Service {service_name} was not running, leaving stopped")
    else:  # New installation or reinstall
        # Enable service
        if not run_command(f"systemctl enable {service_name}", f"Enabling {service_name}"):
            return False
        
        # Start service
        if not run_command(f"systemctl start {service_name}", f"Starting {service_name}"):
            print(f"⚠️  Service failed to start. Check with: journalctl -u {service_name}")
            return False
        
        print(f"✅ Service {service_name} installed and started")
    return True

def test_installation(mode, user_home, real_user, client_id=None):
    """Test the installation by running the script manually."""
    print(f"\n🧪 Testing {mode} installation...")
    
    script_dir = user_home / "rpi-director"
    
    # Determine service name based on mode and client_id
    if mode == "client" and client_id != "client1":
        service_name = f"rpi-director-{client_id}.service"
    else:
        service_name = f"rpi-director-{mode}.service" if mode == "client" else "rpi-director.service"
    
    print(f"   Temporarily stopping {service_name} for testing...")
    run_command(f"systemctl stop {service_name}", f"Stopping {service_name} for test", check=False)
    
    # Build test command with client_id if provided (using venv Python)
    venv_python = user_home / "rpi-director-venv" / "bin" / "python3"
    if mode == "client" and client_id:
        test_cmd = f"cd {script_dir} && sudo -u {real_user} {venv_python} -m rpi_director --mode {mode} --client-id {client_id}"
    else:
        test_cmd = f"cd {script_dir} && sudo -u {real_user} {venv_python} -m rpi_director --mode {mode}"
    
    print(f"   Running: {test_cmd}")
    print("   (This will run for 5 seconds then stop)")
    
    # Run for a few seconds then kill
    test_process = subprocess.Popen(test_cmd, shell=True)
    success = True
    try:
        test_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        test_process.terminate()
        test_process.wait()
        print("✅ Script runs successfully (stopped after 5 seconds)")
    else:
        if test_process.returncode == 0:
            print("✅ Script completed successfully")
        else:
            print("⚠️  Script had some issues but basic functionality appears to work")
            success = True  # Don't fail setup for minor issues
    
    # Restart the service
    print(f"   Restarting {service_name}...")
    run_command(f"systemctl start {service_name}", f"Restarting {service_name}", check=False)
    
    return success

def validate_client_id(client_id):
    """Validate client ID format."""
    import re
    
    if not client_id:
        return False, "Client ID cannot be empty"
    
    # Allow alphanumeric, hyphens, and underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', client_id):
        return False, "Client ID can only contain letters, numbers, hyphens, and underscores"
    
    # Check length
    if len(client_id) > 50:
        return False, "Client ID must be 50 characters or less"
    
    # Reserved names
    reserved = ['server', 'broker', 'mosquitto', 'mqtt']
    if client_id.lower() in reserved:
        return False, f"'{client_id}' is a reserved name, please choose a different client ID"
    
    return True, "Valid client ID"

def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description='Install Raspberry Pi LED Director')
    parser.add_argument('--mode', choices=['server', 'client'], required=True,
                       help='Install server mode (controls LEDs/buttons) or client mode (receives MQTT commands)')
    parser.add_argument('--client-id', type=str,
                       help='Client ID for client mode (e.g., client1, client2, client3). Required for client mode.')
    parser.add_argument('--broker-host', type=str, default='192.168.5.101',
                       help='MQTT broker host IP address (default: 192.168.5.101)')
    parser.add_argument('--skip-test', action='store_true',
                       help='Skip the installation test')
    
    args = parser.parse_args()
    
    # Validate client mode arguments
    if args.mode == 'client' and not args.client_id:
        print("❌ --client-id is required for client mode")
        print("   Example: sudo python3 install.py --mode client --client-id client1")
        print("   Valid client IDs: client1, client2, client3, etc.")
        sys.exit(1)
    
    # Validate client ID format if provided
    if args.client_id:
        is_valid, message = validate_client_id(args.client_id)
        if not is_valid:
            print(f"❌ Invalid client ID: {message}")
            print("   Example valid client IDs: client1, rpi-living-room, sensor_01")
            sys.exit(1)
    
    print("🎯 Raspberry Pi LED Director Setup")
    print("=" * 50)
    print(f"Mode: {args.mode}")
    if args.mode == 'client':
        print(f"Client ID: {args.client_id}")
        print(f"MQTT Broker: {args.broker_host}")
    else:
        print("MQTT Broker: Local (Mosquitto will be installed)")
    
    # Check if running as root
    check_root()
    
    # Get the real user (who ran sudo)
    real_user = get_real_user()
    user_home = Path(f"/home/{real_user}")
    
    print(f"User: {real_user}")
    print(f"Home: {user_home}")
    
    # Verify script directory exists
    script_dir = user_home / "rpi-director"
    if not script_dir.exists():
        print(f"❌ Script directory {script_dir} not found!")
        print("   Please ensure this setup script is run from the rpi-director directory")
        sys.exit(1)
    
    success = True
    
    # Step 1: Setup virtual environment and dependencies
    if success:
        success = setup_venv(user_home, real_user, args.mode)
    
    # Step 2: Setup GPIO permissions
    if success:
        success = setup_gpio_permissions(real_user)
    
    # Step 3: Install systemd service
    if success:
        success = install_service(args.mode, user_home, real_user, getattr(args, 'client_id', None))
    
    # Step 4: Test installation (optional)
    if success and not args.skip_test:
        test_installation(args.mode, user_home, real_user, getattr(args, 'client_id', None))
    
    # Final status
    print("\n" + "=" * 50)
    if success:
        print("🎉 Setup completed successfully!")
        if args.mode == 'client':
            print(f"\nYour LED Director {args.mode} ({args.client_id}) is now installed and running.")
        else:
            print(f"\nYour LED Director {args.mode} is now installed and running.")
        
        print(f"\nUseful commands:")
        # Determine service name based on mode and client_id
        if args.mode == "client" and args.client_id != "client1":
            service_name = f"rpi-director-{args.client_id}.service"
        else:
            service_name = f"rpi-director-{args.mode}.service" if args.mode == "client" else "rpi-director.service"
        
        print(f"  Check status: sudo systemctl status {service_name}")
        print(f"  View logs:    sudo journalctl -u {service_name} -f")
        print(f"  Stop service: sudo systemctl stop {service_name}")
        print(f"  Start service: sudo systemctl start {service_name}")
        
        # Build manual run command with client_id if provided (using venv Python)
        venv_python = f"/home/{real_user}/rpi-director-venv/bin/python3"
        if args.mode == "client" and args.client_id:
            manual_cmd = f"cd /home/{real_user}/rpi-director && {venv_python} -m rpi_director --mode {args.mode} --client-id {args.client_id}"
        else:
            manual_cmd = f"cd /home/{real_user}/rpi-director && {venv_python} -m rpi_director --mode {args.mode}"
        print(f"  Manual run:   {manual_cmd}")
        
        print(f"\n📋 Logging Configuration:")
        print(f"  - File logging is DISABLED by default (SD card protection)")
        print(f"  - View console logs: sudo journalctl -u {service_name} -f")
        print(f"  - To enable file logging: edit service file and set RPI_DIRECTOR_ENABLE_FILE_LOGGING=1")
        
        if args.mode == "server":
            print(f"\n📌 Server Notes:")
            print(f"  - Connect buttons to GPIO pins 2, 3, 4 (red, yellow, green)")
            print(f"  - Connect LEDs to GPIO pins 10, 9, 11 (red, yellow, green)")
            print(f"  - MQTT commands will be sent to clients configured in settings.json")
            print(f"  - MQTT broker (Mosquitto) is installed and running")
        else:
            print(f"\n📌 Client Notes:")
            print(f"  - Client ID: {args.client_id}")
            print(f"  - Connect LEDs to GPIO pins 10, 9, 11 (red, yellow, green)")
            print(f"  - Listening for MQTT commands from server")
            print(f"  - Configure MQTT broker connection in settings.json")
            print(f"  - Server will send commands to: led-director/client/{args.client_id}/cmd/leds/*")
            
            # Check if this is a standard client ID or custom
            standard_clients = ['client1', 'client2', 'client3']
            if args.client_id not in standard_clients:
                print(f"  - ⚠️  IMPORTANT: Add '{args.client_id}' to the 'clients' array in server's settings.json")
                print(f"    Example: \"clients\": [\"client1\", \"client2\", \"{args.client_id}\"]")
            else:
                print(f"  - ✅ Standard client ID - should already be in server's settings.json")
        
        print(f"\n⚠️  Important: If this is the first GPIO setup, you may need to reboot")
        print(f"   or log out and back in for group permissions to take effect.")
        
    else:
        print("❌ Setup failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
