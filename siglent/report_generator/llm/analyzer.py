"""
High-level analyzer that uses LLM to generate insights and summaries.

Provides convenient methods for common analysis tasks.
"""

from typing import List, Optional

from siglent.report_generator.llm.client import LLMClient
from siglent.report_generator.llm.context_builder import ContextBuilder
from siglent.report_generator.llm.prompts import get_system_prompt
from siglent.report_generator.models.report_data import MeasurementResult, TestReport


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

        Args:
            report: Test report context
            question: User's question

        Returns:
            Answer text, or None if generation failed
        """
        system_prompt = get_system_prompt("chat")
        user_prompt = ContextBuilder.build_chat_context(report, question)

        answer = self.client.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        return answer

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

        return suggestions

    def generate_key_findings(self, report: TestReport, max_findings: int = 5) -> Optional[List[str]]:
        """
        Generate a list of key findings from the report.

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
            "Return them as a numbered list, with each finding on its own line. "
            "Focus on the most significant results, issues, or noteworthy observations.\n\n"
            "=== TEST REPORT ===\n\n"
        )
        prompt += context

        response = self.client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        if not response:
            return None

        # Parse numbered list into individual findings
        findings = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # Remove list numbering (e.g., "1.", "1)", "- ", etc.)
            for prefix in ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "1)", "2)", "3)", "4)", "5)", "6)", "7)", "8)", "9)", "- ", "* ", "• "]:
                if line.startswith(prefix):
                    line = line[len(prefix) :].strip()
                    break

            if line:
                findings.append(line)

        return findings[:max_findings] if findings else None

    def generate_recommendations(self, report: TestReport, max_recommendations: int = 5) -> Optional[List[str]]:
        """
        Generate actionable recommendations based on the test results.

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
            "Return them as a numbered list, with each recommendation on its own line. "
            "Focus on what actions should be taken based on the results.\n\n"
            "=== TEST REPORT ===\n\n"
        )
        prompt += context

        response = self.client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
        )

        if not response:
            return None

        # Parse numbered list into individual recommendations
        recommendations = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # Remove list numbering (e.g., "1.", "1)", "- ", etc.)
            for prefix in ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "1)", "2)", "3)", "4)", "5)", "6)", "7)", "8)", "9)", "- ", "* ", "• "]:
                if line.startswith(prefix):
                    line = line[len(prefix) :].strip()
                    break

            if line:
                recommendations.append(line)

        return recommendations[:max_recommendations] if recommendations else None
