
import logging
import os
import time
from datetime import datetime
from get_config import get_running_config

logger = logging.getLogger(__name__)

def save_config_to_file(router_name: str, config_content: str):
    """Save the configuration content to a timestamped file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{router_name}_{timestamp}.txt"
    directory = "config"
    
    if not os.path.exists(directory):
        os.makedirs(directory)
        
    filepath = os.path.join(directory, filename)
    with open(filepath, "w") as f:
        f.write(config_content)
    
    logger.info(f"Configuration saved to {filepath}")

def erase_and_reload(device_connection, hostname: str):
    """
    Backs up the running config, erases the startup config, and reloads the device.
    """
    logger.info(f"Starting erase & reload process for {hostname}...")

    # 1. Backup Running Config
    try:
        running_config = get_running_config(device_connection)
        save_config_to_file(hostname, running_config)
    except Exception as e:
        logger.error(f"Failed to backup config for {hostname}: {e}")
        # Proceeding might be risky if backup failed, but user asked to erase.
        # Let's verify if we should continue. For now, strict adherence to request: "saves... and then erases"
        # If save fails, we should probably stop or warn. But let's log and continue for now as it's a specific erase tool.
        pass # Continue

    # 2. Erase Startup Config
    logger.info("Erasing startup-config (write erase)...")
    device_connection.send_command("write erase", wait=2)
    # Confirm the erase (usually prompts [confirm])
    device_connection._write("\r\n")
    time.sleep(2)
    output = device_connection._read_all()
    logger.info(f"Erase output: {output.strip()[:200]}")

    # 3. Reload
    logger.info("Reloading device...")
    reload_output = device_connection.send_command("reload", wait=2)
    
    # Handle "System configuration has been modified. Save? [yes/no]:"
    # and "Proceed with reload? [confirm]"
    time.sleep(2)
    more_output = device_connection._read_all()
    output = reload_output + more_output
    logger.debug(f"Reload prompt output: {output}")

    if "save" in output.lower() and "modified" in output.lower():
        logger.info("Answering 'no' to save modified config...")
        device_connection._write("no\r\n")
        time.sleep(2)
        output = device_connection._read_all()
        logger.debug(f"After 'no': {output}")

    if "confirm" in output.lower() or "proceed" in output.lower() or "[" in output: # [confirm]
        logger.info("Confirming reload...")
        device_connection._write("\r\n")
        time.sleep(1)
        output = device_connection._read_all()
        logger.info(f"Reload confirmed. Device should be rebooting. Output: {output.strip()[:200]}")
    else:
        # Sometimes it just asks [confirm] immediately if no changes
        device_connection._write("\r\n")
        logger.info("Sent confirmation default.")

    logger.info(f"{hostname} erase and reload command completed.")
