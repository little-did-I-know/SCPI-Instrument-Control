# GUI Components API

PyQt6-based graphical user interface for oscilloscope control

## Main Window

::: siglent.gui.main_window
    options:
      show_root_heading: false
      show_source: true
      heading_level: 3
      members_order: source
      group_by_category: true
      show_signature_annotations: true
      separate_signature: true
      merge_init_into_class: true
      filters:
        - "!^_"  # Exclude private members

## Connection Manager

::: siglent.gui.connection_manager
    options:
      show_root_heading: false
      show_source: true
      heading_level: 3
      members_order: source
      group_by_category: true
      show_signature_annotations: true
      separate_signature: true
      merge_init_into_class: true
      filters:
        - "!^_"

## Widgets

### Waveform Display

::: siglent.gui.widgets.waveform_display
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

::: siglent.gui.widgets.waveform_display_pg
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Channel Control

::: siglent.gui.widgets.channel_control
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Trigger Control

::: siglent.gui.widgets.trigger_control
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Timebase Control

::: siglent.gui.widgets.timebase_control
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Measurement Panel

::: siglent.gui.widgets.measurement_panel
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Cursor Panel

::: siglent.gui.widgets.cursor_panel
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Math Panel

::: siglent.gui.widgets.math_panel
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Reference Panel

::: siglent.gui.widgets.reference_panel
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Protocol Decode Panel

::: siglent.gui.widgets.protocol_decode_panel
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### FFT Display

::: siglent.gui.widgets.fft_display
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Visual Measurement Panel

::: siglent.gui.widgets.visual_measurement_panel
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Vector Graphics Panel

::: siglent.gui.widgets.vector_graphics_panel
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Terminal Widget

::: siglent.gui.widgets.terminal_widget
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Error Dialog

::: siglent.gui.widgets.error_dialog
    options:
      show_root_heading: false
      show_source: true
      heading_level: 4
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

## Workers

### Live View Worker

::: siglent.gui.live_view_worker
    options:
      show_root_heading: false
      show_source: true
      heading_level: 3
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

### Waveform Capture Worker

::: siglent.gui.waveform_capture_worker
    options:
      show_root_heading: false
      show_source: true
      heading_level: 3
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

## VNC Window

::: siglent.gui.vnc_window
    options:
      show_root_heading: false
      show_source: true
      heading_level: 3
      members_order: source
      show_signature_annotations: true
      filters:
        - "!^_"

## See Also

- [GUI Overview](../gui/overview.md) - GUI features and installation
- [Interface Guide](../gui/interface.md) - Complete UI tour
- [Live View](../gui/live-view.md) - Real-time waveform display
- [Visual Measurements](../gui/visual-measurements.md) - Interactive markers
- [Main Oscilloscope API](oscilloscope.md) - Core library API
