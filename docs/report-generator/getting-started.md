# Getting Started

This guide will help you install and start using the Siglent Report Generator.

## Installation

### Option 1: Install from Source (Development)

If you have the source code:

```bash
# Navigate to the project directory
cd Siglent

# Install with report generator dependencies
pip install -e ".[report-generator]"
```

### Option 2: Install from PyPI (Future)

Once published to PyPI:

```bash
pip install siglent-oscilloscope[report-generator]
```

### Verify Installation

```bash
# Check that the command is available
siglent-report-generator --version

# Or try launching it
siglent-report-generator
```

## Dependencies

The Report Generator requires:

- **Required:**
  - `PyQt6` - GUI framework
  - `matplotlib` - Plotting
  - `numpy` - Numerical computing
  - `scipy` - Signal processing
  - `Pillow` - Image handling

- **Optional:**
  - `reportlab` - PDF generation (highly recommended)
  - `requests` - LLM API calls (for AI features)
  - `h5py` - HDF5 file support

All dependencies are installed automatically with `pip install -e ".[report-generator]"`.

## Launching the Application

### GUI Application

```bash
# Method 1: Using the installed command
siglent-report-generator

# Method 2: Using Python module
python -m siglent.report_generator.app
```

### Standalone Executable

If you have a pre-built executable:

**Windows:**

```bash
# Navigate to the executable folder
cd dist/SiglentReportGenerator

# Run it
SiglentReportGenerator.exe
```

**Linux:**

```bash
# Navigate to the executable folder
cd dist/SiglentReportGenerator

# Run it
./SiglentReportGenerator
```

## GUI Overview

### Main Window Layout

The Report Generator window is divided into two main sections:

```
┌─────────────────────────────────────────────────────────┐
│  File  Settings  Help                                   │
├──────────────────────────┬──────────────────────────────┤
│                          │                              │
│  DATA IMPORT             │  AI ASSISTANT                │
│                          │                              │
│  ┌────────────────────┐  │  Status: Connected           │
│  │ Imported Waveforms │  │                              │
│  │                    │  │  Chat History...             │
│  │ • CH1 - file1.npz  │  │                              │
│  │ • CH2 - file1.npz  │  │                              │
│  └────────────────────┘  │                              │
│                          │                              │
│  [Import Waveforms...]   │  [Type question...]          │
│  [Import Images...]      │                              │
│  [Clear All]             │  [Generate Summary]          │
│                          │  [Analyze Waveforms]         │
│  REPORT METADATA         │  [Interpret Measurements]    │
│                          │                              │
│  Title: ____________     │                              │
│  Technician: _______     │                              │
│  Date: ______________    │                              │
│  Equipment: _________    │                              │
│  ...                     │                              │
│                          │                              │
│  [Generate PDF Report]   │                              │
│  [Generate MD Report]    │                              │
│                          │                              │
└──────────────────────────┴──────────────────────────────┘
```

### Left Panel - Data & Configuration

**Data Import Section:**

- Shows list of imported waveforms
- Buttons to import waveforms and images
- Clear all data button

**Report Metadata:**

- Scrollable form with all metadata fields
- Required: Title, Technician, Test Date
- Optional: Equipment details, environmental conditions, branding

**Generation Buttons:**

- Generate PDF Report
- Generate Markdown Report

### Right Panel - AI Assistant

**Status Display:**

- Shows LLM connection status
- Displays current model

**Chat Interface:**

- Type questions about your data
- View AI responses
- Clear chat history

**Quick Actions:**

- Generate Summary - Auto-create executive summary
- Analyze Waveforms - Get signal quality insights
- Interpret Measurements - Explain pass/fail results

## Creating Your First Report

### Step 1: Prepare Sample Data

First, let's create some sample waveform data:

```bash
# Run the example script to generate sample data
python examples/report_generation_example.py
```

This creates sample waveform files in `example_reports/` directory.

Or, if you have existing oscilloscope data, use that!

### Step 2: Import Waveforms

1. **Launch the application**

   ```bash
   siglent-report-generator
   ```

2. **Click "Import Waveforms..."**

3. **Select your waveform files**
   - Supported formats: `.npz`, `.csv`, `.mat`, `.h5`, `.hdf5`
   - You can select multiple files at once
   - The waveforms will appear in the list

4. **Verify the import**
   - Each channel should appear as a separate item
   - Format: `ChannelName - filename.ext`

### Step 3: Fill in Metadata

Scroll through the metadata form and fill in the fields:

**Required Fields:**

- **Report Title** - e.g., "Power Supply Ripple Test"
- **Technician** - Your name
- **Test Date** - Defaults to current date/time

**Optional but Recommended:**

- **Equipment Model** - e.g., "SDS2104X Plus"
- **Equipment ID** - Serial number
- **Test Procedure** - Reference number
- **Project Name** - What project this belongs to
- **Customer** - If applicable
- **Notes** - Any additional context

