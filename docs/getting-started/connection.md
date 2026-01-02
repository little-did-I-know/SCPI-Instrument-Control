# Connection Setup

This guide provides detailed instructions for connecting to your Siglent oscilloscope over the network, including network configuration, troubleshooting, and advanced connection options.

## Overview

The Siglent Oscilloscope Control library communicates with oscilloscopes using the SCPI (Standard Commands for Programmable Instruments) protocol over TCP/IP. This allows:

- **Remote Control**: Send commands from your computer
- **Data Retrieval**: Download waveforms and screenshots
- **Automation**: Script complex measurement sequences
- **GUI Control**: Use the PyQt6 GUI interface
- **Multi-Scope Access**: Control multiple oscilloscopes

### Connection Methods

**LAN (Ethernet)** - Recommended
- Fast and reliable
- Best performance for live view
- No special drivers needed
- Works across platforms

**USB** - Not directly supported
- Requires USBTMC drivers
- Platform-specific limitations
- Use LAN for best results

**GPIB** - Not supported
- Legacy interface
- Requires GPIB adapter
- Use LAN instead

## Prerequisites

### Hardware Requirements

**Oscilloscope:**
- Siglent SDS1000X-E, SDS2000X-E, or SDS5000X series
- Ethernet port
- Network connectivity enabled

**Computer:**
- Network interface (Ethernet or WiFi)
- Python 3.8 or later installed
- Siglent library installed: `pip install Siglent-Oscilloscope`

**Network:**
- Ethernet cable (for direct connection)
- Network switch/router (for network connection)
- Same subnet for oscilloscope and computer

### Software Requirements

**Python Packages:**
```bash
pip install Siglent-Oscilloscope
```

**Optional for GUI:**
```bash
pip install "Siglent-Oscilloscope[gui]"
```

**Network Tools (for troubleshooting):**
- `ping` - Test connectivity
- `nmap` - Scan for devices
- `telnet` or `nc` - Test port access

## Finding Your Oscilloscope

### From the Oscilloscope

**Method 1: Utility Menu**
1. Press **Utility** button on oscilloscope
2. Navigate to **IO Setting** → **LAN Config**
3. Note the IP address shown

**Method 2: System Info**
1. Press **Utility** button
2. Select **System** → **System Info**
3. IP address displayed in network section

**Typical Display:**
```
IP Address: 192.168.1.100
Subnet Mask: 255.255.255.0
Gateway: 192.168.1.1
Port: 5024
```

### Network Scanning

**Using nmap (Linux/Mac):**
```bash
# Scan your local network
nmap -p 5024 192.168.1.0/24

# Example output:
# Nmap scan report for 192.168.1.100
# PORT     STATE SERVICE
# 5024/tcp open  scpi-raw
```

**Using Siglent Discovery Tool:**
```python
from siglent.discovery import find_oscilloscopes

# Scan network for Siglent devices
scopes = find_oscilloscopes()
for scope in scopes:
    print(f"Found: {scope.model} at {scope.ip_address}")
```

**Manual Check:**
```bash
# Ping common IP addresses
ping 192.168.1.100
ping 192.168.1.101
# etc.
```

## Network Configuration

### Direct Connection (PC to Scope)

**Easiest for single oscilloscope:**

1. **Connect Ethernet Cable**
   - Connect PC network port to oscilloscope
   - Use standard Ethernet cable (Cat5e or better)

2. **Configure Oscilloscope**
   - Utility → IO Setting → LAN Config
   - Set IP: `192.168.1.100`
   - Subnet: `255.255.255.0`
   - Gateway: `192.168.1.1`
   - Apply settings

3. **Configure PC**

   **Windows:**
   - Control Panel → Network and Sharing Center
   - Change adapter settings
   - Right-click Ethernet → Properties
   - Internet Protocol Version 4 (TCP/IPv4)
   - Set IP: `192.168.1.10`
   - Subnet: `255.255.255.0`

   **Linux:**
   ```bash
   sudo ip addr add 192.168.1.10/24 dev eth0
   ```

   **macOS:**
   - System Preferences → Network
   - Select Ethernet
   - Configure IPv4: Manually
   - IP: `192.168.1.10`
   - Subnet: `255.255.255.0`

4. **Test Connection**
   ```bash
   ping 192.168.1.100
   ```

### Network Connection (via Router/Switch)

**Best for multiple devices:**

1. **Connect to Network**
   - Connect oscilloscope to network switch/router
   - Connect PC to same network

