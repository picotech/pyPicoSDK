# Trigger Configuration
<!-- Copyright (C) 2026 Pico Technology Ltd. See LICENSE file for terms. -->

The ps4000a driver takes auto-trigger timeouts in milliseconds at the C
level; pyPicoSDK converts the cross-driver microsecond arguments
automatically. The EXT trigger input has a fixed ±5 V range.

::: pypicosdk.pypicosdk.ps4000a
    options:
        filters:
        - "!.*"
        - "trigger"
        - "aux"
        - "!^_"
        show_root_toc_entry: false
        summary: true
