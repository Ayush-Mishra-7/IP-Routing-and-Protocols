#!/usr/bin/env python3
"""
Debug OSPF Neighbor Establishment on R2
========================================
This script captures the OSPF neighbor establishment process by:
1. Enabling debug on R2 BEFORE any OSPF configuration
2. Configuring OSPF on all routers (which will trigger neighbor state machine)
3. Waiting for neighbors to establish
4. Capturing and logging the debug output

The debug output shows the neighbor state transitions (Down -> Init -> 2-way -> ExStart -> Exchange -> Loading -> Full)
on the adjacency establishment process.

NOTE: All routers are configured in OSPF area 0 with no explicit router IDs,
meaning router IDs will be derived from the highest IP address on active interfaces.

Usage:
    python debug_ospf_neighbor_establishment.py

Output:
    debug_ospf_neighbor_establishment.log - Contains all debug output and neighbor status
"""

import os
import sys
import logging
import time

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("debug_ospf_neighbor_establishment.log", mode="w"),
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
        compute_ospf_networks,
        build_ospf_commands,
    )
except ImportError as exc:
    logger.error("Could not import from configure_ospf.py: %s", exc)
    sys.exit(1)


def enable_debug_on_r2(r2_device: dict) -> object:
    """Enable OSPF adjacency debugging on R2 and return connection object."""
    logger.info("\n" + "="*70)
    logger.info("STEP 1: Enabling OSPF Debug on R2")
    logger.info("="*70)
    
    try:
        logger.info("Connecting to R2 (%s)", r2_device.get("host"))
        r2_conn = ConnectHandler(**r2_device)
        
        if r2_device.get("secret"):
            r2_conn.enable()
        
        # Set up logging buffer to capture debug output
        logger.info("Configuring logging buffer on R2...")
        r2_conn.send_command("logging buffered 32768")  # 32KB buffer
        logger.info("Enabled logging buffer (32KB)")
        
        # Enable OSPF adjacency debugging
        logger.info("Enabling 'debug ospf adj' on R2...")
        debug_output = r2_conn.send_command("debug ospf adj")
        logger.info("Debug command sent. Ready to capture neighbor establishment.\n")
        
        return r2_conn
        
    except Exception as e:
        logger.error("Error enabling debug on R2: %s", e)
        sys.exit(1)


def configure_all_routers(routers: list, creds: dict, ospf_cmds: list[str]) -> None:
    """Configure OSPF on all routers."""
    logger.info("\n" + "="*70)
    logger.info("STEP 2: Configuring OSPF on All Routers")
    logger.info("="*70)
    
    for router in routers:
        router_name = router.get("RouterName")
        try:
            device = build_device_dict(router, creds)
        except ValueError as ve:
            logger.warning("Skipping %s: %s", router_name, ve)
            continue
        
        logger.info("Configuring %s (%s)...", router_name, device.get("host"))
        try:
            conn = ConnectHandler(**device)
            
            if device.get("secret"):
                conn.enable()
            
            # Send OSPF configuration
            output = conn.send_config_set(ospf_cmds)
            logger.info("✓ OSPF configured on %s", router_name)
            
            conn.disconnect()
            
        except Exception as e:
            logger.error("Error configuring %s: %s", router_name, e)
    
    logger.info("\n✓ OSPF configuration complete on all routers\n")


def wait_for_adjacency(wait_seconds: int = 35) -> None:
    """Wait for OSPF adjacencies to form."""
    logger.info("="*70)
    logger.info("STEP 3: Waiting for OSPF Neighbors to Establish")
    logger.info("="*70)
    logger.info("Waiting %d seconds for neighbor adjacencies to establish...", wait_seconds)
    logger.info("(OSPF Hello interval is typically 10 seconds on Ethernet)")
    logger.info("(Adjacency formation involves multiple state transitions)\n")
    
    for i in range(wait_seconds):
        remaining = wait_seconds - i
        if remaining % 5 == 0:
            logger.info("  ... %d seconds remaining", remaining)
        time.sleep(1)


