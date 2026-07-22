# Comparison & Batch Reports

Multi-run comparison (before/after deltas) and batch (cross-DUT yield) analysis and report building

::: scpi_control.report_generator.models.comparison
    options:
      show_root_heading: false
      show_source: true
      heading_level: 2
      members_order: source
      group_by_category: true
      show_signature_annotations: true
      separate_signature: true
      merge_init_into_class: true
      filters:
        - "!^_"  # Exclude private members

::: scpi_control.report_generator.analysis.comparison_analyzer
    options:
      show_root_heading: false
      show_source: true
      heading_level: 2
      members_order: source
      group_by_category: true
      show_signature_annotations: true
      separate_signature: true
      merge_init_into_class: true
      filters:
        - "!^_"  # Exclude private members

::: scpi_control.report_generator.comparison_report_builder
    options:
      show_root_heading: false
      show_source: true
      heading_level: 2
      members_order: source
      group_by_category: true
      show_signature_annotations: true
      separate_signature: true
      merge_init_into_class: true
      filters:
        - "!^_"  # Exclude private members

## See Also

- [Waveform](waveform.md) - Waveform acquisition and data handling
- [Analysis](analysis.md) - Signal analysis (FFT, THD, SNR)
- [Signal Synthesis](signal_synth.md) - Parameterized synthetic waveforms for hardware-free examples
- [Report Generator: API Reference](../report-generator/api-reference.md) - Single-run report building blocks (ReportMetadata, TestReport, generators)
