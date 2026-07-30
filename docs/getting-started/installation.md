# Installation

This page describes how to install SCPI Instrument Control, a universal Python library for SCPI test equipment — oscilloscopes, function generators/AWGs, power supplies, and DAQ units — with a PyQt6 desktop GUI and a browser-based lab gateway.

## Requirements

- **Python**: 3.9 or higher
- **Operating System**: Windows, macOS, or Linux
- **Network**: Ethernet connection to oscilloscope
- **Oscilloscope**: Siglent SDS series with SCPI support

## Standalone Downloads

If you only want the desktop GUI and would rather not install Python at all, every release
attaches a prebuilt bundle for each platform. These carry their own Python runtime and every
dependency, so the Python requirement above does not apply — the network and instrument
requirements still do.

**[Download the latest release](https://github.com/little-did-I-know/SCPI-Instrument-Control/releases/latest)**

| Platform | File | How to run |
| --- | --- | --- |
| Windows (x64) | `SiglentGUI-<version>-Windows-x64.zip` | Extract, then run `SiglentGUI.exe` |
| macOS (Apple Silicon) | `SiglentGUI-<version>-macOS-arm64.zip` | Extract, then open `SiglentGUI.app` |
| macOS (Intel) | `SiglentGUI-<version>-macOS-x86_64.zip` | Extract, then open `SiglentGUI.app` |
| Linux (x86_64) | `SiglentGUI-<version>-Linux-x86_64.tar.gz` | `tar -xzf SiglentGUI-*.tar.gz`, then `./SiglentGUI` |

The bundles are large — roughly 200-300 MB — because each one carries its own Python runtime,
PyQt6 and the scientific stack.

The Intel macOS build is available from **v6.0.0 onward**. Earlier releases shipped an Apple
Silicon build only.

### Which macOS build do I need?

Apple menu → **About This Mac**, or run `uname -m` in Terminal:

- `arm64` → Apple Silicon (M1/M2/M3/M4) → the **arm64** download
- `x86_64` → Intel → the **x86_64** download

### First launch warnings

The executables are **not code-signed**, so each operating system will question them the first
time. This is expected, and the workaround is per-platform:

- **macOS**: right-click the app → **Open** → confirm. Double-clicking alone will refuse it.
- **Windows**: SmartScreen shows "Windows protected your PC" → **More info** → **Run anyway**.
- **Linux**: no warning, but you may need `chmod +x SiglentGUI` before the binary will run.

These bundles give you the desktop GUI only. To use the library from your own scripts, or to run
the `scpi-web` browser gateway, install the Python package as described below.

## Basic Installation

Install the base package using pip:

```bash
pip install "SCPI-Instrument-Control"
```

This provides the core functionality for programmatic control.

## Optional Features

The library provides several optional feature sets that can be installed as needed:

### GUI Application

For the PyQt6-based graphical interface:

```bash
pip install "SCPI-Instrument-Control[gui]"
```

**Includes:**

- PyQt6 >= 6.6.0
- PyQt6-WebEngine >= 6.6.0
- pyqtgraph >= 0.13.0 (high-performance plotting)

### Data Export

For advanced data export formats:

```bash
pip install "SCPI-Instrument-Control[hdf5]"
```

**Includes:**

- h5py >= 3.8.0 (HDF5 file format support)

### Vector Graphics

For XY mode vector graphics and shapes:

```bash
pip install "SCPI-Instrument-Control[fun]"
```

**Includes:**

- shapely >= 2.0.0 (geometric operations)
- Pillow >= 10.0.0 (text rendering)
- svgpathtools >= 1.6.0 (SVG support)

### Web Gateway

For the browser-based lab gateway (a FastAPI server plus a web UI) so any
browser on your LAN can control the instrument, no client install required:

```bash
pip install "SCPI-Instrument-Control[web]"
```

**Includes:**

- fastapi >= 0.115
- uvicorn[standard] >= 0.30
- Pillow >= 10.0

Start it with `scpi-web`. See the [Web Gateway guide](../gateway/index.md) for details.

### USB / GPIB / Serial

For instruments connected via USB, GPIB, or serial instead of Ethernet:

```bash
pip install "SCPI-Instrument-Control[usb]"
```

**Includes:**

- pyvisa >= 1.14.0
- pyvisa-py >= 0.7.0 (pure Python backend, no NI-VISA required)

### All Features

Install everything:

```bash
pip install "SCPI-Instrument-Control[all]"
```

`[all]` does **not** include the web gateway (`[web]`) or USB/GPIB/Serial
support (`[usb]`) — install those explicitly if you need them.

## Development Installation

For contributing to the project:

```bash
# Clone the repository
git clone https://github.com/little-did-I-know/SCPI-Instrument-Control.git
cd SCPI-Instrument-Control

# Install in editable mode with development dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks
make dev-setup
```

**Development extras include:**

- pytest and pytest-cov (testing)
- black (code formatting)
- flake8 (linting)
- isort (import sorting)
- bandit (security checks)
- build and twine (packaging)

## Documentation

To build the documentation locally:

```bash
# Install documentation dependencies
pip install "SCPI-Instrument-Control[docs]"

# Serve documentation locally
mkdocs serve
```

Then open http://127.0.0.1:8000 in your browser.

## Verification

Verify your installation:

```python
import scpi_control
print(scpi_control.__version__)

# Test connection (replace with your oscilloscope IP)
from scpi_control import Oscilloscope
scope = Oscilloscope('192.168.1.100')
scope.connect()
print(scope.identify())
scope.disconnect()
```

Expected output:

```
3.3.0
Siglent Technologies,SDS824X HD,SDSMMDD1XXXXX,8.2.5.1.37R9
```

## Network Configuration

### Finding Your Oscilloscope IP

1. On the oscilloscope, press **Utility** → **System** → **LAN Setup**
2. Note the IP address shown (e.g., 192.168.1.100)
3. Ensure the oscilloscope and your computer are on the same network

### Testing Connection

Ping the oscilloscope to verify network connectivity:

```bash
# Windows/macOS/Linux
ping 192.168.1.100
```

Test SCPI connection using netcat (Linux/macOS):

```bash
# Send *IDN? command
echo "*IDN?" | nc 192.168.1.100 5024
```

Or using PowerShell (Windows):

```powershell
$client = New-Object System.Net.Sockets.TcpClient("192.168.1.100", 5024)
$stream = $client.GetStream()
$writer = New-Object System.IO.StreamWriter($stream)
$reader = New-Object System.IO.StreamReader($stream)
$writer.WriteLine("*IDN?")
$writer.Flush()
$reader.ReadLine()
$client.Close()
```

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'siglent'`

**Solution**: Ensure the package is installed in the correct Python environment:

```bash
# Check which Python you're using
python --version
pip --version

# Install in the correct environment
python -m pip install "SCPI-Instrument-Control"
```

### GUI Missing Dependencies

**Problem**: `ERROR: Missing Required GUI Dependencies`

**Solution**: Install the GUI extras:

```bash
pip install "SCPI-Instrument-Control[gui]"
```

### Connection Refused

**Problem**: `SiglentConnectionError: Failed to connect to 192.168.1.100:5024`

**Possible causes:**

1. **Incorrect IP address** - Verify on oscilloscope settings
2. **Firewall blocking** - Disable firewall temporarily to test
3. **Wrong network** - Ensure computer and oscilloscope are on same subnet
4. **Port 5024 blocked** - Check if another application is using the port

**Solutions:**

```bash
# Test ping first
ping 192.168.1.100

# Check if port is open (Linux/macOS)
nc -zv 192.168.1.100 5024

# Windows: Use Test-NetConnection
Test-NetConnection -ComputerName 192.168.1.100 -Port 5024
```

### Permission Errors (Linux)

**Problem**: Permission denied when accessing network

**Solution**: Run with sudo or add your user to the dialout group:

```bash
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Get started with basic usage
- [Connection Setup](connection.md) - Detailed connection configuration
- [User Guide](../user-guide/basic-usage.md) - Learn all features

## Support

If you encounter issues not covered here:

- Check the [GitHub Issues](https://github.com/little-did-I-know/SCPI-Instrument-Control/issues)
- Ask in [Discussions](https://github.com/little-did-I-know/SCPI-Instrument-Control/discussions)
- Report bugs with detailed error messages and Python version
