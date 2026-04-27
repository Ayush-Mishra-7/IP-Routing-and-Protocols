import os
import time
import datetime
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

    target_ip = "17.17.17.4"
    source_interface = "Loopback0"

    print(f"Connecting to Router 3 ({router3['host']})...")
    conn = ConnectHandler(**router3)
    conn.enable()

    print("Enabling debugging...")
    conn.send_command_timing("terminal monitor")
    conn.send_command_timing("debug ip routing")
    conn.send_command_timing("debug ip rip")

    log_rows = ["Time\t\t\tStatus\tOutput"]
    log_rows.append("-" * 80)
    debug_log = []

    def run_ping():
        now = datetime.datetime.now()
        out = conn.send_command_timing(f"ping {target_ip} source {source_interface} repeat 1 timeout 1")
        success = "!" in out
        return success, out, now

    print(f"Sending pre-failure pings (5 iterations) to {target_ip} from {source_interface}...")
    for _ in range(5):
        succ, out, ts = run_ping()
        status = "SUCCESS" if succ else "FAIL"
        clean_out = out.replace("\n", " | ").replace("\r", "")
        log_rows.append(f"{ts.strftime('%H:%M:%S')}\t\t{status}\t{clean_out}")
        debug_log.append(f"[{ts}] Ping Output & Debugs: {out}")
        time.sleep(1)

    print("Simulating VLAN change by shutting down GigabitEthernet0/0 on R3...")
    conn.send_config_set(["interface GigabitEthernet0/0", "shutdown"])
    fail_time = datetime.datetime.now()
    log_rows.append(f"--- R3 SUBNET 2 INTERFACE MOVED TO NEW VLAN AT {fail_time.strftime('%H:%M:%S')} ---")
    debug_log.append(f"--- R3 SUBNET 2 INTERFACE MOVED TO NEW VLAN AT {fail_time} ---")

    print("Pinging continuously until recovery...")
    consecutive_success = 0
    recovery_time = None
    
    while True:
        succ, out, ts = run_ping()
        status = "SUCCESS" if succ else "FAIL"
        clean_out = out.replace("\n", " | ").replace("\r", "")
        log_rows.append(f"{ts.strftime('%H:%M:%S')}\t\t{status}\t{clean_out}")
        debug_log.append(f"[{ts}] {out}")

        if succ:
            consecutive_success += 1
            if consecutive_success >= 3:
                recovery_time = ts
                break
        else:
            consecutive_success = 0
            
        if (ts - fail_time).total_seconds() > 300:
            print("Timeout reached waiting for recovery.")
            break
        
        time.sleep(1)

    if recovery_time:
        downtime = (recovery_time - fail_time).total_seconds()
        print(f"Network recovered after ~{downtime} seconds.")
        log_rows.append(f"--- NETWORK RECOVERED. APPROX DOWNTIME: {downtime} seconds ---")
    
    print("Capturing trailing debugs...")
    for _ in range(3):
        out = conn.send_command_timing("\n")
        if out.strip():
            debug_log.append(f"[{datetime.datetime.now()}] {out}")
        time.sleep(1)

    print("Bringing GigabitEthernet0/0 back up...")
    conn.send_config_set(["interface GigabitEthernet0/0", "no shutdown"])
    
    conn.send_command_timing("no debug all")
    conn.send_command_timing("terminal no monitor")
    conn.disconnect()

    with open("vlan_failover_log.txt", "w") as f:
        f.write("\n".join(log_rows) + "\n")
        
    with open("debug_failover_vlan_r3.txt", "w") as f:
        f.write("\n".join(debug_log) + "\n")
        
    print("Logs written to vlan_failover_log.txt and debug_failover_vlan_r3.txt")

if __name__ == '__main__':
    main()
