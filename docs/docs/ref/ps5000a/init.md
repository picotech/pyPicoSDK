# Initializing ps5000a
<!-- Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms. -->

## Setup
The ps5000a drivers are intended for PicoScope 5000D Series.

## Quickstart Code
To get started, use the following code:
```
import pypicosdk as psdk

scope = psdk.ps5000a()

scope.open_unit()

# Print scope serial (Optional)
print(scope.get_unit_serial())

# Do something here

scope.close_unit()
```

# Troubleshooting
 - Without an external power supply the PicoScope 5000D 4-channel units disable channels C and D.
   To get the full usage, use the 5V power supply provided in addition to the USB.
