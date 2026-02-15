import subprocess
import logging

logger = logging.getLogger(__name__)

def kill_process(process_name: str) -> bool:
    """
    Attempts to kill a process by name using taskkill.
    Returns True if the command was sent successfully/process found, False otherwise.
    """
    try:
        # /F = force, /IM = image name
        cmd = ["taskkill", "/F", "/IM", process_name]
        # capture_output=True prevents it from spamming stdout
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Successfully killed {process_name}")
            return True
        elif "not found" in result.stderr:
            # Process wasn't running, which is fine
            return False
        else:
            logger.warning(f"Failed to kill {process_name}: {result.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"Error killing {process_name}: {e}")
        return False

def kill_common_terminal_apps() -> list[str]:
    """
    Kills common terminal applications that might be blocking a serial port.
    Returns a list of applications that were successfully killed.
    """
    # List of common apps that might hold a serial port open
    # Add more as needed (e.g., 'plink.exe', 'realterm.exe')
    apps_to_kill = [
        "putty.exe",
        # "kitty.exe", 
        # "ttermpro.exe", # Tera Term
        # "securecrt.exe",
        # "mobaxterm.exe" 
    ]
    
    killed = []
    for app in apps_to_kill:
        if kill_process(app):
            killed.append(app)
            
    return killed
