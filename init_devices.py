
import logging

logger = logging.getLogger(__name__)

def initialize_device(device_connection, hostname: str):
    """
    Sets the hostname and enable password for the device.
    
    Args:
        device_connection: An instance of ConsoleDeviceConfigurator.
        hostname: The hostname to set on the device.
    """
    logger.info(f"Initializing device to hostname: {hostname}...")
    
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
