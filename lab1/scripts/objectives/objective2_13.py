import os
import time
import datetime
from netmiko import ConnectHandler

def main():
    router4 = {
        "device_type": "cisco_ios",
        "host": "10.0.0.4",
        "username": "cisco",
        "password": "lab123",
        "secret": "lab123",
        "global_delay_factor": 2,
    }

    target_ip = "17.17.17.5"
    source_ip = "17.17.17.4"

    print(f"Connecting to Router 4 ({router4['host']})...")
    conn = ConnectHandler(**router4)
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
        out = conn.send_command(f"ping {target_ip} repeat 1 timeout 1 source {source_ip}", expect_string=r"#", read_timeout=300)
        success = "!" in out
        return success, out, now

    print("Sending pre-failure pings (5 iterations)...")
    for _ in range(5):
        succ, out, ts = run_ping()
        status = "SUCCESS" if succ else "FAIL"
        clean_out = out.replace("\n", " | ").replace("\r", "")
        log_rows.append(f"{ts.strftime('%H:%M:%S')}\t\t{status}\t{clean_out}")
        debug_log.append(f"[{ts}] Ping Output & Debugs: {out}")
        time.sleep(1)

    router3 = {
        "device_type": "cisco_ios",
        "host": "10.0.0.3",
        "username": "cisco",
        "password": "lab123",
        "secret": "lab123",
        "global_delay_factor": 2,
    }
    print("Shutdown R3...")
    conn3 = ConnectHandler(**router3)
    conn3.enable()
    conn3.send_config_set(["interface Gi0/0", "shutdown", "interface Serial0/0/0", "shutdown"])
    conn3.disconnect()

    fail_time = datetime.datetime.now()
    log_rows.append(f"--- R3 SHUTDOWN AT {fail_time.strftime('%H:%M:%S')} ---")
    debug_log.append(f"--- R3 SHUTDOWN INITIATED AT {fail_time} ---")

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

    print("Bringing R3 back up...")
    conn.send_config_set(["interface Gi0/0", "no shutdown"])
    
    conn.send_command_timing("no debug all")
    conn.send_command_timing("terminal no monitor")
    conn.disconnect()

    with open("R3_shutdown_failover_log.txt", "w") as f:
        f.write("\n".join(log_rows) + "\n")
        
    with open("R3_shutdown_debug_failover.txt", "w") as f:
        f.write("\n".join(debug_log) + "\n")

    print("Bringing R3 back up...")
    conn3 = ConnectHandler(**router3)
    conn3.enable()
    conn3.send_config_set(["interface Gi0/0", "no shutdown", "interface Serial0/0/0", "no shutdown"])
    conn3.disconnect()
        
    print("Logs written to vlan_failover_log.txt and vlan_debug_failover_r3.txt")

if __name__ == '__main__':
    main()
