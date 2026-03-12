#!/usr/bin/env python3
"""
Lab 1 OSPF Automation
======================
Reads router_config.json for router IPs and credentials and then
connects via Netmiko to each box to configure OSPF.  The script removes
any existing RIP configuration ("no router rip") before enabling OSPF.

Backbone-facing links (the 200.200.200.0/24 network on Gi0/0 of R1 and
R5) are deliberately excluded from the OSPF process as required by the
lab instructions.

Usage:
    python configure_ospf.py
"""

import os
import sys
import json
import logging
import ipaddress
from typing import Iterable

# logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("configure_ospf.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)

try:
    from netmiko import ConnectHandler
except ImportError as exc:
    logger.error("Netmiko is required to run this script: %s", exc)
    sys.exit(1)


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        logger.error("Config file not found: %s", path)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def build_device_dict(router: dict, creds: dict) -> dict:
    # identical to configure_rip.build_device_dict
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


def compute_ospf_networks(routers: Iterable[dict]) -> dict[str, str]:
    """Return dict of network addresses to wildcard masks for OSPF.

    Management interfaces are skipped.  Additionally, any network whose
    address falls inside 200.200.200.0/24 is treated as a backbone link
    and excluded per the assignment.
    """
    networks: dict[str, str] = {}
    backbone_net = ipaddress.IPv4Network("200.200.200.0/24")
    for r in routers:
        for ifname, cfg in r.get("interfaces", {}).items():
            # ignore management
            if ifname.lower() == "gi0/1":
                continue
            ip = cfg.get("ip")
            mask = cfg.get("subnet")
            if not ip or not mask:
                continue
            try:
                net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
            except Exception as e:
                logger.warning("skipping invalid address %s/%s: %s", ip, mask, e)
                continue
            if net.subnet_of(backbone_net):
                # backbone-facing link; do not include
                continue
            # Calculate wildcard mask as inverse of netmask
            wildcard_int = int(ipaddress.IPv4Address("255.255.255.255")) - int(net.netmask)
            wildcard = str(ipaddress.IPv4Address(wildcard_int))
            networks[str(net.network_address)] = wildcard
    return networks


def build_ospf_commands(networks: dict[str, str]) -> list[str]:
    cmds = [
        "no router rip",          # remove existing RIP
        "no router ospf 1",
        "router ospf 1",
        # we could add additional OSPF settings here if desired
    ]
    for net in sorted(networks.keys()):
        # Use the wildcard mask calculated for each network's actual subnet
        wildcard = networks[net]
        cmds.append(f"network {net} {wildcard} area 0")
    cmds.append("exit")
    return cmds


def configure_router(device: dict, commands: Iterable[str]) -> None:
    logger.info("connecting to %s", device.get("host"))
    try:
        conn = ConnectHandler(**device)
        if device.get("secret"):
            conn.enable()
        output = conn.send_config_set(commands)
        logger.info("applied config to %s:\n%s", device.get("host"), output)
    except Exception as e:
        logger.error("error configuring %s: %s", device.get("host"), e)
    finally:
        try:
            conn.disconnect()
        except Exception:
            pass


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

    networks = compute_ospf_networks(routers)
    if not networks:
        logger.error("no networks could be calculated from router interfaces")
        sys.exit(1)

    ospf_cmds = build_ospf_commands(networks)
    logger.info("OSPF commands:\n%s", "\n".join(ospf_cmds))

    for router in routers:
        try:
            device = build_device_dict(router, creds)
        except ValueError as ve:
            logger.warning("skipping router due to config issue: %s", ve)
            continue
        configure_router(device, ospf_cmds)


if __name__ == "__main__":
    main()
