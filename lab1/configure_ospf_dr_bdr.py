#!/usr/bin/env python3
"""
Configure OSPF DR/BDR Election
==============================
This script configures OSPF interface priorities to force a specific DR/BDR election:
- R2 (5R2): priority 200 (DESIGNATED ROUTER)
- R4 (5R4): priority 50 (BACKUP DESIGNATED ROUTER)
- R3 (5R3): priority 0 (NEVER competes - stays as DROther)
- R1, R5: default priority (DROther)

The priority is set on interfaces in the 5.0.234.0/24 multi-access network where
R2, R3, and R4 meet. Then 'clear ip ospf process' is run on all routers to force
a new election with the updated priorities.

Usage:
    python configure_ospf_dr_bdr.py

Output:
    configure_ospf_dr_bdr.log - Contains configuration steps and show command outputs
    Shows final DR/BDR status with:
    - show ip ospf neighbor
    - show ip ospf interface
    - show ip ospf
"""

import os
import sys
import json
import logging
import time

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("configure_ospf_dr_bdr.log", mode="w"),
    ],
)
logger = logging.getLogger(__name__)

try:
    from netmiko import ConnectHandler
except ImportError as exc:
    logger.error("Netmiko is required to run this script: %s", exc)
    sys.exit(1)

# Import shared utility functions from configure_ospf module
try:
    from configure_ospf import (
        load_config,
        build_device_dict,
    )
except ImportError as exc:
    logger.error("Could not import from configure_ospf.py: %s", exc)
    sys.exit(1)


def configure_interface_priority(router_name: str, device: dict, interface_name: str, priority: int) -> None:
    """Configure OSPF priority on a specific interface."""
    logger.info("Configuring priority %d on %s interface %s", priority, router_name, interface_name)
    
    try:
        conn = ConnectHandler(**device)
        
        if device.get("secret"):
            conn.enable()
        
        # Configure interface priority
        if router_name == '5R3':
            commands = [
            f"interface {interface_name}",
            "no ip ospf priority",  # Clear existing priority
            "exit",
            ]
        else:
            commands = [
                f"interface {interface_name}",
                "no ip ospf priority",  # Clear existing priority
                f"ip ospf priority {priority}",
                "exit",
            ]
        
        output = conn.send_config_set(commands)
        logger.info("✓ Priority %d set on %s %s\n%s", priority, router_name, interface_name, output)
        
        conn.disconnect()
        
    except Exception as e:
        logger.error("Error configuring priority on %s: %s", router_name, e)


def clear_ospf_process(router_name: str, device: dict) -> None:
    """Clear OSPF process to force new DR/BDR election."""
    logger.info("Clearing OSPF process on %s to force re-election...", router_name)
    
    try:
        conn = ConnectHandler(**device)
        
        if device.get("secret"):
            conn.enable()
        
        # Clear OSPF process (this will reset all adjacencies and force re-election)
        output = conn.send_command("clear ip ospf process")
        conn.send_command("yes")
        
        logger.info("✓ OSPF process cleared on %s\n%s", router_name, output)
        
        conn.disconnect()
        
    except Exception as e:
        logger.error("Error clearing OSPF process on %s: %s", router_name, e)


def show_ospf_status(router_name: str, device: dict) -> dict:
    """Retrieve and log OSPF DR/BDR status from a router."""
    logger.info("\n" + "-"*70)
    logger.info("OSPF STATUS ON %s", router_name)
    logger.info("-"*70)
    
    status = {}
    
    try:
        conn = ConnectHandler(**device)
        
        if device.get("secret"):
            conn.enable()
        
        # Disable paging
        conn.send_command("terminal length 0")
        
        # Get neighbor information
        logger.info("\nNeighbors on %s:", router_name)
        neighbors = conn.send_command("show ip ospf neighbor")
        logger.info("%s", neighbors)
        status["neighbors"] = neighbors
        
        # Get interface information
        logger.info("\nOSPF Interfaces on %s:", router_name)
        interfaces = conn.send_command("show ip ospf interface brief")
        logger.info("%s", interfaces)
        status["interfaces"] = interfaces
        
        # Get OSPF process information (shows router ID)
        logger.info("\nOSPF Process on %s:", router_name)
        ospf_info = conn.send_command("show ip ospf | include Router ID")
        logger.info("%s", ospf_info)
        status["ospf_info"] = ospf_info
        
        # Get detailed interface status showing priority and DR/BDR information
        logger.info("\nDetailed OSPF Interface Status on %s:", router_name)
        detailed = conn.send_command("show ip ospf interface")
        logger.info("%s", detailed)
        status["detailed"] = detailed
        
        conn.disconnect()
        
    except Exception as e:
        logger.error("Error retrieving OSPF status from %s: %s", router_name, e)
    
    return status


