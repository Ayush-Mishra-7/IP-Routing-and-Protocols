# Cisco Router Serial Configuration & Backup Tool

This project provides a robust Python script for automating the configuration and backup of Cisco routers via a serial console server.

## Features

- **Serial Connection Management**: Connects to devices through a Comm Server (e.g., via COM6).
- **Robustness**: automatically detects and closes blocking applications (like PuTTY or Tera Term) that might be holding the serial port open.
- **Connection Stability**: Active keep-alive mechanisms and retry logic for slow-booting routers or noisy serial lines.
- **IP Configuration**: Configures Loopback and physical interfaces based on a JSON config file.
- **Static Routes**: Supports configuring static routes.
- **Configuration Backup**: Automatically saves the `running-config` to timestamped text files.
- **Interactive Workflow**: Choose between "Configure & Backup" or "Backup Only" modes.

## Requirements

- Python 3.6+
- `pyserial`

Install dependencies:
```bash
pip install -r requirements.txt
```

## Setup

1.  **Hardware**: Ensure your computer is connected to the Console Server via serial (e.g., COM6).
2.  **Configuration**: Edit `routers_config.json` to define your routers, interfaces, and static routes.

    ```json
    {
      "routers": [
        {
          "RouterName": "R1",
          "PortNo": 2002,
          "interfaces": {
            "Gi0/0": { "ip": "10.0.0.5", "subnet": "255.255.255.252" }
          },
          "static_routes": [
            { "destination": "10.0.0.16/29", "next_hop": "10.0.0.6" }
          ]
        }
      ]
    }
    ```

## Usage

Run the main script:

```bash
python console_device_config.py
```

You will be prompted to select a mode:

1.  **Configure devices & Backup**: Applies IP addresses, static routes, and 'no shutdown' commands, then saves the running config.
2.  **Backup running-config ONLY**: Connects to each router and saves the current running config without making changes.

## Output

- **Logs**: Detailed execution logs are saved to `console_device_config.log`.
- **Backups**: Configuration files are saved in the `config/` directory, e.g., `config/R1_20260214_153000.txt`.

## Project Structure

- `console_device_config.py`: Main script orchestrating the connection and configuration logic.
- `routers_config.json`: Configuration data (IPs, routes, ports).
- `config_ip_address.py`: Logic for generating IP interface commands.
- `config_static_routes.py`: Logic for generating static route commands.
- `get_config.py`: Logic for retrieving `show running-config` output.
- `utils.py`: Utilities for process management (killing blocking apps).
