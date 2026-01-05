"""Test the power supply GUI with a mock connection.

This script demonstrates the PSU control GUI using a mock connection,
allowing you to test the interface without physical hardware.
"""

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from siglent import PowerSupply
from siglent.connection.mock import MockConnection
from siglent.gui.main_window import MainWindow


def test_psu_gui_with_mock():
    """Launch GUI and connect to mock PSU."""
    app = QApplication(sys.argv)

    # Create main window
    window = MainWindow()
    window.show()

    # Create mock PSU connection
    print("Creating mock PSU connection (Siglent SPD3303X)...")
    mock_conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,V1.01")

    # Create PSU instance with mock connection
    psu = PowerSupply("mock", connection=mock_conn)

    try:
        # Connect to mock PSU
        psu.connect()
        print(f"Connected to: {psu.model_capability.model_name}")
        print(f"Outputs: {psu.model_capability.num_outputs}")

        # Pass PSU to GUI
        window.psu = psu
        window.psu_control.set_psu(psu)

        # Switch to Power Supply tab
        for i in range(window.tabs.count()):
            if window.tabs.tabText(i) == "Power Supply":
                window.tabs.setCurrentIndex(i)
                break

        # Show connection info
        info_msg = (
            f"Mock PSU Connected!\n\n"
            f"Model: {psu.model_capability.model_name}\n"
            f"Outputs: {psu.model_capability.num_outputs}\n"
            f"SCPI Variant: {psu.model_capability.scpi_variant}\n\n"
            f"You can now test the PSU controls:\n"
            f"- Set voltage and current\n"
            f"- Enable/disable outputs\n"
            f"- View real-time measurements\n"
            f"- Test the safety 'All Off' button"
        )
        QMessageBox.information(window, "Mock PSU Connected", info_msg)

        print("\nGUI launched successfully!")
        print("Try the PSU controls in the 'Power Supply' tab")
        print("\nInstructions:")
        print("1. Adjust voltage and current sliders")
        print("2. Enable outputs with checkboxes")
        print("3. Watch real-time measurements update")
        print("4. Test the 'All Outputs OFF' safety button")

        # Run the application
        sys.exit(app.exec())

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


def test_generic_psu():
    """Test with a generic SCPI PSU."""
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    # Create mock generic PSU connection
    print("Creating mock generic PSU connection...")
    mock_conn = MockConnection(psu_mode=True, psu_idn="RIGOL TECHNOLOGIES,DP832,DP8XXXX,V1.0")

    psu = PowerSupply("mock", connection=mock_conn)

    try:
        psu.connect()
        print(f"Connected to: {psu.model_capability.model_name}")
        print(f"SCPI Variant: {psu.model_capability.scpi_variant}")

        window.psu = psu
        window.psu_control.set_psu(psu)

        # Switch to Power Supply tab
        for i in range(window.tabs.count()):
            if window.tabs.tabText(i) == "Power Supply":
                window.tabs.setCurrentIndex(i)
                break

        info_msg = (
            f"Mock Generic PSU Connected!\n\n"
            f"Model: {psu.model_capability.model_name}\n"
            f"Manufacturer: {psu.model_capability.manufacturer}\n"
            f"SCPI Variant: generic (standard commands)\n\n"
            f"This demonstrates generic SCPI-99 compatibility"
        )
        QMessageBox.information(window, "Generic PSU Connected", info_msg)

        print("\nGeneric PSU GUI test launched!")
        sys.exit(app.exec())

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("Power Supply GUI Test with Mock Connection")
    print("=" * 60)
    print()
    print("Choose test:")
    print("1. Siglent SPD3303X (default)")
    print("2. Generic SCPI PSU")
    print()

    choice = input("Enter choice (1 or 2, default=1): ").strip()

    if choice == "2":
        test_generic_psu()
    else:
        test_psu_gui_with_mock()
