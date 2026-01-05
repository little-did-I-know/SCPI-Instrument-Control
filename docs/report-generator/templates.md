# Templates & Criteria

Templates save time by storing reusable report configurations. Define your test procedures once, then reuse them for every test.

## What are Templates?

A **Report Template** stores:

- Report sections and their order
- Pass/fail criteria for measurements
- Company branding (logo, colors, header/footer)
- Default metadata values
- AI feature preferences

Think of templates as "test procedures" - they ensure consistency across multiple tests.

## Benefits

- ✅ **Consistency** - Same criteria for every test
- ✅ **Time Saving** - No re-entering settings
- ✅ **Quality** - Standardized procedures
- ✅ **Sharing** - Team members use same templates
- ✅ **Version Control** - Templates are JSON files

## Creating Templates (API)

> **Note:** Template creation through the GUI is planned for a future release. For now, use the Python API.

### Basic Template

```python
from siglent.report_generator.models.template import (
    ReportTemplate,
    SectionTemplate,
    BrandingTemplate
)

# Create a new template
template = ReportTemplate(
    name="Power Supply Output Test",
    description="Standard test for 5V power supplies",
    author="Engineering Team"
)

# Add sections
template.add_section(SectionTemplate(
    title="Test Setup",
    content="Equipment configuration and test conditions",
    include_waveforms=False,
    include_measurements=False,
    order=1
))

template.add_section(SectionTemplate(
    title="Waveform Captures",
    content="Captured waveforms and time-domain analysis",
    include_waveforms=True,
    include_measurements=True,
    order=2
))

# Save the template
template.save(Path("power_supply_test.json"))
```

### Loading Templates

```python
# Load an existing template
template = ReportTemplate.load(Path("power_supply_test.json"))

# Use it to configure a report
for section_template in template.sections:
    section = TestSection(
        title=section_template.title,
        content=section_template.content,
        order=section_template.order
    )
    report.add_section(section)
```

## Section Templates

### Section Configuration

Each section template defines:

```python
SectionTemplate(
    title="Section Name",               # Section heading
    content="Description text",          # Introductory text
    include_waveforms=True,             # Show waveform plots?
    include_measurements=True,          # Show measurement table?
    include_fft=False,                  # Show FFT analysis?
    include_ai_insights=False,          # Add AI analysis?
    order=1                             # Display order
)
```

### Common Section Types

**Test Setup:**

```python
SectionTemplate(
    title="Test Setup",
    content="Equipment configuration and test conditions.",
    include_waveforms=False,
    include_measurements=False,
    order=1
)
```

**Waveform Analysis:**

```python
SectionTemplate(
    title="Waveform Captures",
    content="Captured waveforms and time-domain analysis.",
    include_waveforms=True,
    include_measurements=True,
    include_ai_insights=True,  # AI analyzes waveforms
    order=2
)
```

**Frequency Analysis:**

```python
SectionTemplate(
    title="FFT Analysis",
    content="Frequency domain characteristics.",
    include_fft=True,
    include_measurements=True,
    order=3
)
```

**Results Summary:**

```python
SectionTemplate(
    title="Measurement Results",
    content="Detailed measurement results with pass/fail criteria.",
    include_waveforms=False,
    include_measurements=True,
    order=4
)
```

## Pass/Fail Criteria

### Creating Criteria Sets

```python
from siglent.report_generator.models.criteria import (
    CriteriaSet,
    MeasurementCriteria,
    ComparisonType
)

# Create a criteria set
criteria_set = CriteriaSet(
    name="5V Power Supply Test",
    description="Acceptance criteria for 5V output"
)

# Add criteria for each measurement
criteria_set.add_criteria(MeasurementCriteria(
    measurement_name="Frequency",
    comparison_type=ComparisonType.RANGE,
    min_value=990,    # Hz
    max_value=1010,   # Hz
    description="Output frequency within ±1%",
    severity="critical"
))
```

### Comparison Types

#### Range Comparison