def capture_and_analyze_debug(r2_conn: object, r2_device: dict) -> None:
    """Disable debug, capture buffer, and display results."""
    logger.info("\n" + "="*70)
    logger.info("STEP 4: Capturing Debug Output and OSPF Status")
    logger.info("="*70)
    
    try:
        # Disable debug
        logger.info("Disabling debug...")
        undebug_output = r2_conn.send_command("undebug all")
        logger.info("✓ Debug disabled\n")
        
        # Get logging buffer contents (debug messages captured)
        logger.info("-"*70)
        logger.info("OSPF ADJACENCY DEBUG OUTPUT (from logging buffer)")
        logger.info("-"*70)
        buffer_output = r2_conn.send_command("show logging")
        logger.info("%s\n", buffer_output)
        
        # Show OSPF neighbor status
        logger.info("-"*70)
        logger.info("OSPF NEIGHBOR STATUS ON R2")
        logger.info("-"*70)
        neighbors = r2_conn.send_command("show ip ospf neighbor")
        logger.info("%s\n", neighbors)
        
        # Show OSPF neighbor details
        logger.info("-"*70)
        logger.info("OSPF NEIGHBOR DETAILS (verbose)")
        logger.info("-"*70)
        neighbor_details = r2_conn.send_command("show ip ospf neighbor verbose")
        logger.info("%s\n", neighbor_details)
        
        # Show OSPF process information
        logger.info("-"*70)
        logger.info("OSPF PROCESS INFORMATION ON R2")
        logger.info("-"*70)
        ospf_info = r2_conn.send_command("show ip ospf")
        logger.info("%s\n", ospf_info)
        
        # Show OSPF interface status
        logger.info("-"*70)
        logger.info("OSPF INTERFACE STATUS ON R2")
        logger.info("-"*70)
        interface_status = r2_conn.send_command("show ip ospf interface brief")
        logger.info("%s\n", interface_status)
        
        r2_conn.disconnect()
        logger.info("Disconnected from R2\n")
        
    except Exception as e:
        logger.error("Error capturing output: %s", e)


def print_analysis_explanation() -> None:
    """Print explanation of OSPF neighbor establishment stages."""
    logger.info("\n" + "="*70)
    logger.info("OSPF NEIGHBOR ESTABLISHMENT EXPLANATION")
    logger.info("="*70)
    
    explanation = """
The OSPF neighbor establishment process goes through multiple states:

1. DOWN
   - Initial state when no Hello packets have been received from the neighbor
   - OSPF process is running but no communication with neighbor yet

2. INIT
   - Router has received at least one Hello packet from the neighbor
   - BUT the receiving router's own router ID is NOT in neighbor's Hello packet yet
   - One-way communication is happening (asymmetric)

3. 2-WAY
   - Both routers have seen each other's Hello packets
   - The receiving router sees its own router ID in the neighbor's Hello packet
   - Bidirectional communication is established (symmetric)
   - THIS IS THE KEY POINT: After this stage, routers decide if they will form an adjacency
   - On multi-access networks (Ethernet), only DR and BDR form full adjacencies with all routers

4. EXSTART
   - Routers are negotiating DBD (Database Descriptor) exchange parameters
   - Master/Slave relationship is established based on router IDs
   - Higher router ID becomes the Master (controls DBD sequence numbers)

5. EXCHANGE
   - Database Descriptor (DBD) packets are exchanged
   - Each router sends a summary of its link state database
   - Routers identify which LSAs they need to request

6. LOADING
   - Link State Request (LSR) packets are sent
   - Link State Update (LSU) packets are received and processed
   - Full Link State Database synchronization in progress

7. FULL
   - Adjacency is fully established and operational
   - Both routers have synchronized link state databases
   - Routing can now occur through this adjacency
   - Routers are updated when topology changes occur

TIMELINE EXAMPLE:
- Before OSPF config: DOWN (no routes advertising OSPF yet)
- Immediate after config on R2: DOWN (no neighbors configured yet)
- When other routers start OSPF: Hellos arrive → INIT state
- Exchange of Hellos completes: 2-WAY state
- DBD negotiation: EXSTART → EXCHANGE
- Database sync: LOADING
- Complete: FULL (neighbor fully adjacent)

The debug output in the log shows these state transitions as they happen,
revealing the exact sequence and timing of neighbor establishment.
"""
    
    logger.info(explanation)


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
    
    # Compute networks and build commands
    networks = compute_ospf_networks(routers)
    if not networks:
        logger.error("No networks could be calculated from router interfaces")
        sys.exit(1)
    
    logger.info("Networks to be advertised in OSPF (area 0):")
    for net in sorted(networks):
        logger.info("  - %s/24", net)
    logger.info("")
    
    ospf_cmds = build_ospf_commands(networks)
    logger.info("OSPF commands to be applied:")
    for cmd in ospf_cmds:
        logger.info("  > %s", cmd)
    logger.info("")
    
    # Find R2 router
    r2_router = None
    for r in routers:
        if r.get("RouterName") == "5R2":
            r2_router = r
            break
    
    if not r2_router:
        logger.error("Could not find 5R2 in configuration")
        sys.exit(1)
    
    logger.info("Target debug router: %s\n", r2_router.get("RouterName"))
    
    # STEP 1: Enable debug on R2
    r2_device = build_device_dict(r2_router, creds)
    r2_conn = enable_debug_on_r2(r2_device)
    
    # STEP 2: Configure OSPF on all routers
    configure_all_routers(routers, creds, ospf_cmds)
    
    # STEP 3: Wait for neighbors to establish
    wait_for_adjacency(35)
    
    # STEP 4: Capture and display results
    capture_and_analyze_debug(r2_conn, r2_device)
    
    # STEP 5: Print explanation
    print_analysis_explanation()
    
    logger.info("\n" + "="*70)
    logger.info("DEBUG CAPTURE COMPLETE")
    logger.info("="*70)
    logger.info("Results saved to: debug_ospf_neighbor_establishment.log")
    logger.info("="*70)


if __name__ == "__main__":
    main()
