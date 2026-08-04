# Oscilloscope

Main oscilloscope control class for SCPI communication

::: scpi_control.oscilloscope
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

- [Vocabulary](vocabulary.md) - String-compatible enums for token-valued parameters (coupling, trigger mode/slope/source/coupling/type, bandwidth limit, tracking mode) -- enums in, strings out
- [Scope Capabilities](capabilities.md) - Derived, dialect-resolved capabilities of a connected oscilloscope (scope.capabilities)
- [Channel](channel.md) - Channel configuration and control
- [Trigger](trigger.md) - Trigger configuration and modes
- [Waveform](waveform.md) - Waveform acquisition and data handling
- [Measurement](measurement.md) - Automated measurements (frequency, voltage, timing)
- [Exceptions](exceptions.md) - Custom exception classes
