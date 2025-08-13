# Initializing psospa

## Setup
The psospa drivers are intended for PicoScope 3000E Series.

## Quickstart Code
To get started, use the following code:
```
import pypicosdk as psdk

scope = psdk.psospa()

scope.open_unit()

# Print scope serial (Optional)
print(scope.get_unit_serial())

# Do something here

scope.close_unit()
```

# Troubleshooting
 - 3000E needs USB-C Power Delivery (PD) or standard USB and the supplied USB-C power supply.
