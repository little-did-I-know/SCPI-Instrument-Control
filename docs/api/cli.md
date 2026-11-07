# Command-line tool (`scpi`)

One entry point for the common no-code tasks. `python -m scpi_control` is
equivalent.

```text
scpi demo [--signal sine|square|triangle|ramp] [--frequency HZ] [--amplitude V] [-o FILE]
scpi discover [--cidr 192.168.1.0/24] [--timeout S]
scpi idn <host> | --mock [--timeout S]
scpi screenshot <host> | --mock [-o FILE.png|FILE.bmp]
scpi capture <host> | --mock --channels 1,2 -o FILE.npz|.csv|.mat|.h5
```

- `demo` needs no hardware: it opens the mock scope, captures a synthesized
  signal and prints Vpp, frequency and an ASCII plot. `-o x.png` saves a plot,
  other extensions save the capture.
- `capture` with several channels writes one file each, adding `_chN` to the
  name.
- `screenshot` saves PNG when Pillow is installed; `.bmp` is the scope's raw
  image and needs nothing extra.
- Errors go to stderr as `error: ...`; exit status 2 means bad arguments,
  1 a runtime failure.

::: scpi_control.cli
    options:
      show_root_heading: false
      show_source: false
      heading_level: 2
      filters:
        - "!^_"

## See Also

- [SCPI Extract (CLI)](scpi_extract.md) - inspect saved waveform files
