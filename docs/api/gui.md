# GUI Components API

PyQt6-based graphical user interface for oscilloscope control

## Main Window

::: scpi_control.gui.main_window
options:
show_root_heading: false
show_source: true
heading_level: 3
members_order: source
group_by_category: true
show_signature_annotations: true
separate_signature: true
merge_init_into_class: true
filters: - "!^*" # Exclude private members

## Connection Manager

::: scpi_control.gui.connection_manager
options:
show_root_heading: false
show_source: true
heading_level: 3
members_order: source
group_by_category: true
show_signature_annotations: true
separate_signature: true
merge_init_into_class: true
filters: - "!^*"

## Widgets

### Waveform Display

::: scpi_control.gui.widgets.waveform_display
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

::: scpi_control.gui.widgets.waveform_display_pg
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Channel Control

::: scpi_control.gui.widgets.channel_control
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Trigger Control

::: scpi_control.gui.widgets.trigger_control
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Timebase Control

::: scpi_control.gui.widgets.timebase_control
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Measurement Panel

::: scpi_control.gui.widgets.measurement_panel
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Cursor Panel

::: scpi_control.gui.widgets.cursor_panel
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Math Panel

::: scpi_control.gui.widgets.math_panel
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Reference Panel

::: scpi_control.gui.widgets.reference_panel
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Protocol Decode Panel

::: scpi_control.gui.widgets.protocol_decode_panel
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### FFT Display

::: scpi_control.gui.widgets.fft_display
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Visual Measurement Panel

::: scpi_control.gui.widgets.visual_measurement_panel
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Vector Graphics Panel

::: scpi_control.gui.widgets.vector_graphics_panel
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Terminal Widget

::: scpi_control.gui.widgets.terminal_widget
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Error Dialog

::: scpi_control.gui.widgets.error_dialog
options:
show_root_heading: false
show_source: true
heading_level: 4
members_order: source
show_signature_annotations: true
filters: - "!^*"

## Workers

### Live View Worker

::: scpi_control.gui.live_view_worker
options:
show_root_heading: false
show_source: true
heading_level: 3
members_order: source
show_signature_annotations: true
filters: - "!^*"

### Waveform Capture Worker

::: scpi_control.gui.waveform_capture_worker
options:
show_root_heading: false
show_source: true
heading_level: 3
members_order: source
show_signature_annotations: true
filters: - "!^*"

## VNC Window

::: scpi_control.gui.vnc_window
options:
show_root_heading: false
show_source: true
heading_level: 3
members_order: source
show_signature_annotations: true
filters: - "!^*"

## See Also

- [GUI Overview](../gui/overview.md) - GUI features and installation
- [Interface Guide](../gui/interface.md) - Complete UI tour
- [Live View](../gui/live-view.md) - Real-time waveform display
- [Visual Measurements](../gui/visual-measurements.md) - Interactive markers
- [Main Oscilloscope API](oscilloscope.md) - Core library API
