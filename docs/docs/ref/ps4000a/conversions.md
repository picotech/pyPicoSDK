# Built-in Conversions
<!-- Copyright (C) 2026 Pico Technology Ltd. See LICENSE file for terms. -->
These functions are general functions to convert data to another format.
This is particularly useful for converting ADC data to mV or calculating
the needed timebase for your PicoScope.

As the conversions talk to the PicoScope to retrieve the resolution and ADC limits,
the PicoScope needs to be initialized using `scope.open_unit()` followed by the conversion.

## Example
```
>>> import pypicosdk as psdk
>>> scope = psdk.ps4000a()
>>> scope.open_unit()
>>> scope.mv_to_adc(100, channel=psdk.CHANNEL.A)
3276
>>> scope.close_unit()
```

## Reference
::: pypicosdk.pypicosdk.ps4000a
    options:
        filters:
        - "!.*"
        - "_to_"
        - "!^_"
        show_root_toc_entry: false
        summary: true
