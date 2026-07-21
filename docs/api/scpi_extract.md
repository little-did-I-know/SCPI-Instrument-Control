# SCPI Extract (CLI)

Command-line tool for inspecting and exporting saved waveform files

::: scpi_control.scpi_extract
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

- [Waveform I/O](waveform_io.md) - `load_waveform()`, the function backing this CLI
- [Provenance](provenance.md) - Acquisition provenance this tool prints and exports