2. **Configure Oscilloscope**

   **Option A: DHCP (Automatic)**
   - Utility → IO Setting → LAN Config
   - Enable DHCP
   - Note assigned IP address
   - Recommended for most users

   **Option B: Static IP**
   - Disable DHCP
   - Set IP: `192.168.1.100` (or available address)
   - Subnet: `255.255.255.0` (match your network)
   - Gateway: `192.168.1.1` (your router IP)
   - DNS: `192.168.1.1` or `8.8.8.8`

3. **Verify Connection**
   ```bash
   ping 192.168.1.100
   ```

### Firewall Configuration

**Windows Firewall:**
```powershell
# Allow Python through firewall
netsh advfirewall firewall add rule name="Python SCPI" dir=in action=allow program="C:\Python39\python.exe" enable=yes

# Or allow port 5024
netsh advfirewall firewall add rule name="SCPI Port" dir=in action=allow protocol=TCP localport=5024
```

**Linux (ufw):**
```bash
sudo ufw allow from 192.168.1.100 to any port 5024
```

**macOS:**
- System Preferences → Security & Privacy → Firewall
- Firewall Options
- Add Python application
- Allow incoming connections

## Making Your First Connection

### Using Python API

**Basic Connection:**
```python
from siglent import Oscilloscope

# Connect to oscilloscope
scope = Oscilloscope('192.168.1.100')

# Get identification
print(scope.idn)
# Output: SIGLENT TECHNOLOGIES,SDS2104X Plus,...

# Close connection
scope.close()
```

**Using Context Manager (Recommended):**
```python
from siglent import Oscilloscope

with Oscilloscope('192.168.1.100') as scope:
    print(f"Connected to {scope.model}")
    print(f"Serial: {scope.serial_number}")
    # Connection automatically closed
```

**With Custom Timeout:**
```python
scope = Oscilloscope('192.168.1.100', timeout=10.0)
```

**Custom Port:**
```python
scope = Oscilloscope('192.168.1.100', port=5025)
```

### Using GUI Application

**Launch GUI:**
```bash
siglent-gui
```

**Connection Steps:**
1. Click **Connect** button or press `Ctrl+O`
2. Enter oscilloscope IP address
3. (Optional) Set timeout and port
4. Click **Connect**
5. Connection status shown in status bar

**Save Connection Profile:**
1. After entering IP address
2. Enter a name (e.g., "Lab Scope")
3. Click **Save Profile**
4. Quick access from File → Recent Connections

## Testing Your Connection

### Verify Connectivity

**Ping Test:**
```bash
ping 192.168.1.100
# Should see replies
```

**Port Test:**
```bash
# Using telnet
telnet 192.168.1.100 5024

# Using netcat
nc -zv 192.168.1.100 5024
# Should show "succeeded" or "open"
```

**Python Test:**
```python
from siglent import Oscilloscope

try:
    with Oscilloscope('192.168.1.100', timeout=5) as scope:
        print(f"✓ Connected to {scope.model}")
        print(f"✓ Firmware: {scope.firmware_version}")
        print(f"✓ Serial: {scope.serial_number}")
        print("Connection successful!")
except TimeoutError:
    print("✗ Connection timeout - check IP and network")
except ConnectionRefusedError:
    print("✗ Connection refused - check oscilloscope LAN enabled")
except Exception as e:
    print(f"✗ Error: {e}")
```

### Performance Test

**Measure Latency:**
```python
from siglent import Oscilloscope
import time

with Oscilloscope('192.168.1.100') as scope:
    start = time.time()
    for i in range(10):
        _ = scope.idn
    elapsed = time.time() - start

    latency = elapsed / 10 * 1000  # ms per command
    print(f"Average latency: {latency:.1f} ms")
```

**Expected Latency:**
- **Direct/LAN**: 5-20 ms
- **WiFi**: 10-50 ms
- **Remote/VPN**: 50-200 ms

**Transfer Speed:**
```python
from siglent import Oscilloscope
import time

with Oscilloscope('192.168.1.100') as scope:
    scope.channel1.enabled = True

    start = time.time()
    waveform = scope.get_waveform(1)
    elapsed = time.time() - start

    samples = len(waveform.data)
    speed = samples / elapsed / 1000  # kSa/s
    print(f"Transfer speed: {speed:.1f} kSa/s")
```

**Expected Speed:**
- **Gigabit LAN**: 500-2000 kSa/s
- **100 Mbps LAN**: 100-500 kSa/s
- **WiFi**: 50-300 kSa/s

## Advanced Connection Options

### Connection Profiles

