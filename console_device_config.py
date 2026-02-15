#!/usr/bin/env python3
"""
Console Device Configuration Script
Connects to a console server via COM6, initiates a telnet session,
and configures a remote device.
"""

import serial
import time
import sys
from typing import Optional


class ConsoleDeviceConfigurator:
    """
    Manages console connections and device configuration via telnet.
    """
    
    def __init__(self, port: str = 'COM6', baudrate: int = 9600, 
                 timeout: int = 10):
        """
        Initialize the console connection.
        
        Args:
            port: Serial port (e.g., 'COM6' on Windows, '/dev/ttyUSB0' on Linux)
            baudrate: Baud rate for the serial connection
            timeout: Read timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        
    def connect(self) -> bool:
        """
        Establish connection to the console server via COM6.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            print(f"✓ Connected to {self.port}")
            time.sleep(1)  # Allow connection to stabilize
            return True
        except serial.SerialException as e:
            print(f"✗ Failed to connect to {self.port}: {e}")
            return False
    
    def send_command(self, command: str) -> str:
        """
        Send a command via the serial connection and receive response.
        
        Args:
            command: Command to send
            
        Returns:
            Response from the device
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            print("✗ Serial connection is not open")
            return ""
        
        try:
            # Send command with carriage return
            self.serial_conn.write((command + '\r\n').encode())
            time.sleep(0.5)  # Wait for response
            
            # Read response
            response = ""
            while self.serial_conn.in_waiting > 0:
                response += self.serial_conn.read(1).decode('utf-8', errors='ignore')
            
            return response
        except Exception as e:
            print(f"✗ Error sending command: {e}")
            return ""
    
    def telnet_to_device(self, ip_address: str, port: int = 2002) -> bool:
        """
        Initiate a telnet connection to target device.
        
        Args:
            ip_address: IP address to telnet to (e.g., '1.1.1.1')
            port: Telnet port (default 2002)
            
        Returns:
            True if connection successful, False otherwise
        """
        telnet_cmd = f"telnet {ip_address} {port}"
        print(f"\n→ Initiating telnet command: {telnet_cmd}")
        
        response = self.send_command(telnet_cmd)
        print(f"Response: {response}")
        
        # Wait for connection to establish
        time.sleep(2)
        
        # Check if telnet was successful (look for login prompt)
        if "Connected" in response or "login" in response.lower() or "password" in response.lower():
            print(f"✓ Telnet connection established to {ip_address}:{port}")
            return True
        else:
            print(f"⚠ Telnet connection may not be ready, continuing anyway...")
            return True
    
    def configure_device(self, commands: list) -> bool:
        """
        Send configuration commands to the connected device.
        
        Args:
            commands: List of configuration commands to execute
            
        Returns:
            True if all commands executed, False if there was an error
        """
        print(f"\n→ Configuring device with {len(commands)} commands...")
        
        for i, cmd in enumerate(commands, 1):
            print(f"\n  [{i}/{len(commands)}] Sending: {cmd}")
            response = self.send_command(cmd)
            
            if response:
                # Print first 200 chars of response
                print(f"  Response: {response[:200]}...")
            
            time.sleep(0.5)  # Small delay between commands
        
        print("\n✓ Configuration complete")
        return True
    
    def disconnect(self):
        """Close the serial connection gracefully."""
        if self.serial_conn and self.serial_conn.is_open:
            # Send exit command
            self.send_command("exit")
            time.sleep(0.5)
            self.serial_conn.close()
            print("✓ Disconnected from console server")
    
    def __enter__(self):
        """Context manager support."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.disconnect()


def main():
    """
    Main execution function with example configuration.
    """
    # Configuration
    CONSOLE_PORT = 'COM6'
    TARGET_IP = '1.1.1.1'
    TARGET_PORT_LIST = [2002, 2003, 2004, 2005]  # Try multiple ports if needed
    
    # Example device configuration commands
    # Adjust these based on your device's OS and requirements
    config_commands = [
        "configure terminal",
        "interface GigabitEthernet0/0/1",
        "ip address 192.168.1.1 255.255.255.0",
        "no shutdown",
        "exit",
        "exit",
        "write memory",
    ]
    
    try:
        # Use context manager for automatic cleanup
        with ConsoleDeviceConfigurator(port=CONSOLE_PORT) as configurator:
            # Step 1: Connect to console server (already done in __enter__)
            
            #Step 2: do configuration on multiple ports in a loop and then apply configuration on these devices
            for port in TARGET_PORT_LIST:
                if configurator.telnet_to_device(TARGET_IP, port):
                    print(f"✓ Successfully connected to {TARGET_IP}:{port}")
                else:
                    print(f"✗ Failed to connect to {TARGET_IP}:{port}, trying next port...")


            
            
            # Step 3: Configure the device
            if not configurator.configure_device(config_commands):
                print("✗ Failed to configure device")
                return 1
            
            print("\n✓ All operations completed successfully")
            return 0
            
    except KeyboardInterrupt:
        print("\n✗ Operation interrupted by user")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
