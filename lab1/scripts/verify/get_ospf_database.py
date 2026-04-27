import json
from netmiko import ConnectHandler

def get_ospf_database():
    try:
        with open('router_config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: router_config.json not found in the current directory.")
        return

    credentials = config.get('credentials', {})
    routers = config.get('routers', [])

    # Filter to only get R1 and R5 (named 5R1 and 5R5 in the config)
    target_routers = [r for r in routers if r.get('RouterName') in ['5R1', '5R5']]

    if not target_routers:
        print("Could not find configuration for 5R1 or 5R5 in router_config.json.")
        return

    output_file = 'ospf_database.txt'

    with open(output_file, 'w') as out_f:
        for router in target_routers:
            r_name = router.get('RouterName')
            # Extract management IP
            try:
                ip = router['management_interfaces']['Gi0/1']['ip']
            except KeyError:
                print(f"Could not find management IP for {r_name}. Skipping.")
                continue

            device = {
                'device_type': 'cisco_ios',
                'host': ip,
                'username': credentials.get('username'),
                'password': credentials.get('password'),
                'secret': credentials.get('secret')
            }

            print(f"Connecting to {r_name} at {ip}...")
            try:
                connection = ConnectHandler(**device)
                connection.enable()
                
                # Send command to get OSPF database
                ospf_output = connection.send_command('show ip ospf database')
                route_output = connection.send_command('show ip route')
                
                out_f.write(f"--- OSPF Database for {r_name} ({ip}) ---\n")
                out_f.write(ospf_output)
                out_f.write("\n" + "="*50 + "\n\n")

                out_f.write(f"--- Routing Table for {r_name} ({ip}) ---\n")
                out_f.write(route_output)
                out_f.write("\n" + "="*50 + "\n\n")
                
                connection.disconnect()
                print(f"Successfully retrieved and saved OSPF database and routing table from {r_name}.")
            except Exception as e:
                print(f"Failed to connect or retrieve data from {r_name}: {e}")

if __name__ == "__main__":
    get_ospf_database()
