<!-- Copyright (C) 2018-2022 Pico Technology Ltd. See LICENSE file for terms. -->
# Initializing ps6000a

## Setup
The ps6000a drivers are intended for PicoScope 6000E Series.

## Quickstart Code
To get started, use the following code:
```
import pypicosdk as psdk

scope = psdk.ps6000a()

scope.open_unit()

# Print scope serial (Optional)
print(scope.get_unit_serial())

# Do something here

scope.close_unit()
```

# Troubleshooting
 - 6000E needs USB **and** an external power supply to function fully. USB on its own will not initiate the USB driver.
