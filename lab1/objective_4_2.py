#!/usr/bin/env python3
"""
Objective 4.2 redistribution automation.

This script enables mutual redistribution between RIP and OSPF on R2 and R3,
which act as the ASBRs between the OSPF domain and the RIP domain that
contains R4.
"""

import json
import logging
import os
import sys
from typing import Iterable

try:
    from netmiko import ConnectHandler
except ImportError as exc:
    print(f"Netmiko is required to run this script: {exc}")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("objective_4_2.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        logger.error("Config file not found: %s", path)
        sys.exit(1)
    with open(path, encoding="utf-8") as file_handle:
        return json.load(file_handle)


def build_device_dict(router: dict, creds: dict) -> dict:
    management_interfaces = router.get("management_interfaces") or {}
    if not management_interfaces:
        raise ValueError(f"no management interfaces defined for {router.get('RouterName')}")

    host_ip = None
    for interface_config in management_interfaces.values():
        host_ip = interface_config.get("ip")
        if host_ip:
            break

    if not host_ip:
        raise ValueError(f"no usable management IP for {router.get('RouterName')}")

    return {
        "device_type": "cisco_ios",
        "host": host_ip,
        "username": creds.get("username"),
        "password": creds.get("password"),
        "secret": creds.get("secret"),
    }


def build_router_commands(router_name: str) -> list[str]:
    loopback_ip = {
        "5R2": "17.17.17.2",
        "5R3": "17.17.17.3",
    }.get(router_name)

    if loopback_ip is None:
        raise ValueError(f"unsupported router for redistribution: {router_name}")

    return [
        "router ospf 1",
        "no area 5 stub",
        "redistribute rip subnets metric-type 2 metric 20",
        "exit",
        "router rip",
        "version 2",
        "no auto-summary",
        "passive-interface default",
        "no passive-interface GigabitEthernet0/0",
        "network 5.0.234.0",
        f"network {loopback_ip}",
        "redistribute ospf 1 metric 2",
        "exit",
    ]


def configure_router(device: dict, commands: Iterable[str], router_name: str) -> None:
    logger.info("Connecting to %s (%s)", router_name, device.get("host"))
    connection = None
    try:
        connection = ConnectHandler(**device)
        if device.get("secret"):
            connection.enable()
        output = connection.send_config_set(list(commands))
        logger.info("Applied config to %s:\n%s", router_name, output)
    except Exception as exc:
        logger.error("Error configuring %s: %s", router_name, exc)
    finally:
        if connection is not None:
            try:
                connection.disconnect()
            except Exception:
                pass


def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "router_config.json")
    data = load_config(config_path)

    credentials = data.get("credentials", {})
    routers = data.get("routers", [])

    if not credentials:
        logger.error("credentials not defined in router_config.json")
        sys.exit(1)
    if not routers:
        logger.error("no routers defined in router_config.json")
        sys.exit(1)

    target_routers = {"5R2", "5R3"}

    for router in routers:
        router_name = router.get("RouterName")
        if router_name not in target_routers:
            continue

        try:
            device = build_device_dict(router, credentials)
            commands = build_router_commands(router_name)
        except ValueError as exc:
            logger.error("Skipping router due to config issue: %s", exc)
            continue

        logger.info("Commands for %s:\n%s", router_name, "\n".join(commands))
        configure_router(device, commands, router_name)


if __name__ == "__main__":
    main()