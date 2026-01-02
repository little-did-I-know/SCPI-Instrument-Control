# Protocol Decoding

The Protocol Decoding feature decodes digital communication protocols from captured waveforms, making it easy to analyze I2C, SPI, and UART communications. This guide covers protocol decoding in the GUI.

## Overview

Protocol decoding converts raw digital signals into human-readable data, showing:

- Decoded bytes and packets
- Protocol-specific information (addresses, data, control bits)
- Timing and format errors
- Visual overlay on waveforms
- Export of decoded data

### Supported Protocols

- **I2C** (Inter-Integrated Circuit)
- **SPI** (Serial Peripheral Interface)
- **UART** (Universal Asynchronous Receiver/Transmitter)

## Opening Protocol Decode Panel

### Using Control Panel

1. Click **Protocol Decode** tab in left panel
2. Panel opens with protocol selection
3. Configure protocol settings
4. Enable decoding

### Quick Access

- View menu → Protocol Decoding
- Or `Ctrl+P` keyboard shortcut

## I2C Decoding

### I2C Overview

I2C is a two-wire synchronous serial protocol:

- **SDA**: Serial Data line
- **SCL**: Serial Clock line
- **Addressing**: 7-bit or 10-bit addresses
- **Bidirectional**: Master/slave communication

### Configuring I2C Decoder

**1. Select Protocol:**
```
Protocol: I2C
```

**2. Assign Channels:**
```
SDA Channel: C1
SCL Channel: C2
```

**3. Set Parameters:**
```
Address Width: 7-bit (or 10-bit)
Decode Format: Hex (or Binary, Decimal)
```

**4. Enable Decoding:**
```
☑ Enable I2C Decode
```

### I2C Decode Display

**Waveform Overlay:**
- START condition marker (S)
- Address bytes with R/W bit
- Data bytes
- ACK/NACK indicators
- STOP condition marker (P)

**Example Display:**
```
S [0x50 W] A [0x12] A [0x34] A P
```

Where:
- S = START
- 0x50 = 7-bit address (0x28) with W bit
- W = Write
- A = ACK
- N = NACK
- P = STOP

### I2C Decode Table

**Columns:**
- Timestamp
- Event (START, ADDR, DATA, STOP)
- Value
- R/W
- ACK/NACK
- Error

**Example:**
```
Time      | Event | Value  | R/W | ACK | Error
----------|-------|--------|-----|-----|------
0.000 ms  | START | -      | -   | -   | -
0.045 ms  | ADDR  | 0x50   | W   | A   | -
0.135 ms  | DATA  | 0x12   | -   | A   | -
0.225 ms  | DATA  | 0x34   | -   | A   | -
0.315 ms  | STOP  | -      | -   | -   | -
```

### I2C Triggering

**Trigger on I2C Events:**
- START condition
- Specific address
- Specific data value
- STOP condition
- NACK (error)

**Setup:**
1. Trigger tab
2. Type: I2C
3. Condition: Address Match
4. Value: 0x50

## SPI Decoding

### SPI Overview

SPI is a four-wire synchronous serial protocol:

- **MOSI**: Master Out, Slave In (data from master)
- **MISO**: Master In, Slave Out (data from slave)
- **CLK**: Serial Clock
- **CS** (or SS): Chip Select (active low)

### Configuring SPI Decoder

**1. Select Protocol:**
```
Protocol: SPI
```

**2. Assign Channels:**
```
MOSI: C1
MISO: C2
CLK:  C3
CS:   C4
```

**3. Set Parameters:**
```
Clock Polarity (CPOL): 0 (or 1)
Clock Phase (CPHA):    0 (or 1)
Bit Order:             MSB First (or LSB First)
Word Size:             8 bits (8, 16, 32)
CS Polarity:           Active Low (or High)
```

**4. Enable Decoding:**
```
☑ Enable SPI Decode
```

### SPI Clock Modes

**CPOL and CPHA define 4 modes:**

| Mode | CPOL | CPHA | Clock Idle | Sample Edge |
|------|------|------|------------|-------------|
| 0    | 0    | 0    | Low        | Rising      |
| 1    | 0    | 1    | Low        | Falling     |
| 2    | 1    | 0    | High       | Falling     |
| 3    | 1    | 1    | High       | Rising      |

### SPI Decode Display

**Waveform Overlay:**
- MOSI data bytes
- MISO data bytes
- CS active regions
- Byte boundaries

**Example:**
```
CS ↓
MOSI: 0x12 0x34 0x56
MISO: 0xFF 0xAA 0xBB
CS ↑
```

### SPI Decode Table

**Columns:**
- Timestamp
- MOSI Data
- MISO Data
- CS State

