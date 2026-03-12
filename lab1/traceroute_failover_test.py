import time
from netmiko import ConnectHandler

def main():
    router3 = {
        "device_type": "cisco_ios",
        "host": "10.0.0.3",
        "username": "cisco",
        "password": "lab123",
        "secret": "lab123",
        "global_delay_factor": 2,
    }

    target_ip = "5.0.34.2"

    print(f"Connecting to Router 3 ({router3['host']})...")
    conn = ConnectHandler(**router3)
    conn.enable()

    print(f"Running initial traceroute to {target_ip} before failure...")
    out_before = conn.send_command(f"traceroute {target_ip}")
    print("\n--- Traceroute Before Failure ---")
    print(out_before)
    print("---------------------------------\n")

    print("Shutting down Serial0/0/0 on R3...")
    conn.send_config_set(["interface Serial0/0/0", "shutdown"])
    
    # Wait for the network to converge based on previous ping test (~12-15 seconds)
    wait_time = 15
    print(f"Waiting {wait_time} seconds for the network to converge via alternate path...")
    time.sleep(wait_time)

    print(f"Running traceroute to {target_ip} after failure...")
    out_after = conn.send_command(f"traceroute {target_ip}")
    print("\n--- Traceroute After Failure ---")
    print(out_after)
    print("---------------------------------\n")

    print("Bringing Serial0/0/0 back up...")
    conn.send_config_set(["interface Serial0/0/0", "no shutdown"])
    
    conn.disconnect()

    log_filename = "traceroute_failover_log.txt"
    with open(log_filename, "w") as f:
        f.write("--- Traceroute Before Failure ---\n")
        f.write(out_before + "\n\n")
        f.write("--- Traceroute After Failure ---\n")
        f.write(out_after + "\n")
        
    print(f"Logs written to {log_filename}")

if __name__ == '__main__':
    main()