**Environmental Conditions:**

- Temperature
- Humidity
- Location

**Branding (Optional):**

- Company Name
- Company Logo (click "Select Logo...")
- Header/Footer Text

### Step 4: Generate Your Report

1. **Choose format:**
   - Click "Generate PDF Report" for PDF
   - Click "Generate Markdown Report" for Markdown

2. **Choose save location:**
   - A file dialog will appear
   - Select where to save the report
   - Use a descriptive filename

3. **Wait for generation:**
   - A progress dialog appears
   - Report generation typically takes 5-30 seconds
   - Depends on number of waveforms and plots

4. **Success!**
   - A confirmation dialog shows the save location
   - Open the report to view it

### Step 5: Review Your Report

**PDF Report Sections:**

1. **Header** - Company logo and name (if configured)
2. **Title** - Report title centered
3. **Metadata Table** - All test information
4. **Overall Result** - PASS/FAIL status
5. **Sections:**
   - Test Setup
   - Waveform Captures (with plots)
   - Measurements (with tables)
   - FFT Analysis (if included)
6. **Footer** - Generation date and company name

**Markdown Report:**

- Same content as PDF
- Markdown-formatted for version control
- Plots saved in `plots/` subdirectory
- Can be converted to other formats

## Working with Images

### Importing Images

1. **Click "Import Images..."**
2. **Select image files:**
   - Supported formats: `.png`, `.jpg`, `.jpeg`, `.bmp`
   - Multiple selection supported
3. **Images are stored** for inclusion in reports

### Image Use Cases

- **Setup Photos** - Show physical test configuration
- **Screenshots** - Capture oscilloscope screen
- **Diagrams** - Include circuit diagrams or schematics
- **Reference Images** - Compare with expected waveforms

## Menu Bar

### File Menu

- **New Report** (Ctrl+N) - Clear all data and start fresh
- **Exit** (Ctrl+Q) - Close the application

### Settings Menu

- **LLM Configuration...** - Configure AI features
  - Opens the LLM settings dialog
  - See [LLM Setup](llm-setup.md) for details

### Help Menu

- **About** - Information about the application
  - Shows version
  - Lists features
  - Links to documentation

## Keyboard Shortcuts

- `Ctrl+N` - New report
- `Ctrl+Q` - Quit application
- `Enter` (in chat) - Send chat message

## Common Tasks

### Creating Multiple Reports from Same Data

1. Import waveforms once
2. Fill in metadata
3. Generate first report (e.g., PDF)
4. Change title or notes as needed
5. Generate second report (e.g., Markdown)

### Batch Processing

For batch processing multiple tests:

1. Use the [Programmatic API](api-reference.md)
2. Write a Python script to:
   - Load multiple waveform sets
   - Apply templates
   - Generate all reports
3. See `examples/report_generation_example.py` for reference

### Saving Time with Templates

Instead of re-entering metadata every time:

1. Create a report with your standard settings
2. Save it as a template (API feature)
3. Load the template for each new test
4. See [Template Guide](templates.md) for details

## Troubleshooting

### "reportlab not installed" error

PDF generation requires reportlab:

```bash
pip install reportlab
```

### "Failed to load waveform" error

**Check file format:**

- Supported: NPZ, CSV, MAT, HDF5
- Unsupported: Binary scope formats

**Verify file structure:**

- Must contain time and voltage data
- See [API Reference](api-reference.md) for expected format

### Application won't start

**Check dependencies:**

```bash
pip install -e ".[report-generator]"
```

**Check PyQt6 platform plugins:**

```bash
# Windows
set QT_QPA_PLATFORM_PLUGIN_PATH=<python>/Lib/site-packages/PyQt6/Qt6/plugins

# Linux
export QT_QPA_PLATFORM_PLUGIN_PATH=<python>/lib/python3.x/site-packages/PyQt6/Qt6/plugins
```

### Generation is slow

**Normal for:**

- Large waveforms (millions of samples)
- Many channels
- Complex plots

**Speed tips:**

- Use Markdown for faster generation
- Reduce plot resolution
- Limit waveform length if possible

### Out of memory errors

**Reduce memory usage:**

- Process waveforms one at a time
- Use lower resolution plots
- Close other applications

## Next Steps

Now that you have the basics:

- [**Enable AI Features →**](llm-setup.md) - Set up Ollama for AI analysis
- [**Use Templates →**](templates.md) - Save time with reusable configurations
- [**Learn the API →**](api-reference.md) - Automate report generation

## Getting Help

- **Documentation** - You're reading it!
- **Examples** - See `examples/report_generation_example.py`
- **Issues** - Report bugs on [GitHub](https://github.com/little-did-I-know/SCPI-Instrument-Control/issues)
- **Discussions** - Ask questions on GitHub Discussions
