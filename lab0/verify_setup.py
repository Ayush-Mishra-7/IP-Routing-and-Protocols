#!/usr/bin/env python3
"""
Verification and diagnostic script to test setup before running main scripts.
"""

import sys
import platform
import serial.tools.list_ports
from importlib import import_module


def check_python_version():
    """Check if Python version is sufficient."""
    print("=" * 60)
    print("1. PYTHON VERSION CHECK")
    print("=" * 60)
    
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major >= 3 and version.minor >= 7:
        print("✓ Python version is compatible")
        return True
    else:
        print("✗ Python 3.7+ required")
        return False


def check_os():
    """Check operating system."""
    print("\n" + "=" * 60)
    print("2. OPERATING SYSTEM CHECK")
    print("=" * 60)
    
    os_name = platform.system()
    print(f"OS: {os_name} {platform.release()}")
    
    if os_name == "Windows":
        print("✓ Windows detected (COM ports available)")
        return True
    elif os_name == "Linux":
        print("⚠ Linux detected (use /dev/ttyUSB0 or similar instead of COM6)")
        return True
    elif os_name == "Darwin":
        print("⚠ macOS detected (use /dev/tty.usbserial or similar)")
        return True
    else:
        print("? Unknown OS")
        return False


def check_com_ports():
    """Check available COM ports."""
    print("\n" + "=" * 60)
    print("3. SERIAL COM PORT CHECK")
    print("=" * 60)
    
    ports = list(serial.tools.list_ports.comports())
    
    if ports:
        print(f"Found {len(ports)} COM port(s):\n")
        for port in ports:
            print(f"  • {port.device}")
            print(f"    Description: {port.description}")
            print(f"    Manufacturer: {port.manufacturer}")
            print()
        
        com6_found = any(p.device == 'COM6' for p in ports)
        if com6_found:
            print("✓ COM6 is available")
        else:
            print("⚠ COM6 not found - update port in script if needed")
        return True
    else:
        print("✗ No COM ports found")
        print("  Check:")
        print("  - USB serial adapter is connected")
        print("  - Drivers are installed")
        return False


def check_package(package_name, import_name=None):
    """Check if a package is installed."""
    if import_name is None:
        import_name = package_name
    
    try:
        module = import_module(import_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"  ✓ {package_name:<20} {version}")
        return True
    except ImportError:
        print(f"  ✗ {package_name:<20} NOT INSTALLED")
        return False


def check_dependencies():
    """Check if required packages are installed."""
    print("\n" + "=" * 60)
    print("4. PYTHON DEPENDENCIES CHECK")
    print("=" * 60)
    
    packages = [
        ('pyserial', 'serial'),
        ('paramiko', 'paramiko'),
        ('netmiko', 'netmiko'),
        ('cryptography', 'cryptography'),
    ]
    
    all_installed = True
    for package_name, import_name in packages:
        if not check_package(package_name, import_name):
            all_installed = False
    
    if not all_installed:
        print("\n⚠ Missing packages detected")
        print("  Run: pip install -r requirements.txt")
    else:
        print("\n✓ All dependencies installed")
    
    return all_installed


def check_files():
    """Check if main script files exist."""
    print("\n" + "=" * 60)
    print("5. SCRIPT FILES CHECK")
    print("=" * 60)
    
    import os
    
    files = [
        'console_device_config.py',
        'netmiko_device_config.py',
        'requirements.txt',
        'README.md',
    ]
    
    all_exist = True
    for filename in files:
        exists = os.path.exists(filename)
        status = "✓" if exists else "✗"
        print(f"  {status} {filename}")
        if not exists:
            all_exist = False
    
    return all_exist


def test_serial_connection(port='COM6', baudrate=9600, timeout=2):
    """Test serial connection to COM port."""
    print("\n" + "=" * 60)
    print("6. SERIAL CONNECTION TEST")
    print("=" * 60)
    
    try:
        print(f"Attempting to open {port} at {baudrate} baud...")
        conn = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS
        )
        
        print(f"✓ Successfully opened {port}")
        print(f"  Port: {conn.port}")
        print(f"  Baudrate: {conn.baudrate}")
        print(f"  Is open: {conn.is_open}")
        
        conn.close()
        print("✓ Connection closed successfully")
        return True
    except serial.SerialException as e:
        print(f"✗ Failed to open {port}: {e}")
        print("\n  Troubleshooting:")
        print("  - Check if COM port exists (run check 3)")
        print("  - Verify device is connected")
        print("  - Check drivers are installed")
        print("  - Try different COM port number")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def run_diagnostics():
    """Run all diagnostic checks."""
    print("\n" + "█" * 60)
    print("█  DEVICE CONFIGURATION SETUP VERIFICATION")
    print("█" * 60 + "\n")
    
    results = []
    
    # Run checks
    results.append(("Python Version", check_python_version()))
    results.append(("Operating System", check_os()))
    results.append(("COM Ports", check_com_ports()))
    results.append(("Dependencies", check_dependencies()))
    results.append(("Script Files", check_files()))
    
    # Only test serial if COM ports exist
    try:
        import serial
        ports = list(serial.tools.list_ports.comports())
        if ports:
            results.append(("Serial Connection", test_serial_connection()))
    except:
        pass
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total} checks\n")
    
    for check_name, result in results:
        status = "✓" if result else "✗"
        print(f"  {status} {check_name}")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    
    failed = [name for name, result in results if not result]
    
    if not failed:
        print("\n✓ All checks passed! You're ready to run:")
        print("  • python console_device_config.py")
        print("  • python netmiko_device_config.py")
        print("\nSee QUICKSTART.md for usage examples.")
    else:
        print(f"\n✗ {len(failed)} check(s) failed:\n")
        for name in failed:
            print(f"  • {name}")
        print("\nRefer to troubleshooting sections above.")
    
    return len(failed) == 0


if __name__ == '__main__':
    success = run_diagnostics()
    sys.exit(0 if success else 1)
