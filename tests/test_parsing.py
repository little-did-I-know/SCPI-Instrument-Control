"""Test script to verify response parsing."""

import sys

# Add parent directory to path
sys.path.insert(0, r'C:\Users\robin\Documents\Siglent')


def test_parsing():
    """Test parsing of various oscilloscope response formats."""

    print("\n" + "="*60)
    print("Response Parsing Test")
    print("="*60)

    # Test cases with various response formats
    test_cases = [
        # Voltage scale responses
        ("C1:VDIV 2.00E+00V", "Voltage scale (full echo)"),
        ("VDIV 2.00E+00V", "Voltage scale (partial echo)"),
        ("2.00E+00V", "Voltage scale (no echo)"),
        ("C1:DI 2.00E+00", "Voltage scale (truncated - the error case)"),
        ("2.00E+00", "Voltage scale (minimal)"),

        # Offset responses
        ("C1:OFST 0.00E+00V", "Voltage offset (full echo)"),
        ("OFST 0.00E+00V", "Voltage offset (partial echo)"),
        ("0.00E+00V", "Voltage offset (no echo)"),

        # Timebase responses
        ("TDIV 1.00E-03S", "Timebase (with echo)"),
        ("1.00E-03S", "Timebase (no echo)"),

        # Sample rate responses
        ("SARA 1.00E+09Sa/s", "Sample rate (with echo)"),
        ("1.00E+09Sa/s", "Sample rate (no echo)"),
        ("1.00E+09SA/S", "Sample rate (uppercase)"),
    ]

    print("\nTesting voltage scale/offset parsing:")
    print("-" * 60)

    for response, description in test_cases:
        print(f"\nInput: '{response}'")
        print(f"Description: {description}")

        # Simulate parsing
        value = response

        # Remove echo prefix if present
        if ":" in value:
            value = value.split(":", 1)[1]
            print(f"  After colon split: '{value}'")

        # Remove command part if present
        if " " in value:
            value = value.split(" ", 1)[1]
            print(f"  After space split: '{value}'")

        # Remove units - handle sample rate specially
        if "Sa/s" in value or "SA/S" in value or "SPS" in value:
            # Sample rate - convert to uppercase first
            value = value.upper().replace("SA/S", "").replace("SPS", "").strip()
            print(f"  After unit removal (sample rate): '{value}'")
        else:
            # Voltage/timebase
            value = value.replace("V", "").replace("S", "").strip()
            print(f"  After unit removal: '{value}'")

        # Try to parse as float
        try:
            result = float(value)
            print(f"  [OK] SUCCESS: {result}")
        except ValueError as e:
            print(f"  [FAIL] FAILED: {e}")

    print("\n" + "="*60)
    print("Test Complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_parsing()
