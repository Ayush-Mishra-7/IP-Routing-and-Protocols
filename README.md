# Console Device Configuration Scripts

This repository contains Python scripts for connecting to devices via console servers and configuring them remotely.

## Overview

Two main scripts are provided:

1. **console_device_config.py** - Basic serial console approach using pyserial
2. **netmiko_device_config.py** - Advanced option combining serial with Netmiko

## Requirements

### Hardware

- Windows machine with available COM port
- Serial console server on COM6
- Target device accessible via telnet on the console server

### Software

Install dependencies:

```bash
pip install -r requirements.txt
```

Or install individually:

```bash
pip install pyserial==3.5
pip install paramiko==3.4.0
pip install netmiko==4.3.0
pip install cryptography==42.0.0
```

## Setup

### 1. Verify COM Port

On Windows, check available COM ports:

```powershell
Get-WmiObject Win32_SerialPort | Select Name, Description
```

Update the script with your COM port if different from COM6.

### 2. Configure Serial Settings

Adjust these in the script if needed:
- Baud rate: 9600 (common for terminal servers)
- Data bits: 8
- Stop bits: 1
- Parity: None
- Flow control: Check your terminal server documentation

## Usage

### Basic Serial Console Approach

```bash
python console_device_config.py
```

**Flow:**
1. Connects to COM6 serial port
2. Initiates: `telnet 1.1.1.1 2002`
3. Sends configuration commands
4. Disconnects gracefully

### Advanced Netmiko Approach

```bash
python netmiko_device_config.py
```

**Flow:**
1. Connects via serial console
2. Initiates telnet session
3. Optionally switches to SSH (Netmiko)
4. Sends configuration commands
5. Saves configuration
6. Retrieves device info

## Customization

### Modifying Serial Settings

Edit the `ConsoleDeviceConfigurator` initialization:

```python
configurator = ConsoleDeviceConfigurator(
    port='COM6',         # Change to your COM port
    baudrate=19200,      # Adjust baud rate
    timeout=10           # Read timeout in seconds
)
```

### Changing Target Device

Edit the main configuration:

```python
TARGET_IP = '1.1.1.1'      # Target device IP
TARGET_PORT = 2002         # Telnet port
```

### Configuration Commands

Modify the `config_commands` list for your device:

```python
config_commands = [
    "configure terminal",
    "interface eth0",
    "ip address 192.168.1.1 255.255.255.0",
    "no shutdown",
    "exit",
    "exit",
    "write memory",
]
```

### Netmiko Device Types

For `netmiko_device_config.py`, specify your device type:

```python
DEVICE_TYPE = 'cisco_ios'  # Options: cisco_ios, cisco_xe, cisco_xr, juniper_junos, arista_eos, etc.
```

## Advanced Features

### Authentication via Telnet

```python
configurator.telnet_via_console(
    ip_address='1.1.1.1',
    port=2002,
    username='admin',
    password='password'
)
```

### Direct SSH/Netmiko Connection

For devices with SSH access:

```python
configurator.connect_netmiko(
    ip_address='1.1.1.1',
    device_type='cisco_ios',
    username='admin',
    password='password',
    port=22,
    secret='enablepassword'
)
```

### Save Configuration

```python
configurator.save_configuration()
```

### Get Device Information

```python
device_info = configurator.get_device_info()
```

## Troubleshooting

### Serial Port Not Found

```
✗ Failed to connect to COM6: (FileNotFoundError) [Errno 2] ...
```

**Solution:** Verify the COM port exists using `Get-WmiObject Win32_SerialPort`

### Telnet Connection Timeout

```
⚠ Telnet connection may not be ready, continuing anyway...
```

**Solution:** 
- Increase `wait_time` parameter
- Verify target device is reachable
- Check telnet port is correct

### Netmiko Connection Refused

```
✗ Netmiko connection failed: ...
```

**Solution:**
- Verify SSH is enabled on target device
- Check credentials
- Verify device type is correct

### Garbled Characters in Serial Output

**Solution:** Adjust baudrate to match your terminal server settings

## Example Workflows

### Workflow 1: Configure Cisco Router via Console

```python
config_commands = [
    "configure terminal",
    "interface GigabitEthernet0/0/1",
    "ip address 192.168.1.1 255.255.255.0",
    "no shutdown",
    "exit",
    "ip route 0.0.0.0 0.0.0.0 192.168.1.254",
    "exit",
    "write memory"
]
```

### Workflow 2: Configure Switch via Netmiko

```python
DEVICE_TYPE = 'cisco_ios_xe'

config_commands = [
    "configure terminal",
    "vlan 100",
    "name MANAGEMENT",
    "exit",
    "interface Vlan100",
    "ip address 10.0.0.1 255.255.255.0",
    "no shutdown",
    "exit",
    "end",
    "write memory"
]
```

### Workflow 3: Multi-Device Configuration

Create a configuration file and loop through multiple devices:

```python
devices = [
    {'ip': '1.1.1.1', 'port': 2002},
    {'ip': '1.1.1.2', 'port': 2003},
]

for device in devices:
    configurator.telnet_via_console(device['ip'], device['port'])
    configurator.configure_with_netmiko(config_commands)
    configurator.disconnect()
```

## Security Considerations

1. **Credentials**: Store credentials in environment variables or config files, not in code
2. **SSH Preferred**: Use SSH (Netmiko) over telnet when possible
3. **Validation**: Verify command responses before assuming success
4. **Logging**: Add logging for audit trails

## Security Best Practice Example

```python
import os
from getpass import getpass

# Load from environment or prompt
username = os.getenv('DEVICE_USERNAME', 'admin')
password = os.getenv('DEVICE_PASSWORD') or getpass("Enter password: ")

configurator.connect_netmiko(
    ip_address='1.1.1.1',
    username=username,
    password=password
)
```

## Logging

Add detailed logging to track operations:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('device_config.log'),
        logging.StreamHandler()
    ]
)
```

## Performance Tips

1. Adjust `wait_time` between commands based on device response time
2. Batch commands to reduce overall execution time
3. Use parallel processing for multiple devices
4. Cache results for repeated queries

## Supported Devices

### Serial Console
- Any device accessible via telnet through a console server
- Terminal servers (Cisco, HP, etc.)

### Netmiko
- Cisco IOS/IOS-XE/IOS-XR
- Juniper Junos
- Arista EOS
- Palo Alto Networks
- And 30+ more platforms

## References

- [Pyserial Documentation](https://pyserial.readthedocs.io/)
- [Netmiko Documentation](https://netmiko.readthedocs.io/)
- [Paramiko Documentation](https://www.paramiko.org/)

## License

MIT

## Support

For issues or questions, check the troubleshooting section or consult the library documentation.
