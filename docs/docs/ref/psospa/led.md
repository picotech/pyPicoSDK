# LED Control

The LED's on the 3000E are controllable via hue, saturation and brightness. To control them these rules need to be met:

- To control each LED `set_led_states([led], 'on')` must be called first per LED. 
<!-- - For both `set_led_brightness()` and `set_led_colours()`, on of the following commands needs to be ran to apply the settings:
    - `run_block_capture()`
    - `run_streaming()`
    - `set_aux_io_mode()`
    - `siggen_apply()` -->

Here is an example of changing Channel A and Channel B to red and green, respectively:
```
import pypicosdk as psdk
import time

scope = psdk.psospa()
scope.open_unit()

scope.set_led_states('A', 'on')
scope.set_led_colours('A', 0, 100)
time.sleep(2)
# OR 
scope.set_led_states(['A', 'B', 'C'], ['on', 'on', 'on'])
scope.set_led_colours(['A', 'B', 'C'], ['red', 'green', 'blue'], [100, 100, 100])
time.sleep(2)
# or 
scope.set_all_led_states('on')
scope.set_all_led_colours('pink')

input('Waiting for user... ')
```

The LEDs are controlled via the functions below:

::: pypicosdk.pypicosdk.psospa
    options:
        filters:
        - "!.*"
        - "set_led"
        - "set_all_led"
        - "!_to_"
        - "!^_"
        show_root_toc_entry: false
        summary: true
