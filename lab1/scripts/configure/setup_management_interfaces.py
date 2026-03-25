#!/usr/bin/env python3
"""
Lab 1 Management Interface Setup
================================
Configures only the management interface (Gi0/1) for R1-R5 from router_config.json.
Relies on ConsoleDeviceConfigurator from lab0 to handle the serial/telnet connections to the Comm Server.

Usage:
  python setup_management_interfaces.py
"""

import os
import sys
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("setup_management_interfaces.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)

# Add lab0 to python path so we can import ConsoleDeviceConfigurator
current_dir = os.path.dirname(os.path.abspath(__file__))
lab0_dir = os.path.abspath(os.path.join(current_dir, "..", "lab0"))
if lab0_dir not in sys.path:
    sys.path.append(lab0_dir)

try:
    from console_device_config import ConsoleDeviceConfigurator
except ImportError as e:
    logger.error(f"Failed to import ConsoleDeviceConfigurator from lab0: {e}")
    logger.error(f"Ensure that {lab0_dir} exists and contains console_device_config.py.")
    sys.exit(1)


def build_management_interface_commands(router: dict) -> list[str]:
    """
    Builds IOS commands for just the interfaces specified in the config.
    Skips loopbacks and static routes.
    """
    commands = []
    interfaces = router.get("interfaces", {})

    for intf_name, intf_cfg in interfaces.items():
        ip = intf_cfg.get("ip")
        mask = intf_cfg.get("subnet")

        if not ip or not mask:
            logger.warning(f"Skipping interface {intf_name} due to missing IP or mask")
            continue

        commands += [
            f"interface {intf_name}",
            f"ip address {ip} {mask}",
            "no shutdown",
            "exit",
        ]

    return commands


def main():
    config_path = os.path.join(current_dir, "router_config.json")
    
    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        config_data = json.load(f)
        
    routers = config_data.get("routers", [])
    if not routers:
        logger.error("No routers found in config file.")
        sys.exit(1)

    logger.info(f"Found {len(routers)} routers to configure in {config_path}")

    # Settings matching lab0
    CONSOLE_PORT = "COM6"
    COMM_SERVER_IP = "1.1.1.1"

    for router in routers:
        expected_name = router.get("RouterName")
        port = router.get("PortNo")

        if not expected_name or not port:
            logger.warning(f"Skipping router config issue: missing name or port: {router}")
            continue

        logger.info("\n" + "=" * 60)
        logger.info(f"  {expected_name}  —  telnet {COMM_SERVER_IP} {port}")
        logger.info("=" * 60)

        # Connect to Comm Server
        try:
            cfg = ConsoleDeviceConfigurator(port=CONSOLE_PORT)
            cfg.open()
            
            # Telnet to Router
            connected = cfg.telnet_to_device(COMM_SERVER_IP, port)
            if not connected:
                logger.error(f"Failed to telnet to {expected_name}")
                cfg.close()
                continue
                
            # Verify we are on the correct device
            if not cfg.verify_hostname(expected_name):
                 logger.error(f"Hostname verification failed for {expected_name}. Skipping config.")
                 cfg.disconnect_from_device()
                 cfg.close()
                 continue

            # Build and push commands
            commands = build_management_interface_commands(router)
            if commands:
                logger.info(f"Applying commands to {expected_name}:")
                for c in commands:
                    logger.info(f"  {c}")
                cfg.configure_device(commands)
                logger.info(f"Successfully configured {expected_name}.")
            else:
                 logger.info(f"No interface commands generated for {expected_name}.")

            # Cleanup
            cfg.disconnect_from_device()
            cfg.close()

        except Exception as e:
            logger.error(f"Error while processing {expected_name}: {e}")
            if 'cfg' in locals() and cfg.serial_conn and cfg.serial_conn.is_open:
                try:
                    if cfg.is_connected_to_device:
                         cfg.disconnect_from_device()
                    cfg.close()
                except Exception:
                    pass

if __name__ == "__main__":
    main()
