"""Math channel operations for waveform analysis."""

import logging
import re
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class MathOperations:
    """Static methods for mathematical operations on waveforms."""

    @staticmethod
    def _create_result_waveform(source_waveform, voltage, channel="MATH"):
        """Helper to create result waveform with all metadata from source.

        Args:
            source_waveform: Source waveform to copy metadata from
            voltage: New voltage array for result
            channel: Channel identifier (default: "MATH")

        Returns:
            New WaveformData with calculated voltage and source metadata
        """
        # Safely propagate optional metadata and estimate missing values
        sample_rate = getattr(source_waveform, "sample_rate", None)
        if sample_rate is None and len(source_waveform.time) > 1:
            dt = float(np.mean(np.diff(source_waveform.time)))
            if dt > 0:
                sample_rate = 1.0 / dt

        voltage_scale = getattr(source_waveform, "voltage_scale", None)
        if voltage_scale is None:
            span = float(np.max(voltage) - np.min(voltage)) if len(voltage) > 0 else 0.0
            voltage_scale = span / 8.0 if span > 0 else 1.0

        timebase = getattr(source_waveform, "timebase", None)
        if timebase is None and sample_rate:
            timebase = len(voltage) / sample_rate / 14.0

        return type(source_waveform)(
            time=source_waveform.time,
            voltage=voltage,
            channel=channel,
            sample_rate=sample_rate,
            record_length=len(voltage),
            timebase=timebase,
            voltage_scale=voltage_scale,
            voltage_offset=0.0,
        )  # Math results typically have no offset

    @staticmethod
    def add(waveform1, waveform2):
        """Add two waveforms.

        Args:
            waveform1: First waveform
            waveform2: Second waveform

        Returns:
            Result waveform with voltage = v1 + v2
        """
        if waveform1 is None or waveform2 is None:
            return None

        return MathOperations._create_result_waveform(waveform1, waveform1.voltage + waveform2.voltage)

    @staticmethod
    def subtract(waveform1, waveform2):
        """Subtract two waveforms.

        Args:
            waveform1: First waveform
            waveform2: Second waveform

        Returns:
            Result waveform with voltage = v1 - v2
        """
        if waveform1 is None or waveform2 is None:
            return None

        return MathOperations._create_result_waveform(waveform1, waveform1.voltage - waveform2.voltage)

    @staticmethod
    def multiply(waveform1, waveform2):
        """Multiply two waveforms.

        Args:
            waveform1: First waveform
            waveform2: Second waveform

        Returns:
            Result waveform with voltage = v1 * v2
        """
        if waveform1 is None or waveform2 is None:
            return None

        return MathOperations._create_result_waveform(waveform1, waveform1.voltage * waveform2.voltage)

    @staticmethod
    def divide(waveform1, waveform2, epsilon=1e-12):
        """Divide two waveforms.

        Args:
            waveform1: First waveform (numerator)
            waveform2: Second waveform (denominator)
            epsilon: Small value to prevent division by zero

        Returns:
            Result waveform with voltage = v1 / v2
        """
        if waveform1 is None or waveform2 is None:
            return None

        # Prevent division by zero
        denominator = np.where(np.abs(waveform2.voltage) < epsilon, epsilon, waveform2.voltage)

        return MathOperations._create_result_waveform(waveform1, waveform1.voltage / denominator)

    @staticmethod
    def integrate(waveform):
        """Integrate a waveform (cumulative sum).

        Args:
            waveform: Input waveform

        Returns:
            Result waveform with integrated values
        """
        if waveform is None:
            return None

        # Calculate time step
        dt = np.mean(np.diff(waveform.time)) if len(waveform.time) > 1 else 1.0

        # Cumulative integration using trapezoidal rule
        integrated = np.cumsum(waveform.voltage) * dt

        return MathOperations._create_result_waveform(waveform, integrated)

    @staticmethod
    def differentiate(waveform):
        """Differentiate a waveform.

        Args:
            waveform: Input waveform

        Returns:
            Result waveform with differentiated values
        """
        if waveform is None:
            return None

        # Calculate derivative using numpy gradient (more stable than diff)
        dt = np.mean(np.diff(waveform.time)) if len(waveform.time) > 1 else 1.0
        differentiated = np.gradient(waveform.voltage, dt)

        return MathOperations._create_result_waveform(waveform, differentiated)

    @staticmethod
    def scale(waveform, factor):
        """Scale a waveform by a constant factor.

        Args:
            waveform: Input waveform
            factor: Scaling factor

        Returns:
            Result waveform with voltage = v * factor
        """
        if waveform is None:
            return None

        return MathOperations._create_result_waveform(waveform, waveform.voltage * factor)

    @staticmethod
    def offset(waveform, offset_value):
        """Add a DC offset to a waveform.

        Args:
            waveform: Input waveform
            offset_value: Offset to add

        Returns:
            Result waveform with voltage = v + offset
        """
        if waveform is None:
            return None

        return MathOperations._create_result_waveform(waveform, waveform.voltage + offset_value)

    @staticmethod
    def abs_value(waveform):
        """Absolute value of a waveform.

        Args:
            waveform: Input waveform

        Returns:
            Result waveform with voltage = |v|
        """
        if waveform is None:
            return None

        return MathOperations._create_result_waveform(waveform, np.abs(waveform.voltage))

    @staticmethod
    def invert(waveform):
        """Invert a waveform.

        Args:
            waveform: Input waveform

        Returns:
            Result waveform with voltage = -v
        """
        if waveform is None:
            return None

        return MathOperations._create_result_waveform(waveform, -waveform.voltage)


