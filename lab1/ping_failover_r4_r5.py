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
    r4_info = get_router_by_name(routers, '5R4')
    r5_info = get_router_by_name(routers, '5R5')

    if not r3_info or not r4_info or not r5_info:
        print("Could not find configuration for 5R3, 5R4, or 5R5.")
        return

    r3_ip = r3_info['management_interfaces']['Gi0/1']['ip']
    r4_ip = r4_info['management_interfaces']['Gi0/1']['ip']
    r5_loopback_ip = r5_info['interfaces']['Loopback0']['ip']

    r3_loopback_ip = r3_info['interfaces']['Loopback0']['ip']

    r3_device = {
        'device_type': 'cisco_ios',
        'host': r3_ip,
        'username': credentials.get('username'),
        'password': credentials.get('password'),
        'secret': credentials.get('secret')
    }

    r4_device = {
        'device_type': 'cisco_ios',
        'host': r4_ip,
        'username': credentials.get('username'),
        'password': credentials.get('password'),
        'secret': credentials.get('secret')
    }

    def pinger():
        try:
            print(f"Connecting to R4 ({r4_ip}) to start pinging...")
            conn = ConnectHandler(**r4_device)
            conn.enable()
            
            consecutive_successes = 0
            
            while not state['stop_pinging']:
                start_time = datetime.now()
                # Sending a single ping from Loopback0
                output = conn.send_command(f"ping {r3_loopback_ip} source Loopback0 repeat 1 timeout 1")
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
                print(f"[{timestamp}] Ping from R4 Loopback to {r3_loopback_ip}: {status_str} (Time: {duration_ms:.0f}ms)")
                
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

        print(f" [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] === configuring VLAN mismatch for R3 interface on Switch ===")
        
        state['link_down']
        state['link_down_time'] = datetime.now().strftime('%H:%M:%S.%f')[:-3]

    # Start threads
    t1 = threading.Thread(target=pinger)
    t2 = threading.Thread(target=link_shutter)

    t1.start()
    t2.start()

    try:
        # Wait for test to finish
        while t1.is_alive() or t2.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user. Saving results so far...")
        state['stop_pinging'] = True
        t1.join()
        t2.join()

    print("\nTest completed.")
    print(f"Total pings sent: {len(state['ping_results'])}")
    if state['link_down_time']:
        print(f"Link was shut down at: {state['link_down_time']}")

    # Write output to results file
    results_file = 'test.txt'
    try:
        with open(results_file, 'w') as f:
            f.write("--- Ping Failover Test Results (R4 Loopback to R3 Loopback) ---\n")
            f.write(f"Interface VLAN mismatch Time (R3 Gi0/0): {state['link_down_time']}\n\n")
            f.write("Time Stamps | Status | Duration\n")
            f.write("-" * 40 + "\n")
            for res in state['ping_results']:
                f.write(f"[{res['timestamp']}] Success: {res['success']} - Duration: {res['duration_ms']:.0f}ms\n")
        print(f"Results saved to {results_file}.")
    except IOError as e:
        print(f"Failed to save results file: {e}")

if __name__ == "__main__":
    main()
