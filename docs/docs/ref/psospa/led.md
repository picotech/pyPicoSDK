# LED Control

The LED's on the 3000E are controllable via hue, saturation and brightness. To control them these rules need to be met:

- To control each LED `set_led_states([led], 'on')` must be called first per LED. It is automatically called in `set_led_colours()`.
<!-- - For both `set_led_brightness()` and `set_led_colours()`, on of the following commands needs to be ran to apply the settings:
    - `run_block_capture()`
    - `run_streaming()`
    - `set_aux_io_mode()`
    - `siggen_apply()` -->

Here is an example of changing Channel A and Channel B to red and green, respectively:
```
import pypicosdk as psdk

scope = psdk.psospa()
scope.open_unit()

scope.set_led_colours('A', 0, 100)
scope.set_led_colours('B', 100, 100)

input('Waiting for user... ')
```

The LEDs are controlled via the functions below:

::: pypicosdk.pypicosdk.psospa
    options:
        filters:
        - "!.*"
        - "set_led"
        - "!_to_"
        - "!^_"
        show_root_toc_entry: false
        summary: true
