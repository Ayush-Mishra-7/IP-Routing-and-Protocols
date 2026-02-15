#!/usr/bin/env python3
"""
Advanced Netmiko-based Device Configuration Script
Uses Netmiko for more robust device management after telnet connection.
"""

import serial
import time
import sys
import re
from typing import Optional, Dict
from netmiko import ConnectHandler
from paramiko import AutoAddPolicy
import warnings

warnings.filterwarnings('ignore')


class AdvancedDeviceConfigurator:
    """
    Advanced configuration combining serial console with Netmiko for device management.
    """
    
    def __init__(self, port: str = 'COM6', baudrate: int = 9600):
        """
        Initialize the configurator.
        
        Args:
            port: Serial port (e.g., 'COM6')
            baudrate: Baud rate for serial connection
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.netmiko_conn = None
        self.device_type = None
        
    def connect_serial(self) -> bool:
        """Connect to console server via serial port."""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=10,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            print(f"✓ Connected to serial port {self.port}")
            time.sleep(1)
            return True
        except serial.SerialException as e:
            print(f"✗ Serial connection failed: {e}")
            return False
    
    def send_serial_command(self, command: str, wait_time: float = 1.0) -> str:
        """
        Send command via serial and get response.
        
        Args:
            command: Command to send
            wait_time: Time to wait for response
            
        Returns:
            Response text
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            return ""
        
        self.serial_conn.write((command + '\r\n').encode())
        time.sleep(wait_time)
        
        response = ""
        while self.serial_conn.in_waiting > 0:
            response += self.serial_conn.read(1).decode('utf-8', errors='ignore')
        
        return response
    
    def telnet_via_console(self, ip_address: str, port: int = 2002, 
                          username: Optional[str] = None, 
                          password: Optional[str] = None) -> bool:
        """
        Establish telnet connection via console server.
        
        Args:
            ip_address: Target device IP
            port: Telnet port
            username: Optional username for device login
            password: Optional password for device login
            
        Returns:
            True if successful
        """
        telnet_cmd = f"telnet {ip_address} {port}"
        print(f"\n→ Executing: {telnet_cmd}")
        
        response = self.send_serial_command(telnet_cmd, wait_time=2)
        
        if "Connected" in response or "Trying" in response:
            time.sleep(2)  # Wait for full connection
            
            # Handle authentication if needed
            if username and password:
                print(f"→ Authenticating as {username}...")
                self.send_serial_command(username, wait_time=1)
                self.send_serial_command(password, wait_time=1)
                time.sleep(1)
            
            print(f"✓ Telnet connection to {ip_address}:{port} established")
            return True
        else:
            print(f"⚠ Telnet response: {response}")
            return False
    
    def connect_netmiko(self, ip_address: str, device_type: str = 'cisco_ios',
                       username: str = 'admin', password: str = 'password',
                       port: int = 22, secret: str = '') -> bool:
        """
        Establish direct Netmiko connection (for SSH-based access).
        
        Args:
            ip_address: Device IP address
            device_type: Netmiko device type (cisco_ios, cisco_xe, cisco_xr, etc.)
            username: SSH username
            password: SSH password
            port: SSH port
            secret: Enable secret/privilege password
            
        Returns:
            True if successful
        """
        try:
            device = {
                'device_type': device_type,
                'host': ip_address,
                'username': username,
                'password': password,
                'port': port,
                'secret': secret,
                'timeout': 10,
                'read_timeout': 20,
            }
            
            print(f"\n→ Connecting to {ip_address} via Netmiko ({device_type})...")
            self.netmiko_conn = ConnectHandler(**device)
            self.device_type = device_type
            self.netmiko_conn.enable()  # Enter privileged mode if applicable
            
            print(f"✓ Netmiko connection established")
            return True
        except Exception as e:
            print(f"✗ Netmiko connection failed: {e}")
            return False
    
    def configure_with_netmiko(self, commands: list, 
                               exit_config_mode: bool = True) -> list:
        """
        Send configuration commands via Netmiko.
        
        Args:
            commands: List of configuration commands
            exit_config_mode: Whether to exit config mode after
            
        Returns:
            List of command outputs
        """
        if not self.netmiko_conn:
            print("✗ No Netmiko connection established")
            return []
        
        results = []
        print(f"\n→ Sending {len(commands)} configuration commands...")
        
        try:
            for i, cmd in enumerate(commands, 1):
                print(f"  [{i}/{len(commands)}] {cmd}")
                output = self.netmiko_conn.send_command(cmd)
                results.append(output)
                time.sleep(0.2)
            
            if exit_config_mode and 'configure' in commands[0].lower():
                self.netmiko_conn.exit_config_mode()
            
            print("✓ Configuration sent successfully")
        except Exception as e:
            print(f"✗ Configuration failed: {e}")
        
        return results
    
    def save_configuration(self) -> bool:
        """Save configuration on the device."""
        if not self.netmiko_conn:
            return False
        
        try:
            print("\n→ Saving configuration...")
            
            if 'cisco' in self.device_type.lower():
                output = self.netmiko_conn.send_command("write memory")
            else:
                output = self.netmiko_conn.send_command("save")
            
            print("✓ Configuration saved")
            return True
        except Exception as e:
            print(f"⚠ Save failed: {e}")
            return False
    
    def get_device_info(self) -> Dict:
        """Get device information via Netmiko."""
        if not self.netmiko_conn:
            return {}
        
        try:
            print("\n→ Retrieving device information...")
            
            if 'cisco' in self.device_type.lower():
                output = self.netmiko_conn.send_command("show version")
            else:
                output = self.netmiko_conn.send_command("show system")
            
            return {'version_output': output}
        except Exception as e:
            print(f"⚠ Could not retrieve device info: {e}")
            return {}
    
    def disconnect(self):
        """Disconnect from both serial and Netmiko connections."""
        if self.netmiko_conn:
            try:
                self.netmiko_conn.disconnect()
                print("✓ Netmiko connection closed")
            except:
                pass
        
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.send_serial_command("exit", wait_time=0.5)
                self.serial_conn.close()
                print("✓ Serial connection closed")
            except:
                pass