Value must be within min and max:

```python
MeasurementCriteria(
    measurement_name="Peak-to-Peak",
    comparison_type=ComparisonType.RANGE,
    min_value=3.8,  # V
    max_value=4.2,  # V
)
```

#### Minimum Only

Value must be above minimum:

```python
MeasurementCriteria(
    measurement_name="Signal-to-Noise",
    comparison_type=ComparisonType.MIN_ONLY,
    min_value=20,  # dB
)
```

#### Maximum Only

Value must be below maximum:

```python
MeasurementCriteria(
    measurement_name="Rise Time",
    comparison_type=ComparisonType.MAX_ONLY,
    max_value=100e-9,  # 100 ns
)
```

#### Equals (with tolerance)

Value must equal target within tolerance:

```python
MeasurementCriteria(
    measurement_name="DC Offset",
    comparison_type=ComparisonType.EQUALS,
    target_value=0.0,  # V
    tolerance=0.01,    # ±10 mV
)
```

#### Not Equals

Value must be different from target:

```python
MeasurementCriteria(
    measurement_name="Amplitude",
    comparison_type=ComparisonType.NOT_EQUALS,
    target_value=0.0,
    tolerance=0.1,  # Must be > 0.1V different from 0
)
```

### Severity Levels

Set the importance of each criterion:

- **`"critical"`** - Must pass for overall PASS
- **`"warning"`** - Failure noted but not critical
- **`"info"`** - Informational only

```python
MeasurementCriteria(
    measurement_name="Jitter",
    max_value=50e-12,  # 50 ps
    severity="warning"  # Not critical
)
```

### Channel-Specific Criteria

Apply different criteria to different channels:

```python
# CH1 criteria
criteria_set.add_criteria(MeasurementCriteria(
    measurement_name="Vpp",
    channel="CH1",
    min_value=4.8,
    max_value=5.2,
))

# CH2 criteria (different range)
criteria_set.add_criteria(MeasurementCriteria(
    measurement_name="Vpp",
    channel="CH2",
    min_value=2.8,
    max_value=3.2,
))
```

### Validating Measurements

```python
# Apply criteria to measurements
measurements = report.get_all_measurements()
results = criteria_set.validate_measurements(
    [{"name": m.name, "value": m.value, "channel": m.channel}
     for m in measurements]
)

# Check results
for result in results:
    print(result)  # [PASS] or [FAIL] with explanation
    if not result.passed:
        print(f"  Failed: {result.message}")
```

## Branding Templates

### Company Branding

```python
from siglent.report_generator.models.template import BrandingTemplate

branding = BrandingTemplate(
    company_name="Acme Test Laboratory",
    company_logo_path=Path("logo.png"),
    header_text="CONFIDENTIAL - Internal Use Only",
    footer_text="© 2024 Acme Corp - All Rights Reserved",

    # Color scheme (hex colors)
    primary_color="#1f77b4",
    secondary_color="#ff7f0e",
    success_color="#2ca02c",   # PASS color
    failure_color="#d62728",   # FAIL color
)
```

### Using Branding

```python
# Add branding to template
template.branding = branding

# Or apply directly to report
report.metadata.company_name = branding.company_name
report.metadata.company_logo_path = branding.company_logo_path
report.metadata.header_text = branding.header_text
report.metadata.footer_text = branding.footer_text
```

## Complete Template Example

Here's a complete template for power supply testing:

```python
from pathlib import Path
from siglent.report_generator.models.template import (
    ReportTemplate,
    SectionTemplate,
    BrandingTemplate
)
from siglent.report_generator.models.criteria import (
    CriteriaSet,
    MeasurementCriteria,
    ComparisonType
)

# Create template
template = ReportTemplate(
    name="5V Power Supply Validation",
    description="Standard validation procedure for 5V DC power supplies",
    author="QA Team",
    version="2.1"
)

# Add sections
template.add_section(SectionTemplate(
    title="Test Setup",
    content=(
        "The device under test (DUT) is configured for 5V output with a 1A "
        "resistive load. Measurements are taken using a Siglent SDS2104X Plus "
        "oscilloscope with 1:1 probe on Channel 1."
    ),
    include_waveforms=False,
    include_measurements=False,
    order=1
))

template.add_section(SectionTemplate(
    title="Ripple and Noise",
    content="Time-domain analysis of output ripple and noise.",
    include_waveforms=True,
    include_measurements=True,
    include_ai_insights=True,
    order=2
))

template.add_section(SectionTemplate(
    title="Frequency Analysis",
    content="FFT analysis to identify noise sources and harmonics.",
    include_fft=True,
    include_measurements=True,
    order=3
))

template.add_section(SectionTemplate(
    title="Load Regulation",
    content="Output voltage stability under varying loads.",
    include_waveforms=True,
    include_measurements=True,
    order=4
))

template.add_section(SectionTemplate(
    title="Transient Response",
    content="Response to step load changes.",
    include_waveforms=True,
    include_measurements=True,
    order=5
))

# Create criteria set
criteria = CriteriaSet(
    name="5V Supply Acceptance Criteria",
    description="Based on design specification DS-PS-001 Rev 3"
)

# Output voltage: 5.0V ±2%
criteria.add_criteria(MeasurementCriteria(
    measurement_name="Mean",
    comparison_type=ComparisonType.RANGE,
    min_value=4.9,  # V
    max_value=5.1,  # V
    description="Output voltage within ±2%",
    severity="critical"
))

# Ripple: < 50 mVpp
criteria.add_criteria(MeasurementCriteria(
    measurement_name="Peak-to-Peak",
    comparison_type=ComparisonType.MAX_ONLY,
    max_value=0.050,  # V
    description="Ripple amplitude within spec",
    severity="critical"
))

# RMS noise: < 10 mV
criteria.add_criteria(MeasurementCriteria(
    measurement_name="RMS",
    comparison_type=ComparisonType.MAX_ONLY,
    max_value=0.010,  # V
    description="RMS noise acceptable",
    severity="warning"
))

# Frequency: 1 kHz ±1% (test signal)
criteria.add_criteria(MeasurementCriteria(
    measurement_name="Frequency",
    comparison_type=ComparisonType.RANGE,
    min_value=990,   # Hz
    max_value=1010,  # Hz
    description="Test signal frequency nominal",
    severity="info"
))

template.criteria_set = criteria

# Add branding
template.branding = BrandingTemplate(
    company_name="Acme Test Laboratory",
    header_text="CONFIDENTIAL",
    footer_text="© 2024 Acme Corp",
    primary_color="#1f77b4",
    success_color="#2ca02c",
    failure_color="#d62728"
)

# Set defaults
template.default_equipment_model = "SDS2104X Plus"
template.default_test_procedure = "TEST-PS-001"

# Enable AI features
template.enable_ai_summary = True
template.enable_ai_insights = True
template.enable_ai_interpretation = True

# Save template
template.save(Path("templates/5v_power_supply.json"))
print(f"Template saved: {template.name} v{template.version}")
```

## Using Templates in Reports

### Load and Apply

```python
from siglent.report_generator.models.template import ReportTemplate
from siglent.report_generator.models.report_data import TestReport, ReportMetadata

# Load template
template = ReportTemplate.load(Path("templates/5v_power_supply.json"))

# Create report metadata
metadata = ReportMetadata(
    title="Power Supply #12345 - Validation Test",
    technician="Alice Engineer",
    test_date=datetime.now(),
    equipment_model=template.default_equipment_model,
    test_procedure=template.default_test_procedure,
    company_name=template.branding.company_name
)

# Create report
report = TestReport(metadata=metadata)

# Apply template sections
for section_template in template.sections:
    section = TestSection(
        title=section_template.title,
        content=section_template.content,
        order=section_template.order
    )
    report.add_section(section)

# Add your waveforms and measurements to appropriate sections
# ... (load waveforms, calculate measurements)

# Apply criteria
if template.criteria_set:
    measurements = report.get_all_measurements()
    # Validate and update measurement pass/fail status
```

