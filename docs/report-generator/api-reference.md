# API Reference

This guide covers programmatic usage of the Report Generator for automation and integration.

## Installation

```bash
pip install -e ".[report-generator]"
```

## Quick Example

```python
from pathlib import Path
from datetime import datetime
from siglent.report_generator.models.report_data import (
    TestReport, ReportMetadata, WaveformData, MeasurementResult, TestSection
)
from siglent.report_generator.generators.pdf_generator import PDFReportGenerator

# Create metadata
metadata = ReportMetadata(
    title="My Test Report",
    technician="Alice",
    test_date=datetime.now()
)

# Create report
report = TestReport(metadata=metadata)

# Add section with your data
section = TestSection(
    title="Results",
    waveforms=[...],  # Your WaveformData objects
    measurements=[...],  # Your MeasurementResult objects
    order=1
)
report.add_section(section)

# Generate PDF
generator = PDFReportGenerator()
generator.generate(report, Path("report.pdf"))
```

## Core Modules

### `siglent.report_generator.models.report_data`

Data structures for reports.

#### `ReportMetadata`

```python
ReportMetadata(
    title: str,                          # Required
    technician: str,                     # Required
    test_date: datetime,                 # Required
    equipment_model: Optional[str],
    equipment_id: Optional[str],
    test_procedure: Optional[str],
    notes: Optional[str],
    # ... many more optional fields
)
```

**Methods:**

- `to_dict()` - Convert to dictionary
- `from_dict(data)` - Create from dictionary

#### `WaveformData`

```python
WaveformData(
    channel_name: str,         # e.g., "CH1"
    time_data: np.ndarray,     # Time values
    voltage_data: np.ndarray,  # Voltage values
    sample_rate: float,        # Samples per second
    record_length: int,        # Number of samples
    timebase: Optional[float],  # s/div
    voltage_scale: Optional[float],  # V/div
    probe_ratio: Optional[float],  # e.g., 10.0 for 10:1
    coupling: Optional[str],  # "DC", "AC", "GND"
    source_file: Optional[Path],
    color: Optional[str],  # Hex color for plot
    label: Optional[str],  # Display name
)
```

**Methods:**

- `to_dict()` - Convert to dictionary (excludes arrays)

#### `MeasurementResult`

```python
MeasurementResult(
    name: str,                # e.g., "Frequency"
    value: float,             # Numerical value
    unit: str,                # e.g., "Hz"
    channel: Optional[str],   # e.g., "CH1"
    passed: Optional[bool],   # Pass/fail status
    criteria_min: Optional[float],
    criteria_max: Optional[float],
    ai_interpretation: Optional[str],
)
```

**Methods:**

- `format_value()` - Returns formatted string "value unit"
- `get_status_symbol()` - Returns "✓", "✗", or "—"
- `to_dict()` / `from_dict()` - Serialization

#### `TestSection`

```python
TestSection(
    title: str,
    content: str = "",
    waveforms: List[WaveformData] = [],
    measurements: List[MeasurementResult] = [],
    images: List[Path] = [],
    include_fft: bool = False,
    fft_frequency: Optional[np.ndarray] = None,
    fft_magnitude: Optional[np.ndarray] = None,
    ai_summary: Optional[str] = None,
    ai_insights: Optional[str] = None,
    order: int = 0,
)
```

**Methods:**

- `to_dict()` - Convert to dictionary

#### `TestReport`

```python
TestReport(
    metadata: ReportMetadata,
    sections: List[TestSection] = [],
    executive_summary: Optional[str] = None,
    ai_generated_summary: bool = False,
    key_findings: List[str] = [],
    recommendations: List[str] = [],
    overall_result: Optional[str] = None,  # "PASS", "FAIL", "INCONCLUSIVE"
)
```

**Methods:**

- `add_section(section)` - Add and sort section
- `get_all_measurements()` - Get measurements from all sections
- `get_all_waveforms()` - Get waveforms from all sections
- `calculate_overall_result()` - Determine PASS/FAIL
- `to_dict()` - Convert to dictionary

### `siglent.report_generator.utils.waveform_loader`

Load waveforms from files.

#### `WaveformLoader`

```python
from siglent.report_generator.utils.waveform_loader import WaveformLoader

# Load single file (auto-detects format)
waveforms = WaveformLoader.load(Path("data.npz"))

# Load multiple files
filepaths = [Path("data1.npz"), Path("data2.csv")]
all_waveforms = WaveformLoader.load_multiple(filepaths)
```

**Supported formats:**

- `.npz` - NumPy archive
- `.csv` - Comma-separated values
- `.mat` - MATLAB file
- `.h5`, `.hdf5` - HDF5

