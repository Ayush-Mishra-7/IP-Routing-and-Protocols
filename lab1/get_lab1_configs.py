#!/usr/bin/env python3
"""
Lab1 – Get Running Configs
===========================
Connects to each Lab1 router (5R1–5R5) via the comm server,
retrieves 'show running-config', and saves each config to
lab1/config/<RouterName>_<timestamp>.txt

Uses the same ConsoleDeviceConfigurator + get_running_config
from Lab0.

Usage:
    cd <project root>            (IP-Routing-and-Protocols)
    python lab1/get_lab1_configs.py
"""

import json
import os
import sys
import logging
from datetime import datetime

# ---------------------------------------------------------------------------
# Make Lab0 importable  (adds ../Lab0 to sys.path)
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
LAB0_DIR = os.path.join(PROJECT_ROOT, "Lab0")
sys.path.insert(0, LAB0_DIR)

from console_device_config import ConsoleDeviceConfigurator
from get_config import get_running_config

# ---------------------------------------------------------------------------
# Settings  – edit these to match your environment
# ---------------------------------------------------------------------------
CONSOLE_PORT = "COM5"               # Serial port to the comm server
BAUDRATE     = 9600
COMM_SERVER_IP = "1.1.1.1"          # Comm-server management IP
CONFIG_FILE  = os.path.join(SCRIPT_DIR, "get_config_routers.json")
OUTPUT_DIR   = os.path.join(SCRIPT_DIR, "config")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(SCRIPT_DIR, "get_lab1_configs.log"), mode="a"
        ),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def save_config_to_file(router_name: str, config_content: str):
    """Save the running-config to config/<RouterName>_<timestamp>.txt"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{router_name}_{timestamp}.txt"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w") as f:
        f.write(config_content)

    logger.info(f"Configuration saved to {filepath}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Load router list
    logger.info(f"Loading router config from {CONFIG_FILE}")
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    routers = config["routers"]
    credentials = config.get("credentials", {})
    logger.info(f"Found {len(routers)} router(s) to back up")

    results = {}

    for router in routers:
        name = router["RouterName"]
        port = int(router["PortNo"])

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"  {name}  —  telnet {COMM_SERVER_IP} {port}")
        logger.info("=" * 60)

        try:
            cfg = ConsoleDeviceConfigurator(port=CONSOLE_PORT, baudrate=BAUDRATE)
            cfg.open()

            connected = cfg.telnet_to_device(COMM_SERVER_IP, port)
            if not connected:
                logger.error(f"Failed to telnet to {name}")
                results[name] = "FAILED (telnet)"
                cfg.close()
                continue

            # Verify hostname
            if not cfg.verify_hostname(name):
                logger.error(f"Hostname mismatch for {name} — skipping")
                results[name] = "FAILED (hostname mismatch)"
                cfg.disconnect_from_device()
                cfg.close()
                continue

            # Get and save running-config
            running_config = get_running_config(cfg)
            save_config_to_file(name, running_config)
            results[name] = "BACKED UP"

            cfg.disconnect_from_device()
            cfg.close()

        except Exception as e:
            logger.error(f"Error with {name}: {e}")
            results[name] = f"ERROR: {e}"

    # Summary
    print("\n" + "=" * 60)
    print("  BACKUP SUMMARY")
    print("=" * 60)
    for rname, status in results.items():
        print(f"  {rname:10s}  {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
