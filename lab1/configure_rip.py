#!/usr/bin/env python3
"""
Lab 1 RIPv2 Automation
======================
Reads router_config.json for router IPs and credentials and then
connects via Netmiko to each box to configure RIPv2.

The config file has been reorganized so that the original
management interface addresses (previously under `interfaces`)
are now stored in a separate `management_interfaces` key.  The
`interfaces` section contains all data interfaces that should be
advertised by RIP.

Usage:
    python configure_rip.py
"""

import os
import sys
import json
import logging
import ipaddress
from typing import Iterable, Dict

# logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("configure_rip.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)

# third-party import deferred to runtime so script can still be
# inspected even if Netmiko is not installed.
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
        data = json.load(f)
    return data


def build_device_dict(router: dict, creds: dict) -> dict:
    """Convert a router entry to a Netmiko device dict.

    The management interface definitions are now stored under
    ``management_interfaces``.  We still accept ``interfaces``
    for backwards compatibility, but ``management_interfaces`` is
    preferred.

    The caller should supply credentials separately.  The first
    IP address found on a management interface is used as the
    ``host`` field.
    """
    mgmt_ifaces = router.get("management_interfaces")
    if mgmt_ifaces is None:
        # fall back for older config files
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
        # default to ssh port 22, could be overriden if needed
    }
    return device


def compute_rip_networks(routers: Iterable[dict]) -> set[str]:
    """Return set of network addresses (string) for all interfaces.

    Management addresses (Gi0/1) are intentionally excluded even if they
    accidentally appear in the ``interfaces`` section.
    """
    networks: set[str] = set()
    for r in routers:
        for ifname, cfg in r.get("interfaces", {}).items():
            # don't advertise the management interface
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
            networks.add(str(net.network_address))
    return networks


def build_rip_commands(networks: Iterable[str]) -> list[str]:
    cmds = ["no router rip", "router rip", "version 2", "no auto-summary"]
    for net in sorted(networks):
        cmds.append(f"network {net}")
    cmds.append("exit")
    return cmds


def configure_router(device: dict, commands: Iterable[str]) -> None:
    logger.info("connecting to %s", device.get("host"))
    try:
        conn = ConnectHandler(**device)
        # enter enable if needed
        if "secret" in device and device["secret"]:
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

    networks = compute_rip_networks(routers)
    if not networks:
        logger.error("no networks could be calculated from router interfaces")
        sys.exit(1)

    rip_cmds = build_rip_commands(networks)
    logger.info("RIP commands:\n%s", "\n".join(rip_cmds))

    for router in routers:
        try:
            device = build_device_dict(router, creds)
        except ValueError as ve:
            logger.warning("skipping router due to config issue: %s", ve)
            continue
        configure_router(device, rip_cmds)


if __name__ == "__main__":
    main()
