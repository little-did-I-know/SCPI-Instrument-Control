"""Automation and programmatic data collection for Siglent oscilloscopes.

This module provides high-level APIs for automated data collection, batch processing,
and analysis of oscilloscope traces. It simplifies common workflows for users who want
to collect and analyze data programmatically.

Example:
    Simple waveform capture:
    >>> from siglent import Oscilloscope
    >>> from siglent.automation import DataCollector
    >>>
    >>> collector = DataCollector('192.168.1.100')
    >>> collector.connect()
    >>> data = collector.capture_single([1, 2])  # Capture channels 1 and 2
    >>> collector.save_data(data, 'measurement.npz')
    >>> collector.disconnect()

    Batch collection with different timebase settings:
    >>> collector = DataCollector('192.168.1.100')
    >>> with collector:
    ...     results = collector.batch_capture(
    ...         channels=[1],
    ...         timebase_scales=['1us', '10us', '100us'],
    ...         triggers_per_config=10
    ...     )
    ...     collector.save_batch(results, 'batch_data')

    Time-series collection:
    >>> collector = DataCollector('192.168.1.100')
    >>> with collector:
    ...     collector.start_continuous_capture(
    ...         channels=[1, 2],
    ...         duration=60,  # 60 seconds
    ...         interval=1.0,  # 1 capture per second
    ...         output_dir='time_series_data'
    ...     )
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np

from siglent import Oscilloscope
from siglent.connection import BaseConnection
from siglent.exceptions import SiglentError
from siglent.waveform import WaveformData

logger = logging.getLogger(__name__)


class DataCollector:
    """High-level API for automated oscilloscope data collection.

    This class wraps the Oscilloscope class and provides convenient methods
    for common data collection workflows, batch processing, and automated
    measurements.
    """

    def __init__(
        self,
        host: str,
        port: int = 5024,
        timeout: float = 5.0,
        connection: Optional[BaseConnection] = None,
    ):
        """Initialize data collector.

        Args:
            host: IP address or hostname of the oscilloscope
            port: TCP port for SCPI communication (default: 5024)
            timeout: Command timeout in seconds (default: 5.0)
            connection: Optional connection implementation (e.g., MockConnection for offline tests)
        """
        self.scope = Oscilloscope(host, port, timeout, connection=connection)
        self._connected = False

    def connect(self) -> None:
        """Connect to the oscilloscope."""
        self.scope.connect()
        self._connected = True
        logger.info(f"Connected to {self.scope.identify()}")

    def disconnect(self) -> None:
        """Disconnect from the oscilloscope."""
        if self._connected:
            self.scope.disconnect()
            self._connected = False
            logger.info("Disconnected from oscilloscope")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False

    def capture_single(self, channels: List[int], auto_setup: bool = False) -> Dict[int, WaveformData]:
        """Capture waveforms from specified channels.

        Args:
            channels: List of channel numbers to capture (e.g., [1, 2, 3])
            auto_setup: If True, run auto-setup before capture

        Returns:
            Dictionary mapping channel number to WaveformData object

        Example:
            >>> data = collector.capture_single([1, 2])
            >>> print(f"Channel 1: {len(data[1].voltage)} samples")
            >>> print(f"Sample rate: {data[1].sample_rate} Hz")
        """
        if not self._connected:
            raise SiglentError(f"Not connected to oscilloscope at {self.scope.host}:{self.scope.port}")

        if auto_setup:
            self.scope.auto_setup()
            time.sleep(1)  # Wait for auto-setup to complete

        # Trigger single acquisition
        self.scope.trigger_single()
        time.sleep(0.5)  # Wait for trigger

        # Capture waveforms
        waveforms = {}
        for ch in channels:
            try:
                channel = getattr(self.scope, f"channel{ch}")
                if channel.enabled:
                    waveforms[ch] = self.scope.waveform.acquire(ch)
                    logger.info(f"Captured {len(waveforms[ch].voltage)} samples from channel {ch}")
                else:
                    logger.warning(f"Channel {ch} is not enabled, skipping")
            except Exception as e:
                logger.error(f"Failed to capture channel {ch}: {e}")

        return waveforms

    def batch_capture(
        self,
        channels: List[int],
        timebase_scales: Optional[List[str]] = None,
        voltage_scales: Optional[Dict[int, List[str]]] = None,
        triggers_per_config: int = 1,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Capture multiple waveforms with different configurations.

        Args:
            channels: List of channel numbers to capture
            timebase_scales: List of timebase scale strings (e.g., ['1us', '10us', '100us'])
            voltage_scales: Dict mapping channel number to list of voltage scale strings
                           (e.g., {1: ['1V', '2V'], 2: ['500mV', '1V']})
            triggers_per_config: Number of captures per configuration
            progress_callback: Optional callback function(current, total, status)

        Returns:
            List of dictionaries containing waveforms and configuration metadata

        Example:
            >>> results = collector.batch_capture(
            ...     channels=[1],
            ...     timebase_scales=['1us', '10us', '100us'],
            ...     triggers_per_config=5
            ... )
            >>> print(f"Collected {len(results)} captures")
        """
        if not self._connected:
            raise SiglentError(f"Not connected to oscilloscope at {self.scope.host}:{self.scope.port}")

        results = []

        # Build configuration list
        configs = []
        if timebase_scales:
            for tb in timebase_scales:
                configs.append({"timebase": tb})
        else:
            configs.append({})

        if voltage_scales:
            new_configs = []
            for config in configs:
                for ch, scales in voltage_scales.items():
                    for scale in scales:
                        new_config = config.copy()
                        new_config[f"ch{ch}_vdiv"] = scale
                        new_configs.append(new_config)
            if new_configs:
                configs = new_configs

        total = len(configs) * triggers_per_config
        current = 0

        # Execute batch capture
        for config in configs:
            # Apply configuration
            if "timebase" in config:
                if hasattr(self.scope, "set_timebase"):
                    self.scope.set_timebase(config["timebase"])
                else:
                    self.scope.timebase = config["timebase"]
                logger.info(f"Set timebase to {config['timebase']}")

            for ch, scale in [(int(k[2]), v) for k, v in config.items() if k.startswith("ch") and k.endswith("_vdiv")]:
                channel = getattr(self.scope, f"channel{ch}")
                if hasattr(channel, "set_scale"):
                    channel.set_scale(scale)
                else:
                    channel.voltage_scale = scale
                logger.info(f"Set channel {ch} scale to {scale}")

            time.sleep(0.2)  # Allow settings to settle

            # Capture multiple triggers with this configuration
            for trigger_num in range(triggers_per_config):
                current += 1

                if progress_callback:
                    status = f"Config {configs.index(config)+1}/{len(configs)}, Trigger {trigger_num+1}/{triggers_per_config}"
                    progress_callback(current, total, status)

                waveforms = self.capture_single(channels)

                results.append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "config": config.copy(),
                        "waveforms": waveforms,
                        "trigger_num": trigger_num,
                    }
                )

        logger.info(f"Batch capture complete: {len(results)} captures")
        return results

    def start_continuous_capture(
        self,
        channels: List[int],
        duration: float,
        interval: float = 1.0,
        output_dir: Optional[Union[str, Path]] = None,
        file_format: str = "npz",
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Capture waveforms continuously over a time period.

        Args:
            channels: List of channel numbers to capture
            duration: Total capture duration in seconds
            interval: Time between captures in seconds
            output_dir: Optional directory to save captures (saves to memory if None)
            file_format: Format for saved files ('npz', 'csv', 'mat', 'h5')
            progress_callback: Optional callback function(captures_done, status)

        Returns:
            List of capture dictionaries (or empty list if output_dir is specified)

        Example:
            >>> # Capture for 60 seconds, save to files
            >>> collector.start_continuous_capture(
            ...     channels=[1, 2],
            ...     duration=60,
            ...     interval=2.0,
            ...     output_dir='continuous_data',
            ...     file_format='npz'
            ... )
        """
        if not self._connected:
            raise SiglentError(f"Not connected to oscilloscope at {self.scope.host}:{self.scope.port}")

        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Saving captures to {output_path}")

        results = []
        start_time = time.time()
        capture_count = 0

        # Set to AUTO trigger mode for continuous acquisition
        self.scope.trigger.mode = "AUTO"

        while (time.time() - start_time) < duration:
            try:
                capture_start = time.time()

                # Capture waveforms
                waveforms = {}
                for ch in channels:
                    try:
                        channel = getattr(self.scope, f"channel{ch}")
                        if channel.enabled:
                            waveforms[ch] = self.scope.waveform.acquire(ch)
                    except Exception as e:
                        logger.error(f"Failed to capture channel {ch}: {e}")

                capture_count += 1
                elapsed = time.time() - start_time

                capture_data = {
                    "timestamp": datetime.now().isoformat(),
                    "elapsed_time": elapsed,
                    "capture_num": capture_count,
                    "waveforms": waveforms,
                }

                # Save to file or memory
                if output_dir:
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    for ch, waveform in waveforms.items():
                        filename = output_path / f"ch{ch}_{timestamp_str}.{file_format}"
                        self.scope.waveform.save_waveform(waveform, str(filename), format=file_format)
                    logger.debug(f"Saved capture {capture_count}")
                else:
                    results.append(capture_data)

                if progress_callback:
                    remaining = duration - elapsed
                    status = f"Captured {capture_count}, {remaining:.1f}s remaining"
                    progress_callback(capture_count, status)

                # Wait for next interval
                capture_duration = time.time() - capture_start
                sleep_time = max(0, interval - capture_duration)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except KeyboardInterrupt:
                logger.info("Continuous capture interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error during continuous capture: {e}")

        logger.info(f"Continuous capture complete: {capture_count} captures over {duration}s")
        return results

    def save_data(self, waveforms: Dict[int, WaveformData], filename: str, format: str = "npz") -> None:
        """Save captured waveform data to file.

        Args:
            waveforms: Dictionary mapping channel number to WaveformData
            filename: Output filename
            format: File format ('npz', 'csv', 'mat', 'h5')

        Example:
            >>> data = collector.capture_single([1, 2])
            >>> collector.save_data(data, 'measurement.npz')
        """
        for ch, waveform in waveforms.items():
            base, ext = filename.rsplit(".", 1) if "." in filename else (filename, format)
            ch_filename = f"{base}_ch{ch}.{ext}"
            self.scope.waveform.save_waveform(waveform, ch_filename, format=format)
            logger.info(f"Saved channel {ch} to {ch_filename}")

    def save_batch(self, batch_results: List[Dict[str, Any]], output_dir: str, format: str = "npz") -> None:
        """Save batch capture results to directory.

        Args:
            batch_results: List of batch capture results
            output_dir: Output directory path
            format: File format ('npz', 'csv', 'mat', 'h5')

        Example:
            >>> results = collector.batch_capture(...)
            >>> collector.save_batch(results, 'batch_output')
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save metadata
        metadata = {
            "total_captures": len(batch_results),
            "timestamp": datetime.now().isoformat(),
            "configurations": [r["config"] for r in batch_results],
        }

        metadata_file = output_path / "metadata.txt"
        with open(metadata_file, "w") as f:
            f.write(f"Batch Capture Metadata\n")
            f.write(f"=====================\n\n")
            f.write(f"Total Captures: {metadata['total_captures']}\n")
            f.write(f"Timestamp: {metadata['timestamp']}\n\n")
            f.write(f"Configurations:\n")
            for i, config in enumerate(metadata["configurations"]):
                f.write(f"  {i+1}. {config}\n")

        # Save waveforms
        for i, result in enumerate(batch_results):
            config_str = "_".join([f"{k}={v}" for k, v in result["config"].items()]).replace("/", "-")
            trigger_num = result["trigger_num"]

            for ch, waveform in result["waveforms"].items():
                filename = f"capture_{i:04d}_ch{ch}_{config_str}_trig{trigger_num}.{format}"
                filepath = output_path / filename
                self.scope.waveform.save_waveform(waveform, str(filepath), format=format)

        logger.info(f"Saved {len(batch_results)} captures to {output_path}")

    def analyze_waveform(self, waveform: WaveformData) -> Dict[str, float]:
        """Analyze a waveform and extract common measurements.

        Args:
            waveform: WaveformData object to analyze

        Returns:
            Dictionary of measurement names and values

        Example:
            >>> data = collector.capture_single([1])
            >>> stats = collector.analyze_waveform(data[1])
            >>> print(f"Peak-to-peak: {stats['vpp']:.3f}V")
            >>> print(f"RMS: {stats['rms']:.3f}V")
        """
        voltage = waveform.voltage

        analysis = {
            "vpp": np.max(voltage) - np.min(voltage),
            "amplitude": (np.max(voltage) - np.min(voltage)) / 2,
            "max": np.max(voltage),
            "min": np.min(voltage),
            "mean": np.mean(voltage),
            "rms": np.sqrt(np.mean(voltage**2)),
            "std_dev": np.std(voltage),
            "median": np.median(voltage),
        }

        # Try to detect frequency (simple zero-crossing method)
        frequency = 0.0
        period = 0.0

        try:
            mean_val = analysis["mean"]
            crossings = np.where(np.diff(np.sign(voltage - mean_val)))[0]

            # Estimate sample interval from the time axis, falling back to sample_rate
            dt = float(np.mean(np.diff(waveform.time))) if len(waveform.time) > 1 else None
            if (dt is None or dt <= 0) and getattr(waveform, "sample_rate", None):
                if waveform.sample_rate > 0:
                    dt = 1.0 / float(waveform.sample_rate)

            if len(crossings) > 2 and dt and dt > 0:
                # Average time between positive-going zero crossings
                periods = np.diff(crossings[::2]) * dt
                avg_period = float(np.mean(periods))
                if avg_period > 0:
                    period = avg_period
                    frequency = 1.0 / avg_period
        except Exception:
            # Keep zero defaults on parsing errors
            pass

        analysis["frequency"] = frequency
        analysis["period"] = period

        return analysis


class TriggerWaitCollector:
    """Specialized collector for waiting on specific trigger conditions.

    Useful for capturing events that occur sporadically or based on
    specific signal conditions.
    """

    def __init__(
        self,
        host: str,
        port: int = 5024,
        timeout: float = 5.0,
        connection: Optional[BaseConnection] = None,
    ):
        """Initialize trigger wait collector.

        Args:
            host: IP address or hostname of the oscilloscope
            port: TCP port for SCPI communication
            timeout: Command timeout in seconds
            connection: Optional connection implementation (e.g., MockConnection for offline tests)
        """
        self.collector = DataCollector(host, port, timeout, connection=connection)

    def __enter__(self):
        """Context manager entry."""
        self.collector.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.collector.disconnect()
        return False

    def wait_for_trigger(
        self,
        channels: List[int],
        max_wait: float = 60.0,
        save_on_trigger: bool = True,
        output_dir: Optional[str] = None,
    ) -> Optional[Dict[int, WaveformData]]:
        """Wait for a trigger event and capture waveform.

        Args:
            channels: List of channel numbers to capture
            max_wait: Maximum time to wait for trigger in seconds
            save_on_trigger: If True, save waveform when triggered
            output_dir: Directory to save waveforms (required if save_on_trigger=True)

        Returns:
            Captured waveforms or None if timeout

        Example:
            >>> with TriggerWaitCollector('192.168.1.100') as tc:
            ...     # Configure trigger on channel 1, edge = rising, level = 1V
            ...     tc.collector.scope.trigger.set_source(1)
            ...     tc.collector.scope.trigger.set_slope('POS')
            ...     tc.collector.scope.trigger.set_level(1, 1.0)
            ...
            ...     # Wait for trigger
            ...     data = tc.wait_for_trigger([1, 2], max_wait=30.0)
            ...     if data:
            ...         print("Trigger captured!")
        """
        # Set to NORMAL trigger mode
        self.collector.scope.trigger.mode = "NORM"
        self.collector.scope.trigger_single()

        start_time = time.time()
        while (time.time() - start_time) < max_wait:
            # Check trigger status
            status = self.collector.scope.query(":TRIG:STAT?").strip()

            if status == "Stop":
                # Trigger occurred, capture waveform
                logger.info("Trigger detected!")
                waveforms = {}
                for ch in channels:
                    try:
                        waveforms[ch] = self.collector.scope.waveform.acquire(ch)
                    except Exception as e:
                        logger.error(f"Failed to capture channel {ch}: {e}")

                if save_on_trigger and output_dir:
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    self.collector.save_data(waveforms, f"{output_dir}/trigger_{timestamp_str}")

                return waveforms

            time.sleep(0.1)  # Check every 100ms

        logger.warning(f"Trigger timeout after {max_wait}s")
        return None
