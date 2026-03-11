import ipaddress

def get_static_route_commands(router_config: dict) -> list[str]:
    """
    Generate IOS static route commands for a single router based on its config.
    
    Args:
        router_config (dict): The configuration dictionary for a specific router,
                              containing a "static_routes" list.
                              
    Returns:
        list[str]: A list of 'ip route ...' commands.
    """
    commands: list[str] = []
    
    static_routes = router_config.get("static_routes", [])
    
    for route in static_routes:
        destination = route.get("destination")
        next_hop = route.get("next_hop")
        
        if not destination or not next_hop:
            continue
            
        try:
            # Parse network to get network address and netmask
            network = ipaddress.ip_network(destination, strict=False)
            network_addr = str(network.network_address)
            netmask = str(network.netmask)
            
            # command: ip route <network> <mask> <next_hop>
            cmd = f"ip route {network_addr} {netmask} {next_hop}"
            commands.append(cmd)
            
        except ValueError as e:
            # Handle invalid CIDR or IP formats gracefully
            # In a real script we might want to log this
            print(f"Error parsing static route {destination}: {e}")
            continue
            
    return commands