## Template Library

### Organizing Templates

Create a template library for your organization:

```
templates/
├── power_supplies/
│   ├── 5v_linear.json
│   ├── 5v_switching.json
│   └── adjustable.json
├── signal_integrity/
│   ├── digital_io.json
│   ├── high_speed_serial.json
│   └── clock_quality.json
├── audio/
│   ├── amplifier_thd.json
│   ├── frequency_response.json
│   └── noise_floor.json
└── general/
    ├── standard_report.json
    └── quick_test.json
```

### Sharing Templates

Templates are JSON files - easy to share:

```bash
# Share via email
# Share on network drive
# Commit to version control

git add templates/
git commit -m "Add new power supply test template"
git push
```

### Version Control

Track template changes:

```python
template = ReportTemplate(
    name="5V Power Supply Test",
    version="2.1",  # Increment when changing
    author="QA Team"
)

# Document changes in template description
template.description = (
    "Standard 5V power supply validation.\n"
    "Version 2.1 changes:\n"
    "- Added transient response section\n"
    "- Tightened ripple criteria to 50mV\n"
    "- Updated per design spec DS-PS-001 Rev 3"
)
```

## Built-in Templates

### Default Template

The system includes a default template:

```python
# Get default template
template = ReportTemplate.create_default_template()
```

This includes standard sections:

- Executive Summary
- Test Setup
- Waveform Captures
- Frequency Analysis
- Measurement Results
- Conclusions

## Best Practices

### Template Design

1. **Start Simple** - Begin with basic sections, add complexity later
2. **Clear Descriptions** - Explain what each section shows
3. **Logical Order** - Setup → Measurements → Analysis → Conclusions
4. **Consistent Naming** - Use same measurement names across templates
5. **Document Changes** - Track versions and changes

### Criteria Definition

1. **Reference Specs** - Link to design specifications
2. **Realistic Margins** - Don't make criteria too tight
3. **Severity Levels** - Not everything needs to be critical
4. **Channel Specific** - Different channels may need different criteria
5. **Unit Consistency** - Use consistent units (V, Hz, s)

### Branding

1. **Professional** - Use high-quality logos
2. **Consistent** - Same branding across all reports
3. **Legal** - Include required legal text in footer
4. **Readable** - Choose colors that work in print

### Maintenance

1. **Review Regularly** - Update criteria as specs change
2. **Version Control** - Track all template files in git
3. **Team Input** - Get feedback from all users
4. **Archive Old** - Keep old versions for reference
5. **Document** - Explain why criteria were chosen

## Troubleshooting

### Template Won't Load

**Check JSON syntax:**

```bash
python -m json.tool templates/my_template.json
```

**Verify file path:**

```python
from pathlib import Path
template_path = Path("templates/my_template.json")
assert template_path.exists(), f"Not found: {template_path}"
```

### Criteria Not Applied

**Check measurement names match exactly:**

```python
# Criteria
measurement_name="Frequency"  # Must match exactly

# Measurement
name="frequency"  # Won't match (case sensitive)
```

**Check channels:**

```python
# Channel-specific criteria requires channel match
criteria.channel = "CH1"
measurement.channel = "C1"  # Won't match
```

### Branding Not Showing

**Verify logo path exists:**

```python
logo_path = Path("logo.png")
assert logo_path.exists(), "Logo not found"
```

**Check logo format:**

- Supported: PNG, JPG, JPEG, BMP
- Recommended: PNG with transparency

## Next Steps

- **Learn the API** - See [API Reference](api-reference.md) for programmatic use
- **See Examples** - Check `examples/report_generation_example.py`
- **Get Help** - Ask on [GitHub Discussions](https://github.com/little-did-I-know/Siglent-Oscilloscope/discussions)
