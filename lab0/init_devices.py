
import logging
import time

logger = logging.getLogger(__name__)

def initialize_device(device_connection, hostname: str):
    """
    Sets the hostname and enable password for the device.
    
    Args:
        device_connection: An instance of ConsoleDeviceConfigurator.
        hostname: The hostname to set on the device.
    """
    logger.info(f"Initializing device to hostname: {hostname}...")

    # Check for "initial configuration dialog"
    # Usually appears as: "Would you like to enter the initial configuration dialog? [yes/no]: "
    # We send a blank line first to see where we are.
    device_connection._write("\r\n")
    time.sleep(1)
    output = device_connection._read_all()
    
    if "initial configuration" in output.lower() or "dialog? [yes/no]" in output.lower():
        logger.info("Detected Initial Configuration Dialog. Sending 'no'...")
        device_connection._write("no\r\n")
        
        # Wait for "Press RETURN to get started" or similar
        time.sleep(5)
        
        # Send a few returns to get to "Router>"
        device_connection._write("\r\n")
        time.sleep(1)
        device_connection._write("\r\n")
        time.sleep(1)
        output = device_connection._read_all()
        logger.info(f"Output after exiting dialog: {output.strip()[:200]}")

    
    # Ensure we are in enable mode first
    device_connection.enter_enable_mode()
    
    # Enter global config mode
    device_connection.enter_config_mode()
    
    # Set Hostname
    logger.info(f"Setting hostname to {hostname}")
    device_connection.send_command(f"hostname {hostname}")
    
    # Set Enable Password
    logger.info("Setting enable password to 'lab123'")
    device_connection.send_command("enable password lab123")
    
    # Exit and Save
    device_connection.exit_config_mode()
    device_connection.save_config()
    
    logger.info(f"Initialization of {hostname} complete.")
