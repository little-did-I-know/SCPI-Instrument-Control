# 📊 Siglent Report Generator - Complete Feature Documentation

## Overview

The **Siglent Report Generator** is a powerful standalone application for creating professional test reports from oscilloscope waveform data. It features AI-powered analysis using local LLMs (Ollama/LM Studio) for completely private, offline report generation with intelligent insights.

## ✨ Key Features

### 🔬 Data Import & Analysis

- **Multiple file formats:** NPZ, CSV, MATLAB (.mat), HDF5
- **Batch import:** Load multiple waveform files at once
- **Image import:** Add screenshots, setup photos, diagrams
- **Live scope connection:** Ready for future real-time capture integration
- **Signal type detection:** Automatic waveform classification (sine, square, triangle, sawtooth, pulse, DC, noise)
- **Comprehensive statistics:** 25+ measurements including amplitude, frequency, timing, and quality metrics
- **Plateau stability:** Measures noise on flat signal regions for power supply and logic level testing

### 📝 Professional Reports

- **PDF Reports:** Publication-ready PDFs with company branding
- **Markdown Reports:** Documentation-friendly format for version control
- **Customizable branding:** Company logo, header/footer, custom colors
- **Automatic plots:** Waveform graphs, FFT analysis, embedded images
- **Real-time progress:** Visual progress bar with granular updates during PDF generation

### ✅ Pass/Fail Testing

- **Measurement criteria:** Define acceptable ranges for measurements
- **Multiple comparison types:** Range, min/max only, equals, not-equals
- **Template system:** Save and reuse test procedures
- **Visual indicators:** Color-coded pass/fail status in reports

### 🤖 AI-Powered Analysis (Optional)

- **Executive summaries:** Auto-generate report summaries
- **Waveform insights:** AI analyzes signal quality and integrity
- **Pass/fail interpretation:** Explains why measurements failed and suggests fixes
- **Interactive chat:** Ask questions about your test data
- **100% Private:** Uses local LLM - no cloud, no data sharing

### 💾 Template System

- **Save configurations:** Reuse report settings across tests
- **Criteria sets:** Store pass/fail criteria for standard tests
- **Branding presets:** Maintain consistent company branding
- **JSON format:** Easy to share and version control

## 🚀 Quick Start

### Installation

```bash
# Install with report generator dependencies
pip install -e ".[report-generator]"

# Or install all features
pip install -e ".[all]"
```

### Launch the GUI

```bash
# Using the command
siglent-report-generator

# Or using Python module
python -m siglent.report_generator.app
```

### Basic Workflow

1. **Import Data:** Click "Import Waveforms" and select your saved waveform files
2. **Add Metadata:** Fill in technician name, test date, equipment details, etc.
3. **Generate Report:** Click "Generate PDF Report" or "Generate Markdown Report"
4. **Done!** Your professional report is ready

### With AI Features

1. **Configure LLM:** Go to Settings → LLM Configuration
2. **Select Service:** Choose Ollama (recommended) or LM Studio
3. **Test Connection:** Click "Test Connection" to verify
4. **Use AI Features:**
   - Click "Generate Summary" for executive summary
   - Click "Analyze Waveforms" for signal quality insights
   - Use the chat sidebar to ask questions

## 📖 Example Usage

### Programmatic API

```python
from siglent.report_generator.models.report_data import (
    TestReport, ReportMetadata, WaveformData, MeasurementResult
)
from siglent.report_generator.generators.pdf_generator import PDFReportGenerator
from datetime import datetime

# Create metadata
metadata = ReportMetadata(
    title="Power Supply Test",
    technician="John Engineer",
    test_date=datetime.now(),
    equipment_model="SDS2104X Plus"
)

# Create report
report = TestReport(metadata=metadata)

# Add your waveforms and measurements
# ... (load from files or capture from scope)

# Generate PDF
generator = PDFReportGenerator()
generator.generate(report, Path("my_report.pdf"))
```

### Run the Example Script

```bash
cd examples
python report_generation_example.py
```

This creates a complete sample report with:

- Synthetic waveform data
- Pass/fail measurements
- Optional AI analysis
- Both PDF and Markdown outputs

