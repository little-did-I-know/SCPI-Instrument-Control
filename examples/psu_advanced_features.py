"""Advanced PSU features demonstration.

Demonstrates:
- Data logging (CSV)
- Tracking modes (series/parallel)
- Timer functionality
- Waveform generation
- OVP/OCP protection
"""

import time

from siglent import PowerSupply, PSUDataLogger, TimedPSULogger
from siglent.connection.mock import MockConnection


def demo_data_logging():
    """Demonstrate CSV data logging."""
    print("\n" + "=" * 60)
    print("Data Logging Demo")
    print("=" * 60)

    # Create mock PSU
    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")
    psu = PowerSupply("mock", connection=mock_conn)
    psu.connect()

    print(f"Connected to: {psu.model_capability.model_name}")

    # Configure outputs
    psu.output1.voltage = 5.0
    psu.output1.current = 1.0
    psu.output1.enabled = True

    psu.output2.voltage = 12.0
    psu.output2.current = 0.5
    psu.output2.enabled = True

    # Manual logging
    print("\n1. Manual logging:")
    logger = PSUDataLogger(psu, "psu_manual_log.csv")
    logger.start()

    for i in range(5):
        print(f"   Logging measurement {i+1}/5...")
        logger.log_measurement()
        time.sleep(0.5)

    logger.stop()
    print(f"   Log saved to: {logger.filepath}")

    # Timed logging with context manager
    print("\n2. Timed logging (1 second interval):")
    with TimedPSULogger(psu, "psu_timed_log.csv", interval=1.0) as timed_logger:
        print("   Logging started (will run for 5 seconds)...")
        time.sleep(5)
    print(f"   Log saved to: {timed_logger.logger.filepath}")

    # Selective output logging
    print("\n3. Selective output logging (output 1 only):")
    with PSUDataLogger(psu, "psu_output1_log.csv", outputs=[1]) as selective_logger:
        for i in range(3):
            print(f"   Logging output 1 measurement {i+1}/3...")
            selective_logger.log_measurement()
            time.sleep(0.5)
    print(f"   Log saved to: {selective_logger.filepath}")

    psu.all_outputs_off()
    psu.disconnect()
    print("\nData logging demo complete!")


def demo_tracking_modes():
    """Demonstrate tracking modes (series/parallel)."""
    print("\n" + "=" * 60)
    print("Tracking Modes Demo")
    print("=" * 60)

    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")
    psu = PowerSupply("mock", connection=mock_conn)
    psu.connect()

    if not psu.model_capability.has_tracking:
        print("Tracking not supported on this model")
        return

    print(f"Connected to: {psu.model_capability.model_name}")

    # Independent mode (default)
    print("\n1. Independent Mode:")
    psu.set_independent_mode()
    psu.output1.voltage = 5.0
    psu.output2.voltage = 12.0
    print(f"   Tracking mode: {psu.tracking_mode}")
    print(f"   Output 1: {psu.output1.voltage}V")
    print(f"   Output 2: {psu.output2.voltage}V")

    # Series mode
    print("\n2. Series Mode:")
    print("   In series mode, voltages add (V_total = V1 + V2)")
    psu.set_series_mode()
    psu.output1.voltage = 10.0
    psu.output2.voltage = 15.0
    print(f"   Tracking mode: {psu.tracking_mode}")
    print(f"   Output 1: {psu.output1.voltage}V")
    print(f"   Output 2: {psu.output2.voltage}V")
    print(f"   Total voltage: {psu.output1.voltage + psu.output2.voltage}V")

    # Parallel mode
    print("\n3. Parallel Mode:")
    print("   In parallel mode, currents add (I_total = I1 + I2)")
    psu.set_parallel_mode()
    psu.output1.current = 1.0
    psu.output2.current = 1.5
    print(f"   Tracking mode: {psu.tracking_mode}")
    print(f"   Output 1: {psu.output1.current}A")
    print(f"   Output 2: {psu.output2.current}A")
    print(f"   Total current: {psu.output1.current + psu.output2.current}A")

    # Back to independent
    psu.set_independent_mode()
    psu.all_outputs_off()
    psu.disconnect()
    print("\nTracking modes demo complete!")


def demo_timer_functionality():
    """Demonstrate timer functionality (Siglent-specific)."""
    print("\n" + "=" * 60)
    print("Timer Functionality Demo")
    print("=" * 60)

    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")
    psu = PowerSupply("mock", connection=mock_conn)
    psu.connect()

    if not psu.model_capability.has_timer:
        print("Timer not supported on this model")
        return

    print(f"Connected to: {psu.model_capability.model_name}")

    # Enable timer on output 1
    print("\n1. Enabling timer on output 1:")
    output = psu.output1
    output.voltage = 5.0
    output.current = 1.0

    print(f"   Timer enabled: {output.timer_enabled}")
    output.timer_enabled = True
    print(f"   Timer enabled: {output.timer_enabled}")
    print("   Timer can be configured for scheduled voltage/current changes")

    # Disable timer
    output.timer_enabled = False
    print(f"   Timer disabled: {not output.timer_enabled}")

    psu.disconnect()
    print("\nTimer functionality demo complete!")


