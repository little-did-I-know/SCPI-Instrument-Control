"""
High-level analyzer that uses LLM to generate insights and summaries.

Provides convenient methods for common analysis tasks.
"""

import logging
import re
from typing import List, Optional

from scpi_control.report_generator.llm.client import LLMClient
from scpi_control.report_generator.llm.context_builder import ContextBuilder
from scpi_control.report_generator.llm.prompts import get_system_prompt
from scpi_control.report_generator.llm.tools import ReportTools
from scpi_control.report_generator.models.report_data import SUMMARY_SOURCE_AI, MeasurementResult, TestReport

logger = logging.getLogger(__name__)

# The local model is asked for a numbered list but does not always oblige: it
# may bold the numbers, count past 9, or open with a "Here are the findings:"
# line. Match list markers tolerantly; if the reply has no markers at all,
# salvage its non-preamble lines rather than returning nothing.
_LIST_ITEM = re.compile(r"^\s*\*{0,2}\s*(?:\d+[.)]|[-*•])\*{0,2}\s+")


def _unwrap_bold(text: str) -> str:
    """Remove a markdown emphasis wrapper only when it surrounds the WHOLE item.

    ``**foo**`` -> ``foo`` and ``*foo*`` -> ``foo``, but a partially-bolded item
    like ``**foo** bar`` or a leading glob like ``*.tmp`` is left untouched --
    stripping those would strand an interior marker or eat real content.
    """
    for marker in ("**", "*"):
        if len(text) > 2 * len(marker) and text.startswith(marker) and text.endswith(marker):
            inner = text[len(marker) : -len(marker)].strip()
            if inner:
                return inner
    return text


def _parse_numbered_list(text: Optional[str], max_items: int) -> Optional[List[str]]:
    """Parse a model's numbered/bulleted list into clean items.

    Handles multi-digit prefixes, markdown-bold numbering (``**1.**``), and a
    leading preamble line. Falls back to plain non-preamble lines when the model
    emits no list markers at all. Returns None for empty/whitespace/None input.

    Args:
        text: The raw model reply.
        max_items: Cap on the number of items returned.
    """
    if not text:
        return None
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    items = [_unwrap_bold(line[m.end() :].strip()) for line in lines if (m := _LIST_ITEM.match(line))]
    if not items:
        items = [line for line in lines if not line.endswith(":")]
    items = [item for item in items if item]
    return items[:max_items] if items else None


