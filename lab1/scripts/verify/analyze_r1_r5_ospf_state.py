#!/usr/bin/env python3
"""Collect and compare OSPF LSDB and routing-table output for R1 and R5.

This script connects to routers 5R1 and 5R5 using the management IPs in
router_config.json, gathers OSPF database and routing-table output, and writes
both the raw command output and a short comparison summary to a timestamped
report file.

Usage:
    python analyze_r1_r5_ospf_state.py
"""

import json
import os
import re
import sys
from datetime import datetime

try:
    from netmiko import ConnectHandler
except ImportError as exc:
    print(f"Netmiko is required to run this script: {exc}", file=sys.stderr)
    sys.exit(1)


TARGET_ROUTERS = ("5R1", "5R5")
COMMANDS = {
    "ospf_database": "show ip ospf database",
    "route_table": "show ip route",
    "ospf_routes": "show ip route ospf",
}


def load_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, encoding="utf-8") as handle:
        return json.load(handle)


def build_device(router: dict, credentials: dict) -> dict:
    management_interfaces = router.get("management_interfaces") or router.get("interfaces", {})
    for cfg in management_interfaces.values():
        ip_address = cfg.get("ip")
        if ip_address:
            return {
                "device_type": "cisco_ios",
                "host": ip_address,
                "username": credentials.get("username"),
                "password": credentials.get("password"),
                "secret": credentials.get("secret"),
            }
    raise ValueError(f"No usable management IP found for {router.get('RouterName', 'unknown router')}")


def extract_sections(ospf_database_output: str) -> dict[str, int]:
    return {
        "router_lsa": len(re.findall(r"Router Link States", ospf_database_output)),
        "network_lsa": len(re.findall(r"Net Link States", ospf_database_output)),
        "summary_lsa": len(re.findall(r"Summary Net Link States", ospf_database_output)),
        "summary_asbr_lsa": len(re.findall(r"Summary ASB Link States", ospf_database_output)),
        "external_lsa": len(re.findall(r"Type-5 AS External Link States", ospf_database_output)),
        "nssa_external_lsa": len(re.findall(r"Type-7 AS External Link States", ospf_database_output)),
    }


def summarize_routes(route_output: str, ospf_route_output: str) -> dict[str, object]:
    route_lines = [line.strip() for line in route_output.splitlines()]
    ospf_lines = [line.strip() for line in ospf_route_output.splitlines()]
    ospf_entries = [line for line in ospf_lines if line.startswith("O") or line.startswith("O*")]
    return {
        "has_gateway_of_last_resort": any("Gateway of last resort" in line for line in route_lines),
        "has_ospf_default": any(line.startswith("O*IA") or line.startswith("O*E") or line.startswith("O*N") for line in ospf_entries),
        "intra_area_routes": sum(1 for line in ospf_entries if line.startswith("O ")),
        "inter_area_routes": sum(1 for line in ospf_entries if line.startswith("O IA")),
        "external_routes": sum(1 for line in ospf_entries if line.startswith("O E") or line.startswith("O N")),
        "route_count": len(ospf_entries),
    }


def collect_router_state(device: dict) -> dict[str, str]:
    connection = ConnectHandler(**device)
    try:
        if device.get("secret"):
            connection.enable()
        return {name: connection.send_command(command, read_timeout=60) for name, command in COMMANDS.items()}
    finally:
        connection.disconnect()


def build_comparison(results: dict[str, dict[str, object]]) -> str:
    r1 = results.get("5R1", {})
    r5 = results.get("5R5", {})

    lines = [
        "Comparison Summary",
        "==================",
        "Both R1 and R5 should look very similar because each router is acting as an ABR between backbone area 0 and stub area 5.",
        "",
        f"R1 route counts: {r1.get('route_summary', {}).get('route_count', 'n/a')} OSPF routes, "
        f"{r1.get('route_summary', {}).get('inter_area_routes', 'n/a')} inter-area, "
        f"{r1.get('route_summary', {}).get('external_routes', 'n/a')} external.",
        f"R5 route counts: {r5.get('route_summary', {}).get('route_count', 'n/a')} OSPF routes, "
        f"{r5.get('route_summary', {}).get('inter_area_routes', 'n/a')} inter-area, "
        f"{r5.get('route_summary', {}).get('external_routes', 'n/a')} external.",
        "",
        "Expected interpretation:",
        "1. The LSDB should not contain Type-5 external LSAs for the stub area because stub areas block external LSAs.",
        "2. R1 and R5 may still show area-0 LSAs for the 200.200.200.0/24 backbone segment in addition to summary information for area 5 because they border both areas.",
        "3. If a default route appears as O*IA, that is normal for stub-area behavior: the ABR injects a default route instead of flooding external LSAs into the stub area.",
        "4. Any remaining differences between R1 and R5 are usually local-interface differences, such as their directly connected loopback or serial networks and which specific next hop is used toward the opposite side of the topology.",
    ]

    for router_name in TARGET_ROUTERS:
        router_result = results.get(router_name, {})
        lsa_summary = router_result.get("lsa_summary", {})
        route_summary = router_result.get("route_summary", {})
        lines.extend(
            [
                "",
                f"{router_name} quick summary:",
                f"- Router LSA sections found: {lsa_summary.get('router_lsa', 'n/a')}",
                f"- Network LSA sections found: {lsa_summary.get('network_lsa', 'n/a')}",
                f"- Summary LSA sections found: {lsa_summary.get('summary_lsa', 'n/a')}",
                f"- External LSA sections found: {lsa_summary.get('external_lsa', 'n/a')}",
                f"- Has OSPF default route: {route_summary.get('has_ospf_default', 'n/a')}",
                f"- Has gateway of last resort: {route_summary.get('has_gateway_of_last_resort', 'n/a')}",
            ]
        )

    return "\n".join(lines)


def write_report(report_path: str, results: dict[str, dict[str, object]]) -> None:
    with open(report_path, "w", encoding="utf-8") as handle:
        for router_name in TARGET_ROUTERS:
            router_result = results[router_name]
            device_host = router_result["host"]
            handle.write(f"=== {router_name} ({device_host}) ===\n\n")
            handle.write("--- show ip ospf database ---\n")
            handle.write(router_result["raw"]["ospf_database"])
            handle.write("\n\n--- show ip route ---\n")
            handle.write(router_result["raw"]["route_table"])
            handle.write("\n\n--- show ip route ospf ---\n")
            handle.write(router_result["raw"]["ospf_routes"])
            handle.write("\n\n")
        handle.write(build_comparison(results))
        handle.write("\n")


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

    results: dict[str, dict[str, object]] = {}

    for router_name in TARGET_ROUTERS:
        router = routers[router_name]
        try:
            device = build_device(router, credentials)
            print(f"Collecting OSPF state from {router_name} at {device['host']}...")
            raw_output = collect_router_state(device)
        except Exception as exc:
            print(f"Failed to collect data from {router_name}: {exc}", file=sys.stderr)
            return 1

        results[router_name] = {
            "host": device["host"],
            "raw": raw_output,
            "lsa_summary": extract_sections(raw_output["ospf_database"]),
            "route_summary": summarize_routes(raw_output["route_table"], raw_output["ospf_routes"]),
        }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(base_dir, f"r1_r5_ospf_state_{timestamp}.txt")
    write_report(report_path, results)

    print(f"Wrote report to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())