**Example:**
```
Time      | MOSI   | MISO   | CS
----------|--------|--------|----
0.000 ms  | -      | -      | ↓
0.080 ms  | 0x12   | 0xFF   | Low
0.160 ms  | 0x34   | 0xAA   | Low
0.240 ms  | 0x56   | 0xBB   | Low
0.320 ms  | -      | -      | ↑
```

## UART Decoding

### UART Overview

UART is asynchronous serial communication:

- **TX**: Transmit data line
- **RX**: Receive data line
- **No clock**: Uses agreed baud rate
- **Frame format**: Start bit, data bits, parity, stop bits

### Configuring UART Decoder

**1. Select Protocol:**
```
Protocol: UART
```

**2. Assign Channels:**
```
TX Channel: C1
RX Channel: C2
```

**3. Set Parameters:**
```
Baud Rate:   9600 (or custom)
Data Bits:   8 (5, 6, 7, 8, 9)
Parity:      None (None, Even, Odd)
Stop Bits:   1 (1, 1.5, 2)
Bit Order:   LSB First (or MSB First)
Polarity:    Non-inverted (or Inverted)
```

**4. Enable Decoding:**
```
☑ Enable UART Decode
```

### Common Baud Rates

- 1200
- 2400
- 4800
- 9600 (common)
- 19200
- 38400
- 57600
- 115200 (common)
- 230400
- 460800
- 921600

### UART Decode Display

**Waveform Overlay:**
- TX data bytes
- RX data bytes
- Frame errors
- Parity errors

**Example:**
```
TX: H e l l o
RX: O K
```

### UART Decode Table

**Columns:**
- Timestamp
- Direction (TX/RX)
- Data (Hex/ASCII)
- Error

**Example:**
```
Time      | Dir | Data (Hex) | ASCII | Error
----------|-----|------------|-------|-------
0.000 ms  | TX  | 0x48       | 'H'   | -
1.042 ms  | TX  | 0x65       | 'e'   | -
2.083 ms  | TX  | 0x6C       | 'l'   | -
3.125 ms  | TX  | 0x6C       | 'l'   | -
4.167 ms  | TX  | 0x6F       | 'o'   | -
5.208 ms  | RX  | 0x4F       | 'O'   | -
6.250 ms  | RX  | 0x4B       | 'K'   | -
```

## Decoding Features

### Display Modes

**Overlay Mode:**
- Decoded data overlaid on waveform
- Color-coded by protocol element
- Helps correlate timing with data

**Table Mode:**
- Decoded data in tabular format
- Easy to read and analyze
- Sortable and filterable

**Both Modes:**
- Show both simultaneously
- Best for analysis

### Data Format Options

**Display Formats:**
- **Hexadecimal**: 0x12, 0x34
- **Decimal**: 18, 52
- **Binary**: 0b00010010, 0b00110100
- **ASCII**: 'A', 'B', 'C'

**Selection:**
```
Format dropdown → Choose format
```

### Error Detection

**Detected Errors:**
- Framing errors (UART)
- Parity errors (UART)
- Missing ACK (I2C)
- Invalid addresses (I2C)
- Bus contentionColor

**Error Highlighting:**
- Red background for errors
- Error column in table
- Visual marker on waveform

## Filtering and Search

### Filter Decoded Data

**Filter by:**
- Protocol element (Address, Data, etc.)
- Value range
- Error status
- Time range

**Example:**
```
Filter: I2C Address = 0x50
Result: Show only transactions to/from 0x50
```

### Search Function

**Search for:**
- Specific byte value
- Byte sequence
- ASCII string (UART)
- Address (I2C)

**Example:**
```
Search: "Hello" in UART data
Result: Highlights all occurrences
```

## Exporting Decoded Data

### Export to CSV

**Format:**
```
Timestamp, Protocol, Event, Value, Details
0.000, I2C, START, -, -
0.045, I2C, ADDR, 0x50, W, ACK
0.135, I2C, DATA, 0x12, ACK
...
```

**To Export:**
1. Protocol Decode tab
2. Click "Export" button
3. Choose file location
4. Save as CSV

### Export to Text

**Human-Readable Format:**
```
I2C Transaction at 0.000 ms:
  START
  Address: 0x50 (Write) - ACK
  Data: 0x12 - ACK
  Data: 0x34 - ACK
  STOP
```

### Include in Waveform Export

When saving waveform:
- Checkbox: "Include protocol decode"
- Decode data saved with waveform
- Reload together

## Live Decoding

### Real-Time Protocol Decode

**Enable Live View + Decode:**

1. Start Live View
2. Enable protocol decoder
3. Decoder processes each frame
4. Table updates in real-time

**Use Cases:**
- Monitor bus traffic
- Debug communication
- Verify protocol compliance
- Capture intermittent errors

### Trigger-Based Capture

**Capture on Protocol Event:**

1. Configure protocol decoder
2. Set trigger on event (e.g., I2C address match)
3. Arm trigger
4. Capture when event occurs