def main():
    """Main execution with example workflow."""
    
    # Configuration for console access
    CONSOLE_PORT = 'COM6'
    CONSOLE_BAUDRATE = 9600
    
    # Target device info
    TARGET_IP = '1.1.1.1'
    TELNET_PORT = 2002
    
    # Optional SSH/Netmiko connection (if device supports it)
    SSH_USERNAME = 'admin'
    SSH_PASSWORD = 'password'
    DEVICE_TYPE = 'cisco_ios'  # Change based on your device
    
    # Configuration commands
    config_commands = [
        "configure terminal",
        "interface GigabitEthernet0/0/1",
        "ip address 192.168.1.1 255.255.255.0",
        "description Connected via Script",
        "no shutdown",
        "exit",
        "exit"
    ]
    
    configurator = AdvancedDeviceConfigurator(
        port=CONSOLE_PORT,
        baudrate=CONSOLE_BAUDRATE
    )
    
    try:
        # Step 1: Connect via serial console
        if not configurator.connect_serial():
            return 1
        
        # Step 2: Establish telnet via console
        if not configurator.telnet_via_console(TARGET_IP, TELNET_PORT):
            return 1
        
        # Step 3a: Option A - Use Netmiko for SSH (if available)
        # Uncomment to use SSH instead of serial commands
        # if configurator.connect_netmiko(TARGET_IP, DEVICE_TYPE, 
        #                                 SSH_USERNAME, SSH_PASSWORD):
        #     outputs = configurator.configure_with_netmiko(config_commands)
        #     configurator.save_configuration()
        #     device_info = configurator.get_device_info()
        # else:
        
        # Step 3b: Option B - Send commands via serial connection
        print(f"\n→ Configuring device via serial console...")
        for i, cmd in enumerate(config_commands, 1):
            print(f"  [{i}/{len(config_commands)}] {cmd}")
            response = configurator.send_serial_command(cmd)
            if response:
                print(f"    Response: {response[:100]}...")
            time.sleep(0.5)
        
        print("\n✓ All operations completed successfully")
        return 0
        
    except KeyboardInterrupt:
        print("\n✗ Operation interrupted")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1
    finally:
        configurator.disconnect()


if __name__ == '__main__':
    sys.exit(main())