class ReportAnalyzer:
    """High-level interface for AI-powered report analysis."""

    def __init__(self, llm_client: LLMClient):
        """
        Initialize analyzer.

        Args:
            llm_client: Configured LLM client
        """
        self.client = llm_client

    def generate_executive_summary(self, report: TestReport) -> Optional[str]:
        """
        Generate an executive summary of the test report.

        Args:
            report: Test report to summarize

        Returns:
            Executive summary text, or None if generation failed
        """
        system_prompt = get_system_prompt("summary")
        user_prompt = ContextBuilder.build_analysis_request(report, "summary")

        summary = self.client.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return summary

    def analyze_waveforms(self, report: TestReport) -> Optional[str]:
        """
        Analyze waveforms for signal quality and integrity issues.

        Args:
            report: Test report containing waveforms

        Returns:
            Analysis text, or None if generation failed
        """
        system_prompt = get_system_prompt("analysis")
        user_prompt = ContextBuilder.build_analysis_request(report, "insights")

        analysis = self.client.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return analysis

    def interpret_measurements(self, report: TestReport) -> Optional[str]:
        """
        Interpret measurement results and explain pass/fail status.

        Args:
            report: Test report with measurements

        Returns:
            Interpretation text, or None if generation failed
        """
        system_prompt = get_system_prompt("interpretation")
        user_prompt = ContextBuilder.build_analysis_request(report, "interpretation")

        interpretation = self.client.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return interpretation

    def answer_question(self, report: TestReport, question: str) -> Optional[str]:
        """
        Answer a user question about the test report.

        Uses tool calling when the model supports it, so the model can reach the
        real analyses. Otherwise falls back to the summarized context, which is
        eight scalars per waveform.

        Args:
            report: Test report context
            question: User's question

        Returns:
            Answer text, or None if generation failed
        """
        if self.client.supports_tools():
            logger.info("Answering with tool calling")
            messages = [
                {"role": "system", "content": get_system_prompt("chat_tools")},
                {"role": "user", "content": question},
            ]
            return self.client.chat_with_tools(messages, ReportTools(report).functions())

        logger.info("Model cannot call tools; answering from the summarized context")
        return self.client.complete(
            prompt=ContextBuilder.build_chat_context(report, question),
            system_prompt=get_system_prompt("chat"),
            temperature=0.7,
        )

    def explain_measurement(
        self,
        measurement: MeasurementResult,
        context: Optional[str] = None,
    ) -> Optional[str]:
        """
        Explain a specific measurement and its significance.

        Args:
            measurement: Measurement to explain
            context: Optional additional context

        Returns:
            Explanation text, or None if generation failed
        """
        system_prompt = get_system_prompt("expert")

        prompt = f"Please explain this oscilloscope measurement:\n\n"
        prompt += f"Measurement: {measurement.name}\n"
        prompt += f"Value: {measurement.format_value()}\n"

        if measurement.channel:
            prompt += f"Channel: {measurement.channel}\n"

        if measurement.passed is not None:
            status = "PASSED" if measurement.passed else "FAILED"
            prompt += f"Status: {status}\n"

            if measurement.criteria_min is not None:
                prompt += f"Minimum allowed: {measurement.criteria_min} {measurement.unit}\n"
            if measurement.criteria_max is not None:
                prompt += f"Maximum allowed: {measurement.criteria_max} {measurement.unit}\n"

        if context:
            prompt += f"\nAdditional context: {context}\n"

        prompt += "\nWhat does this measurement tell us about the signal? "
        if measurement.passed is False:
            prompt += "Why might it have failed? What could be the root cause?"

        explanation = self.client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return explanation

    def suggest_next_steps(self, report: TestReport) -> Optional[str]:
        """
        Suggest next steps based on test results.

        Side effect: on success, sets report.recommendations_source to
        SUMMARY_SOURCE_AI (audit M31), exactly as generate_recommendations does --
        this method is the other AI-producing path into report.recommendations
        (see examples/report_generation_example.py's create_report_with_ai()).

        Args:
            report: Test report

        Returns:
            Suggestions text, or None if generation failed
        """
        system_prompt = get_system_prompt("expert")

        context = ContextBuilder.build_report_context(report)

        prompt = (
            "Based on this test report, what should the technician do next? "
            "Consider the overall result, any failed measurements, and signal quality. "
            "Provide 3-5 specific, actionable recommendations.\n\n"
            "=== TEST REPORT ===\n\n"
        )
        prompt += context

        suggestions = self.client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        if suggestions:
            # The producer marks its own output so no caller can forget to (audit M31).
            report.recommendations_source = SUMMARY_SOURCE_AI

        return suggestions

    def generate_key_findings(self, report: TestReport, max_findings: int = 5) -> Optional[List[str]]:
        """
        Generate a list of key findings from the report.

        Side effect: on success, sets report.findings_source to SUMMARY_SOURCE_AI
        (audit M31) so downstream renderers label this content as AI-generated.

        Args:
            report: Test report
            max_findings: Maximum number of findings to generate

        Returns:
            List of key finding strings, or None if generation failed
        """
        system_prompt = get_system_prompt("expert")
        context = ContextBuilder.build_report_context(report)

        prompt = (
            f"Please identify the {max_findings} most important findings from this test report. "
            "Return ONLY a numbered list, one finding per line, starting at '1.'. "
            "No heading, no preamble, no text before the first item or after the last. "
            "Focus on the most significant results, issues, or noteworthy observations.\n\n"
            "=== TEST REPORT ===\n\n"
        )
        prompt += context

        response = self.client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        findings = _parse_numbered_list(response, max_findings)
        if findings:
            # The producer marks its own output so no caller can forget to (audit M31).
            report.findings_source = SUMMARY_SOURCE_AI
        return findings

    def generate_recommendations(self, report: TestReport, max_recommendations: int = 5) -> Optional[List[str]]:
        """
        Generate actionable recommendations based on the test results.

        Side effect: on success, sets report.recommendations_source to
        SUMMARY_SOURCE_AI (audit M31) so downstream renderers label this
        content as AI-generated.

        Args:
            report: Test report
            max_recommendations: Maximum number of recommendations to generate

        Returns:
            List of recommendation strings, or None if generation failed
        """
        system_prompt = get_system_prompt("expert")
        context = ContextBuilder.build_report_context(report)

        prompt = (
            f"Based on this test report, provide {max_recommendations} specific, actionable recommendations. "
            "These should be practical next steps or suggestions for the technician. "
            "Return ONLY a numbered list, one recommendation per line, starting at '1.'. "
            "No heading, no preamble, no text before the first item or after the last. "
            "Focus on what actions should be taken based on the results.\n\n"
            "=== TEST REPORT ===\n\n"
        )
        prompt += context

        response = self.client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        recommendations = _parse_numbered_list(response, max_recommendations)
        if recommendations:
            # The producer marks its own output so no caller can forget to (audit M31).
            report.recommendations_source = SUMMARY_SOURCE_AI
        return recommendations
