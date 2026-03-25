import time
from netmiko import ConnectHandler
from configure_rip import main as configure_rip_main

# Router configurations
routers = [
    {
        "device_type": "cisco_ios",
        "host": "10.0.0.1",
        "username": "cisco",
        "password": "lab123",
        "secret": "lab123",
    },
    {
        "device_type": "cisco_ios",
        "host": "10.0.0.5",
        "username": "cisco",
        "password": "lab123",
        "secret": "lab123",
    }
]

def run_debug_on_router(router_config, router_name):
    try:
        # Connect to the router
        net_connect = ConnectHandler(**router_config)
        net_connect.enable()


        # Enable terminal monitoring
        net_connect.send_command("term mon")

        # Enable RIP debugging
        net_connect.send_command("debug ip rip")

        # Capture debug output for 1 minute
        debug_log = ""
        for _ in range(60):
            time.sleep(1)
            output = net_connect.read_channel()
            debug_log += output

        # Disable all debugging
        net_connect.send_command("no debug all")

        # Disconnect
        net_connect.disconnect()

        # Save the log to a file
        log_filename = f"debug_log_{router_name}.txt"
        with open(log_filename, "w") as log_file:
            log_file.write(debug_log)
        print(f"Debug log saved to {log_filename}")

    except Exception as e:
        print(f"Error connecting to {router_name}: {str(e)}")



configure_rip_main()  # Ensure RIP is configured before debugging

# Run on backbone routers
run_debug_on_router(routers[0], "5R1")
run_debug_on_router(routers[1], "5R5")