### `siglent.report_generator.generators`

Generate reports in various formats.

#### `PDFReportGenerator`

```python
from siglent.report_generator.generators.pdf_generator import PDFReportGenerator

generator = PDFReportGenerator(
    page_size=letter,  # or A4
    include_plots=True,
    plot_width=6.5,  # inches
    plot_height=3.0,  # inches
)

success = generator.generate(report, Path("output.pdf"))
```

#### `MarkdownReportGenerator`

```python
from siglent.report_generator.generators.markdown_generator import MarkdownReportGenerator

generator = MarkdownReportGenerator(
    include_plots=True,
    plots_dir="plots"  # Subdirectory for plot images
)

success = generator.generate(report, Path("output.md"))
```

### `siglent.report_generator.models.criteria`

Pass/fail criteria system.

#### `MeasurementCriteria`

```python
from siglent.report_generator.models.criteria import (
    MeasurementCriteria, ComparisonType
)

criteria = MeasurementCriteria(
    measurement_name="Frequency",
    comparison_type=ComparisonType.RANGE,
    min_value=990,
    max_value=1010,
    channel="CH1",  # Optional
    description="Frequency within ±1%",
    severity="critical",  # or "warning", "info"
)

# Validate a measurement value
result = criteria.validate(1005)  # Returns CriteriaResult
print(result.passed)  # True
print(result.message)  # "Value 1005 is within range [990, 1010]"
```

**Comparison types:**

- `ComparisonType.RANGE` - Min and max
- `ComparisonType.MIN_ONLY` - Minimum only
- `ComparisonType.MAX_ONLY` - Maximum only
- `ComparisonType.EQUALS` - Equals target ± tolerance
- `ComparisonType.NOT_EQUALS` - Not equal to target

#### `CriteriaSet`

```python
from siglent.report_generator.models.criteria import CriteriaSet

criteria_set = CriteriaSet(
    name="Power Supply Test",
    description="Acceptance criteria for 5V output"
)

criteria_set.add_criteria(criteria1)
criteria_set.add_criteria(criteria2)

# Validate measurements
measurements = [
    {"name": "Frequency", "value": 1005, "channel": "CH1"},
    {"name": "Vpp", "value": 4.1}
]
results = criteria_set.validate_measurements(measurements)

for result in results:
    print(result)  # [PASS] or [FAIL] with details
```

### `siglent.report_generator.models.template`

Template system for reusable configurations.

#### `ReportTemplate`

```python
from siglent.report_generator.models.template import ReportTemplate

# Create new template
template = ReportTemplate(
    name="My Template",
    description="Template description",
    author="Your Name"
)

# Save to file
template.save(Path("my_template.json"))

# Load from file
template = ReportTemplate.load(Path("my_template.json"))

# Get default template
template = ReportTemplate.create_default_template()
```

### `siglent.report_generator.llm`

AI/LLM integration.

#### `LLMClient`

```python
from siglent.report_generator.llm.client import LLMClient, LLMConfig

# Create config
config = LLMConfig.create_ollama_config(model="llama3.2")
# or
config = LLMConfig.create_lm_studio_config(model="local-model")
# or
config = LLMConfig.create_openai_config(api_key="sk-...", model="gpt-4")

# Create client
client = LLMClient(config)

# Test connection
if client.test_connection():
    print("Connected!")

# Get completion
response = client.complete(
    prompt="Explain this measurement...",
    system_prompt="You are an expert...",
    temperature=0.7
)

# Stream response
for chunk in client.stream_chat(messages):
    print(chunk, end="")
```

#### `ReportAnalyzer`

High-level AI analysis functions.

```python
from siglent.report_generator.llm.analyzer import ReportAnalyzer

analyzer = ReportAnalyzer(llm_client)

# Generate executive summary
summary = analyzer.generate_executive_summary(report)

# Analyze waveforms
analysis = analyzer.analyze_waveforms(report)

# Interpret measurements
interpretation = analyzer.interpret_measurements(report)

# Answer question
answer = analyzer.answer_question(report, "Why did it fail?")

# Get key findings
findings = analyzer.generate_key_findings(report, max_findings=5)
```

## Complete Example

Here's a complete example showing all major features:

```python
from pathlib import Path
from datetime import datetime
import numpy as np

from siglent.report_generator.models.report_data import *
from siglent.report_generator.models.criteria import *
from siglent.report_generator.models.template import *
from siglent.report_generator.utils.waveform_loader import WaveformLoader
from siglent.report_generator.generators.pdf_generator import PDFReportGenerator
from siglent.report_generator.llm.client import LLMClient, LLMConfig
from siglent.report_generator.llm.analyzer import ReportAnalyzer


def generate_automated_report(waveform_files, output_path):
    """Generate a complete report with AI analysis."""

    # 1. Load waveforms
    waveforms = WaveformLoader.load_multiple(waveform_files)

    # 2. Create metadata
    metadata = ReportMetadata(
        title="Automated Test Report",
        technician="AutoTest System",
        test_date=datetime.now(),
        equipment_model="SDS2104X Plus",
        test_procedure="AUTO-001"
    )

    # 3. Create report
    report = TestReport(metadata=metadata)

    # 4. Add waveform section
    section = TestSection(
        title="Waveform Analysis",
        content="Automated waveform capture and analysis.",
        waveforms=waveforms,
        order=1
    )

    # 5. Add measurements (calculate from waveforms)
    for wf in waveforms:
        # Calculate measurements
        vpp = np.ptp(wf.voltage_data)
        mean = np.mean(wf.voltage_data)
        rms = np.sqrt(np.mean(wf.voltage_data**2))

        section.measurements.extend([
            MeasurementResult(name="Vpp", value=vpp, unit="V", channel=wf.channel_name),
            MeasurementResult(name="Mean", value=mean, unit="V", channel=wf.channel_name),
            MeasurementResult(name="RMS", value=rms, unit="V", channel=wf.channel_name),
        ])

    report.add_section(section)

    # 6. Apply pass/fail criteria
    criteria_set = CriteriaSet(name="Standard Criteria")
    criteria_set.add_criteria(MeasurementCriteria(
        measurement_name="Vpp",
        comparison_type=ComparisonType.RANGE,
        min_value=3.8,
        max_value=4.2
    ))

    # Validate measurements
    results = criteria_set.validate_measurements([
        {"name": m.name, "value": m.value, "channel": m.channel}
        for m in section.measurements
    ])

    # Update measurement status
    for measurement, result in zip(section.measurements, results):
        if result.criteria.measurement_name == measurement.name:
            measurement.passed = result.passed
            measurement.criteria_min = result.criteria.min_value
            measurement.criteria_max = result.criteria.max_value

    # 7. Add AI analysis (optional)
    try:
        llm_config = LLMConfig.create_ollama_config()
        llm_client = LLMClient(llm_config)

        if llm_client.test_connection():
            analyzer = ReportAnalyzer(llm_client)

            # Generate summary
            report.executive_summary = analyzer.generate_executive_summary(report)
            report.ai_generated_summary = True

            # Add insights to section
            section.ai_insights = analyzer.analyze_waveforms(report)
    except Exception as e:
        print(f"AI analysis skipped: {e}")

    # 8. Calculate overall result
    report.overall_result = report.calculate_overall_result()

    # 9. Generate PDF
    generator = PDFReportGenerator()
    success = generator.generate(report, output_path)

    return success, report


# Usage
files = [Path("data1.npz"), Path("data2.npz")]
success, report = generate_automated_report(files, Path("automated_report.pdf"))

if success:
    print(f"Report generated: {report.metadata.title}")
    print(f"Overall result: {report.overall_result}")
```

## Error Handling

```python
from siglent.report_generator.exceptions import *

try:
    waveforms = WaveformLoader.load(Path("data.npz"))
except FileNotFoundError:
    print("File not found")
except ValueError as e:
    print(f"Invalid file format: {e}")

try:
    generator.generate(report, output_path)
except Exception as e:
    print(f"Generation failed: {e}")
```

## Best Practices

### Memory Management

```python
# For large datasets, process one at a time
for file in large_file_list:
    waveforms = WaveformLoader.load(file)
    # Process waveforms
    # Generate section
    del waveforms  # Free memory
```

### Asynchronous Generation

```python
from concurrent.futures import ThreadPoolExecutor

def generate_report(config):
    # ... report generation code
    pass

# Generate multiple reports in parallel
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(generate_report, cfg) for cfg in configs]
    results = [f.result() for f in futures]
```

### Data Validation

```python
def validate_waveform(wf: WaveformData) -> bool:
    """Validate waveform data before adding to report."""
    if len(wf.time_data) != len(wf.voltage_data):
        return False
    if wf.sample_rate <= 0:
        return False
    if wf.record_length != len(wf.voltage_data):
        return False
    return True

# Use it
if validate_waveform(waveform):
    section.waveforms.append(waveform)
```

## See Also

- **GUI Guide** - [Getting Started](getting-started.md)
- **Templates** - [Template Guide](templates.md)
- **AI Features** - [LLM Setup](llm-setup.md)
- **Examples** - `examples/report_generation_example.py`
