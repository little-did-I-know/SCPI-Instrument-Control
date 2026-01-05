"""
Measurement criteria and pass/fail validation.

This module provides classes for defining measurement criteria and
validating measurement results against those criteria.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ComparisonType(Enum):
    """Types of comparison for criteria."""

    RANGE = "range"  # Value must be within min/max range
    MIN_ONLY = "min_only"  # Value must be >= min
    MAX_ONLY = "max_only"  # Value must be <= max
    EQUALS = "equals"  # Value must equal target (within tolerance)
    NOT_EQUALS = "not_equals"  # Value must not equal target (outside tolerance)


@dataclass
class MeasurementCriteria:
    """Criteria for a measurement with pass/fail limits."""

    measurement_name: str
    comparison_type: ComparisonType = ComparisonType.RANGE

    # Range criteria
    min_value: Optional[float] = None
    max_value: Optional[float] = None

    # Equals criteria
    target_value: Optional[float] = None
    tolerance: Optional[float] = None  # Absolute tolerance for equals comparison

    # Optional metadata
    channel: Optional[str] = None
    description: Optional[str] = None
    severity: str = "critical"  # "critical", "warning", "info"

    def validate(self, value: float) -> "CriteriaResult":
        """
        Validate a measurement value against this criteria.

        Args:
            value: The measurement value to validate

        Returns:
            CriteriaResult with pass/fail status and details
        """
        passed = False
        message = ""

        if self.comparison_type == ComparisonType.RANGE:
            if self.min_value is not None and self.max_value is not None:
                passed = self.min_value <= value <= self.max_value
                message = f"Value {value:.6g} is {'within' if passed else 'outside'} " f"range [{self.min_value:.6g}, {self.max_value:.6g}]"
            else:
                passed = True
                message = "Range criteria not fully specified"

        elif self.comparison_type == ComparisonType.MIN_ONLY:
            if self.min_value is not None:
                passed = value >= self.min_value
                message = f"Value {value:.6g} is {'above' if passed else 'below'} " f"minimum {self.min_value:.6g}"
            else:
                passed = True
                message = "Minimum value not specified"

        elif self.comparison_type == ComparisonType.MAX_ONLY:
            if self.max_value is not None:
                passed = value <= self.max_value
                message = f"Value {value:.6g} is {'below' if passed else 'above'} " f"maximum {self.max_value:.6g}"
            else:
                passed = True
                message = "Maximum value not specified"

        elif self.comparison_type == ComparisonType.EQUALS:
            if self.target_value is not None:
                tolerance = self.tolerance if self.tolerance is not None else 0
                passed = abs(value - self.target_value) <= tolerance
                message = f"Value {value:.6g} is {'equal to' if passed else 'not equal to'} " f"target {self.target_value:.6g} (tolerance: ±{tolerance:.6g})"
            else:
                passed = True
                message = "Target value not specified"

        elif self.comparison_type == ComparisonType.NOT_EQUALS:
            if self.target_value is not None:
                tolerance = self.tolerance if self.tolerance is not None else 0
                passed = abs(value - self.target_value) > tolerance
                message = f"Value {value:.6g} is {'different from' if passed else 'equal to'} " f"target {self.target_value:.6g} (tolerance: ±{tolerance:.6g})"
            else:
                passed = True
                message = "Target value not specified"

        return CriteriaResult(
            criteria=self,
            value=value,
            passed=passed,
            message=message,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            "measurement_name": self.measurement_name,
            "comparison_type": self.comparison_type.value,
            "severity": self.severity,
        }

        # Add optional fields
        if self.min_value is not None:
            data["min_value"] = self.min_value
        if self.max_value is not None:
            data["max_value"] = self.max_value
        if self.target_value is not None:
            data["target_value"] = self.target_value
        if self.tolerance is not None:
            data["tolerance"] = self.tolerance
        if self.channel:
            data["channel"] = self.channel
        if self.description:
            data["description"] = self.description

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MeasurementCriteria":
        """Create from dictionary."""
        data = data.copy()
        data["comparison_type"] = ComparisonType(data["comparison_type"])
        return cls(**data)


@dataclass
class CriteriaResult:
    """Result of validating a measurement against criteria."""

    criteria: MeasurementCriteria
    value: float
    passed: bool
    message: str

    def __str__(self) -> str:
        """String representation."""
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.criteria.measurement_name}: {self.message}"


@dataclass
class CriteriaSet:
    """A collection of measurement criteria for a test procedure."""

    name: str
    description: Optional[str] = None
    criteria_list: List[MeasurementCriteria] = field(default_factory=list)

    def add_criteria(self, criteria: MeasurementCriteria) -> None:
        """Add a criteria to this set."""
        self.criteria_list.append(criteria)

    def get_criteria(self, measurement_name: str, channel: Optional[str] = None) -> Optional[MeasurementCriteria]:
        """
        Get criteria for a specific measurement.

        Args:
            measurement_name: Name of the measurement
            channel: Optional channel name for channel-specific criteria

        Returns:
            MeasurementCriteria if found, None otherwise
        """
        for criteria in self.criteria_list:
            if criteria.measurement_name == measurement_name:
                # If channel is specified, match it; otherwise, match any
                if channel is None or criteria.channel is None or criteria.channel == channel:
                    return criteria
        return None

    def validate_measurements(self, measurements: List[Dict[str, Any]]) -> List[CriteriaResult]:
        """
        Validate a list of measurements against this criteria set.

        Args:
            measurements: List of measurement dictionaries with 'name', 'value', and optionally 'channel'

        Returns:
            List of CriteriaResult objects
        """
        results = []

        for measurement in measurements:
            name = measurement["name"]
            value = measurement["value"]
            channel = measurement.get("channel")

            criteria = self.get_criteria(name, channel)
            if criteria:
                result = criteria.validate(value)
                results.append(result)

        return results

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "criteria_list": [c.to_dict() for c in self.criteria_list],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CriteriaSet":
        """Create from dictionary."""
        data = data.copy()
        data["criteria_list"] = [MeasurementCriteria.from_dict(c) for c in data.get("criteria_list", [])]
        return cls(**data)
