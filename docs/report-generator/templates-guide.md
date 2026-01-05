# Report Templates Guide

## Overview

Report templates allow you to save and reuse your preferred report configurations, making it easy to generate consistent reports across multiple test sessions. Templates store everything from which sections to include to plot styling preferences.

## What's Stored in a Template?

A template saves:

- **Report Sections**: Which sections to include (executive summary, key findings, recommendations, etc.)
- **AI/LLM Preferences**: Which LLM provider to use and auto-generation settings
- **Metadata Defaults**: Company name, technician name, environmental conditions, location
- **Output Format**: Page size (Letter/A4), plot dimensions, DPI
- **Plot Styles**: Colors, fonts, grid settings, matplotlib style presets

## Creating a Template

### Method 1: Save During Report Generation

1. **Start generating a report**:
   - Click "Generate PDF Report" or "Generate Markdown Report"
   - The Report Options dialog will appear

2. **Configure your preferences**:
   - **Content Tab**: Select which sections to include
     - Check "Include Executive Summary" for overview
     - Check "Include Key Findings" for bullet-point highlights
     - Check "Include Recommendations" for suggested next steps
     - Enable AI generation options if you have LLM configured

   - **Format Tab**: Set output format preferences
     - Choose page size (Letter or A4)
     - Set plot dimensions (width × height in inches)
     - Set plot DPI (resolution, typically 150)

   - **Plot Style Tab**: Customize plot appearance
     - Select a matplotlib style preset (default, seaborn, ggplot, etc.)
     - Click color buttons to customize waveform, FFT, grid, and background colors
     - Adjust line width and grid transparency
     - Set font sizes for titles, labels, and ticks

3. **Save as template**:
   - Click "Save as Template..." button at the bottom
   - Enter a descriptive name (e.g., "Quick Test Report", "Full Analysis", "Customer Report")
   - Optionally add a description
   - Click OK

4. **Continue with report generation** or cancel

### Method 2: Save Current Session Configuration

1. **Configure your session**:
   - Fill in metadata fields (company name, technician, etc.)
   - Configure LLM settings if using AI features
   - Set up your preferred workflow

2. **Save as template**:
   - Go to `File → Save as Template...` (or press Ctrl+S)
   - Enter template name and description
   - Click OK

The template will include all current metadata values as defaults.

## Using Templates

### Loading a Template

**Option A: From File Menu**

1. Go to `File → Load Template...` (or press Ctrl+L)
2. Select a template from the list
3. Click "Load Selected"
4. The template's metadata defaults will auto-fill the form
5. Import your waveforms and generate reports as usual

**Option B: During Report Generation**

1. Click "Generate PDF Report" or "Generate Markdown Report"
2. In the Report Options dialog, click "Load from Template..."
3. Select and load a template
4. The dialog will update with the template's settings
5. Make any one-off adjustments if needed
6. Click "Generate Report"

### When you load a template:

- **Metadata fields** are auto-filled with template defaults (you can still edit them)
- **Report options** are set according to the template
- **Plot styles** are applied
- Your previous session settings are preserved until you close the app

## Managing Templates

Access the Template Manager via `File → Manage Templates...`

### Template Manager Features

**View Template Details**:

- Click on any template to see its configuration
- Review which sections are included
- See AI generation settings
- Check output format preferences

**Load a Template**:

- Select a template from the list
- Click "Load Selected"
- The template is applied to your current session

**Duplicate a Template**:

- Select a template
- Click "Duplicate..."
- Enter a new name (e.g., "Customer Report (Copy)")
- Modify the duplicate as needed

**Delete a Template**:

- Select a template
- Click "Delete"
- Confirm deletion (this cannot be undone)

**Import/Export Templates**:

- **Import**: Click "Import..." to load a template from a JSON file
- **Export**: Select a template and click "Export..." to share with colleagues
- Templates are stored as JSON files for easy sharing

## Template Storage Location

Templates are automatically saved to:

- **Windows**: `%APPDATA%\SiglentReportGenerator\templates\`
- **macOS**: `~/Library/Application Support/SiglentReportGenerator/templates/`
- **Linux**: `~/.config/SiglentReportGenerator/templates/`

Each template is saved as a JSON file (e.g., `Quick_Test_Report.json`).

## Example Templates

### Template 1: Quick Test Report

**Use Case**: Fast internal testing, minimal documentation

**Configuration**:

- Sections: Waveform plots only, no AI-generated content
- Format: Letter size, standard plot dimensions
- Plot Style: Default matplotlib style
- AI: Disabled

**When to use**: Quick validation tests, internal review

### Template 2: Full Analysis Report

**Use Case**: Comprehensive analysis with AI insights

**Configuration**:

- Sections: All sections enabled (summary, findings, recommendations)
- AI: Auto-generate summary and findings enabled
- Format: Letter size, high-resolution plots (DPI: 300)
- Plot Style: Seaborn style, professional colors
- Metadata: Company name, standard location pre-filled

**When to use**: Detailed test documentation, root cause analysis

### Template 3: Customer-Facing Report

**Use Case**: Professional reports for external clients

**Configuration**:

- Sections: Executive summary, key findings, recommendations
- AI: Auto-generate executive summary
- Format: A4 size (international standard), large plots
- Plot Style: Custom colors matching company branding
- Metadata: Company name, logo, technician pre-filled

**When to use**: Deliverables for customers, certification reports

## Tips for Effective Templates

### Naming Conventions

Use descriptive names that indicate purpose:

- ✅ "Quick Internal Test"
- ✅ "Full Customer Report - A4"
- ✅ "Debug Analysis - Verbose"
- ❌ "Template 1"
- ❌ "My Template"

### Descriptions

Add helpful descriptions:

```
"High-resolution customer report with AI summary.
Uses company branding colors. A4 format for international clients."
```

### Organization Strategies

**By Purpose**:

- Internal Testing
- Customer Deliverables
- Certification/Compliance
- Debug/Analysis

**By Customer**:

- Customer A - Standard Report
- Customer B - Detailed Analysis
- Internal - Quick Test

**By Test Type**:

- Power Supply Test
- Signal Integrity Test
- EMI/EMC Test

## Workflow Examples

### Example 1: Regular Testing with Template

```
1. Open Siglent Report Generator
2. File → Load Template... → Select "Quick Internal Test"
3. Import waveforms from test data
4. Metadata fields auto-fill with template defaults
5. Update date and specific test details
6. Generate PDF Report
7. Review and save
```

### Example 2: Creating a New Template

```
1. Run a test and configure report exactly how you want it
2. Fill in metadata with standard values you always use
3. Configure LLM settings if using AI
4. Generate PDF Report
5. In Report Options dialog:
   - Configure all tabs (Content, Format, Plot Style)
   - Click "Save as Template..."
   - Name: "Power Supply Test - Customer Format"
   - Description: "Standard power supply validation report for customers"
6. Click OK to save template
7. Continue with report generation or cancel
```

### Example 3: Sharing Templates with Team

```
1. Create and test your template
2. File → Manage Templates...
3. Select your template
4. Click "Export..."
5. Save to shared drive: "\\server\templates\Power_Supply_Test.json"
6. Team members can then:
   - Open Template Manager
   - Click "Import..."
   - Select the shared JSON file
```

## Advanced: Editing Template JSON

Templates are stored as JSON files and can be manually edited if needed.

### Template JSON Structure

```json
{
  "name": "My Template",
  "description": "Template description",
  "include_executive_summary": true,
  "include_key_findings": true,
  "include_recommendations": true,
  "include_waveform_plots": true,
  "include_fft_analysis": false,
  "auto_generate_summary": true,
  "page_size": "letter",
  "plot_width_inches": 6.5,
  "plot_height_inches": 3.0,
  "plot_dpi": 150,
  "plot_style": {
    "waveform_color": "#1f77b4",
    "fft_color": "#ff7f0e",
    "grid_color": "#cccccc",
    "background_color": "#ffffff",
    "waveform_linewidth": 0.8,
    "grid_alpha": 0.3,
    "grid_enabled": true,
    "title_fontsize": 11,
    "label_fontsize": 10,
    "tick_fontsize": 9,
    "matplotlib_style": "default"
  },
  "default_company_name": "ACME Corporation",
  "default_technician": "John Doe",
  "default_temperature": "25°C",
  "default_humidity": "45%",
  "default_location": "Lab A",
  "llm_provider": "ollama",
  "llm_model": "llama3.2",
  "version": "1.0"
}
```

### Caution

- Always backup templates before manual editing
- Invalid JSON will fail to load
- Use the Template Manager UI for safety

## Troubleshooting

### Template Won't Load

**Problem**: Error message when loading template

**Solutions**:

1. Check that the JSON file is valid (use a JSON validator)
2. Ensure the template file isn't corrupted
3. Try importing from a backup or re-creating the template

### Template Doesn't Apply All Settings

**Problem**: Some settings aren't being applied when loading a template

**Solutions**:

1. Re-save the template to ensure all current fields are included
2. Check that you're loading the correct template
3. Verify the template JSON contains all expected fields

### Templates Not Showing in List

**Problem**: Template Manager shows "No templates found"

**Solutions**:

1. Check templates directory exists and has JSON files
2. Verify file permissions (read access required)
3. Template names must end with `.json`

### Lost Templates After Update

**Problem**: Templates disappeared after software update

**Solutions**:

1. Check if templates moved to new location
2. Templates are stored in user config directory (see "Template Storage Location")
3. Import from backup if available

## Best Practices

1. **Create templates as you go**: Whenever you configure a report you like, save it as a template

2. **Use descriptive names**: Future you will thank current you

3. **Add descriptions**: Explain when and why to use each template

4. **Regular backups**: Export important templates to a backup location

5. **Share with team**: Export templates to shared drive for consistency

6. **Version your templates**: Use template names like "Customer Report v2" when making major changes

7. **Test before sharing**: Generate a test report to verify template works as expected

8. **Document custom templates**: Keep a reference document explaining your organization's template standards

## Keyboard Shortcuts

- `Ctrl+L` - Load Template
- `Ctrl+S` - Save as Template
- `Ctrl+N` - New Report (clears current session)

## Related Documentation

- [LLM Setup Guide](llm-setup.md) - Configure AI features for templates
- [Report Generation Guide](report-generation.md) - General report creation workflow
- [Plot Customization](plot-customization.md) - Advanced plot styling options