**Save Multiple Scopes:**
```python
from siglent import ConnectionManager

# Create connection manager
manager = ConnectionManager()

# Add profiles
manager.add_profile('lab_scope', '192.168.1.100')
manager.add_profile('bench_scope', '192.168.1.101', port=5025)

# Connect to a profile
scope = manager.connect('lab_scope')

# List profiles
for name, config in manager.profiles.items():
    print(f"{name}: {config['ip']}")
```

**Configuration File (~/.siglent/connections.json):**
```json
{
  "lab_scope": {
    "ip": "192.168.1.100",
    "port": 5024,
    "timeout": 5.0
  },
  "bench_scope": {
    "ip": "192.168.1.101",
    "port": 5024,
    "timeout": 5.0
  }
}
```

### Multiple Oscilloscopes

**Connect to Multiple Scopes:**
```python
from siglent import Oscilloscope

# Connect to two oscilloscopes
scope1 = Oscilloscope('192.168.1.100')
scope2 = Oscilloscope('192.168.1.101')

print(f"Scope 1: {scope1.model}")
print(f"Scope 2: {scope2.model}")

# Use both
waveform1 = scope1.get_waveform(1)
waveform2 = scope2.get_waveform(1)

# Close connections
scope1.close()
scope2.close()
```

**Using Context Managers:**
```python
from siglent import Oscilloscope

with Oscilloscope('192.168.1.100') as scope1, \
     Oscilloscope('192.168.1.101') as scope2:

    # Synchronized capture
    scope1.trigger.single()
    scope2.trigger.single()

    # Get waveforms
    data1 = scope1.get_waveform(1)
    data2 = scope2.get_waveform(1)
```

### Hostname/DNS

**Use Hostname Instead of IP:**
```python
# If DNS/mDNS is configured
scope = Oscilloscope('scope.local')
scope = Oscilloscope('lab-scope.example.com')
```

**Configure mDNS on Oscilloscope:**
1. Utility → IO Setting → LAN Config
2. Set hostname: `lab-scope`
3. Enable mDNS (if available)
4. Connect using: `lab-scope.local`

**Add to /etc/hosts (Linux/Mac):**
```bash
sudo nano /etc/hosts
# Add line:
192.168.1.100  lab-scope
```

**Windows hosts file:**
```
C:\Windows\System32\drivers\etc\hosts
# Add line:
192.168.1.100  lab-scope
```

### VNC Access

**Enable VNC Server on Oscilloscope:**
1. Utility → IO Setting → VNC Config
2. Enable VNC Server
3. Set password (optional but recommended)
4. Note VNC port (default: 5900)

**Using GUI VNC Viewer:**
```bash
siglent-gui
# Tools → VNC Viewer
# Enter IP address
```

**Standalone VNC Client:**
```bash
# Using TightVNC, RealVNC, etc.
vncviewer 192.168.1.100:5900
```

**Python VNC Access:**
```python
from siglent import Oscilloscope

with Oscilloscope('192.168.1.100') as scope:
    # Capture oscilloscope screen via VNC
    screenshot = scope.vnc.capture_screen()
    screenshot.save('scope_screen.png')
```

## Security Considerations

### Network Security

!!! warning "Security Best Practices"
    - Use isolated network for lab equipment
    - Don't expose oscilloscope to internet
    - Use VPN for remote access
    - Change default passwords
    - Disable unused services

**Isolated Network:**
- Dedicated VLAN for test equipment
- Separate from corporate network
- Firewall rules to control access

**VPN Access:**
```
[Your Computer] → [VPN] → [Lab Network] → [Oscilloscope]
```

Better than direct internet exposure

### Authentication

**SCPI Protocol:**
- No built-in authentication
- Anyone on network can connect
- Use network security for protection

**VNC Server:**
- Set strong password
- Change from default
- Use encrypted VNC if possible

**Best Practices:**
1. Physical network security
2. Firewall rules
3. Access control lists
4. Regular firmware updates

## Troubleshooting

### Cannot Find Oscilloscope

**Problem:** Can't locate oscilloscope on network

**Solutions:**

1. **Verify Physical Connection**
   - Ethernet cable plugged in both ends
   - Link lights on both ports
   - Try different cable

2. **Check Oscilloscope LAN Settings**
   - Utility → IO Setting → LAN Config
   - LAN enabled
   - Valid IP address
   - Correct subnet mask

3. **Check Same Subnet**
   ```bash
   # Your PC: 192.168.1.10/255.255.255.0
   # Scope must be: 192.168.1.x/255.255.255.0
   ```

4. **Try DHCP**
   - Enable DHCP on oscilloscope
   - Check router's DHCP client list
   - Note assigned IP