def main():
    """Main execution flow."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base, "router_config.json")
    
    # Load configuration
    logger.info("Loading configuration...")
    data = load_config(config_path)
    
    creds = data.get("credentials", {})
    if not creds:
        logger.error("Credentials not defined in config file")
        sys.exit(1)
    
    routers = data.get("routers", [])
    if not routers:
        logger.error("No routers defined in config file")
        sys.exit(1)
    
    logger.info("✓ Loaded %d routers from %s\n", len(routers), config_path)
    
    # Build a mapping of router names to their devices and interfaces
    router_map = {}
    for router in routers:
        name = router.get("RouterName")
        try:
            device = build_device_dict(router, creds)
            router_map[name] = {
                "device": device,
                "interfaces": router.get("interfaces", {}),
            }
        except ValueError as ve:
            logger.warning("Skipping %s: %s", name, ve)
    
    logger.info("\n" + "="*70)
    logger.info("STEP 1: Configure OSPF Interface Priorities")
    logger.info("="*70)
    
    # Configure R2 (5R2): priority 200 on data interfaces
    logger.info("\n>>> Configuring 5R2 (Designated Router - priority 200)")
    r2_info = router_map.get("5R2")
    if r2_info:
        for ifname in r2_info["interfaces"].keys():
            if ifname.lower() != "gi0/1":  # Skip management
                configure_interface_priority("5R2", r2_info["device"], ifname, 200)
    
    # Configure R4 (5R4): priority 50 on data interfaces
    logger.info("\n>>> Configuring 5R4 (Backup Designated Router - priority 50)")
    r4_info = router_map.get("5R4")
    if r4_info:
        for ifname in r4_info["interfaces"].keys():
            if ifname.lower() != "gi0/1":  # Skip management
                configure_interface_priority("5R4", r4_info["device"], ifname, 50)
    
    # Configure R3 (5R3): priority 0 on data interfaces (never competes)
    logger.info("\n>>> Configuring 5R3 (DROther - priority 0, never competes)")
    r3_info = router_map.get("5R3")
    if r3_info:
        for ifname in r3_info["interfaces"].keys():
            if ifname.lower() != "gi0/1":  # Skip management
                configure_interface_priority("5R3", r3_info["device"], ifname, 0)
    
    logger.info("\n" + "="*70)
    logger.info("STEP 2: Clear OSPF Process on All Routers")
    logger.info("="*70)
    logger.info("(This forces all OSPF adjacencies down and triggers new election)")
    
    for name, info in router_map.items():
        clear_ospf_process(name, info["device"])
        time.sleep(1)  # Small delay between router clears
    
    logger.info("\n" + "="*70)
    logger.info("STEP 3: Wait for OSPF Election to Complete")
    logger.info("="*70)
    logger.info("Waiting 45 seconds for neighbors to re-establish and elect DR/BDR...")
    
    for i in range(45):
        remaining = 45 - i
        if remaining % 15 == 0:
            logger.info("  ... %d seconds remaining", remaining)
        time.sleep(1)
    
    logger.info("\n✓ Election complete\n")
    
    logger.info("\n" + "="*70)
    logger.info("STEP 4: Display Final OSPF Configuration")
    logger.info("="*70)
    
    all_status = {}
    for name, info in router_map.items():
        all_status[name] = show_ospf_status(name, info["device"])
    
    logger.info("\n" + "="*70)
    logger.info("OSPF DR/BDR ELECTION SUMMARY")
    logger.info("="*70)
    
    summary = """
EXPECTED RESULTS:
=================
Network: 5.0.234.0/24 (connects R2, R3, R4)

Designated Router (DR):
  - 5R2 with priority 200 (highest priority)
  
Backup Designated Router (BDR):
  - 5R4 with priority 50 (second highest)
  
DROther routers:
  - 5R3 with priority 0 (never competes)
  - Other routers remain DROther with default priorities

Other networks (5.0.12.x, 5.0.34.x - point-to-point or different segments):
  - Will have their own DR/BDR elections
  - On point-to-point links, both routers become adjacent (no DR/BDR needed)

VERIFICATION:
=============
Check the output above for:
1. show ip ospf neighbor - shows DR/BDR roles and adjacency states
2. show ip ospf interface - shows priority, DR, BDR, and state (WAITING, BACKUP, DR)
3. show ip ospf - shows router ID and OSPF process info

Key indicators:
- R2 should show as "DR" on the 5.0.234.0/24 network
- R4 should show as "BDR" on the 5.0.234.0/24 network
- R3 should show as "DROTHER" (passive participant)
"""
    
    logger.info(summary)
    
    logger.info("\n" + "="*70)
    logger.info("CONFIGURATION COMPLETE")
    logger.info("="*70)
    logger.info("Results saved to: configure_ospf_dr_bdr.log")
    logger.info("="*70)


if __name__ == "__main__":
    main()
