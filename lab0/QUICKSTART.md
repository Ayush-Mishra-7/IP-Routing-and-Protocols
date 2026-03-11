# Quick Start Guide

## 30-Second Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Verify Your COM Port
```powershell
Get-WmiObject Win32_SerialPort | Select Name
```

### 3. Run the Script
```bash
python console_device_config.py
```

---

## Common Scenarios

### Scenario 1: Cisco Router Configuration via Console

Edit `console_device_config.py` main() function:

```python
def main():
    CONSOLE_PORT = 'COM6'
    TARGET_IP = '1.1.1.1'
    TARGET_PORT = 2002
    
    config_commands = [
        "configure terminal",
        "interface GigabitEthernet0/0/1",
        "ip address 192.168.100.1 255.255.255.0",
        "description LAN Interface",
        "no shutdown",
        "exit",
        "ip route 0.0.0.0 0.0.0.0 192.168.100.254",
        "exit",
        "write memory",
    ]
    
    with ConsoleDeviceConfigurator(port=CONSOLE_PORT) as configurator:
        if configurator.telnet_to_device(TARGET_IP, TARGET_PORT):
            configurator.configure_device(config_commands)
```

### Scenario 2: Switch Configuration with Save

```python
config_commands = [
    "configure terminal",
    "vlan 10",
    "name Management",
    "exit",
    "vlan 20",
    "name Data",
    "exit",
    "interface Vlan10",
    "ip address 10.0.0.1 255.255.255.0",
    "exit",
    "end",
    "write memory",
]
```

### Scenario 3: Using Netmiko for SSH

Edit `netmiko_device_config.py`:

```python
def main():
    TARGET_IP = '1.1.1.1'
    
    configurator = AdvancedDeviceConfigurator()
    
    # Connect directly via SSH (skip serial)
    if configurator.connect_netmiko(
        TARGET_IP,
        device_type='cisco_ios',
        username='admin',
        password='yourpassword'
    ):
        configurator.configure_with_netmiko(config_commands)
        configurator.save_configuration()
        configurator.disconnect()
```

### Scenario 4: Multiple Devices

```python
devices = [
    {'ip': '1.1.1.1', 'port': 2002, 'name': 'router1'},
    {'ip': '1.1.1.2', 'port': 2003, 'name': 'router2'},
    {'ip': '1.1.1.3', 'port': 2004, 'name': 'router3'},
]

for device in devices:
    print(f"\n{'='*50}")
    print(f"Configuring {device['name']} ({device['ip']})")
    print(f"{'='*50}")
    
    with ConsoleDeviceConfigurator(port='COM6') as configurator:
        if configurator.telnet_to_device(device['ip'], device['port']):
            configurator.configure_device(config_commands)
```

---

## Troubleshooting Quick Fixes

### COM Port Not Working?
```powershell
# List all COM ports
Get-WmiObject Win32_SerialPort

# Check if port is in use
Get-Process | Where-Object {$_.Handles -like "*COM6*"}
```

### Telnet Timeout?
```python
# Increase wait times
configurator.telnet_to_device('1.1.1.1', 2002)
time.sleep(5)  # Wait longer for connection

configurator.send_command("some_command")
time.sleep(2)  # Wait for response
```

### Garbled Output?
```python
# Try different baudrate
configurator = ConsoleDeviceConfigurator(
    port='COM6',
    baudrate=19200  # Try: 9600, 19200, 38400, 115200
)
```

### SSH Connection Failed?
```python
# Verify SSH is enabled
# Try with explicit port 22
configurator.connect_netmiko(
    '1.1.1.1',
    device_type='cisco_ios',
    username='admin',
    password='password',
    port=22
)
```

---

## Command Examples by Device Type

### Cisco IOS
```
configure terminal
interface Gi0/0
 ip address 192.168.1.1 255.255.255.0
 no shutdown
exit
exit
write memory
```

### Juniper Junos
```
configure
set interfaces ge-0/0/0 unit 0 family inet address 192.168.1.1/24
commit
exit
request system host-name newname
commit and-quit
```

### Arista EOS
```
configure
interface Ethernet1
 ip address 192.168.1.1/24
interface Ethernet2
 ip address 192.168.2.1/24
end
write memory
```

### Palo Alto Networks
```
configure
set deviceconfig system hostname fw-01
set deviceconfig system dns-setting servers primary 8.8.8.8
commit
exit
```

---

## Advanced: Custom Logging

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('device_config.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"Connecting to {TARGET_IP}:{TARGET_PORT}")
```

---

## Advanced: Error Handling

```python
try:
    with ConsoleDeviceConfigurator(port=CONSOLE_PORT) as configurator:
        if not configurator.telnet_to_device(TARGET_IP, TARGET_PORT):
            logger.error("Telnet connection failed")
            return 1
        
        if not configurator.configure_device(config_commands):
            logger.error("Configuration failed")
            return 1
        
        logger.info("Configuration successful")
        return 0
        
except serial.SerialException as e:
    logger.error(f"Serial error: {e}")
    return 1
except TimeoutError:
    logger.error("Connection timeout")
    return 1
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return 1
```

---

## Best Practices Checklist

- [ ] Test with one device before scaling to multiple
- [ ] Store passwords in environment variables (not in code)
- [ ] Use SSH (Netmiko) instead of telnet when possible
- [ ] Backup existing configurations before applying changes
- [ ] Add logging for audit trails
- [ ] Validate command responses
- [ ] Use context managers (`with` statement) for cleanup
- [ ] Test in a lab environment first
- [ ] Have a rollback plan
- [ ] Document device-specific configuration requirements

---

## Getting Help

1. **Check the README.md** for detailed documentation
2. **Review examples** in this file matching your use case
3. **Check library docs**:
   - Pyserial: https://pyserial.readthedocs.io/
   - Netmiko: https://netmiko.readthedocs.io/
4. **Verify hardware**: COM port exists and is connected
5. **Test connectivity**: Use Terminal/Putty to manually verify telnet access

Good luck! 🚀