## 🏗️ Building Standalone Executables

### Windows

```bash
# Install build dependencies
pip install -e ".[report-generator,build-exe]"

# Build executable
pyinstaller report-generator-windows.spec

# Output: dist/SiglentReportGenerator/SiglentReportGenerator.exe
```

### Linux

```bash
# Install dependencies
pip install -e ".[report-generator,build-exe]"
sudo apt-get install libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0

# Build executable
pyinstaller report-generator-linux.spec

# Output: dist/SiglentReportGenerator/SiglentReportGenerator
```

### AppImage (Linux Universal Package)

See `BUILD_EXECUTABLE.md` for detailed AppImage creation instructions.

## 🔧 Setting Up AI Features

### Option 1: Ollama (Recommended)

1. **Download Ollama:** https://ollama.com
2. **Install and run:**

   ```bash
   # Download a model
   ollama pull llama3.2

   # Verify it's running
   ollama list
   ```

3. **In Report Generator:**
   - Go to Settings → LLM Configuration
   - Select "Ollama" tab
   - Default settings should work (port 11434, model llama3.2)
   - **NEW:** Click "Detect Models" to automatically populate available models
   - Click "Test Connection"

### Option 2: LM Studio

1. **Download LM Studio:** https://lmstudio.ai
2. **Load a model** (e.g., Llama 3, Mistral)
3. **Start local server** (usually port 1234)
4. **In Report Generator:**
   - Go to Settings → LLM Configuration
   - Select "LM Studio" tab
   - Set port number
   - **NEW:** Click "Detect Models" to automatically populate available models
   - Select your model from dropdown or type manually
   - Click "Test Connection"

### Recommended Models

- **Fast & Lightweight:** llama3.2 (3B)
- **Balanced:** llama3.2 (8B), mistral (7B)
- **Best Quality:** llama3.1 (70B) - requires powerful hardware

## 📁 Project Structure

```
siglent/report_generator/
├── __init__.py
├── app.py                      # Application entry point
├── main_window.py              # Main GUI window
│
├── models/                     # Data structures
│   ├── report_data.py          # Report, waveform, measurement models
│   ├── criteria.py             # Pass/fail criteria system
│   └── template.py             # Template save/load
│
├── utils/                      # Utilities
│   ├── waveform_loader.py      # Multi-format waveform loading
│   └── image_handler.py        # Image processing
│
├── llm/                        # AI integration
│   ├── client.py               # LLM API client
│   ├── context_builder.py      # Data formatting for LLM
│   ├── prompts.py              # Expert system prompts
│   └── analyzer.py             # High-level AI functions
│
├── generators/                 # Report output
│   ├── base.py                 # Base generator class
│   ├── markdown_generator.py   # Markdown reports
│   └── pdf_generator.py        # PDF reports
│
└── widgets/                    # GUI components
    ├── metadata_panel.py       # Metadata input form
    ├── llm_settings_dialog.py  # LLM configuration
    └── chat_sidebar.py         # AI chat interface
```

## 🎯 Use Cases

### Quality Assurance

- **Automated test documentation** for production testing
- **Pass/fail criteria enforcement** with audit trails
- **Batch testing** with consistent report formatting

### Research & Development

- **Signal analysis** with AI insights
- **Reproducible results** with saved templates
- **Publication-ready** figures and reports

### Education

- **Lab reports** for oscilloscope experiments
- **Learning tool** - AI explains measurements
- **Professional formatting** for student submissions

### Field Service

- **On-site testing** with portable executable
- **Quick report generation** for customers
- **No internet required** - fully offline capable

## 📊 Report Content

Reports can include:

- **Executive Summary** (AI-generated or custom)
- **Test Metadata** (technician, date, equipment, conditions)
- **Waveform Captures** (plots with statistics)
- **Signal Type Classification** (automatic detection with confidence score)
- **Comprehensive Statistics** (25+ measurements per waveform)
- **Plateau Stability Analysis** (optional, for periodic signals)
- **Measurement Results** (with pass/fail status)
- **FFT Analysis** (frequency domain plots)
- **Custom Images** (setup photos, diagrams)
- **AI Insights** (signal quality analysis)
- **Recommendations** (next steps, troubleshooting)