def demo_waveform_generation():
    """Demonstrate waveform generation (SPD3303X-specific)."""
    print("\n" + "=" * 60)
    print("Waveform Generation Demo")
    print("=" * 60)

    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")
    psu = PowerSupply("mock", connection=mock_conn)
    psu.connect()

    if not psu.model_capability.has_waveform:
        print("Waveform generation not supported on this model")
        return

    print(f"Connected to: {psu.model_capability.model_name}")

    # Enable waveform on output 1
    print("\n1. Enabling waveform generation on output 1:")
    output = psu.output1
    output.voltage = 5.0

    print(f"   Waveform enabled: {output.waveform_enabled}")
    output.waveform_enabled = True
    print(f"   Waveform enabled: {output.waveform_enabled}")
    print("   Can generate sine, square, ramp, pulse, and noise waveforms")
    print("   Useful for ripple testing, dynamic load simulation, etc.")

    # Disable waveform
    output.waveform_enabled = False
    print(f"   Waveform disabled: {not output.waveform_enabled}")

    psu.disconnect()
    print("\nWaveform generation demo complete!")


def demo_ovp_ocp_protection():
    """Demonstrate OVP/OCP protection limits."""
    print("\n" + "=" * 60)
    print("OVP/OCP Protection Demo")
    print("=" * 60)

    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")
    psu = PowerSupply("mock", connection=mock_conn)
    psu.connect()

    print(f"Connected to: {psu.model_capability.model_name}")

    output = psu.output1

    # OVP (Over-Voltage Protection)
    if psu.model_capability.has_ovp:
        print("\n1. Over-Voltage Protection (OVP):")
        print(f"   Output 1 max voltage: {output._spec.max_voltage}V")
        ovp_limit = 25.0
        output.ovp_level = ovp_limit
        print(f"   OVP set to: {output.ovp_level}V")
        print(f"   PSU will shut down if voltage exceeds {ovp_limit}V")
    else:
        print("\n1. OVP not supported on this model")

    # OCP (Over-Current Protection)
    if psu.model_capability.has_ocp:
        print("\n2. Over-Current Protection (OCP):")
        print(f"   Output 1 max current: {output._spec.max_current}A")
        ocp_limit = 2.5
        output.ocp_level = ocp_limit
        print(f"   OCP set to: {output.ocp_level}A")
        print(f"   PSU will shut down if current exceeds {ocp_limit}A")
    else:
        print("\n2. OCP not supported on this model")

    psu.disconnect()
    print("\nOVP/OCP protection demo complete!")


def demo_real_world_scenario():
    """Demonstrate a real-world testing scenario."""
    print("\n" + "=" * 60)
    print("Real-World Scenario: Automated Device Characterization")
    print("=" * 60)

    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")
    psu = PowerSupply("mock", connection=mock_conn)
    psu.connect()

    print(f"Connected to: {psu.model_capability.model_name}")
    print("\nScenario: Testing a device at different voltage levels")
    print("Logging power consumption at each voltage step")

    # Set up protection
    psu.output1.ovp_level = 15.0
    psu.output1.ocp_level = 2.0
    print(f"\nSafety limits: OVP={psu.output1.ovp_level}V, OCP={psu.output1.ocp_level}A")

    # Start data logging
    with PSUDataLogger(psu, "characterization_log.csv", outputs=[1]) as logger:
        print("\nStarting characterization sweep:")

        # Test at different voltages
        test_voltages = [3.3, 5.0, 9.0, 12.0]

        for voltage in test_voltages:
            print(f"\n  Testing at {voltage}V:")
            psu.output1.voltage = voltage
            psu.output1.current = 2.0  # 2A current limit
            psu.output1.enabled = True

            # Wait for settling
            time.sleep(0.5)

            # Log measurements
            for i in range(3):
                logger.log_measurement()
                v_actual = psu.output1.measure_voltage()
                i_actual = psu.output1.measure_current()
                p_actual = psu.output1.measure_power()
                mode = psu.output1.get_mode()

                print(f"    Sample {i+1}: {v_actual:.3f}V, {i_actual:.3f}A, {p_actual:.3f}W [{mode}]")
                time.sleep(0.5)

        psu.output1.enabled = False

    print(f"\nCharacterization complete! Data saved to: characterization_log.csv")
    psu.disconnect()


if __name__ == "__main__":
    print("=" * 60)
    print("Siglent PSU Advanced Features Demonstration")
    print("=" * 60)
    print("\nThis demo shows advanced PSU capabilities:")
    print("- Data logging (CSV)")
    print("- Tracking modes (series/parallel)")
    print("- Timer functionality")
    print("- Waveform generation")
    print("- OVP/OCP protection")
    print("\nUsing mock connection (no hardware required)")

    try:
        # Run all demos
        demo_data_logging()
        demo_tracking_modes()
        demo_timer_functionality()
        demo_waveform_generation()
        demo_ovp_ocp_protection()
        demo_real_world_scenario()

        print("\n" + "=" * 60)
        print("All demos completed successfully!")
        print("=" * 60)
        print("\nCheck the generated CSV files:")
        print("- psu_manual_log.csv")
        print("- psu_timed_log.csv")
        print("- psu_output1_log.csv")
        print("- characterization_log.csv")

    except Exception as e:
        print(f"\nError during demo: {e}")
        import traceback

        traceback.print_exc()
