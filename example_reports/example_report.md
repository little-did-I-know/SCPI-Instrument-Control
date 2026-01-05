# Power Supply Ripple and Noise Test

| Field              | Value                      |
| ------------------ | -------------------------- |
| **Technician**     | John Engineer              |
| **Date**           | 2026-01-02 19:15:39        |
| **Equipment**      | SDS2104X Plus              |
| **Equipment ID**   | SN12345678                 |
| **Test Procedure** | TEST-PS-001 Rev 2.1        |
| **Project**        | DC Power Supply Validation |
| **Customer**       | Acme Electronics           |
| **Temperature**    | 23°C                       |
| **Humidity**       | 45% RH                     |
| **Location**       | Test Lab 3                 |

## Overall Result: ❌ FAIL

## Test Setup

The device under test (DUT) was configured for 5V output with a 1A resistive load. Channel 1 of the oscilloscope was connected to the output using a 1:1 probe. The oscilloscope was set to 100 µs/div timebase with 1 V/div vertical scale.

## Waveform Captures

Captured waveform showing the 1 kHz test signal output.

### Waveforms

#### Power Supply Output

![Power Supply Output](plots/Waveform_Captures_0.png)

| Parameter     | Value           |
| ------------- | --------------- |
| Sample Rate   | 1000.00 MS/s    |
| Record Length | 1000000 samples |
| Timebase      | 100.00 µs/div   |
| Voltage Scale | 1.0 V/div       |
| Probe Ratio   | 1.0:1           |
| Peak-to-Peak  | 4.8598 V        |
| Min           | -2.4402 V       |
| Max           | 2.4195 V        |

### Measurements

| Measurement        | Value      | Status  | Criteria                    |
| ------------------ | ---------- | ------- | --------------------------- |
| Frequency (CH1)    | 1002 Hz    | ✅ PASS | min: 990 Hz<br>max: 1010 Hz |
| Peak-to-Peak (CH1) | 3.98 V     | ✅ PASS | min: 3.8 V<br>max: 4.2 V    |
| RMS (CH1)          | 1.42 V     | ✅ PASS | min: 1.35 V<br>max: 1.5 V   |
| Rise Time (CH1)    | 1.25e-07 s | ❌ FAIL | max: 1e-07 s                |

## Measurement Results

Automated measurements with pass/fail criteria.

### Measurements

| Measurement        | Value      | Status  | Criteria                    |
| ------------------ | ---------- | ------- | --------------------------- |
| Frequency (CH1)    | 1002 Hz    | ✅ PASS | min: 990 Hz<br>max: 1010 Hz |
| Peak-to-Peak (CH1) | 3.98 V     | ✅ PASS | min: 3.8 V<br>max: 4.2 V    |
| RMS (CH1)          | 1.42 V     | ✅ PASS | min: 1.35 V<br>max: 1.5 V   |
| Rise Time (CH1)    | 1.25e-07 s | ❌ FAIL | max: 1e-07 s                |

---

_Report generated on 2026-01-02 at 19:15:39_
_Example Test Laboratory_
