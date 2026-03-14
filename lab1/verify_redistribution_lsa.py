#!/usr/bin/env python3
"""
Collect evidence for redistributed RIP routes on R1 and R5.

The report captures the external OSPF LSDB and the external OSPF routes so it
is easy to answer Questions 4.2 and 4.3 with current router output.
"""

import json
import os
import sys
from datetime import datetime

try:
    from netmiko import ConnectHandler
except ImportError as exc:
    print(f"Netmiko is required to run this script: {exc}", file=sys.stderr)
    sys.exit(1)


TARGET_ROUTERS = ("5R1", "5R5")
COMMANDS = {
    "external_lsdb": "show ip ospf database external",
    "ospf_routes": "show ip route ospf",
    "route_r4": "show ip route 17.17.17.4",
}


def load_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, encoding="utf-8") as handle:
        return json.load(handle)


def build_device(router: dict, credentials: dict) -> dict:
    management_interfaces = router.get("management_interfaces") or router.get("interfaces", {})
    for config in management_interfaces.values():
        ip_address = config.get("ip")
        if ip_address:
            return {
                "device_type": "cisco_ios",
                "host": ip_address,
                "username": credentials.get("username"),
                "password": credentials.get("password"),
                "secret": credentials.get("secret"),
            }
    raise ValueError(f"No usable management IP found for {router.get('RouterName', 'unknown router')}")


def collect_router_state(device: dict) -> dict[str, str]:
    connection = ConnectHandler(**device)
    try:
        if device.get("secret"):
            connection.enable()
        return {name: connection.send_command(command, read_timeout=60) for name, command in COMMANDS.items()}
    finally:
        connection.disconnect()


def write_report(report_path: str, results: dict[str, dict[str, str]]) -> None:
    with open(report_path, "w", encoding="utf-8") as handle:
        for router_name in TARGET_ROUTERS:
            output = results[router_name]
            handle.write(f"=== {router_name} ===\n\n")
            handle.write("--- show ip ospf database external ---\n")
            handle.write(output["external_lsdb"])
            handle.write("\n\n--- show ip route ospf ---\n")
            handle.write(output["ospf_routes"])
            handle.write("\n\n--- show ip route 17.17.17.4 ---\n")
            handle.write(output["route_r4"])
            handle.write("\n\n")


def main() -> int:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "router_config.json")

    try:
        config = load_config(config_path)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    credentials = config.get("credentials", {})
    routers = {router.get("RouterName"): router for router in config.get("routers", [])}

    missing = [name for name in TARGET_ROUTERS if name not in routers]
    if missing:
        print(f"Missing router definitions: {', '.join(missing)}", file=sys.stderr)
        return 1

    results: dict[str, dict[str, str]] = {}
    for router_name in TARGET_ROUTERS:
        try:
            device = build_device(routers[router_name], credentials)
            print(f"Collecting redistribution evidence from {router_name} at {device['host']}...")
            results[router_name] = collect_router_state(device)
        except Exception as exc:
            print(f"Failed to collect data from {router_name}: {exc}", file=sys.stderr)
            return 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(base_dir, f"redistribution_lsa_report_{timestamp}.txt")
    write_report(report_path, results)
    print(f"Wrote report to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())