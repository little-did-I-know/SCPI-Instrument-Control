"""Data logging for power supply measurements.

Provides CSV-based logging of PSU output measurements over time.
Useful for automated testing, characterization, and monitoring.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from siglent.power_supply import PowerSupply

logger = logging.getLogger(__name__)


class PSUDataLogger:
    """Logs PSU output measurements to CSV file.

    Records voltage, current, power, and mode for all outputs at regular intervals.

    Example:
        >>> psu = PowerSupply('192.168.1.200')
        >>> psu.connect()
        >>> logger = PSUDataLogger(psu, "psu_log.csv")
        >>> logger.start()
        >>> # ... PSU operates ...
        >>> logger.log_measurement()  # Manual logging
        >>> logger.stop()
    """

    def __init__(
        self,
        psu: "PowerSupply",
        filepath: str,
        outputs: Optional[List[int]] = None,
    ):
        """Initialize data logger.

        Args:
            psu: PowerSupply instance to log
            filepath: Path to CSV log file
            outputs: List of output numbers to log (None = all outputs)
        """
        self.psu = psu
        self.filepath = Path(filepath)
        self.outputs = outputs
        self._file = None
        self._writer = None
        self._is_logging = False

        # Validate outputs
        if outputs is not None:
            for output_num in outputs:
                if not hasattr(self.psu, f"output{output_num}"):
                    raise ValueError(f"PSU does not have output{output_num}")

    def start(self) -> None:
        """Start logging (open file and write header).

        Creates CSV file with timestamp and measurement columns.
        """
        if self._is_logging:
            logger.warning("Logger already started")
            return

        # Create directory if needed
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

        # Open CSV file
        self._file = open(self.filepath, "w", newline="")
        self._writer = csv.writer(self._file)

        # Write header
        header = ["timestamp"]
        outputs_to_log = self._get_outputs_to_log()

        for output_num in outputs_to_log:
            header.extend(
                [
                    f"output{output_num}_voltage_V",
                    f"output{output_num}_current_A",
                    f"output{output_num}_power_W",
                    f"output{output_num}_mode",
                    f"output{output_num}_enabled",
                ]
            )

        self._writer.writerow(header)
        self._file.flush()

        self._is_logging = True
        logger.info(f"Started logging to {self.filepath}")

    def log_measurement(self) -> None:
        """Log a single measurement from all configured outputs.

        Writes timestamp and current measurements to CSV.

        Raises:
            RuntimeError: If logger not started
        """
        if not self._is_logging:
            raise RuntimeError("Logger not started. Call start() first.")

        timestamp = datetime.now().isoformat()
        row = [timestamp]

        outputs_to_log = self._get_outputs_to_log()

        for output_num in outputs_to_log:
            output = getattr(self.psu, f"output{output_num}")

            try:
                voltage = output.measure_voltage()
                current = output.measure_current()
                power = output.measure_power()
                mode = output.get_mode()
                enabled = output.enabled

                row.extend(
                    [
                        f"{voltage:.6f}",
                        f"{current:.6f}",
                        f"{power:.6f}",
                        mode,
                        str(enabled),
                    ]
                )

            except Exception as e:
                logger.error(f"Failed to measure output {output_num}: {e}")
                # Write placeholder values on error
                row.extend(["ERROR", "ERROR", "ERROR", "ERROR", "ERROR"])

        self._writer.writerow(row)
        self._file.flush()

    def stop(self) -> None:
        """Stop logging and close file."""
        if not self._is_logging:
            logger.warning("Logger not running")
            return

        if self._file:
            self._file.close()
            self._file = None
            self._writer = None

        self._is_logging = False
        logger.info(f"Stopped logging. Data saved to {self.filepath}")

    def _get_outputs_to_log(self) -> List[int]:
        """Get list of output numbers to log.

        Returns:
            List of output numbers (uses self.outputs or all available outputs)
        """
        if self.outputs is not None:
            return self.outputs

        # Log all available outputs
        return list(range(1, self.psu.model_capability.num_outputs + 1))

    @property
    def is_logging(self) -> bool:
        """Check if logger is currently active.

        Returns:
            True if logging, False otherwise
        """
        return self._is_logging

    def __enter__(self):
        """Context manager entry - start logging."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop logging."""
        self.stop()
        return False

    def __repr__(self) -> str:
        """String representation."""
        status = "active" if self._is_logging else "stopped"
        return f"PSUDataLogger({self.filepath}, status={status})"


class TimedPSULogger:
    """Timed data logger with automatic periodic measurements.

    Uses a background thread to log measurements at regular intervals.

    Example:
        >>> psu = PowerSupply('192.168.1.200')
        >>> psu.connect()
        >>> with TimedPSULogger(psu, "psu_log.csv", interval=1.0) as logger:
        ...     time.sleep(10)  # Log for 10 seconds
    """

    def __init__(
        self,
        psu: "PowerSupply",
        filepath: str,
        interval: float = 1.0,
        outputs: Optional[List[int]] = None,
    ):
        """Initialize timed logger.

        Args:
            psu: PowerSupply instance to log
            filepath: Path to CSV log file
            interval: Logging interval in seconds (default: 1.0)
            outputs: List of output numbers to log (None = all outputs)
        """
        self.psu = psu
        self.interval = interval
        self.logger = PSUDataLogger(psu, filepath, outputs)
        self._timer = None
        self._running = False

    def start(self) -> None:
        """Start timed logging."""
        if self._running:
            logger.warning("Timed logger already running")
            return

        self.logger.start()
        self._running = True
        self._schedule_next_log()
        logger.info(f"Started timed logging (interval={self.interval}s)")

    def stop(self) -> None:
        """Stop timed logging."""
        if not self._running:
            logger.warning("Timed logger not running")
            return

        self._running = False

        if self._timer:
            self._timer.cancel()
            self._timer = None

        self.logger.stop()
        logger.info("Stopped timed logging")

    def _schedule_next_log(self) -> None:
        """Schedule next measurement."""
        if not self._running:
            return

        import threading

        self._timer = threading.Timer(self.interval, self._log_and_schedule)
        self._timer.daemon = True
        self._timer.start()

    def _log_and_schedule(self) -> None:
        """Log measurement and schedule next one."""
        try:
            self.logger.log_measurement()
        except Exception as e:
            logger.error(f"Error logging measurement: {e}")

        self._schedule_next_log()

    @property
    def is_logging(self) -> bool:
        """Check if logger is currently active.

        Returns:
            True if logging, False otherwise
        """
        return self._running

    def __enter__(self):
        """Context manager entry - start logging."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop logging."""
        self.stop()
        return False

    def __repr__(self) -> str:
        """String representation."""
        status = "active" if self._running else "stopped"
        return f"TimedPSULogger(interval={self.interval}s, status={status})"
