"""
DAQ-specific LLM analyzer for data acquisition insights and recommendations.

Provides methods for trend analysis, threshold suggestions, and session summaries.
"""

import logging
from typing import Dict, List, Optional

from scpi_control.report_generator.llm.client import LLMClient
from scpi_control.report_generator.llm.daq_context_builder import DAQContextBuilder
from scpi_control.report_generator.llm.daq_prompts import get_daq_system_prompt

logger = logging.getLogger(__name__)


class DAQAnalyzer:
    """High-level interface for AI-powered DAQ data analysis."""

    def __init__(self, llm_client: LLMClient):
        """
        Initialize DAQ analyzer.

        Args:
            llm_client: Configured LLM client (Ollama, OpenAI, etc.)
        """
        self.client = llm_client

    def analyze_trends(
        self,
        data_buffer: List[Dict],
        channels: List[int],
        channel_configs: Optional[Dict[int, Dict]] = None,
        window_size: int = 100,
    ) -> Optional[str]:
        """
        Analyze trends in DAQ data.

        Args:
            data_buffer: List of {timestamp, readings} dictionaries
            channels: List of active channel numbers
            channel_configs: Optional channel configurations
            window_size: Number of recent samples to analyze

        Returns:
            Trend analysis text, or None if generation failed
        """
        if not data_buffer:
            return "No data available for trend analysis."

        system_prompt = get_daq_system_prompt("trends")
        user_prompt = DAQContextBuilder.build_trend_analysis_request(data_buffer, channels, channel_configs, window_size)

        analysis = self.client.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return analysis

    def suggest_thresholds(
        self,
        data_buffer: List[Dict],
        channel: int,
        channel_config: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        Suggest alarm thresholds for a channel.

        Args:
            data_buffer: List of readings
            channel: Channel number to analyze
            channel_config: Channel configuration

        Returns:
            Dictionary with threshold suggestions, or None if failed
        """
        if not data_buffer:
            return None

        system_prompt = get_daq_system_prompt("thresholds")
        user_prompt = DAQContextBuilder.build_threshold_suggestion_request(data_buffer, channel, channel_config)

        response = self.client.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.5,  # Lower temperature for more consistent numeric suggestions
        )

        if not response:
            return None

        # Parse response into structured format
        result = {
            "channel": channel,
            "raw_response": response,
            "thresholds": {},
        }

        # Try to extract numeric thresholds from response
        # This is a simple extraction - could be enhanced with structured output
        lines = response.lower().split("\n")
        for line in lines:
            if "warning" in line and "high" in line:
                value = DAQAnalyzer._extract_number(line)
                if value is not None:
                    result["thresholds"]["warning_high"] = value
            elif "warning" in line and "low" in line:
                value = DAQAnalyzer._extract_number(line)
                if value is not None:
                    result["thresholds"]["warning_low"] = value
            elif "critical" in line or "alarm" in line:
                if "high" in line or "upper" in line:
                    value = DAQAnalyzer._extract_number(line)
                    if value is not None:
                        result["thresholds"]["critical_high"] = value
                elif "low" in line or "lower" in line:
                    value = DAQAnalyzer._extract_number(line)
                    if value is not None:
                        result["thresholds"]["critical_low"] = value

        return result

    def generate_session_summary(
        self,
        data_buffer: List[Dict],
        channels: List[int],
        channel_configs: Optional[Dict[int, Dict]] = None,
        session_metadata: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Generate a summary report for a DAQ session.

        Args:
            data_buffer: Complete session data
            channels: Active channels
            channel_configs: Channel configurations
            session_metadata: Session metadata

        Returns:
            Summary report text, or None if generation failed
        """
        if not data_buffer:
            return "No data available for summary generation."

        system_prompt = get_daq_system_prompt("summary")
        user_prompt = DAQContextBuilder.build_session_summary_request(data_buffer, channels, channel_configs, session_metadata)

        summary = self.client.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return summary

    def answer_question(
        self,
        data_buffer: List[Dict],
        channels: List[int],
        question: str,
        channel_configs: Optional[Dict[int, Dict]] = None,
    ) -> Optional[str]:
        """
        Answer a user question about the DAQ data.

        Args:
            data_buffer: Session data
            channels: Active channels
            question: User's question
            channel_configs: Channel configurations

        Returns:
            Answer text, or None if generation failed
        """
        if not data_buffer:
            return "No data available. Please start a logging session first."

        system_prompt = get_daq_system_prompt("chat")
        user_prompt = DAQContextBuilder.build_chat_context(data_buffer, channels, question, channel_configs)

        answer = self.client.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return answer

    def detect_anomalies(
        self,
        data_buffer: List[Dict],
        channels: List[int],
        channel_configs: Optional[Dict[int, Dict]] = None,
    ) -> Optional[str]:
        """
        Detect anomalies or unusual patterns in the data.

        Args:
            data_buffer: Session data
            channels: Active channels
            channel_configs: Channel configurations

        Returns:
            Anomaly detection report, or None if generation failed
        """
        if not data_buffer:
            return "No data available for anomaly detection."

        system_prompt = get_daq_system_prompt("expert")

        context = DAQContextBuilder.build_session_context(data_buffer, channels, channel_configs)

        prompt = (
            "Please analyze this DAQ data for anomalies and unusual patterns. "
            "Look for:\n"
            "1. Sudden jumps or drops in values\n"
            "2. Values outside expected ranges\n"
            "3. Unusual noise or variability\n"
            "4. Missing or invalid readings\n"
            "5. Unexpected correlations between channels\n\n"
            "Report any anomalies found with specific values and timestamps.\n\n"
            "=== DAQ DATA ===\n\n"
        )
        prompt += context

        analysis = self.client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return analysis

    def compare_channels(
        self,
        data_buffer: List[Dict],
        channel_a: int,
        channel_b: int,
        channel_configs: Optional[Dict[int, Dict]] = None,
    ) -> Optional[str]:
        """
        Compare two channels and analyze their relationship.

        Args:
            data_buffer: Session data
            channel_a: First channel number
            channel_b: Second channel number
            channel_configs: Channel configurations

        Returns:
            Comparison analysis, or None if generation failed
        """
        if not data_buffer:
            return "No data available for channel comparison."

        system_prompt = get_daq_system_prompt("expert")

        context = DAQContextBuilder.build_session_context(data_buffer, [channel_a, channel_b], channel_configs)

        prompt = (
            f"Please compare Channel {channel_a} and Channel {channel_b} from this DAQ data. "
            "Analyze:\n"
            "1. Are they correlated (moving together or inversely)?\n"
            "2. Is there a time lag between them?\n"
            "3. How do their statistical properties compare?\n"
            "4. Are there any cause-effect relationships suggested?\n\n"
            "Provide specific observations with numeric values.\n\n"
            "=== DAQ DATA ===\n\n"
        )
        prompt += context

        analysis = self.client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return analysis

    @staticmethod
    def _extract_number(text: str) -> Optional[float]:
        """Extract a number from a line of text."""
        import re

        # Find numbers (including negative and decimal)
        numbers = re.findall(r"-?\d+\.?\d*", text)
        if numbers:
            try:
                return float(numbers[0])
            except ValueError:
                pass
        return None


def create_daq_analyzer(
    provider: str = "ollama",
    model: Optional[str] = None,
    **kwargs,
) -> DAQAnalyzer:
    """
    Factory function to create a DAQ analyzer with the specified LLM provider.

    Args:
        provider: LLM provider ('ollama', 'openai', 'anthropic')
        model: Model name (defaults to provider's default)
        **kwargs: Additional arguments for the LLM client

    Returns:
        Configured DAQAnalyzer instance
    """
    from scpi_control.report_generator.llm.client import LLMClient

    client = LLMClient(provider=provider, model=model, **kwargs)
    return DAQAnalyzer(client)