5. **Scan Network**
   ```bash
   nmap -p 5024 192.168.1.0/24
   ```

### Connection Timeout

**Problem:** "Connection timeout" error

**Solutions:**

1. **Verify Connectivity**
   ```bash
   ping 192.168.1.100
   ```
   If ping fails, network issue

2. **Check Port 5024**
   ```bash
   telnet 192.168.1.100 5024
   ```
   Should connect immediately

3. **Check Firewall**
   - Temporarily disable firewall to test
   - Add exception for Python/port 5024
   - Re-enable firewall

4. **Increase Timeout**
   ```python
   scope = Oscilloscope('192.168.1.100', timeout=10.0)
   ```

5. **Check Oscilloscope**
   - Reboot oscilloscope
   - Verify SCPI service running
   - Check for firmware issues

### Connection Refused

**Problem:** "Connection refused" error

**Solutions:**

1. **Check SCPI Server**
   - Oscilloscope may not have SCPI server running
   - Reboot oscilloscope
   - Check IO settings

2. **Verify Port Number**
   ```python
   # Try default ports
   scope = Oscilloscope('192.168.1.100', port=5024)  # SCPI
   scope = Oscilloscope('192.168.1.100', port=5025)  # Alternative
   ```

3. **Check for Other Connections**
   - Only one active connection allowed (some models)
   - Close other SCPI applications
   - Disconnect web interface

### Slow Performance

**Problem:** Commands are slow or timeouts occur

**Solutions:**

1. **Check Network Speed**
   ```python
   # Measure latency (see Performance Test above)
   ```

2. **Use Wired Connection**
   - WiFi has higher latency
   - Use Ethernet for best performance

3. **Reduce Waveform Size**
   ```python
   # Get fewer points
   waveform = scope.get_waveform(1, max_points=1000)
   ```

4. **Check Network Load**
   - Other traffic on network
   - Large file transfers
   - Video streaming

5. **Optimize Code**
   ```python
   # Bad: Many small commands
   for i in range(100):
       scope.write(f"C1:VDIV {i/100}")

   # Good: Batch operations
   scope.channel1.voltage_scale = 1.0
   ```

### Intermittent Disconnections

**Problem:** Connection drops randomly

**Solutions:**

1. **Check Cable**
   - Replace Ethernet cable
   - Check for damage
   - Ensure secure connections

2. **Check Network Switch**
   - Switch may be dropping link
   - Try different port
   - Update switch firmware

3. **Power Management**
   - Disable network adapter power saving
   - Windows: Device Manager → Network Adapter → Power Management → Uncheck "Allow computer to turn off"

4. **Update Firmware**
   - Check for oscilloscope firmware updates
   - Update to latest stable version

5. **Increase Keepalive**
   ```python
   # Send periodic commands to keep connection alive
   scope = Oscilloscope('192.168.1.100', keepalive=True)
   ```

### Wrong Oscilloscope Model

**Problem:** Connected to wrong scope

**Solutions:**

1. **Verify IP Address**
   ```python
   with Oscilloscope('192.168.1.100') as scope:
       print(f"Connected to: {scope.model}")
       print(f"Serial: {scope.serial_number}")
   ```

2. **Use Connection Profiles**
   - Name profiles clearly
   - Include location/purpose
   - "Lab Bench 1", "Production Test", etc.

3. **Check Physical Labels**
   - Label oscilloscopes with IP addresses
   - Update labels when IP changes

## Remote Access

### SSH Tunnel

**Access oscilloscope remotely via SSH:**

```bash
# On remote machine with SSH access
ssh -L 5024:192.168.1.100:5024 user@lab-server.com

# On your local machine
python3
>>> from siglent import Oscilloscope
>>> scope = Oscilloscope('localhost')  # Connects through tunnel
```

### VPN Connection

**Setup:**
1. Configure VPN to lab network
2. Connect to VPN
3. Access oscilloscope using lab IP
4. Works like local connection

**Example:**
```python
# After VPN connected
from siglent import Oscilloscope

# Use oscilloscope's IP on lab network
scope = Oscilloscope('10.0.50.100')
```

### Port Forwarding (Not Recommended)

!!! warning "Security Risk"
    Exposing oscilloscope directly to internet is a security risk. Use VPN instead.

If you must:
```
Router: Forward external:5024 → 192.168.1.100:5024
Access: scope = Oscilloscope('your-public-ip', timeout=30)
```

## Best Practices

### Connection Management

!!! tip "Use Context Managers"
    Always use `with` statements to ensure connections are closed properly:
    ```python
    with Oscilloscope('192.168.1.100') as scope:
        # Your code here
        pass
    # Connection automatically closed
    ```

