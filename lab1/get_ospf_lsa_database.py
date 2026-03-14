#!/usr/bin/env python3
"""
Get OSPF LSA Database from R1 and R5
=====================================
Connects to R1 and R5 via Netmiko and retrieves the OSPF LSA database
using 'show ip ospf database' command. Saves output to timestamped files.

Usage:
    python get_ospf_lsa_database.py
"""

import os
import sys
import json
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("get_ospf_lsa_database.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)

try:
    from netmiko import ConnectHandler
except ImportError as exc:
    logger.error("Netmiko is required to run this script: %s", exc)
    sys.exit(1)


def load_config(path: str) -> dict:
    """Load router configuration from JSON file."""
    if not os.path.exists(path):
        logger.error("Config file not found: %s", path)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def build_device_dict(router: dict, creds: dict) -> dict:
    """Build Netmiko device connection dictionary."""
    mgmt_ifaces = router.get("management_interfaces")
    if mgmt_ifaces is None:
        mgmt_ifaces = router.get("interfaces", {})

    if not mgmt_ifaces:
        raise ValueError(f"no management interfaces defined for {router}")

    for _name, cfg in mgmt_ifaces.items():
        ip = cfg.get("ip")
        if ip:
            break
    else:
        raise ValueError(f"no usable IP address in {mgmt_ifaces}")

    device = {
        "device_type": "cisco_ios",
        "host": ip,
        "username": creds.get("username"),
        "password": creds.get("password"),
        "secret": creds.get("secret"),
    }
    return device


def get_lsa_database(device: dict, router_name: str) -> tuple[bool, str]:
    """
    Connect to router and retrieve OSPF LSA database.
    Returns (success, output) tuple.
    """
    logger.info("connecting to %s (%s)", router_name, device.get("host"))
    try:
        conn = ConnectHandler(**device)
        if device.get("secret"):
            conn.enable()
        
        # Get the LSA database
        output = conn.send_command("show ip ospf database")
        
        logger.info("successfully retrieved LSA database from %s", router_name)
        conn.disconnect()
        return True, output
    except Exception as e:
        logger.error("error getting LSA database from %s: %s", router_name, e)
        return False, str(e)


def save_output(router_name: str, output: str) -> str:
    """Save output to timestamp file and return filepath."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{router_name}_LSA_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(f"OSPF LSA Database from {router_name}\n")
        f.write(f"Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        f.write(output)
    
    logger.info("saved output to %s", filename)
    return filename


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base, "router_config.json")
    data = load_config(config_path)

    creds = data.get("credentials", {})
    if not creds:
        logger.error("credentials not defined in config file")
        sys.exit(1)

    routers = data.get("routers", [])
    if not routers:
        logger.error("no routers defined in config file")
        sys.exit(1)

    logger.info("loaded %d routers from %s", len(routers), config_path)

    # Find R1 and R5 (or 5R1 and 5R5)
    target_routers = {}
    for router in routers:
        router_name = router.get("RouterName", "")
        if "R1" in router_name or router_name == "5R1":
            target_routers["R1"] = router
        elif "R5" in router_name or router_name == "5R5":
            target_routers["R5"] = router

    if not target_routers:
        logger.error("could not find R1 and/or R5 in router configuration")
        sys.exit(1)

    logger.info("found %d target routers: %s", len(target_routers), list(target_routers.keys()))

    # Retrieve LSA database from each target router
    for label, router in sorted(target_routers.items()):
        try:
            device = build_device_dict(router, creds)
            router_name = router.get("RouterName", label)
            success, output = get_lsa_database(device, router_name)
            
            if success:
                filepath = save_output(label, output)
                logger.info("LSA database saved for %s to %s", label, filepath)
            else:
                logger.error("failed to retrieve LSA database from %s", label)
        except ValueError as ve:
            logger.warning("skipping router due to config issue: %s", ve)
            continue

    logger.info("LSA database retrieval complete")


if __name__ == "__main__":
    main()
