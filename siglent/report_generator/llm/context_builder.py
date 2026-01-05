"""
Context builder for formatting waveform data for LLM analysis.

Prepares measurement data, waveform statistics, and test information
in a format suitable for LLM consumption.
"""

from typing import Any, Dict, List, Optional

import numpy as np

from siglent.report_generator.models.report_data import MeasurementResult, TestReport, TestSection, WaveformData
from siglent.report_generator.models.test_types import get_test_type


class ContextBuilder:
    """Builds context strings for LLM prompts from oscilloscope data."""

    @staticmethod
    def build_waveform_context(waveform: WaveformData) -> str:
        """
        Build a context string describing a waveform.

        Args:
            waveform: Waveform data

        Returns:
            Formatted context string
        """
        lines = [f"Waveform: {waveform.label or waveform.channel_name}"]

        # Basic stats
        lines.append(f"  Sample Rate: {waveform.sample_rate / 1e6:.2f} MS/s")
        lines.append(f"  Record Length: {waveform.record_length} samples")

        if waveform.timebase:
            lines.append(f"  Timebase: {waveform.timebase * 1e6:.2f} µs/div")

        # Voltage statistics
        v_min = np.min(waveform.voltage_data)
        v_max = np.max(waveform.voltage_data)
        v_mean = np.mean(waveform.voltage_data)
        v_std = np.std(waveform.voltage_data)
        v_pp = v_max - v_min

        lines.append(f"  Voltage Range: {v_min:.4f} V to {v_max:.4f} V")
        lines.append(f"  Peak-to-Peak: {v_pp:.4f} V")
        lines.append(f"  Mean: {v_mean:.4f} V")
        lines.append(f"  Std Dev: {v_std:.4f} V")

        # Time statistics
        time_span = waveform.time_data[-1] - waveform.time_data[0]
        lines.append(f"  Time Span: {time_span * 1e6:.2f} µs")

        return "\n".join(lines)

    @staticmethod
    def build_measurements_context(measurements: List[MeasurementResult]) -> str:
        """
        Build a context string describing measurements.

        Args:
            measurements: List of measurement results

        Returns:
            Formatted context string
        """
        if not measurements:
            return "No measurements available."

        lines = ["Measurements:"]

        for meas in measurements:
            status = ""
            if meas.passed is not None:
                status = " [PASS]" if meas.passed else " [FAIL]"

            channel_str = f" ({meas.channel})" if meas.channel else ""
            lines.append(f"  {meas.name}{channel_str}: {meas.format_value()}{status}")

            if meas.criteria_min is not None or meas.criteria_max is not None:
                criteria_parts = []
                if meas.criteria_min is not None:
                    criteria_parts.append(f"min: {meas.criteria_min:.6g} {meas.unit}")
                if meas.criteria_max is not None:
                    criteria_parts.append(f"max: {meas.criteria_max:.6g} {meas.unit}")
                lines.append(f"    Criteria: {', '.join(criteria_parts)}")

        return "\n".join(lines)

    @staticmethod
    def build_section_context(section: TestSection) -> str:
        """
        Build a context string for a test section.

        Args:
            section: Test section

        Returns:
            Formatted context string
        """
        lines = [f"## {section.title}"]

        if section.content:
            lines.append(section.content)
            lines.append("")

        # Add waveform context
        if section.waveforms:
            lines.append("### Waveforms")
            for waveform in section.waveforms:
                lines.append(ContextBuilder.build_waveform_context(waveform))
                lines.append("")

        # Add measurements
        if section.measurements:
            lines.append(ContextBuilder.build_measurements_context(section.measurements))
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def build_report_context(report: TestReport, include_sections: bool = True) -> str:
        """
        Build a complete context string for a test report.

        Args:
            report: Test report
            include_sections: Whether to include detailed section information

        Returns:
            Formatted context string
        """
        lines = [f"# Test Report: {report.metadata.title}"]
        lines.append(f"Technician: {report.metadata.technician}")
        lines.append(f"Date: {report.metadata.test_date.strftime('%Y-%m-%d %H:%M:%S')}")

        if report.metadata.equipment_model:
            lines.append(f"Equipment: {report.metadata.equipment_model}")

        if report.metadata.test_procedure:
            lines.append(f"Procedure: {report.metadata.test_procedure}")

        # Add test type information if available
        if report.metadata.test_type:
            test_type_def = get_test_type(report.metadata.test_type)
            if test_type_def:
                lines.append(f"Test Type: {test_type_def.name}")
            else:
                lines.append(f"Test Type: {report.metadata.test_type}")

        lines.append("")

        # Overall result
        overall = report.overall_result or report.calculate_overall_result()
        lines.append(f"Overall Result: {overall}")
        lines.append("")

        # Get all measurements for summary
        all_measurements = report.get_all_measurements()
        if all_measurements:
            passed = sum(1 for m in all_measurements if m.passed is True)
            failed = sum(1 for m in all_measurements if m.passed is False)
            lines.append(f"Measurements: {len(all_measurements)} total, {passed} passed, {failed} failed")
            lines.append("")

        # Sections
        if include_sections and report.sections:
            lines.append("## Test Sections")
            for section in report.sections:
                lines.append(ContextBuilder.build_section_context(section))
                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def build_analysis_request(
        report: TestReport,
        analysis_type: str = "summary",
        focus_areas: Optional[List[str]] = None,
    ) -> str:
        """
        Build a prompt requesting specific analysis from LLM.

        Args:
            report: Test report to analyze
            analysis_type: Type of analysis ('summary', 'insights', 'interpretation')
            focus_areas: Optional list of specific areas to focus on

        Returns:
            Prompt string for LLM
        """
        context = ContextBuilder.build_report_context(report, include_sections=True)

        # Build test type specific context if available
        test_type_context = ""
        if report.metadata.test_type:
            test_type_def = get_test_type(report.metadata.test_type)
            print(f"[DEBUG] Test type ID: {report.metadata.test_type}")
            print(f"[DEBUG] Test type definition: {test_type_def.name if test_type_def else 'None'}")
            if test_type_def and test_type_def.id != "general":
                test_type_context = (
                    "=== TEST TYPE CONTEXT ===\n\n"
                    f"{test_type_def.get_ai_context()}\n\n"
                    "IMPORTANT: When analyzing this data, consider the expected signal characteristics "
                    "and analysis focus areas listed above. Do not flag expected signal characteristics "
                    "as problems. For example:\n"
                    "- In probe calibration tests, square waves are EXPECTED and should not be interpreted as noise\n"
                    "- In power supply ripple tests, small AC ripple on DC is EXPECTED\n"
                    "- In clock signal tests, periodic square waves are EXPECTED\n\n"
                )
                print(f"[DEBUG] Adding test type context for: {test_type_def.name}")
        else:
            print("[DEBUG] No test type set in report metadata")

        if analysis_type == "summary":
            prompt = (
                "Please provide a concise executive summary of this oscilloscope test report. "
                "Highlight the key findings, overall test result, and any critical issues that need attention. "
                "Keep the summary to 2-3 paragraphs.\n\n"
            )

        elif analysis_type == "insights":
            prompt = (
                "Please analyze this oscilloscope test data and provide insights about the signal quality. "
                "Consider factors like noise levels, signal integrity, frequency characteristics, and any anomalies. "
                "Provide practical recommendations for improvement if applicable.\n\n"
            )

        elif analysis_type == "interpretation":
            prompt = (
                "Please interpret the measurement results in this test report. "
                "For any failed measurements, explain what the failure indicates and suggest potential causes. "
                "For passed measurements, note if any values are near the limits.\n\n"
            )

        else:
            prompt = f"Please analyze this oscilloscope test report focusing on: {analysis_type}\n\n"

        if focus_areas:
            prompt += f"Pay special attention to: {', '.join(focus_areas)}\n\n"

        # Add test type context before report data
        if test_type_context:
            prompt += test_type_context

        prompt += "=== TEST REPORT DATA ===\n\n"
        prompt += context

        # Debug: Print full prompt
        print("\n" + "=" * 80)
        print("FULL PROMPT BEING SENT TO LLM:")
        print("=" * 80)
        print(prompt[:1000] + "..." if len(prompt) > 1000 else prompt)
        print("=" * 80 + "\n")

        return prompt

    @staticmethod
    def build_chat_context(report: TestReport, user_question: str) -> str:
        """
        Build context for an interactive chat question about the report.

        Args:
            report: Test report
            user_question: User's question

        Returns:
            Full prompt with context and question
        """
        context = ContextBuilder.build_report_context(report, include_sections=True)

        prompt = (
            "You are an expert oscilloscope technician and test engineer. "
            "Answer the following question about this test report data. "
            "Be specific, technical, and refer to actual measurements when relevant.\n\n"
        )

        # Add test type context if available
        if report.metadata.test_type:
            test_type_def = get_test_type(report.metadata.test_type)
            if test_type_def and test_type_def.id != "general":
                prompt += "=== TEST TYPE CONTEXT ===\n\n"
                prompt += test_type_def.get_ai_context()
                prompt += "\n\nWhen answering, consider the expected signal characteristics for this test type.\n\n"

        prompt += "=== TEST REPORT DATA ===\n\n"
        prompt += context
        prompt += "\n\n=== USER QUESTION ===\n\n"
        prompt += user_question

        return prompt
