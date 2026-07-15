# PSU Data Logger

Timed logging of power supply readings

::: scpi_control.psu_data_logger
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