**Example:**
- Trigger on I2C address 0x50
- Capture write to EEPROM
- Decode and save transaction

## Protocol-Specific Examples

### Example 1: I2C EEPROM Read

**Objective:** Decode I2C EEPROM read operation

**Configuration:**
```
Protocol: I2C
SDA: C1
SCL: C2
Address Width: 7-bit
```

**Captured Transaction:**
```
S [0x50 W] A [0x00] A [0x10] A Sr [0x51 R] A [0xAB] A [0xCD] N P
```

**Interpretation:**
1. START
2. Address 0x50 (Write) - ACK
3. Register address 0x00 (high byte) - ACK
4. Register address 0x10 (low byte) - ACK
5. Repeated START
6. Address 0x51 (Read, same device) - ACK
7. Data 0xAB - ACK
8. Data 0xCD - NACK (last byte)
9. STOP

**Result:** Read 2 bytes (0xAB, 0xCD) from address 0x0010

### Example 2: SPI Flash Read

**Objective:** Decode SPI Flash read command

**Configuration:**
```
Protocol: SPI
MOSI: C1, MISO: C2, CLK: C3, CS: C4
Mode: 0 (CPOL=0, CPHA=0)
```

**Captured Transaction:**
```
CS ↓
MOSI: 0x03 0x00 0x10 0x00 [0x00 0x00 ...]
MISO: 0xFF 0xFF 0xFF 0xFF [0x12 0x34 ...]
CS ↑
```

**Interpretation:**
1. CS active (low)
2. Command: 0x03 (Read Data)
3. Address: 0x001000 (24-bit)
4. Dummy bytes from MISO
5. Data from flash: 0x12, 0x34, ...
6. CS inactive (high)

### Example 3: UART AT Commands

**Objective:** Decode UART AT commands

**Configuration:**
```
Protocol: UART
TX: C1, RX: C2
Baud: 115200
Format: 8N1
```

**Captured Data:**
```
TX: "AT\r\n"
RX: "OK\r\n"
TX: "AT+GMR\r\n"
RX: "v1.2.3\r\nOK\r\n"
```

**Interpretation:**
- Send AT command
- Receive OK response
- Query version (AT+GMR)
- Receive version and OK

## Troubleshooting

### No Decode Output

**Problem:** Decoder shows no data

**Solutions:**
1. Verify channels assigned correctly
2. Check signal levels (logic high/low)
3. Verify protocol parameters (baud rate, clock polarity, etc.)
4. Ensure waveform captured
5. Check threshold levels

### Incorrect Decoding

**Problem:** Decoded data incorrect

**Solutions:**
1. Verify baud rate (UART)
2. Check clock polarity/phase (SPI)
3. Verify bit order (MSB/LSB first)
4. Check address width (I2C)
5. Adjust trigger level if needed

### Missing Decodes

**Problem:** Some bytes not decoded

**Solutions:**
1. Increase sample rate
2. Extend capture time
3. Check for signal integrity issues
4. Verify all required signals present (e.g., CS for SPI)

### Frame Errors

**Problem:** Many frame/parity errors

**Solutions:**
1. Verify baud rate is correct
2. Check signal quality
3. Verify parity and stop bit settings
4. Check for clock drift (long transmissions)
5. Ensure proper ground connection

## Tips and Best Practices

### Signal Quality

!!! tip "Clean Signals"
    - Use short ground leads on probes
    - Proper grounding essential
    - Minimize noise and ringing
    - Check signal integrity with eye diagram

### Sample Rate

!!! tip "Adequate Sampling"
    - Sample rate ≥ 10× baud rate (UART)
    - Sample rate ≥ 10× clock frequency (I2C, SPI)
    - Higher is better for reliability
    - Minimum: 4× for basic decoding

### Trigger Setup

!!! tip "Efficient Triggering"
    - Trigger on START condition (I2C)
    - Trigger on CS edge (SPI)
    - Trigger on specific data value
    - Use protocol trigger, not edge trigger

### Analysis Workflow

!!! tip "Systematic Analysis"
    1. Capture known-good transaction first
    2. Verify decoder configuration
    3. Compare with expected data
    4. Look for timing violations
    5. Check for errors and retries

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+P` | Open protocol decode panel |
| `Ctrl+F` | Find/search in decoded data |
| `Ctrl+E` | Export decoded data |
| `Ctrl+R` | Reset decoder |
| `F3` | Find next |
| `Shift+F3` | Find previous |

## Next Steps

- [Interface Guide](interface.md) - Learn all GUI controls
- [Live View](live-view.md) - Real-time protocol decoding
- [Visual Measurements](visual-measurements.md) - Measure timing
- [User Guide](../user-guide/basic-usage.md) - Programmatic protocol decoding
