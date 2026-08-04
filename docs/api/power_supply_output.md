# Power Supply Output

PSU output channel configuration

## CH3 on the SPD3303X / SPD3303X-E

CH3 on these two models is a fixed, DIP-switch-selected auxiliary rail
(2.5V / 3.3V / 5V -- QS0503X-E01B p.21), not a fully programmable output like
CH1/CH2. The manual documents exactly one SCPI verb for it:
`OUTPut {CH1|CH2|CH3},{ON|OFF}` (p.40), so `output3.enable()` /
`output3.disable()` work as expected. Everything else -- `voltage`,
`current`, `measure_voltage()`, `measure_current()`, `measure_power()`,
`get_mode()`, the `enabled` read-back, the timer, and the waveform display --
has no command form for CH3 (`VOLTage`/`CURRent` p.39 and `MEASure` p.38 are
`{CH1|CH2}` only, `TIMEr` p.41 and `OUTPut:WAVE` p.40 are `{CH1|CH2}` only,
and p.42's `SYSTem:STATus?` bitmap has no CH3 state bit). Calling any of
those on `output3` now raises `FeatureNotSupportedError` instead of sending a
command the firmware silently discards.

Check `psu.model_capability.output_specs[output_num - 1]` (see
[Models](models.md)) before touching an output programmatically rather than
guessing with try/except -- the six flags (`programmable`, `measurable`,
`switchable`, `state_readable`, `supports_timer`, `supports_waveform`) say
exactly what the connected model's manual documents for that output.

`FeatureNotSupportedError` is also a `NotImplementedError` (see
[Exceptions](exceptions.md)), so code that already caught
`NotImplementedError` around these calls keeps working unchanged.

::: scpi_control.power_supply_output
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
