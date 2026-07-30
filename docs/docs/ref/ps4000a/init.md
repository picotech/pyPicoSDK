# Initializing ps4000a
<!-- Copyright (C) 2026 Pico Technology Ltd. See LICENSE file for terms. -->

## Setup
The ps4000a drivers are intended for the PicoScope 4000A Series
(PicoScope 4444 and 4824A).

## Quickstart Code
To get started, use the following code:
```
import pypicosdk as psdk

scope = psdk.ps4000a()

scope.open_unit()

# Print scope serial (Optional)
print(scope.get_unit_serial())

# Do something here

scope.close_unit()
```

# Troubleshooting
 - Current 4000A hardware is 12-bit native, so `open_unit()` defaults to
   12-bit resolution. Only the PicoScope 4444 supports other resolutions
   (e.g. 14-bit).
 - Without its DC power supply a PicoScope 4444 runs on USB power with a
   restricted feature set. pyPicoSDK acknowledges this automatically and
   raises a `PowerSourceWarning`; connect the supplied power adapter for
   full functionality.
 - Bandwidth-limiter availability depends on the input configuration: on a
   PicoScope 4444 with the D9-to-BNC adaptor, 100 kHz and 1 MHz limiters
   are accepted but the 20 kHz limiter returns `PICO_INVALID_BANDWIDTH`
   (it is intended for current-clamp inputs).
 - `get_minimum_timebase_stateless()` returns
   `PICO_NOT_SUPPORTED_BY_THIS_DEVICE` on the PicoScope 4444; use
   `get_nearest_sampling_interval()` instead.
