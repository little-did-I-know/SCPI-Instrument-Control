"""
Context builder for formatting DAQ/Data Logger data for LLM analysis.

Prepares time-series readings, channel statistics, and session metadata
in a format suitable for LLM consumption.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class DAQContextBuilder:
    """Builds context strings for LLM prompts from DAQ data."""

    @staticmethod
    def build_channel_statistics(
        channel: int,
        values: List[float],
        measurement_type: str = "Unknown",
        unit: str = "",
    ) -> Dict[str, Any]:
        """
        Calculate statistics for a channel's readings.

        Args:
            channel: Channel number
            values: List of measurement values
            measurement_type: Type of measurement (e.g., "DC Voltage")
            unit: Unit string (e.g., "V")

        Returns:
            Dictionary of statistics
        """
        if not values:
            return {"channel": channel, "count": 0}

        arr = np.array(values)
        # Filter out NaN values
        arr = arr[~np.isnan(arr)]

        if len(arr) == 0:
            return {"channel": channel, "count": 0}

        return {
            "channel": channel,
            "measurement_type": measurement_type,
            "unit": unit,
            "count": len(arr),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "range": float(np.max(arr) - np.min(arr)),
            "first": float(arr[0]),
            "last": float(arr[-1]),
            "trend": float(arr[-1] - arr[0]) if len(arr) > 1 else 0.0,
        }

    @staticmethod
    def build_session_context(
        data_buffer: List[Dict],
        channels: List[int],
        channel_configs: Optional[Dict[int, Dict]] = None,
        session_metadata: Optional[Dict] = None,
    ) -> str:
        """
        Build a complete context string for a DAQ session.

        Args:
            data_buffer: List of {timestamp, readings} dictionaries
            channels: List of active channel numbers
            channel_configs: Optional channel configuration dictionary
            session_metadata: Optional session metadata

        Returns:
            Formatted context string
        """
        lines = ["# DAQ Session Data"]
        lines.append("")

        # Session metadata
        if session_metadata:
            if "start_time" in session_metadata:
                lines.append(f"Start Time: {session_metadata['start_time']}")
            if "duration" in session_metadata:
                lines.append(f"Duration: {session_metadata['duration']:.1f} seconds")
            if "scan_interval" in session_metadata:
                lines.append(f"Scan Interval: {session_metadata['scan_interval']:.1f} seconds")
            if "model" in session_metadata:
                lines.append(f"Instrument: {session_metadata['model']}")
            lines.append("")

        # Data summary
        lines.append(f"Total Scans: {len(data_buffer)}")
        lines.append(f"Active Channels: {len(channels)}")

        if data_buffer:
            time_span = data_buffer[-1]["timestamp"] - data_buffer[0]["timestamp"]
            lines.append(f"Time Span: {time_span:.1f} seconds")
        lines.append("")

        # Channel statistics
        lines.append("## Channel Statistics")
        lines.append("")

        for ch in channels:
            # Get values for this channel
            values = [d["readings"].get(ch) for d in data_buffer if ch in d.get("readings", {})]
            values = [v for v in values if v is not None]

            # Get channel config
            config = channel_configs.get(ch, {}) if channel_configs else {}
            meas_type = config.get("function_display", "Unknown")
            unit = DAQContextBuilder._get_unit_for_function(config.get("function", ""))

            stats = DAQContextBuilder.build_channel_statistics(ch, values, meas_type, unit)

            if stats["count"] > 0:
                lines.append(f"### Channel {ch} ({meas_type})")
                lines.append(f"  Readings: {stats['count']}")
                lines.append(f"  Min: {stats['min']:.6f} {unit}")
                lines.append(f"  Max: {stats['max']:.6f} {unit}")
                lines.append(f"  Mean: {stats['mean']:.6f} {unit}")
                lines.append(f"  Std Dev: {stats['std']:.6f} {unit}")
                lines.append(f"  Range: {stats['range']:.6f} {unit}")
                lines.append(f"  Overall Change: {stats['trend']:+.6f} {unit}")
                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def build_trend_analysis_request(
        data_buffer: List[Dict],
        channels: List[int],
        channel_configs: Optional[Dict[int, Dict]] = None,
        window_size: int = 100,
    ) -> str:
        """
        Build a prompt for trend analysis.

        Args:
            data_buffer: List of readings
            channels: Active channels
            channel_configs: Channel configurations
            window_size: Number of recent samples to analyze

        Returns:
            Prompt string for LLM
        """
        # Use recent data
        recent_data = data_buffer[-window_size:] if len(data_buffer) > window_size else data_buffer

        context = DAQContextBuilder.build_session_context(recent_data, channels, channel_configs)

        prompt = (
            "Please analyze the trends in this DAQ data. For each channel:\n"
            "1. Identify if values are increasing, decreasing, or stable\n"
            "2. Calculate the rate of change if trending\n"
            "3. Detect any sudden changes or anomalies\n"
            "4. Predict where values will be if trends continue\n"
            "5. Note any correlations between channels\n\n"
            "Provide specific numeric values in your analysis.\n\n"
            "=== DAQ DATA ===\n\n"
        )
        prompt += context

        # Add recent time-series samples
        prompt += "\n## Recent Readings (last 10 samples)\n\n"
        for entry in recent_data[-10:]:
            timestamp = entry["timestamp"]
            readings_str = ", ".join(f"CH{ch}={entry['readings'].get(ch, 'N/A'):.4f}" for ch in channels if ch in entry.get("readings", {}))
            prompt += f"t={timestamp:.2f}s: {readings_str}\n"

        return prompt

    @staticmethod
    def build_threshold_suggestion_request(
        data_buffer: List[Dict],
        channel: int,
        channel_config: Optional[Dict] = None,
    ) -> str:
        """
        Build a prompt for threshold suggestion.

        Args:
            data_buffer: List of readings
            channel: Channel to analyze
            channel_config: Channel configuration

        Returns:
            Prompt string for LLM
        """
        # Get values for this channel
        values = [d["readings"].get(channel) for d in data_buffer if channel in d.get("readings", {})]
        values = [v for v in values if v is not None]

        config = channel_config or {}
        meas_type = config.get("function_display", "Unknown")
        unit = DAQContextBuilder._get_unit_for_function(config.get("function", ""))

        stats = DAQContextBuilder.build_channel_statistics(channel, values, meas_type, unit)

        prompt = (
            f"Based on the measurement data for Channel {channel}, please suggest appropriate "
            "alarm thresholds. Consider:\n"
            "1. Normal operating range based on the data statistics\n"
            "2. Warning thresholds (approaching limits)\n"
            "3. Critical/alarm thresholds (definite problem)\n"
            "4. The measurement type and typical acceptable ranges\n\n"
            "Provide specific numeric values that can be configured as alarm limits.\n\n"
            f"=== CHANNEL {channel} DATA ===\n\n"
            f"Measurement Type: {meas_type}\n"
            f"Unit: {unit}\n"
            f"Samples: {stats.get('count', 0)}\n"
        )

        if stats.get("count", 0) > 0:
            prompt += f"Minimum: {stats['min']:.6f} {unit}\n"
            prompt += f"Maximum: {stats['max']:.6f} {unit}\n"
            prompt += f"Mean: {stats['mean']:.6f} {unit}\n"
            prompt += f"Standard Deviation: {stats['std']:.6f} {unit}\n"
            prompt += f"Range (Max-Min): {stats['range']:.6f} {unit}\n"

        return prompt

    @staticmethod
    def build_session_summary_request(
        data_buffer: List[Dict],
        channels: List[int],
        channel_configs: Optional[Dict[int, Dict]] = None,
        session_metadata: Optional[Dict] = None,
    ) -> str:
        """
        Build a prompt for session summary generation.

        Args:
            data_buffer: Complete session data
            channels: Active channels
            channel_configs: Channel configurations
            session_metadata: Session metadata

        Returns:
            Prompt string for LLM
        """
        context = DAQContextBuilder.build_session_context(data_buffer, channels, channel_configs, session_metadata)

        prompt = (
            "Please generate a comprehensive summary report for this data acquisition session. "
            "Include:\n"
            "1. Session Overview: Duration, channels monitored, data quality\n"
            "2. Key Findings: Notable trends, events, or anomalies\n"
            "3. Statistical Summary: Important values for each channel\n"
            "4. Observations: Any patterns or correlations noticed\n"
            "5. Recommendations: Suggested actions or follow-up\n\n"
            "Format the report professionally for documentation purposes.\n\n"
            "=== SESSION DATA ===\n\n"
        )
        prompt += context

        return prompt

    @staticmethod
    def build_chat_context(
        data_buffer: List[Dict],
        channels: List[int],
        user_question: str,
        channel_configs: Optional[Dict[int, Dict]] = None,
    ) -> str:
        """
        Build context for an interactive chat question about DAQ data.

        Args:
            data_buffer: Session data
            channels: Active channels
            user_question: User's question
            channel_configs: Channel configurations

        Returns:
            Full prompt with context and question
        """
        context = DAQContextBuilder.build_session_context(data_buffer, channels, channel_configs)

        prompt = (
            "You are a data acquisition expert assistant. "
            "Answer the following question about this DAQ session data. "
            "Be specific and reference actual measurement values.\n\n"
            "=== DAQ SESSION DATA ===\n\n"
        )
        prompt += context
        prompt += "\n\n=== USER QUESTION ===\n\n"
        prompt += user_question

        return prompt

    @staticmethod
    def _get_unit_for_function(func_id: str) -> str:
        """Get the unit string for a measurement function."""
        unit_map = {
            "VOLT:DC": "V",
            "VOLT:AC": "V",
            "CURR:DC": "A",
            "CURR:AC": "A",
            "RES": "Ω",
            "FRES": "Ω",
            "TEMP:TC:K": "°C",
            "TEMP:TC:J": "°C",
            "TEMP:RTD": "°C",
            "FREQ": "Hz",
            "PER": "s",
        }
        return unit_map.get(func_id, "")

    @staticmethod
    def format_readings_for_export(
        data_buffer: List[Dict],
        channels: List[int],
    ) -> List[Dict]:
        """
        Format readings for JSON export or external analysis.

        Args:
            data_buffer: Session data
            channels: Active channels

        Returns:
            List of formatted reading dictionaries
        """
        formatted = []
        for entry in data_buffer:
            record = {"timestamp": entry["timestamp"]}
            for ch in channels:
                if ch in entry.get("readings", {}):
                    record[f"CH{ch}"] = entry["readings"][ch]
            formatted.append(record)
        return formatted
