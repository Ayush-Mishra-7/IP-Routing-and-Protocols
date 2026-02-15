#!/usr/bin/env python3
"""
Console Device Configuration Script
====================================
Connects to a comm server via serial console (COM6), then telnets into
each router defined in routers_config.json to configure:
  - Loopback0 interface with a unique IP
  - All physical/serial interfaces with IPs from the config
  - Enables all interfaces with 'no shutdown'

Safety features:
  - Fresh serial connection per router (open → configure → close)
  - State detection on open: if a stale router session exists, exits
    back to the comm server automatically
  - Smart enable: skips 'enable' if already in privileged mode (#)
  - Hostname verification: reads the router prompt to confirm identity
    before applying any configuration
  - Clean disconnect with verification after each router
  - Graceful Ctrl+C handling: disconnects from router and returns to
    comm server before shutting down

Topology:
  R1 -- R2 -- R3
              |
              R4
  (R3 and R4 connect on Gi0/0)

Usage:
  python console_device_config.py
"""

import json
import re
import signal
import time
import serial
import logging
import sys
import os

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("console_device_config.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CONSOLE_PORT = "COM6"
BAUDRATE = 9600
COMM_SERVER_IP = "1.1.1.1"
CONFIG_FILE = "routers_config.json"
ENABLE_PASSWORD = "lab123"
CLEAR_LINE_ATTEMPTS = 3
TELNET_MAX_RETRIES = 3
COMM_SERVER_HOSTNAME = "commserver"


# ---------------------------------------------------------------------------
# ConsoleDeviceConfigurator
# ---------------------------------------------------------------------------
class ConsoleDeviceConfigurator:
    """Manage a serial connection to a comm server and configure a single
    router by telneting through it.

    Designed for one-router-per-instance usage:
        for each router:
            open COM6 → telnet → verify hostname → configure → disconnect → close COM6
    """

    def __init__(self, port=CONSOLE_PORT, baudrate=BAUDRATE, timeout=2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.is_connected_to_device = False  # Track if we're in a router session

    # -- Context manager ----------------------------------------------------
    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # If we're still connected to a device, disconnect first
        if self.is_connected_to_device:
            try:
                self.disconnect_from_device()
            except Exception:
                logger.warning("Could not disconnect from device during cleanup")
        self.close()
        return False

    # -- Connection helpers -------------------------------------------------
    def open(self):
        """Open a fresh serial connection to the comm server.

        Detects the current state of the session:
          - If we land inside a router (config/enable mode), exits back
            to the comm server first.
          - If already in comm server privileged mode (#), skips enable.
          - If in comm server user mode (>), enters enable with password.
        """

        logger.info(f"Opening serial connection on {self.port} @ {self.baudrate} baud")
        
        # Retry loop for serial connection
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                self.serial_conn = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                )
                break  # Success!
            except serial.SerialException as e:
                # Check for "Access is denied" (Windows error 5 / 13)
                if "Access is denied" in str(e) or "PermissionError" in str(e):
                    if attempt < max_attempts:
                        logger.warning(
                            f"Serial port access denied. Attempting to close blocking "
                            f"applications (e.g., PuTTY) before retrying..."
                        )
                        killed_apps = kill_common_terminal_apps()
                        if killed_apps:
                            logger.info(f"Killed apps: {', '.join(killed_apps)}")
                        else:
                            logger.info("No common blocking apps found running.")
                        
                        # Wait a moment for the port to release
                        time.sleep(2)
                        continue
                
                # If not access denied, or retries exhausted, re-raise
                logger.error(f"Failed to open serial port: {e}")
                raise

        # Give the connection a moment to stabilise
        time.sleep(1)

        # Wake the session — send blank lines and read whatever comes back
        for _ in range(3):
            self._write("\r\n")
            time.sleep(0.5)
        time.sleep(1)
        wake_output = self._read_all()
        logger.info(f"Wake output: {wake_output.strip()[:300]}")

        # ── Detect current state ──────────────────────────────────────
        prompt_info = self._detect_prompt_state(wake_output)
        logger.info(f"Detected state: {prompt_info}")

        if prompt_info["location"] == "router":
            # We're stuck inside a router session — exit back to comm server
            logger.warning(
                f"Stale router session detected ({prompt_info['hostname']}, "
                f"mode={prompt_info['mode']}). Exiting back to comm server ..."
            )
            self._escape_to_comm_server()
            # Re-detect state
            self._write("\r\n")
            time.sleep(1)
            output = self._read_all()
            prompt_info = self._detect_prompt_state(output)
            logger.info(f"State after escape: {prompt_info}")

        # ── Ensure comm server is in privileged mode ──────────────────
        if prompt_info["mode"] == "privileged":
            logger.info("[OK] Comm server already in privileged EXEC mode")
        else:
            logger.info("Entering enable mode on comm server ...")
            self._flush_input()
            self._write("enable\r\n")
            time.sleep(2)
            self._write(ENABLE_PASSWORD + "\r\n")
            time.sleep(1)
            enable_output = self._read_all()
            logger.debug(f"Enable output: {enable_output.strip()[:200]}")

            # Verify
            self._flush_input()
            self._write("\r\n")
            time.sleep(1)
            verify_output = self._read_all()
            if "#" in verify_output:
                logger.info("[OK] Comm server is now in privileged EXEC mode")
            else:
                logger.warning(
                    "[WARN] Could not confirm privileged mode — "
                    "clear line commands may fail"
                )

        logger.info(f"Serial connection ready on {self.port}")

    def _detect_prompt_state(self, output: str) -> dict:
        """Analyse raw output to determine where we are.

        Returns a dict with:
          - location: 'comm_server' | 'router' | 'unknown'
          - hostname: detected hostname string
          - mode:     'user' | 'privileged' | 'config' | 'unknown'
        """
        result = {"location": "unknown", "hostname": "", "mode": "unknown"}

        # Look for a Cisco-style prompt at the end of the output
        # Patterns:  hostname>  hostname#  hostname(config)#  hostname(config-if)#
        match = re.search(
            r"(\S+?)(\([^)]*\))?([>#])\s*$", output, re.MULTILINE
        )
        if not match:
            return result

        hostname = match.group(1)
        sub_mode = match.group(2)  # e.g. (config), (config-if), or None
        prompt_char = match.group(3)  # > or #

        result["hostname"] = hostname

        # Determine if this is the comm server or a router
        if hostname.lower() == COMM_SERVER_HOSTNAME.lower():
            result["location"] = "comm_server"
        else:
            result["location"] = "router"

        # Determine the mode
        if sub_mode:  # (config), (config-if), etc.
            result["mode"] = "config"
        elif prompt_char == "#":
            result["mode"] = "privileged"
        elif prompt_char == ">":
            result["mode"] = "user"

        return result

    def _escape_to_comm_server(self):
        """Escape from whatever router mode we're in back to the comm server.

        Sends 'end' to exit config, then multiple 'exit' commands,
        then Ctrl+Shift+6 x, then 'disconnect'.
        """
        # Exit config mode if applicable
        self._write("end\r\n")
        time.sleep(0.5)

        # Send exits to leave enable/user mode
        for _ in range(3):
            self._write("exit\r\n")
            time.sleep(0.5)

        # Cisco escape: Ctrl+Shift+6 (ASCII 0x1E) then 'x'
        self._write("\x1e")
        time.sleep(0.5)
        self._write("x")
        time.sleep(1)
        self._read_all()  # consume output

        # Disconnect the session
        self._write("disconnect\r\n")
        time.sleep(1)
        self._write("\r\n")  # confirm
        time.sleep(1)
        self._read_all()  # consume output

        # Send blank line to get a clean prompt
        self._write("\r\n")
        time.sleep(1)
        self._read_all()

        logger.info("Escaped back to comm server")

    def close(self):
        """Close the serial connection completely."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("Serial connection closed")
            self.serial_conn = None

    # -- Low-level I/O ------------------------------------------------------
    def _write(self, data: str):
        """Write a string to the serial port."""
        self.serial_conn.write(data.encode("ascii"))

    def _read_all(self) -> str:
        """Read all available bytes from the serial buffer."""
        output = b""
        while self.serial_conn.in_waiting:
            output += self.serial_conn.read(self.serial_conn.in_waiting)
            time.sleep(0.1)
        return output.decode("ascii", errors="ignore")

    def _read_until(self, timeout: float = 5.0) -> str:
        """Read from serial until no new data arrives or timeout."""
        start = time.time()
        buffer = ""
        while time.time() - start < timeout:
            if self.serial_conn.in_waiting:
                buffer += self.serial_conn.read(self.serial_conn.in_waiting).decode(
                    "ascii", errors="ignore"
                )
                time.sleep(0.3)
            else:
                # If we already have data and nothing new is coming, we're done
                if buffer:
                    time.sleep(0.5)
                    if not self.serial_conn.in_waiting:
                        break
                time.sleep(0.2)
        return buffer

    def _flush_input(self):
        """Discard anything sitting in the serial input buffer."""
        self.serial_conn.reset_input_buffer()

    # -- Command helpers ----------------------------------------------------
    def send_command(self, command: str, wait: float = 1.0) -> str:
        """Send a single command and return the output after *wait* seconds."""
        logger.debug(f"TX >>> {command}")
        self._flush_input()
        self._write(command + "\r\n")
        time.sleep(wait)
        output = self._read_all()
        logger.debug(f"RX <<< {output}")
        return output

    def send_commands(self, commands: list[str], wait: float = 1.0):
        """Send a list of commands sequentially."""
        for cmd in commands:
            output = self.send_command(cmd, wait)
            # Log the first 200 chars of output for visibility
            snippet = output.strip()[:200]
            if snippet:
                logger.info(f"  {cmd:40s}  ->  {snippet}")
            else:
                logger.info(f"  {cmd}")

    # -- Line clearing -------------------------------------------------------
    def clear_line(self, line_number: int, attempts: int = CLEAR_LINE_ATTEMPTS):
        """Run 'clear line <n>' on the comm server multiple times.

        This frees up a stuck/busy VTY line so a subsequent telnet
        can succeed.  The comm server will prompt '[confirm]' after
        each clear — we send Enter to confirm.
        """
        for i in range(1, attempts + 1):
            logger.info(f"  clear line {line_number}  (attempt {i}/{attempts})")
            self._flush_input()
            self._write(f"clear line {line_number}\r\n")
            time.sleep(1)
            # Comm server asks for [confirm] — press Enter
            self._write("\r\n")
            time.sleep(1)
            output = self._read_all()
            logger.debug(f"  clear line output: {output.strip()[:200]}")
        logger.info(f"  Cleared line {line_number} ({attempts} times)")

    # -- Telnet to device ---------------------------------------------------
    def telnet_to_device(
        self, ip: str, port: int, max_retries: int = TELNET_MAX_RETRIES
    ) -> bool:
        """Issue a telnet command on the comm server to reach a router.

        Before the first attempt, clears the line (line = port - 2000)
        to avoid 'Connection refused'.  If the connection is still
        refused, retries up to *max_retries* times with another round
        of line clearing between each attempt.

        Returns True if the connection appears successful.
        """
        line_number = port - 2000

        for attempt in range(1, max_retries + 1):
            # Always clear the line before attempting telnet
            logger.info(f"Preparing line {line_number} before telnet (attempt {attempt}/{max_retries}) ...")
            self.clear_line(line_number)

            logger.info(f"Telneting to {ip} {port} ...")
            self._flush_input()
            self._write(f"telnet {ip} {port}\r\n")
            # Wait for the connection to be established
            time.sleep(3)
            output = self._read_all()
            logger.info(f"Telnet output: {output.strip()[:300]}")

            # Check for connection refused
            if "refused" in output.lower() or "failed" in output.lower():
                logger.warning(
                    f"Connection refused/failed on attempt {attempt}/{max_retries}"
                )
                if attempt < max_retries:
                    logger.info("Retrying after a short pause ...")
                    time.sleep(2)
                    continue
                else:
                    logger.error("All telnet attempts exhausted — giving up.")
                    return False

            # Connection seems OK — wait for initial garbage output to settle.
            # We actively send Backspace / Enter to help clear any jargon.
            logger.info("Waiting for router output to settle (max 10s) ...")
            settled_buffer = ""
            start_wait = time.time()
            max_wait_seconds = 10
            
            # We want to see 'silence' for at least 2 seconds before we consider it settled
            silence_threshold = 2.0
            silence_start = time.time()
            
            while True:
                # Check for timeout
                if time.time() - start_wait > max_wait_seconds:
                    logger.info("Max settle time reached. Proceeding...")
                    break
                
                if self.serial_conn.in_waiting:
                    chunk = self.serial_conn.read(
                        self.serial_conn.in_waiting
                    ).decode("ascii", errors="ignore")
                    settled_buffer += chunk
                    silence_start = time.time()  # reset silence timer
                else:
                    # No new data — if we've been silent long enough, we're done
                    if time.time() - silence_start >= silence_threshold:
                        break
                    
                    # If not silent long enough yet, maybe send a helper char to clear jargon
                    # Send Backspace (\x08) or Enter (\r\n) occasionally
                    if (time.time() - start_wait) % 2 < 0.2: 
                        # slightly random check to ensure we don't spam too fast, 
                        # but roughly every 2 seconds
                        self._write("\x08") # Backspace
                        time.sleep(0.1)
                
                time.sleep(0.1)

            if settled_buffer:
                logger.info(
                    f"Garbage/boot output ({len(settled_buffer)} chars) consumed"
                )
                logger.debug(f"Settled output tail: ...{settled_buffer[-200:]}")

            # Now send Enter to get a clean prompt
            self._write("\r\n")
            time.sleep(1)
            self._write("\r\n")
            time.sleep(1)
            output = self._read_all()
            logger.info(f"Router prompt: {output.strip()[:300]}")
            self.is_connected_to_device = True
            return True

        return False

    # -- Hostname detection -------------------------------------------------
    def detect_hostname(self) -> str:
        """Send an empty line and parse the router hostname from the prompt.
        Retries up to 3 times if not found immediately.
        """
        for attempt in range(1, 4):
            self._flush_input()
            self._write("\r\n")
            time.sleep(2)
            output = self._read_all()

            # Try to match a Cisco-style prompt   e.g.  R1>  R1#  R1(config)#
            # Pattern: non-whitespace hostname followed by optional (mode) and > or #
            match = re.search(r"(\S+?)(?:\([^)]*\))?[>#]\s*$", output, re.MULTILINE)
            if match:
                hostname = match.group(1)
                logger.info(f"Detected hostname: '{hostname}'")
                return hostname
            
            logger.warning(
                f"Hostname detection attempt {attempt}/3 failed. "
                f"Output snippet: {output.strip()[:100]}"
            )
            # Send an extra Enter to nudge it
            if attempt < 3:
                self._write("\r\n")
                time.sleep(1)

        logger.error("Could not detect hostname after 3 attempts.")
        return ""

    def verify_hostname(self, expected_name: str) -> bool:
        """Detect the router hostname and check it matches *expected_name*.

        The comparison is case-insensitive (e.g. 'R1' matches 'r1').
        """
        hostname = self.detect_hostname()
        if not hostname:
            logger.error(
                f"Could not detect hostname — expected '{expected_name}'"
            )
            return False

        if hostname.upper() == expected_name.upper():
            logger.info(
                f"[OK] Hostname verified: '{hostname}' matches expected '{expected_name}'"
            )
            return True
        else:
            logger.error(
                f"[FAIL] Hostname MISMATCH: detected '{hostname}', expected '{expected_name}'"
            )
            return False

    # -- Disconnect ---------------------------------------------------------
    def disconnect_from_device(self):
        """Disconnect from the current telnet session back to the comm server.

        Steps:
          1. Send 'end' + 'exit' repeatedly to leave config/enable modes
          2. Cisco escape sequence: Ctrl+Shift+6 (0x1E) then 'x'
          3. Send 'disconnect' on the comm server to close the session
          4. Confirm the disconnect
          5. Verify we're back at the comm server prompt
        """
        logger.info("Disconnecting from device ...")

        # Step 1 — exit config mode, then exit enable mode
        self._write("end\r\n")
        time.sleep(0.5)
        for _ in range(3):
            self._write("exit\r\n")
            time.sleep(0.5)

        # Step 2 — Cisco escape: Ctrl+Shift+6 (ASCII 0x1E) then 'x'
        logger.info("  Sending Ctrl+Shift+6, x ...")
        self._write("\x1e")
        time.sleep(0.5)
        self._write("x")
        time.sleep(1)
        output = self._read_all()
        logger.debug(f"  After escape: {output}")

        # Step 3 — close the lingering session on the comm server
        self._write("disconnect\r\n")
        time.sleep(1)

        # Step 4 — confirm (comm server may ask "Closing connection… [confirm]")
        self._write("\r\n")
        time.sleep(1)
        output = self._read_all()
        logger.debug(f"  After disconnect: {output}")

        # Step 5 — verify we're back by sending a blank line
        self._write("\r\n")
        time.sleep(1)
        output = self._read_all()
        logger.info(f"  Comm server prompt: {output.strip()[:200]}")
        self.is_connected_to_device = False
        logger.info("Disconnected from device [OK]")

    # -- Configuration helpers ---------------------------------------------
    def _detect_router_mode(self) -> str:
        """Read the current router prompt and return the mode.

        Returns one of: 'user', 'privileged', 'config', 'unknown'.
        """
        self._flush_input()
        self._write("\r\n")
        time.sleep(1)
        output = self._read_all()

        # Match prompt like  R1>  R1#  R1(config)#  R1(config-if)#
        match = re.search(
            r"\S+?(\([^)]*\))?([>#])\s*$", output, re.MULTILINE
        )
        if not match:
            logger.warning(f"Could not detect router mode from: {output.strip()[:200]}")
            return "unknown"

        sub_mode = match.group(1)  # (config), (config-if), or None
        prompt_char = match.group(2)  # > or #

        if sub_mode:
            mode = "config"
        elif prompt_char == "#":
            mode = "privileged"
        elif prompt_char == ">":
            mode = "user"
        else:
            mode = "unknown"

        logger.info(f"Router mode detected: {mode}")
        return mode

    def enter_enable_mode(self):
        """Enter privileged EXEC mode on the router (with password)."""
        mode = self._detect_router_mode()

        if mode == "config":
            # Exit config mode first, then we're in privileged
            logger.info("Already in config mode — sending 'end' first")
            self.send_command("end", wait=1)
        elif mode == "privileged":
            logger.info("Already in privileged EXEC mode — skipping enable")
        else:
            # User mode (>) or unknown — send enable + password
            logger.info("Entering enable mode ...")
            self.send_command("enable", wait=1)
            self.send_command(ENABLE_PASSWORD, wait=1)

    def enter_config_mode(self):
        """Enter global configuration mode."""
        self.send_command("configure terminal", wait=1)

    def exit_config_mode(self):
        """Exit global configuration mode."""
        self.send_command("end", wait=1)

    def save_config(self):
        """Save running-config to startup-config."""
        output = self.send_command("write memory", wait=3)
        logger.info(f"Save config: {output.strip()[:200]}")

    def configure_device(self, commands: list[str]):
        """Ensure enable mode → config mode → send commands → exit → save.

        Detects the current router mode and only sends the necessary
        commands to reach config mode before applying the configuration.
        """
        self.enter_enable_mode()
        self.enter_config_mode()
        self.send_commands(commands)
        self.exit_config_mode()
        self.save_config()


# ---------------------------------------------------------------------------
# Config generation
# ---------------------------------------------------------------------------
from config_ip_address import build_router_commands
from config_static_routes import get_static_route_commands
from utils import kill_common_terminal_apps
from get_config import get_running_config
from datetime import datetime


def save_config_to_file(router_name: str, config_content: str):
    """Save the configuration content to a timestamped file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{router_name}_{timestamp}.txt"
    directory = "config"
    
    if not os.path.exists(directory):
        os.makedirs(directory)
        
    filepath = os.path.join(directory, filename)
    with open(filepath, "w") as f:
        f.write(config_content)
    
    logger.info(f"Configuration saved to {filepath}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # User Menu
    print("\n" + "=" * 60)
    print("  CISCO ROUTER CONFIGURATION & BACKUP TOOL")
    print("=" * 60)
    print("Select an option:")
    print("  [1] Configure devices & Backup")
    print("  [2] Backup running-config ONLY")
    choice = input("\nEnter your choice (1 or 2): ").strip()
    
    do_configure = False
    do_backup = False
    
    if choice == "1":
        do_configure = True
        do_backup = True
        logger.info("Selected: Configure & Backup")
    elif choice == "2":
        do_configure = False
        do_backup = True
        logger.info("Selected: Backup ONLY")
    else:
        print("Invalid choice. Exiting.")
        return

    # Resolve config path relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, CONFIG_FILE)

    # Load router definitions
    logger.info(f"Loading router config from {config_path}")
    with open(config_path, "r") as f:
        config = json.load(f)

    routers = config["routers"]
    logger.info(f"Found {len(routers)} router(s) to configure")

    results: dict[str, str] = {}

    # Keep track of the active configurator for cleanup on Ctrl+C
    active_cfg: ConsoleDeviceConfigurator | None = None

    for router in routers:
        expected_name = router["RouterName"]
        port = router["PortNo"]

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"  {expected_name}  —  telnet {COMM_SERVER_IP} {port}")
        logger.info("=" * 60)

        # ── Fresh serial connection for each router ──────────────────
        try:
            cfg = ConsoleDeviceConfigurator(port=CONSOLE_PORT)
            active_cfg = cfg
            cfg.open()

            try:
                # 1. Telnet into the router via the comm server
                #    (clear line + telnet, with retries on refused)
                connected = cfg.telnet_to_device(COMM_SERVER_IP, port)
                if not connected:
                    logger.error(f"Failed to telnet to {expected_name} after retries")
                    results[expected_name] = "FAILED (telnet — connection refused)"
                    continue

                # 2. Verify we landed on the correct router
                if not cfg.verify_hostname(expected_name):
                    logger.error(
                        f"Hostname verification failed for {expected_name} "
                        f"— skipping config to avoid misconfiguration!"
                    )
                    results[expected_name] = "FAILED (hostname mismatch)"
                    cfg.disconnect_from_device()
                    continue

                # 3. Configure (if requested)
                if do_configure:
                    commands = build_router_commands(expected_name, router)
                    static_routes = get_static_route_commands(router)
                    commands.extend(static_routes)
                    logger.info(f"Sending {len(commands)} commands to {expected_name} ...")
                    cfg.configure_device(commands)
                    results[expected_name] = "CONFIGURED"

                # 4. Backup (if requested)
                if do_backup:
                    logger.info(f"Backing up running-config for {expected_name} ...")
                    running_config = get_running_config(cfg)
                    save_config_to_file(expected_name, running_config)
                    
                    if results.get(expected_name) == "CONFIGURED":
                        results[expected_name] = "CONFIGURED & BACKED UP"
                    else:
                        results[expected_name] = "BACKED UP"

                logger.info(f"{expected_name} processing complete [OK]")

                # 5. Clean disconnect before closing COM6
                cfg.disconnect_from_device()

            finally:
                # Always close the serial port
                cfg.close()
                active_cfg = None

        except serial.SerialException as e:
            logger.error(f"Serial connection error for {expected_name}: {e}")
            results[expected_name] = f"FAILED (serial: {e})"
        except Exception as e:
            logger.exception(f"Unexpected error configuring {expected_name}: {e}")
            results[expected_name] = f"FAILED ({e})"

        # Small pause between routers to let COM6 fully release
        time.sleep(2)

    # -- Summary ------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  CONFIGURATION SUMMARY")
    print("=" * 60)
    for rname, status in results.items():
        icon = "[OK]" if "SUCCESS" in status else "[FAIL]"
        print(f"  {icon}  {rname:6s}  {status}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 60)
        logger.info("  Ctrl+C detected — shutting down gracefully ...")
        logger.info("=" * 60)

        # Try to open a fresh connection to clean up any stale sessions
        try:
            logger.info("Opening COM6 to clean up any stale router sessions ...")
            cleanup = ConsoleDeviceConfigurator(port=CONSOLE_PORT)
            cleanup.open()  # This will auto-detect & escape stale sessions
            cleanup.close()
            logger.info("Cleanup complete [OK]")
        except Exception as e:
            logger.warning(f"Could not perform cleanup: {e}")

        print("\n[WARN] Script interrupted by user. Cleanup attempted.")
        sys.exit(1)
