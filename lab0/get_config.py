import time
import logging

logger = logging.getLogger(__name__)

def get_running_config(device_connection) -> str:
    """
    Retrieves the running configuration from the device.
    
    Args:
        device_connection: An instance of ConsoleDeviceConfigurator (or compatible)
                           that has an active connection to the device.
                           
    Returns:
        str: The content of 'show running-config'.
    """
    logger.info("Retrieving running-config ...")
    
    # Ensure we are in enable mode (should already be, but good to check/ensure)
    device_connection.enter_enable_mode()
    
    # Disable pagination to get the full config in one go
    device_connection.send_command("terminal length 0", wait=1)
    
    # Send the show command
    # We might need a longer wait time for large configs
    config_output = device_connection.send_command("show running-config", wait=5)
    
    # Optional: Re-enable pagination if needed, but usually not necessary 
    # as we disconnect shortly after.
    # device_connection.send_command("terminal length 24", wait=1)
    
    return config_output
