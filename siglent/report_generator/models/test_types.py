"""
Test type definitions and configuration.

Defines different types of oscilloscope tests with their expected signal
characteristics to provide context for AI analysis.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class TestTypeDefinition:
    """Definition of a test type with expected characteristics."""

    id: str
    name: str
    description: str
    expected_signal_type: str
    expected_characteristics: List[str]
    ai_analysis_focus: List[str]
    common_issues: List[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "expected_signal_type": self.expected_signal_type,
            "expected_characteristics": self.expected_characteristics,
            "ai_analysis_focus": self.ai_analysis_focus,
            "common_issues": self.common_issues,
        }

    def get_ai_context(self) -> str:
        """
        Get formatted AI context string for this test type.

        Returns:
            Formatted string for AI prompt
        """
        context = f"""Test Type: {self.name}
Description: {self.description}

Expected Signal Type: {self.expected_signal_type}

Expected Characteristics:
{chr(10).join('- ' + char for char in self.expected_characteristics)}

Analysis Focus:
{chr(10).join('- ' + focus for focus in self.ai_analysis_focus)}

Common Issues to Check:
{chr(10).join('- ' + issue for issue in self.common_issues)}"""

        return context


# Define standard test types
TEST_TYPES = {
    "general": TestTypeDefinition(
        id="general",
        name="General Test",
        description="General purpose oscilloscope measurement without specific test criteria",
        expected_signal_type="Any",
        expected_characteristics=[
            "No specific expected characteristics",
        ],
        ai_analysis_focus=[
            "Signal quality and noise",
            "Overall signal integrity",
            "Any unusual characteristics",
        ],
        common_issues=[
            "Excessive noise",
            "Unexpected signal levels",
            "Distortion or ringing",
        ],
    ),
    "probe_calibration": TestTypeDefinition(
        id="probe_calibration",
        name="Probe Compensation/Calibration",
        description="Verification that oscilloscope probes are properly compensated using calibration signal",
        expected_signal_type="Square wave (typically 1 kHz, 5V peak-to-peak)",
        expected_characteristics=[
            "Clean square wave with fast rise/fall times",
            "Flat top and bottom (no overshoot, undershoot, or ringing)",
            "Stable amplitude",
            "Minimal noise",
        ],
        ai_analysis_focus=[
            "Overshoot and undershoot on edges",
            "Ringing after transitions",
            "Flatness of top and bottom of square wave",
            "Rise and fall time characteristics",
        ],
        common_issues=[
            "Overshoot indicates over-compensation",
            "Rounded edges indicate under-compensation",
            "Ringing indicates improper probe adjustment",
        ],
    ),
    "signal_integrity": TestTypeDefinition(
        id="signal_integrity",
        name="Signal Integrity Test",
        description="Analysis of signal quality for digital or analog signals in a circuit",
        expected_signal_type="Digital or analog signal from circuit under test",
        expected_characteristics=[
            "Signal levels within expected voltage range",
            "Clean transitions (for digital signals)",
            "Low noise relative to signal amplitude",
            "Minimal overshoot, undershoot, and ringing",
        ],
        ai_analysis_focus=[
            "Signal-to-noise ratio (SNR)",
            "Edge quality and timing",
            "Overshoot/undershoot magnitude",
            "Ringing frequency and damping",
            "DC offset and bias levels",
        ],
        common_issues=[
            "Excessive noise from poor grounding or shielding",
            "Overshoot from impedance mismatch",
            "Slow rise times from excessive capacitance",
            "Ringing from insufficient damping",
        ],
    ),
    "power_supply_ripple": TestTypeDefinition(
        id="power_supply_ripple",
        name="Power Supply Ripple/Noise",
        description="Measurement of AC ripple and noise on DC power supply outputs",
        expected_signal_type="DC voltage with small AC ripple component",
        expected_characteristics=[
            "Stable DC level",
            "Low amplitude AC ripple (typically <50-100 mV peak-to-peak)",
            "Ripple frequency matching switching frequency (for switching supplies)",
            "Minimal high-frequency noise spikes",
        ],
        ai_analysis_focus=[
            "Peak-to-peak ripple voltage",
            "Ripple frequency and harmonics",
            "High-frequency noise spikes",
            "DC voltage stability",
        ],
        common_issues=[
            "Excessive ripple from inadequate filtering",
            "High-frequency spikes from switching transients",
            "Low-frequency ripple from insufficient bulk capacitance",
        ],
    ),
    "clock_verification": TestTypeDefinition(
        id="clock_verification",
        name="Clock Signal Verification",
        description="Verification of clock signal frequency, duty cycle, and quality",
        expected_signal_type="Periodic square wave or pulse train",
        expected_characteristics=[
            "Precise frequency matching specification",
            "Duty cycle close to 50% (unless specified otherwise)",
            "Fast, clean edges",
            "Stable amplitude",
            "Low jitter",
        ],
        ai_analysis_focus=[
            "Frequency accuracy",
            "Duty cycle percentage",
            "Rise and fall times",
            "Jitter and timing stability",
            "Edge quality and monotonicity",
        ],
        common_issues=[
            "Frequency drift from temperature or load changes",
            "Duty cycle errors from asymmetric driver circuits",
            "Excessive jitter from noise coupling",
            "Slow edges from excessive loading",
        ],
    ),
    "pulse_measurement": TestTypeDefinition(
        id="pulse_measurement",
        name="Pulse Width/Timing Measurement",
        description="Measurement of pulse width, period, or timing characteristics",
        expected_signal_type="Pulse or pulse train",
        expected_characteristics=[
            "Pulse width within specified tolerance",
            "Clean rising and falling edges",
            "Stable baseline",
            "Consistent pulse amplitude",
        ],
        ai_analysis_focus=[
            "Pulse width accuracy",
            "Rise and fall times",
            "Pulse amplitude and baseline levels",
            "Pulse-to-pulse consistency",
        ],
        common_issues=[
            "Pulse width variation from timing circuit issues",
            "Slow edges from RC time constants",
            "Baseline shift from DC coupling issues",
        ],
    ),
    "rise_fall_time": TestTypeDefinition(
        id="rise_fall_time",
        name="Rise/Fall Time Analysis",
        description="Detailed analysis of signal transition times",
        expected_signal_type="Signal with transitions to measure",
        expected_characteristics=[
            "Rise/fall times within specification",
            "Monotonic transitions (no oscillations during transition)",
            "Symmetric rise and fall times (unless asymmetry is expected)",
            "No excessive overshoot or undershoot",
        ],
        ai_analysis_focus=[
            "Rise time (10% to 90%)",
            "Fall time (90% to 10%)",
            "Overshoot and undershoot percentages",
            "Monotonicity of transitions",
            "Slew rate",
        ],
        common_issues=[
            "Slow transitions from bandwidth limitations",
            "Overshoot from impedance mismatch or poor termination",
            "Non-monotonic edges from resonance",
            "Asymmetric rise/fall from driver circuit characteristics",
        ],
    ),
    "communication_bus": TestTypeDefinition(
        id="communication_bus",
        name="Communication Bus Analysis (I2C/SPI/UART)",
        description="Analysis of digital communication signals",
        expected_signal_type="Digital communication protocol signals",
        expected_characteristics=[
            "Logic levels meeting specification (TTL, CMOS, LVDS, etc.)",
            "Clean transitions between logic levels",
            "Proper timing relationships between signals",
            "No glitches or runt pulses",
        ],
        ai_analysis_focus=[
            "Logic high and low voltage levels",
            "Rise and fall times",
            "Signal integrity during data transitions",
            "Setup and hold times (where applicable)",
            "Bus idle and active states",
        ],
        common_issues=[
            "Marginal logic levels from voltage supply issues",
            "Slow edges from excessive bus capacitance",
            "Crosstalk between adjacent signals",
            "Reflections from improper termination",
        ],
    ),
}


def get_test_type(test_type_id: str) -> Optional[TestTypeDefinition]:
    """
    Get test type definition by ID.

    Args:
        test_type_id: Test type identifier

    Returns:
        TestTypeDefinition or None if not found
    """
    return TEST_TYPES.get(test_type_id)


def get_all_test_types() -> Dict[str, TestTypeDefinition]:
    """
    Get all available test type definitions.

    Returns:
        Dictionary of test type definitions
    """
    return TEST_TYPES.copy()


def get_test_type_names() -> List[tuple]:
    """
    Get list of (id, name) tuples for all test types.

    Returns:
        List of (id, name) tuples suitable for combo box population
    """
    return [(test_id, test_def.name) for test_id, test_def in TEST_TYPES.items()]