### Error Handling

!!! tip "Handle Connection Errors"
    ```python
    from siglent import Oscilloscope
    import time

    def connect_with_retry(ip, max_retries=3):
        for attempt in range(max_retries):
            try:
                scope = Oscilloscope(ip, timeout=5)
                print(f"Connected to {scope.model}")
                return scope
            except (TimeoutError, ConnectionError) as e:
                print(f"Attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    raise

    scope = connect_with_retry('192.168.1.100')
    ```

### Network Configuration

!!! tip "Static IP for Lab Equipment"
    - Use static IP addresses for oscilloscopes
    - Document IP addresses
    - Keep list of equipment and IPs
    - Use consistent IP scheme (e.g., .100-.199 for scopes)

### Performance Optimization

!!! tip "Optimize for Your Use Case"
    - **Live View**: Use Gigabit Ethernet, minimize latency
    - **Batch Capture**: Wired connection, optimize data transfer
    - **Automation**: Increase timeout for long operations
    - **Remote**: Use VPN, increase timeout, reduce data size

## Example Configurations

### Home Lab Setup

**Equipment:**
- 1 oscilloscope
- 1 PC
- Direct Ethernet connection

**Configuration:**
```
Oscilloscope:
  IP: 192.168.1.100
  Subnet: 255.255.255.0

PC:
  IP: 192.168.1.10
  Subnet: 255.255.255.0

Connection:
  Direct Ethernet cable
  No router needed
```

### University Lab

**Equipment:**
- Multiple oscilloscopes
- Multiple PCs
- Network switch

**Configuration:**
```
Network: 192.168.50.0/24
Router/DHCP: 192.168.50.1

Scopes (Static IPs):
  Bench 1: 192.168.50.101
  Bench 2: 192.168.50.102
  Bench 3: 192.168.50.103

PCs (DHCP):
  Auto-assigned: 192.168.50.10-50.99
```

### Industrial Test Station

**Equipment:**
- Production oscilloscope
- Test PC
- Isolated network

**Configuration:**
```
Dedicated VLAN: 10.50.0.0/24

Oscilloscope:
  IP: 10.50.0.100
  Subnet: 255.255.255.0
  Gateway: 10.50.0.1

Test PC:
  IP: 10.50.0.10
  Subnet: 255.255.255.0

Firewall:
  Allow: 10.50.0.0/24 → 10.50.0.100:5024
  Block: All other traffic
```

## Quick Reference

### Common IP Addresses

| Device | Typical IP | Port |
|--------|-----------|------|
| Oscilloscope (SCPI) | 192.168.1.100 | 5024 |
| Oscilloscope (VNC) | 192.168.1.100 | 5900 |
| Oscilloscope (Web) | 192.168.1.100 | 80 |

### Default Settings

| Parameter | Default Value |
|-----------|---------------|
| Port | 5024 (SCPI) |
| Timeout | 5.0 seconds |
| Subnet Mask | 255.255.255.0 |
| VNC Port | 5900 |

### Network Commands

```bash
# Ping test
ping 192.168.1.100

# Port scan
nmap -p 5024 192.168.1.100

# Port test
nc -zv 192.168.1.100 5024

# Trace route
traceroute 192.168.1.100
```

### Python Connection Examples

```python
# Basic connection
from siglent import Oscilloscope
scope = Oscilloscope('192.168.1.100')

# With timeout
scope = Oscilloscope('192.168.1.100', timeout=10)

# Custom port
scope = Oscilloscope('192.168.1.100', port=5025)

# Context manager (recommended)
with Oscilloscope('192.168.1.100') as scope:
    print(scope.idn)
```

## Next Steps

Now that you have a working connection:

- [Quick Start Guide](quickstart.md) - Basic usage examples
- [User Guide: Basic Usage](../user-guide/basic-usage.md) - Learn core functionality
- [GUI Overview](../gui/overview.md) - Use the graphical interface
- [API Reference](../api/oscilloscope.md) - Complete API documentation

## Additional Resources

**Siglent Resources:**
- [Siglent Official Website](https://www.siglentamerica.com/)
- Oscilloscope User Manual
- Programming Manual (SCPI commands)

**Network Tools:**
- [Wireshark](https://www.wireshark.org/) - Network packet analysis
- [nmap](https://nmap.org/) - Network scanner
- Advanced IP Scanner (Windows)

**Support:**
- GitHub Issues: Report problems
- Documentation: This guide
- Community Forums: Ask questions
