"""Ask a local LLM questions about a report, using tool-calling.

Builds a synthetic report and asks a local Ollama model questions about it. When
the model supports tools, it answers by CALLING the report's analysis tools
(list_waveforms, analyze_waveform, ...) rather than guessing from a summary.

This needs a local Ollama running with a tool-capable model (e.g. `ollama run
llama3.2`). With none available it prints that and exits cleanly -- so the
example is safe to run anywhere.

Requirements: SCPI-Instrument-Control[report-generator]; optional local Ollama
for the live Q&A. No hardware.
"""

from datetime import datetime

import numpy as np

from scpi_control.report_generator.llm.analyzer import ReportAnalyzer
from scpi_control.report_generator.llm.client import LLMClient, LLMConfig
from scpi_control.report_generator.models.report_data import ReportMetadata, TestReport, TestSection, WaveformData


def build_report() -> TestReport:
    sample_rate = 1e6
    t = np.arange(2000) / sample_rate
    np.random.seed(0)
    v = 3.3 * np.sin(2 * np.pi * 1000 * t) + 0.02 * np.random.randn(t.size)
    waveform = WaveformData(channel="C1", time=t, voltage=v, sample_rate=sample_rate, record_length=t.size, label="1 kHz reference")
    return TestReport(
        metadata=ReportMetadata(title="AI Q&A Demo", technician="Lab Tech", test_date=datetime.now()),
        sections=[TestSection(title="Captures", waveforms=[waveform], order=1)],
    )


def main():
    print("=" * 60)
    print("Local-LLM tool-calling Q&A over a report")
    print("=" * 60)

    report = build_report()

    client = LLMClient(LLMConfig.create_ollama_config(model="llama3.2"))

    if not client.supports_tools():
        print("No tool-capable local model available.")
        print("Start Ollama with a tool-capable model (e.g. `ollama run llama3.2`) to try the live Q&A.")
        print("=" * 60)
        print("Done (skipped live Q&A).")
        print("=" * 60)
        return

    analyzer = ReportAnalyzer(client)
    questions = [
        "What channels are in this report?",
        "What kind of signal is on C1, and what is its frequency?",
    ]
    for question in questions:
        print(f"\nQ: {question}")
        try:
            answer = analyzer.answer_question(report, question)
        except Exception as exc:  # never let a model hiccup crash the example
            print(f"A: (the model call failed: {exc})")
            continue
        print(f"A: {answer if answer is not None else '(no answer)'}")

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
