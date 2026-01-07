# Experimental Features and Beta Releases

This guide documents the strategy for introducing, managing, and graduating experimental features in the Siglent Oscilloscope Control project.

## Table of Contents

- [Overview](#overview)
- [What Qualifies as Experimental](#what-qualifies-as-experimental)
- [Marking Features as Experimental](#marking-features-as-experimental)
- [Version Numbering Strategy](#version-numbering-strategy)
- [Installation and Discovery](#installation-and-discovery)
- [Documentation Standards](#documentation-standards)
- [User Communication](#user-communication)
- [Testing Requirements](#testing-requirements)
- [Deprecation and Graduation](#deprecation-and-graduation)
- [Examples](#examples)

## Overview

Experimental features allow the project to:

- **Gather feedback** on new functionality before committing to API stability
- **Iterate quickly** without breaking changes for stable features
- **Test innovative ideas** with early adopters
- **Maintain stability** for production users while exploring new capabilities

**Key Principle**: Experimental features have **no stability guarantees** and may change or be removed in any release.

## What Qualifies as Experimental

Mark a feature as experimental when:

1. **New Hardware Support**: Untested oscilloscope models or instrument types
2. **Novel Functionality**: Features without proven use cases or unclear requirements
3. **API Exploration**: Trying different interface designs before settling on one
4. **Third-Party Integration**: New protocol decoders, file formats, or external tools
5. **Performance Experiments**: Optimizations that might have edge cases
6. **Community Contributions**: Features pending thorough review and validation

**Do NOT mark as experimental**:

- Bug fixes for existing features
- Documentation improvements
- Performance improvements to stable features
- Minor API additions that follow existing patterns

## Marking Features as Experimental

### 1. Optional Extras Package

Use optional dependency groups for experimental features requiring new dependencies:

**In `pyproject.toml`:**

```toml
[project.optional-dependencies]
# Stable optional features
gui = ["PyQt6>=6.6.0", "PyQtGraph>=0.13.0"]
hdf5 = ["h5py>=3.8.0"]

# Experimental features
power-supply-beta = [
    "pyvisa>=1.14.0",  # Example: experimental power supply support
]

# Install experimental features
experimental = [
    "siglent[power-supply-beta]",
]
```

**Installation:**

```bash
# Install experimental feature
pip install "SCPI-Instrument-Control[power-supply-beta]"

# Install all experimental features
pip install "SCPI-Instrument-Control[experimental]"
```

### 2. Module-Level Warnings

Add warnings to experimental modules:

**Example: `siglent/power_supply.py`**

```python
"""
Power supply control module (EXPERIMENTAL).

This module is experimental and may change significantly in future releases.
API stability is not guaranteed. Use in production at your own risk.

To use this feature:
    pip install "SCPI-Instrument-Control[power-supply-beta]"
"""

import warnings

warnings.warn(
    "siglent.power_supply is experimental and may change in future releases. "
    "See docs/development/EXPERIMENTAL_FEATURES.md for details.",
    FutureWarning,
    stacklevel=2
)

class PowerSupply:
    """EXPERIMENTAL: Siglent power supply control."""
    pass
```

### 3. Decorator for Experimental APIs

For experimental methods in stable classes:

**Create `siglent/utils/experimental.py`:**

```python
"""Decorators for marking experimental APIs."""

import functools
import warnings
from typing import Callable


def experimental(message: str = None) -> Callable:
    """
    Mark a function or method as experimental.

    Experimental APIs may change or be removed without warning.

    Args:
        message: Custom warning message (optional)

    Example:
        @experimental("This measurement type is under development")
        def measure_eye_diagram(self, channel: int):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            default_msg = (
                f"{func.__module__}.{func.__name__} is experimental and may "
                f"change in future releases. See docs/development/EXPERIMENTAL_FEATURES.md"
            )
            warnings.warn(
                message or default_msg,
                FutureWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)

        # Mark the function for documentation
        wrapper.__experimental__ = True
        wrapper.__experimental_message__ = message
        return wrapper

    return decorator
```

**Usage:**

```python
from scpi_control.utils.experimental import experimental

class Oscilloscope:
    @experimental("Power analysis features are experimental")
    def analyze_power_efficiency(self, voltage_ch: int, current_ch: int):
        """EXPERIMENTAL: Calculate power efficiency metrics."""
        pass
```

### 4. Feature Flags (Optional)

For fine-grained control over experimental features:

**Create `siglent/config.py`:**

```python
"""Configuration and feature flags."""

import os
from typing import Dict


class FeatureFlags:
    """
    Control experimental features via environment variables.

    Environment variables:
        SIGLENT_EXPERIMENTAL_ALL: Enable all experimental features
        SIGLENT_EXPERIMENTAL_POWER_SUPPLY: Enable power supply support
        SIGLENT_EXPERIMENTAL_PATTERN_GEN: Enable pattern generator support
    """

    _flags: Dict[str, bool] = {}

    @classmethod
    def is_enabled(cls, feature: str) -> bool:
        """Check if an experimental feature is enabled."""
        if feature not in cls._flags:
            # Check environment variables
            all_enabled = os.getenv('SIGLENT_EXPERIMENTAL_ALL', '').lower() in ('1', 'true', 'yes')
            feature_var = f'SIGLENT_EXPERIMENTAL_{feature.upper()}'
            feature_enabled = os.getenv(feature_var, '').lower() in ('1', 'true', 'yes')

            cls._flags[feature] = all_enabled or feature_enabled

        return cls._flags[feature]

    @classmethod
    def enable(cls, feature: str) -> None:
        """Programmatically enable an experimental feature."""
        cls._flags[feature] = True

    @classmethod
    def disable(cls, feature: str) -> None:
        """Programmatically disable an experimental feature."""
        cls._flags[feature] = False


# Usage in code
if FeatureFlags.is_enabled('power_supply'):
    from scpi_control.power_supply import PowerSupply
```

**Enable via environment:**

```bash
# Enable all experimental features
export SIGLENT_EXPERIMENTAL_ALL=1

# Enable specific feature
export SIGLENT_EXPERIMENTAL_POWER_SUPPLY=1
python my_script.py
```

## Version Numbering Strategy

Follow [Semantic Versioning](https://semver.org/) with special considerations for experimental features:

### Stable Releases

```
MAJOR.MINOR.PATCH
```

- **MAJOR**: Breaking changes to stable APIs
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

**Example**: `0.3.2` → `0.4.0` (new feature) → `1.0.0` (stable API)

### Pre-Release Versions

For testing experimental features before official release:

```
MAJOR.MINOR.PATCH-alpha.N
MAJOR.MINOR.PATCH-beta.N
MAJOR.MINOR.PATCH-rc.N
```

**Progression:**

1. **Alpha** (`0.4.0-alpha.1`): Early development, API unstable
2. **Beta** (`0.4.0-beta.1`): Feature complete, API stabilizing
3. **Release Candidate** (`0.4.0-rc.1`): Final testing before release

**Example workflow:**

```bash
# Start experimental power supply feature
git checkout -b feature/power-supply-support

# Tag alpha releases for early testing
git tag v0.4.0-alpha.1
git tag v0.4.0-alpha.2

# Feature stabilizes, move to beta
git tag v0.4.0-beta.1

# Final testing
git tag v0.4.0-rc.1

# Merge to main and release
git checkout main
git merge feature/power-supply-support
git tag v0.4.0
```

### Pre-1.0.0 Projects

Before reaching `1.0.0`, the project is considered unstable:

- **0.x.y**: All APIs may change
- **Experimental features**: Use extra caution, clearly marked

**Current Status**: The project is at `0.3.x`, meaning:

- Core APIs are maturing but not yet stable
- Breaking changes acceptable in `0.x.0` releases
- Experimental features have even fewer guarantees

## Installation and Discovery

### Installation Instructions

Document experimental feature installation clearly:

**In README.md:**

````markdown
## Experimental Features

⚠️ **Experimental features are unstable and may change without warning.**

### Power Supply Control (EXPERIMENTAL)

```bash
# Install with experimental power supply support
pip install "SCPI-Instrument-Control[power-supply-beta]"
```
````

```python
import warnings
warnings.filterwarnings('default', category=FutureWarning)

from scpi_control.power_supply import PowerSupply  # Shows experimental warning

psu = PowerSupply('192.168.1.101')
# ... use at your own risk
```

**Stability**: This feature is experimental. API may change in any release.

**Feedback**: Please report issues and suggestions at [GitHub Issues](https://github.com/little-did-I-know/SCPI-Instrument-Control/issues)

````

### Runtime Discovery

Allow users to discover experimental features:

**Create `siglent/experimental.py`:**

```python
"""Experimental feature registry and discovery."""

from typing import List, Dict


class ExperimentalFeature:
    """Metadata for an experimental feature."""

    def __init__(
        self,
        name: str,
        module: str,
        description: str,
        install_extra: str = None,
        enabled: bool = True,
        since_version: str = None,
    ):
        self.name = name
        self.module = module
        self.description = description
        self.install_extra = install_extra
        self.enabled = enabled
        self.since_version = since_version

    def is_available(self) -> bool:
        """Check if the feature's dependencies are installed."""
        try:
            __import__(self.module)
            return True
        except ImportError:
            return False


# Registry of experimental features
EXPERIMENTAL_FEATURES = [
    ExperimentalFeature(
        name="power_supply",
        module="siglent.power_supply",
        description="Power supply control (SPD3303X series)",
        install_extra="power-supply-beta",
        since_version="0.4.0-beta.1",
    ),
    ExperimentalFeature(
        name="pattern_generator",
        module="siglent.pattern_generator",
        description="Pattern/function generator support",
        install_extra="pattern-gen-beta",
        since_version="0.5.0-alpha.1",
    ),
]


def list_experimental_features() -> List[Dict]:
    """List all experimental features and their status."""
    return [
        {
            'name': f.name,
            'description': f.description,
            'available': f.is_available(),
            'install': f'pip install "SCPI-Instrument-Control[{f.install_extra}]"' if f.install_extra else None,
            'since': f.since_version,
        }
        for f in EXPERIMENTAL_FEATURES
    ]
````

**Usage:**

```python
from scpi_control.experimental import list_experimental_features

features = list_experimental_features()
for f in features:
    print(f"{f['name']}: {f['description']}")
    print(f"  Available: {f['available']}")
    if not f['available'] and f['install']:
        print(f"  Install: {f['install']}")
```

## Documentation Standards

### Module Docstrings

Always include experimental status in module docstrings:

```python
"""
Power Supply Control Module (EXPERIMENTAL)
==========================================

⚠️ **WARNING: This module is experimental**

- API stability is NOT guaranteed
- May change or be removed in any release
- Not recommended for production use

Installation
------------
pip install "SCPI-Instrument-Control[power-supply-beta]"

Stability Timeline
------------------
- v0.4.0-beta.1: Initial experimental release
- Estimated stable release: v0.5.0 (pending feedback)

Feedback
--------
Report issues at: https://github.com/little-did-I-know/SCPI-Instrument-Control/issues

Example
-------
>>> from scpi_control.power_supply import PowerSupply
>>> psu = PowerSupply('192.168.1.101')
>>> psu.connect()
"""
```

### API Documentation

Mark experimental methods in docstrings:

```python
def set_output_voltage(self, channel: int, voltage: float) -> None:
    """
    Set the output voltage for a channel.

    .. experimental::
        This method is experimental and may change in future releases.

    Args:
        channel: Channel number (1-3)
        voltage: Voltage in volts (0.0 - 32.0)

    Raises:
        ValueError: If voltage out of range
        SiglentConnectionError: If not connected

    Since:
        0.4.0-beta.1 (experimental)
    """
```

### CHANGELOG Entries

Document experimental features clearly:

```markdown
## [0.4.0-beta.1] - 2026-01-15

### Added (EXPERIMENTAL)

- **Power Supply Control** (`siglent.power_supply` module)
  - ⚠️ EXPERIMENTAL: API unstable, may change without warning
  - SPD3303X series support
  - Channel voltage/current control
  - Output enable/disable
  - Installation: `pip install "SCPI-Instrument-Control[power-supply-beta]"`
  - Seeking feedback before v0.5.0 stable release
  - See: `docs/development/EXPERIMENTAL_FEATURES.md`
```

### Dedicated Documentation Page

Create documentation in `docs/experimental/`:

**Example: `docs/experimental/power-supply.md`**

```markdown
# Power Supply Control (EXPERIMENTAL)

⚠️ **Status**: Experimental - API may change

**Introduced**: v0.4.0-beta.1
**Target Stable Release**: v0.5.0
**Feedback**: [GitHub Issues #42](https://github.com/little-did-I-know/SCPI-Instrument-Control/issues/42)

## Overview

This module provides programmatic control of Siglent SPD3303X series power supplies.

**⚠️ Experimental Notice**:

- API is subject to change in any release
- Limited hardware testing (SPD3303X-E only)
- Not recommended for production use
- We welcome your feedback!

## Installation

[... installation instructions ...]

## Known Limitations

- Only tested with SPD3303X-E model
- Current readback accuracy needs validation
- No support for preset memory functions yet

## Giving Feedback

We need your input to stabilize this feature:

- Which features are most important?
- What API changes would improve usability?
- What hardware have you tested?

Please comment on [Issue #42](https://github.com/little-did-I-know/SCPI-Instrument-Control/issues/42).
```

## User Communication

### README Badge

Add badges to indicate experimental features:

```markdown
## Features

### Core Features ✅

- Oscilloscope control via SCPI
- Waveform capture and analysis
- GUI application

### Experimental Features ⚠️

| Feature              | Status | Install               | Docs                                      |
| -------------------- | ------ | --------------------- | ----------------------------------------- |
| Power Supply Control | Beta   | `[power-supply-beta]` | [docs](docs/experimental/power-supply.md) |
| Pattern Generator    | Alpha  | `[pattern-gen-beta]`  | [docs](docs/experimental/pattern-gen.md)  |
```

### Warning Messages

Show clear warnings when experimental features are used:

```python
import warnings

warnings.warn(
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "⚠️  EXPERIMENTAL FEATURE WARNING\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "You are using siglent.power_supply, an EXPERIMENTAL feature.\n"
    "\n"
    "This feature:\n"
    "  • May change or be removed in any release\n"
    "  • Has limited testing and validation\n"
    "  • Is NOT recommended for production use\n"
    "\n"
    "Give feedback: https://github.com/little-did-I-know/SCPI-Instrument-Control/issues/42\n"
    "Documentation: docs/development/EXPERIMENTAL_FEATURES.md\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n",
    FutureWarning,
    stacklevel=2
)
```

### GitHub Releases

Tag experimental releases clearly:

```markdown
## 🧪 v0.4.0-beta.1 - Experimental Power Supply Support

**⚠️ This is a BETA release with experimental features**

### Experimental Features

**Power Supply Control** 🔬

- NEW: `siglent.power_supply` module for SPD3303X series
- Install: `pip install "SCPI-Instrument-Control[power-supply-beta]"`
- **Status**: Beta - API may change, seeking feedback
- **Docs**: See `docs/experimental/power-supply.md`

**We need your help!**

- Test with your hardware
- Report issues and suggestions
- Comment on [Issue #42](link)

### Stable Features

[... regular changelog ...]
```

## Testing Requirements

Experimental features must meet minimum testing standards before inclusion:

### Test Coverage

**Minimum Requirements**:

- 50%+ code coverage for experimental modules
- 70%+ coverage before graduating to stable

**Example test structure**:

```python
# tests/experimental/test_power_supply.py

import pytest
from scpi_control.power_supply import PowerSupply


class TestPowerSupplyExperimental:
    """Tests for experimental power supply module."""

    @pytest.mark.experimental
    def test_basic_connection(self, mock_socket):
        """Test basic connection to power supply."""
        psu = PowerSupply('192.168.1.101')
        psu.connect()
        assert psu.connected

    @pytest.mark.experimental
    @pytest.mark.hardware
    def test_voltage_control_real_hardware(self):
        """Test voltage control with real hardware (skip if unavailable)."""
        # Only runs if SIGLENT_TEST_HARDWARE=1
        pytest.skip("Requires real power supply hardware")
```

**pytest markers**:

```python
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "experimental: marks tests for experimental features",
    "hardware: marks tests requiring real hardware",
]
```

**Run tests**:

```bash
# Run only experimental tests
pytest -m experimental

# Skip experimental tests
pytest -m "not experimental"
```

### CI/CD for Experimental Features

**Separate CI workflow** (`.github/workflows/experimental.yml`):

```yaml
name: Experimental Features CI

on:
  push:
    branches: [feature/*, experimental/*]
  pull_request:
    branches: [main]

jobs:
  test-experimental:
    name: Test Experimental Features
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install experimental dependencies
        run: |
          pip install -e ".[experimental,dev]"

      - name: Run experimental tests
        run: |
          pytest -m experimental --cov=siglent --cov-report=term

      - name: Check coverage (relaxed for experimental)
        run: |
          coverage report --fail-under=50
```

**Mark as experimental in PR template**:

```markdown
## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] 🧪 **Experimental feature** (unstable, may change)
```

## Deprecation and Graduation

### Graduation to Stable

When an experimental feature is ready for stable release:

**Checklist**:

- [ ] API has stabilized (no changes for 2+ releases)
- [ ] Test coverage ≥70%
- [ ] Tested with multiple hardware models
- [ ] Documentation complete
- [ ] No critical bugs
- [ ] Positive user feedback
- [ ] Breaking changes finalized

**Process**:

1. **Remove experimental warnings**:

```python
# Before (experimental)
def set_voltage(self, voltage: float):
    warnings.warn("This method is experimental", FutureWarning)
    # ...

# After (stable)
def set_voltage(self, voltage: float):
    """Set voltage (stable since v0.5.0)."""
    # ... (no warning)
```

2. **Update documentation**:

```markdown
# Before

## Power Supply Control (EXPERIMENTAL)

⚠️ **Status**: Beta

# After

## Power Supply Control

✅ **Status**: Stable (since v0.5.0)
```

3. **Move from optional to recommended/core**:

```toml
# Before (experimental)
[project.optional-dependencies]
power-supply-beta = ["pyvisa>=1.14.0"]

# After (stable) - either move to core or keep optional
[project.dependencies]
pyvisa = ">=1.14.0"  # If core feature

# OR keep optional but drop "beta" suffix
[project.optional-dependencies]
power-supply = ["pyvisa>=1.14.0"]  # Stable optional feature
```

4. **Announce in changelog**:

```markdown
## [0.5.0] - 2026-03-01

### Graduated from Experimental to Stable ✅

- **Power Supply Control** (`siglent.power_supply`)
  - API is now stable and follows semantic versioning
  - Install: `pip install "SCPI-Instrument-Control[power-supply]"` (dropped "-beta")
  - Full documentation: [docs/user-guide/power-supply.md](docs/user-guide/power-supply.md)
  - Migration guide for beta users: no API changes required
```

### Deprecation Process

If an experimental feature needs to be removed:

**Timeline**:

1. **v0.4.0**: Feature marked deprecated (still functional)
2. **v0.5.0**: Deprecation warnings shown
3. **v0.6.0**: Feature removed

**Example deprecation**:

```python
# v0.4.0 - Mark as deprecated
def old_experimental_method(self):
    warnings.warn(
        "old_experimental_method is deprecated and will be removed in v0.6.0. "
        "Use new_method instead. See docs/development/EXPERIMENTAL_FEATURES.md#deprecation",
        DeprecationWarning,
        stacklevel=2
    )
    # ... existing implementation

# v0.5.0 - Stronger warning
def old_experimental_method(self):
    warnings.warn(
        "old_experimental_method will be REMOVED in v0.6.0 (next release). "
        "Migrate to new_method immediately.",
        FutureWarning,  # More visible than DeprecationWarning
        stacklevel=2
    )
    # ... existing implementation

# v0.6.0 - Remove method entirely
# (method deleted from codebase)
```

**Changelog documentation**:

```markdown
## [0.4.0] - 2026-01-15

### Deprecated

- `Oscilloscope.old_experimental_method()` - Will be removed in v0.6.0
  - Use `Oscilloscope.new_method()` instead
  - Reason: Experimental API did not meet stability requirements
  - Migration guide: [docs/migration/v0.4-to-v0.6.md](docs/migration/v0.4-to-v0.6.md)
```

## Examples

### Example 1: Power Supply Module (Beta Feature)

**File Structure**:

```
siglent/
├── power_supply.py          # Experimental module
├── experimental.py          # Feature registry
└── utils/
    └── experimental.py      # Decorators
docs/
└── experimental/
    └── power-supply.md      # Feature documentation
tests/
└── experimental/
    └── test_power_supply.py # Tests
```

**Implementation** (`siglent/power_supply.py`):

```python
"""
Power Supply Control (EXPERIMENTAL)

This module provides control for Siglent SPD3303X series power supplies.

⚠️ EXPERIMENTAL: API may change in future releases
Installation: pip install "SCPI-Instrument-Control[power-supply-beta]"
"""

import warnings

warnings.warn(
    "siglent.power_supply is experimental. API may change. "
    "See docs/experimental/power-supply.md",
    FutureWarning,
    stacklevel=2
)

from scpi_control.connection.socket import SocketConnection
from scpi_control.exceptions import SiglentConnectionError, CommandError


class PowerSupply:
    """
    EXPERIMENTAL: Siglent power supply control.

    Supported Models:
        - SPD3303X series
        - SPD3303X-E

    Status: Beta (v0.4.0-beta.1)
    Target Stable: v0.5.0

    Example:
        >>> from scpi_control.power_supply import PowerSupply
        >>> psu = PowerSupply('192.168.1.101')
        >>> psu.connect()
        >>> psu.set_voltage(1, 5.0)  # Channel 1, 5V
        >>> psu.enable_output(1)
    """

    def __init__(self, host: str, port: int = 5025, timeout: float = 5.0):
        self.connection = SocketConnection(host, port, timeout)

    # ... implementation
```

### Example 2: Experimental Method in Stable Class

**Usage of `@experimental` decorator**:

```python
# siglent/oscilloscope.py

from scpi_control.utils.experimental import experimental


class Oscilloscope:
    """Main oscilloscope control class (STABLE)."""

    # Stable methods
    def identify(self) -> str:
        """Get device identification (STABLE since v0.1.0)."""
        return self.connection.query("*IDN?")

    # Experimental method
    @experimental("Eye diagram analysis is experimental and may change")
    def analyze_eye_diagram(
        self,
        channel: int,
        bit_rate: float,
        pattern_length: int = 127
    ) -> dict:
        """
        EXPERIMENTAL: Perform eye diagram analysis.

        ⚠️ This method is experimental and may change in future releases.

        Args:
            channel: Channel number (1-4)
            bit_rate: Bit rate in bps
            pattern_length: PRBS pattern length

        Returns:
            Dictionary with eye diagram metrics

        Since:
            v0.4.0-beta.2 (experimental)
        """
        # Implementation
        pass
```

### Example 3: Feature Flag Usage

**Control experimental features dynamically**:

```python
# my_script.py

from scpi_control import Oscilloscope
from scpi_control.config import FeatureFlags

# Enable experimental power analysis
FeatureFlags.enable('power_analysis')

scope = Oscilloscope('192.168.1.100')
scope.connect()

if FeatureFlags.is_enabled('power_analysis'):
    # This only runs if feature is enabled
    result = scope.analyze_power_efficiency(voltage_ch=1, current_ch=2)
    print(f"Efficiency: {result['efficiency']:.2f}%")
else:
    print("Power analysis not enabled")
```

**Via environment variable**:

```bash
# Enable for this session
export SIGLENT_EXPERIMENTAL_POWER_ANALYSIS=1
python my_script.py
```

### Example 4: Testing Experimental Features

**Test file** (`tests/experimental/test_power_supply.py`):

```python
import pytest
from unittest.mock import Mock, patch
from scpi_control.power_supply import PowerSupply


@pytest.mark.experimental
class TestPowerSupplyBasic:
    """Basic tests for experimental power supply module."""

    def test_connection(self):
        """Test power supply connection."""
        with patch('siglent.power_supply.SocketConnection') as mock_conn:
            psu = PowerSupply('192.168.1.101')
            psu.connect()
            mock_conn.return_value.connect.assert_called_once()

    @pytest.mark.parametrize("channel,voltage", [
        (1, 5.0),
        (2, 12.0),
        (3, 3.3),
    ])
    def test_set_voltage(self, channel, voltage):
        """Test setting voltage on different channels."""
        with patch('siglent.power_supply.SocketConnection'):
            psu = PowerSupply('192.168.1.101')
            psu.connect()

            psu.set_voltage(channel, voltage)
            expected_cmd = f"CH{channel}:VOLT {voltage}"
            psu.connection.send_command.assert_called_with(expected_cmd)


@pytest.mark.experimental
@pytest.mark.hardware
class TestPowerSupplyHardware:
    """Hardware tests (requires real power supply)."""

    @pytest.fixture
    def psu_address(self):
        """Get power supply address from environment."""
        import os
        addr = os.getenv('SIGLENT_PSU_ADDRESS')
        if not addr:
            pytest.skip("Set SIGLENT_PSU_ADDRESS to run hardware tests")
        return addr

    def test_real_hardware(self, psu_address):
        """Test with real hardware (manual testing only)."""
        psu = PowerSupply(psu_address)
        psu.connect()

        # Safe test: read voltage (doesn't change state)
        voltage = psu.measure_voltage(1)
        assert 0 <= voltage <= 35.0  # Within safe range
```

**Run tests**:

```bash
# Run all experimental tests (with mocks)
pytest -m experimental

# Run hardware tests (requires real device)
export SIGLENT_PSU_ADDRESS=192.168.1.101
pytest -m "experimental and hardware"

# Skip all experimental tests
pytest -m "not experimental"
```

## Summary

**Key Takeaways**:

1. **Mark clearly**: Use warnings, decorators, and documentation
2. **Version carefully**: Use pre-release versions (alpha, beta, rc)
3. **Test adequately**: Minimum 50% coverage, hardware testing where possible
4. **Communicate openly**: README, changelog, GitHub releases
5. **Graduate or deprecate**: Don't leave features in limbo indefinitely

**Quick Reference**:

| Mechanism            | Use Case             | Example                         |
| -------------------- | -------------------- | ------------------------------- |
| Optional extras      | Experimental modules | `[power-supply-beta]`           |
| Module warnings      | Entire modules       | `warnings.warn()` in `__init__` |
| `@experimental`      | Individual methods   | Decorator on methods            |
| Feature flags        | Runtime control      | `FeatureFlags.is_enabled()`     |
| Pre-release versions | Testing releases     | `0.4.0-beta.1`                  |
| Dedicated docs       | User guidance        | `docs/experimental/*.md`        |
| Test markers         | Isolated testing     | `@pytest.mark.experimental`     |

**Questions?** Open a discussion at [GitHub Discussions](https://github.com/little-did-I-know/SCPI-Instrument-Control/discussions)
