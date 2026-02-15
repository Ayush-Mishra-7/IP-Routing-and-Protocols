
# Loopback IPs per router (keyed by RouterName)
LOOPBACK_IPS = {
    "R1": "11.11.11.11",
    "R2": "22.22.22.22",
    "R3": "33.33.33.33",
    "R4": "44.44.44.44",
}

def build_router_commands(router_name: str, router: dict) -> list[str]:
    """Generate IOS configuration commands for a single router.

    Configures:
      1. Loopback0 with the pre-defined IP (/32)
      2. Every interface listed in routers_config.json with its IP + mask
      3. 'no shutdown' on every interface
    """
    commands: list[str] = []

    # --- Loopback0 ---------------------------------------------------------
    loopback_ip = LOOPBACK_IPS.get(router_name)
    if loopback_ip:
        commands += [
            "interface Loopback0",
            f"ip address {loopback_ip} 255.255.255.255",
            "no shutdown",
            "exit",
        ]

    # --- Physical / Serial interfaces -------------------------------------
    for intf_name, intf_cfg in router.get("interfaces", {}).items():
        ip = intf_cfg["ip"]
        mask = intf_cfg["subnet"]
        commands += [
            f"interface {intf_name}",
            f"ip address {ip} {mask}",
            "no shutdown",
            "exit",
        ]

    return commands