## 🔬 Advanced Waveform Analysis

### Signal Type Detection

The report generator automatically classifies waveforms using FFT harmonic analysis:

- **Sine waves:** Detected by dominant fundamental frequency (THD < 10%)
- **Square waves:** Odd harmonics with 1/n amplitude ratio
- **Triangle waves:** Odd harmonics with 1/n² amplitude ratio
- **Sawtooth waves:** All harmonics with 1/n amplitude ratio
- **Pulse/PWM:** Detected by duty cycle and harmonic pattern
- **DC signals:** Constant voltage with no AC component
- **Noise:** Random signal with no dominant frequency
- **Complex/Unknown:** Mixed or unclassified signals

Each classification includes a confidence score (0-100%) displayed in the report.

### Comprehensive Waveform Statistics

Every waveform is analyzed with 25+ measurements:

**Amplitude Measurements:**

- Vmax, Vmin, Vpp (peak-to-peak)
- VRMS (root mean square)
- Vmean (average voltage)
- DC offset

**Frequency & Timing:**

- Frequency and period
- Rise time and fall time
- Pulse width and duty cycle

**Quality Metrics:**

- SNR (Signal-to-Noise Ratio)
- THD (Total Harmonic Distortion)
- Noise level
- Overshoot and undershoot
- Jitter

All statistics are automatically formatted with appropriate SI prefixes (mV, µs, kHz, etc.).

### Plateau Stability Analysis (Optional)

For periodic signals (square waves, pulses, PWM, etc.), you can enable **Plateau Stability Analysis** to measure noise on flat signal regions:

**How it works:**

1. Identifies high and low plateau regions using run-length encoding
2. Analyzes the middle 60% of each plateau (excludes edge transitions)
3. Calculates standard deviation as a measure of noise

**Reported metrics:**

- **Plateau High Noise:** Noise on high-level plateaus
- **Plateau Low Noise:** Noise on low-level plateaus
- **Plateau Stability:** Average noise across all plateaus

**Use cases:**

- Power supply ripple testing
- Logic level stability verification
- Signal integrity assessment
- Switch bounce analysis

**To enable:** Check "Plateau Stability Analysis (Advanced)" in the Report Options dialog

## ⚙️ Configuration

### Report Templates

Templates are saved as JSON files and include:

- Section configuration
- Pass/fail criteria
- Branding settings
- Default metadata

Create a template in the GUI, then save it for reuse.

### LLM Configuration

LLM settings are stored in:

- Endpoint URL (e.g., http://localhost:11434/v1)
- Model name
- API key (if required)
- Temperature, max tokens, timeout

### System Requirements

**Minimum:**

- Python 3.8+
- 4 GB RAM
- 500 MB disk space

**Recommended:**

- Python 3.10+
- 8 GB RAM (16 GB for AI features)
- 2 GB disk space

**For AI features:**

- 8 GB RAM minimum (16 GB recommended)
- Multi-core CPU (GPU optional but helpful)

## 🐛 Troubleshooting

### "reportlab not installed" error

```bash
pip install reportlab
```

### LLM connection fails

- Verify Ollama/LM Studio is running
- Check firewall settings
- Confirm port number is correct
- Test with: `curl http://localhost:11434/api/tags`

### Waveform loading errors

- Verify file format is supported (NPZ, CSV, MAT, HDF5)
- Check file is not corrupted
- Ensure file contains time and voltage data

### PDF generation slow

- Normal for large reports with many plots
- Consider reducing plot resolution
- Use Markdown for faster generation

## 📝 License

MIT License - see main project LICENSE file

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- Additional report formats (HTML, Word)
- More AI analysis features
- Advanced measurement calculations
- Protocol decode integration
- Live scope capture in GUI

## 📧 Support

For issues and questions:

- GitHub Issues: https://github.com/little-did-I-know/Siglent-Oscilloscope/issues
- Documentation: See docs/report-generator/ (coming soon)

---

**Built with:** PyQt6, matplotlib, ReportLab, NumPy, SciPy
**AI powered by:** Local LLMs (Ollama, LM Studio)
**Part of:** Siglent Oscilloscope Control Library
