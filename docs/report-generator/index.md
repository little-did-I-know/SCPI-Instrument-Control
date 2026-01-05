# Report Generator

The **Siglent Report Generator** is a powerful standalone application for creating professional test reports from oscilloscope waveform data. Generate beautiful PDF and Markdown reports with AI-powered insights, all running completely offline.

![Report Generator Overview](../images/report-generator-main.png)

## Key Features

### 📊 Professional Reports

- **PDF Reports** - Publication-ready PDFs with company branding, logos, and custom headers/footers
- **Markdown Reports** - Version-control friendly documentation with embedded plots
- **Multiple Sections** - Organize your reports with customizable sections
- **Automatic Plots** - Beautiful waveform graphs, FFT analysis, and measurement tables

### 🔬 Data Import

- **Multi-Format Support** - Import NPZ, CSV, MATLAB (.mat), and HDF5 files
- **Batch Import** - Load multiple waveform files at once
- **Image Support** - Add screenshots, setup photos, and diagrams
- **Live Capture** - Ready for future real-time oscilloscope integration

### 🤖 AI-Powered Analysis

- **Executive Summaries** - Auto-generate professional report summaries
- **Signal Analysis** - AI analyzes waveform quality and identifies issues
- **Pass/Fail Interpretation** - Explains why tests failed and suggests solutions
- **Interactive Chat** - Ask questions about your test data in natural language
- **100% Private** - Uses local LLMs (Ollama/LM Studio) - no cloud, no data sharing

### ✅ Pass/Fail Testing

- **Measurement Criteria** - Define acceptable ranges for all measurements
- **Multiple Comparison Types** - Range, min/max only, equals, not-equals
- **Template System** - Save and reuse test procedures
- **Visual Indicators** - Color-coded pass/fail status in reports

## Quick Start

### Installation

Install the Report Generator with all required dependencies:

```bash
pip install -e ".[report-generator]"
```

Or install everything:

```bash
pip install -e ".[all]"
```

### Launch the Application

```bash
# Using the installed command
siglent-report-generator

# Or using Python module
python -m siglent.report_generator.app
```

### Your First Report

1. **Import Data** - Click "Import Waveforms..." and select saved waveform files
2. **Add Metadata** - Fill in technician name, test date, and equipment details
3. **Generate** - Click "Generate PDF Report" or "Generate Markdown Report"
4. **Done!** - Your professional report is ready

## Documentation Sections

### Getting Started

- [**Installation & Setup**](getting-started.md) - Install and configure the Report Generator
- [**Creating Your First Report**](getting-started.md#creating-your-first-report) - Step-by-step tutorial
- [**GUI Overview**](getting-started.md#gui-overview) - Tour of the interface

### AI Features

- [**LLM Setup**](llm-setup.md) - Configure Ollama or LM Studio for AI features
- [**Using AI Analysis**](llm-setup.md#using-ai-features) - Generate summaries and insights
- [**Chat Assistant**](llm-setup.md#chat-assistant) - Ask questions about your data

### Advanced Usage

- [**Template System**](templates.md) - Save and reuse report configurations
- [**Pass/Fail Criteria**](templates.md#pass-fail-criteria) - Define test criteria
- [**Programmatic API**](api-reference.md) - Use Python API for automation
- [**Building Executables**](building-executables.md) - Create standalone apps

## Example Use Cases

### Quality Assurance

Generate automated test reports for production testing with pass/fail criteria and audit trails.

```python
# Automated QA report generation
report = create_qa_report(waveforms, criteria_set)
if not report.calculate_overall_result() == "PASS":
    send_alert(report)
```

### Research & Development

Create publication-ready figures and comprehensive analysis reports.

```python
# Research report with AI insights
report = create_research_report(experiment_data)
add_ai_analysis(report, llm_client)
export_pdf(report, "research_findings.pdf")
```

### Field Service

Generate quick reports for customers on-site, completely offline.

```python
# On-site service report
report = create_service_report(measurements)
add_technician_notes(report, notes)
export_pdf(report, f"service_{customer_id}.pdf")
```

## System Requirements

**Minimum:**

- Python 3.8 or later
- 4 GB RAM
- 500 MB disk space

**Recommended:**

- Python 3.10 or later
- 8 GB RAM (16 GB for AI features)
- 2 GB disk space

**For AI features:**

- 8 GB RAM minimum (16 GB recommended)
- Multi-core CPU (GPU optional but helpful)
- Ollama or LM Studio installed

## Need Help?

- **Getting Started** - See the [Getting Started Guide](getting-started.md)
- **AI Setup** - See the [LLM Setup Tutorial](llm-setup.md)
- **Templates** - See the [Template Guide](templates.md)
- **API** - See the [API Reference](api-reference.md)
- **Issues** - Report bugs on [GitHub Issues](https://github.com/little-did-I-know/Siglent-Oscilloscope/issues)

## What's Next?

- [**Get Started →**](getting-started.md) - Install and create your first report
- [**Setup AI →**](llm-setup.md) - Enable AI-powered features
- [**Learn Templates →**](templates.md) - Save time with reusable templates
