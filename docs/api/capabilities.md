# Scope Capabilities

Derived, dialect-resolved capabilities of a connected oscilloscope (scope.capabilities)

::: scpi_control.capabilities
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

- [Oscilloscope](oscilloscope.md) - Main oscilloscope control class for SCPI communication
- [Vocabulary](vocabulary.md) - String-compatible enums for token-valued parameters (coupling, trigger mode/slope/source/coupling/type, bandwidth limit, tracking mode) -- enums in, strings out
- [Models](models.md) - Oscilloscope model capabilities and registry
