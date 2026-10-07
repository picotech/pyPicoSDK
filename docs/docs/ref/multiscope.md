# Multi-scope (6000E)
<!-- Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms. -->

`MultiScope` captures on two or more PicoScope 6000E units as one instrument:
a shared 10 MHz reference on every REF IN, the master's AUX output triggering
the followers, and the hardware trigger time stamps lining the records up
sample for sample. Wiring, worked examples and the calibration rules are in
[examples/multiscope/README.md](https://github.com/picotech/pyPicoSDK/tree/main/examples/multiscope)
on GitHub.

::: pypicosdk.multiscope
    options:
        members:
        - MultiScope
        - Calibration
        - FollowerCalibration
        - AlignmentInfo
        - MultiScopeError
        - MultiScopeWarning
        show_root_toc_entry: false
        summary: true
