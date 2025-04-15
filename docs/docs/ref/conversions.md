# PicoScope conversions
These functions are general functions to convert data to another format.
This is particularly useful for converting ADC data to mV or calculating 
the needed timebase for your PicoScope.

As the conversions talk to the PicoScope to retrieve the resolution and ADC limits,
the PicoScope needs to be initialized using `scope.open_unit()` followed by the conversion.

## Example
```
>>> import pypicosdk as psdk
>>> scope = psdk.ps6000a()
>>> scope.open_unit(resolution=psdk.RESOLUTION._8BIT)
>>> scope.mv_to_adc(100, channel_range=psdk.RANGE.V1)
3251
>>> scope.close_unit()
```

## Reference
::: pypicosdk.pypicosdk.PicoScopeBase
    options:
        filters:
        - ".*_to_.*"
        #- "!^_[^_]"
        show_root_toc_entry: false
        summary: true