#!/usr/bin/env python3
"""Rebuild ``lab1/router_config.json`` by querying the
actual routers over SSH.

Each device is contacted via its management interface (Gi0/1), so
that address must already exist in the configuration.  The script
runs IOS commands to discover every IP address assigned to the
router and writes the results back into the JSON file.

Key points:

* ``management_interfaces`` will contain only the Gi0/1 entry used
  for SSH.  The value is refreshed if the router reports a
  different address.
* ``interfaces`` lists all *other* interfaces with an IP address,
  including their subnet masks (pulled from running configuration).

Because the information is collected live, the lab0 inventory is no
longer needed; this script reads the existing JSON only for
management addresses and credentials.  Netmiko must be installed to
run the queries.

Usage::

    cd lab1
    python update_router_config.py
"""

import json
import os
import sys
from typing import Dict, Any, Optional, Tuple

# netmiko is imported lazily so the module can be edited even when
# not installed (useful for static analysis in the editor).
try:
    from netmiko import ConnectHandler
except ImportError:
    ConnectHandler = None  # type: ignore


def load_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


# the name-mapping logic is no longer used; keep the helper for
# backwards compatibility or future use.
def normalize_lab0_name(name: str) -> str:
    """Identity function (left in place for legacy reasons)."""
    return name


def main() -> None:
    base = os.path.dirname(os.path.abspath(__file__))
    lab1_path = os.path.join(base, "router_config.json")
    if not os.path.exists(lab1_path):
        print("lab1/router_config.json not found", file=sys.stderr)
        sys.exit(1)

    lab1 = load_json(lab1_path)

    if ConnectHandler is None:
        print("netmiko is required to query routers; please install it", file=sys.stderr)
        sys.exit(1)

    creds = lab1.get("credentials", {})
    routers = lab1.get("routers", [])
    if not routers:
        print("no routers defined in config file", file=sys.stderr)
        sys.exit(1)

    # iterate each router, log in via its current management address,
    # and collect interface info
    for r in routers:
        mgmt_ifaces = r.get("management_interfaces") or r.pop("interfaces", {})
        # ensure management_interfaces key exists
        r["management_interfaces"] = mgmt_ifaces

        mgmt_ip = None
        for cfg in mgmt_ifaces.values():
            if cfg.get("ip"):
                mgmt_ip = cfg["ip"]
                break
        if not mgmt_ip:
            print(f"no management IP for router {r.get('RouterName')}, skipping", file=sys.stderr)
            r["interfaces"] = {}
            continue

        device = {
            "device_type": "cisco_ios",
            "host": mgmt_ip,
            "username": creds.get("username"),
            "password": creds.get("password"),
            "secret": creds.get("secret"),
        }

        try:
            conn = ConnectHandler(**device)
            if device.get("secret"):
                conn.enable()
        except Exception as e:
            print(f"unable to connect to {mgmt_ip}: {e}", file=sys.stderr)
            r["interfaces"] = {}
            continue

        try:
            brief = conn.send_command("show ip interface brief")
        except Exception as e:
            print(f"error running show ip interface brief on {mgmt_ip}: {e}", file=sys.stderr)
            brief = ""

        # parse output lines, ignoring header
        interfaces: Dict[str, Dict[str, Optional[str]]] = {}
        for line in brief.splitlines():
            parts = line.split()
            if len(parts) < 2 or parts[1] == "unassigned" or parts[0].startswith("Interface"):
                continue
            name, ip_addr = parts[0], parts[1]
            # gather mask via additional command
            mask = None
            try:
                out = conn.send_command(f"show running-config interface {name} | include ip address")
                # expects something like: " ip address 10.0.0.5 255.255.255.252"
                for oline in out.splitlines():
                    tok = oline.strip().split()
                    # expect: ip address <ip> <mask>
                    if len(tok) >= 4 and tok[0] == "ip" and tok[1] == "address":
                        mask = tok[3]
                        break
            except Exception:
                mask = None

            # separate management iface
            if name.lower().startswith("gi0/1") or name.lower() == "gi0/1":
                # override management address if found differently
                r["management_interfaces"] = {name: {"ip": ip_addr, "subnet": mask or ""}}
            else:
                interfaces[name] = {"ip": ip_addr, "subnet": mask or ""}

        r["interfaces"] = interfaces

        try:
            conn.disconnect()
        except Exception:
            pass

    save_json(lab1_path, lab1)
    print(f"queried devices and updated {lab1_path}")


if __name__ == "__main__":
    main()