class MathChannel:
    """Math channel for performing operations on oscilloscope waveforms.

    Supports expressions like:
    - "C1 + C2"
    - "C1 - C2"
    - "C1 * C2"
    - "C1 / C2"
    - "INTG(C1)" - integrate
    - "DIFF(C1)" - differentiate
    - "ABS(C1)" - absolute value
    - "INV(C1)" - invert
    - "2 * C1 + 1" - scale and offset
    """

    def __init__(self, scope, name: str):
        """Initialize math channel.

        Args:
            scope: Parent oscilloscope instance
            name: Math channel name (e.g., "M1", "M2")
        """
        self.scope = scope
        self.name = name
        self.expression = ""
        self.enabled = False
        self._result_waveform = None

        logger.info(f"Math channel {name} initialized")

    def set_expression(self, expression: str):
        """Set the math expression.

        Args:
            expression: Math expression string
        """
        self.expression = expression.strip()
        logger.info(f"Math channel {self.name} expression set to: {self.expression}")

    def enable(self):
        """Enable the math channel."""
        self.enabled = True
        logger.info(f"Math channel {self.name} enabled")

    def disable(self):
        """Disable the math channel."""
        self.enabled = False
        self._result_waveform = None
        logger.info(f"Math channel {self.name} disabled")

    def compute(self, waveforms: Dict[str, any]) -> Optional[any]:
        """Compute the math channel result.

        Args:
            waveforms: Dictionary of channel_name -> waveform

        Returns:
            Computed waveform or None if disabled/error
        """
        if not self.enabled or not self.expression:
            return None

        try:
            result = self._evaluate_expression(self.expression, waveforms)
            self._result_waveform = result
            return result
        except Exception as e:
            logger.error(f"Math channel {self.name} computation error: {e}")
            return None

    def _evaluate_expression(self, expr: str, waveforms: Dict[str, any]):
        """Evaluate a math expression.

        Args:
            expr: Expression string
            waveforms: Available waveforms

        Returns:
            Result waveform
        """
        # Handle function calls first (INTG, DIFF, ABS, INV)
        expr = expr.upper()

        # INTG(C1)
        intg_match = re.search(r"INTG\((C\d+)\)", expr)
        if intg_match:
            ch = intg_match.group(1)
            if ch in waveforms:
                return MathOperations.integrate(waveforms[ch])
            else:
                raise ValueError(f"Channel {ch} not available")

        # DIFF(C1)
        diff_match = re.search(r"DIFF\((C\d+)\)", expr)
        if diff_match:
            ch = diff_match.group(1)
            if ch in waveforms:
                return MathOperations.differentiate(waveforms[ch])
            else:
                raise ValueError(f"Channel {ch} not available")

        # ABS(C1)
        abs_match = re.search(r"ABS\((C\d+)\)", expr)
        if abs_match:
            ch = abs_match.group(1)
            if ch in waveforms:
                return MathOperations.abs_value(waveforms[ch])
            else:
                raise ValueError(f"Channel {ch} not available")

        # INV(C1)
        inv_match = re.search(r"INV\((C\d+)\)", expr)
        if inv_match:
            ch = inv_match.group(1)
            if ch in waveforms:
                return MathOperations.invert(waveforms[ch])
            else:
                raise ValueError(f"Channel {ch} not available")

        # Handle binary operations: C1 + C2, C1 - C2, C1 * C2, C1 / C2
        # Simple parser for basic expressions
        return self._parse_binary_expression(expr, waveforms)

    def _parse_binary_expression(self, expr: str, waveforms: Dict[str, any]):
        """Parse and evaluate binary expressions with constants.

        Args:
            expr: Expression string
            waveforms: Available waveforms

        Returns:
            Result waveform
        """
        # Remove spaces
        expr = expr.replace(" ", "")

        # Try to match: C1 op C2 patterns
        # Addition: C1 + C2
        if "+" in expr and not expr.startswith("+"):
            parts = expr.split("+")
            if len(parts) == 2:
                left = self._get_operand(parts[0], waveforms)
                right = self._get_operand(parts[1], waveforms)
                if isinstance(left, (int, float)) and not isinstance(right, (int, float)):
                    return MathOperations.offset(right, left)
                elif isinstance(right, (int, float)) and not isinstance(left, (int, float)):
                    return MathOperations.offset(left, right)
                else:
                    return MathOperations.add(left, right)

        # Subtraction: C1 - C2
        if "-" in expr and not expr.startswith("-"):
            parts = expr.split("-")
            if len(parts) == 2:
                left = self._get_operand(parts[0], waveforms)
                right = self._get_operand(parts[1], waveforms)
                if isinstance(right, (int, float)) and not isinstance(left, (int, float)):
                    return MathOperations.offset(left, -right)
                else:
                    return MathOperations.subtract(left, right)

        # Multiplication: C1 * C2 or 2 * C1
        if "*" in expr:
            parts = expr.split("*")
            if len(parts) == 2:
                left = self._get_operand(parts[0], waveforms)
                right = self._get_operand(parts[1], waveforms)
                if isinstance(left, (int, float)) and not isinstance(right, (int, float)):
                    return MathOperations.scale(right, left)
                elif isinstance(right, (int, float)) and not isinstance(left, (int, float)):
                    return MathOperations.scale(left, right)
                else:
                    return MathOperations.multiply(left, right)

        # Division: C1 / C2
        if "/" in expr:
            parts = expr.split("/")
            if len(parts) == 2:
                left = self._get_operand(parts[0], waveforms)
                right = self._get_operand(parts[1], waveforms)
                if isinstance(right, (int, float)) and not isinstance(left, (int, float)):
                    return MathOperations.scale(left, 1.0 / right)
                else:
                    return MathOperations.divide(left, right)

        # Single channel reference
        if expr in waveforms:
            return waveforms[expr]

        raise ValueError(f"Unable to parse expression: {expr}")

    def _get_operand(self, operand_str: str, waveforms: Dict[str, any]):
        """Get operand value (either a waveform or a constant).

        Args:
            operand_str: Operand string (e.g., "C1" or "2.5")
            waveforms: Available waveforms

        Returns:
            Waveform or numeric constant
        """
        operand_str = operand_str.strip()

        # Try to get as channel
        if operand_str in waveforms:
            return waveforms[operand_str]

        # Try to parse as number
        try:
            return float(operand_str)
        except ValueError:
            raise ValueError(f"Unknown operand: {operand_str}")

    def get_result(self):
        """Get the most recent computation result.

        Returns:
            Result waveform or None
        """
        return self._result_waveform

    def __repr__(self) -> str:
        """String representation."""
        status = "enabled" if self.enabled else "disabled"
        return f"MathChannel({self.name}, {status}, expr='{self.expression}')"
