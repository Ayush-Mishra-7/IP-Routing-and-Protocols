import json
import threading
import time
from datetime import datetime
from netmiko import ConnectHandler

state = {
    'stop_pinging': False,
    'link_down': False,
    'link_down_time': None,
    'ping_results': []
}

def get_router_by_name(routers, name):
    for r in routers:
        if r.get('RouterName') == name:
            return r
    return None

def main():
    try:
        with open('router_config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: router_config.json not found in the current directory.")
        return

    credentials = config.get('credentials', {})
    routers = config.get('routers', [])

    r3_info = get_router_by_name(routers, '5R3')
    r5_info = get_router_by_name(routers, '5R5')

    if not r3_info or not r5_info:
        print("Could not find configuration for 5R3 or 5R5 in router_config.json.")
        return

    try:
        r3_ip = r3_info['management_interfaces']['Gi0/1']['ip']
        r5_ip = r5_info['management_interfaces']['Gi0/1']['ip']
        r5_loopback_ip = r5_info['interfaces']['Loopback0']['ip']
    except KeyError as e:
        print(f"Missing expected interface or IP in config: {e}")
        return

    r3_device = {
        'device_type': 'cisco_ios',
        'host': r3_ip,
        'username': credentials.get('username'),
        'password': credentials.get('password'),
        'secret': credentials.get('secret')
    }

    r5_device = {
        'device_type': 'cisco_ios',
        'host': r5_ip,
        'username': credentials.get('username'),
        'password': credentials.get('password'),
        'secret': credentials.get('secret')
    }

    def pinger():
        try:
            print(f"Connecting to R3 ({r3_ip}) to start pinging...")
            conn = ConnectHandler(**r3_device)
            conn.enable()
            
            consecutive_successes = 0
            
            while not state['stop_pinging']:
                start_time = datetime.now()
                # Sending a single ping with 1 second timeout
                output = conn.send_command(f"ping {r5_loopback_ip} repeat 1 timeout 1")
                end_time = datetime.now()
                
                # Check for "!" which usually indicates success in Cisco IOS
                success = "!" in output or "Success rate is 100 percent" in output
                
                timestamp = start_time.strftime('%H:%M:%S.%f')[:-3]
                duration_ms = (end_time - start_time).total_seconds() * 1000
                
                result = {
                    'timestamp': timestamp,
                    'duration_ms': duration_ms,
                    'success': success,
                }
                state['ping_results'].append(result)
                
                status_str = "SUCCESS" if success else "FAIL"
                print(f"[{timestamp}] Ping to {r5_loopback_ip}: {status_str} (Time: {duration_ms:.0f}ms)")
                
                if state['link_down']:
                    if success:
                        consecutive_successes += 1
                        # Stop if we see 4 consecutive successes after the link was shut down
                        if consecutive_successes >= 4:
                            print(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Ping is consistently successful again. Stopping test.")
                            state['stop_pinging'] = True
                            break
                    else:
                        consecutive_successes = 0
                
                # Small sleep to avoid overwhelming the SSH session
                time.sleep(0.5)
                
            conn.disconnect()
        except Exception as e:
            print(f"Pinger encountered an error: {e}")
            state['stop_pinging'] = True

    def link_shutter():
        try:
            # Let pinger establish connection and do some initial pings first
            time.sleep(7)
            
            if state['stop_pinging']:
                return

            print(f"\nConnecting to R5 ({r5_ip}) to shut down Serial0/2/0...")
            conn = ConnectHandler(**r5_device)
            conn.enable()
            
            ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"[{ts}] === SHUTTING DOWN INTERFACE Serial0/2/0 ON R5 ===")
            
            commands = ["interface Serial0/2/0", "shutdown"]
            conn.send_config_set(commands)
            
            state['link_down_time'] = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            state['link_down'] = True
            
            conn.disconnect()
        except Exception as e:
            print(f"Link shutter encountered an error: {e}")
            state['stop_pinging'] = True

    # Start threads
    t1 = threading.Thread(target=pinger)
    t2 = threading.Thread(target=link_shutter)

    t1.start()
    t2.start()

    # Wait for test to finish
    t1.join()
    t2.join()

    print("\nTest completed.")
    print(f"Total pings sent: {len(state['ping_results'])}")
    if state['link_down_time']:
        print(f"Link was shut down at: {state['link_down_time']}")

    # Write output to results file
    results_file = 'ping_failover_results.txt'
    try:
        with open(results_file, 'w') as f:
            f.write("--- Ping Failover Test Results ---\n")
            f.write(f"Link Shutdown Time: {state['link_down_time']}\n\n")
            f.write("Pings:\n")
            for res in state['ping_results']:
                f.write(f"[{res['timestamp']}] Success: {res['success']} - Duration: {res['duration_ms']:.0f}ms\n")
        print(f"Results saved to {results_file}.")
    except IOError as e:
        print(f"Failed to save results file: {e}")

if __name__ == "__main__":
    main()
