<!-- Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms. -->
# LED Control

The LED's on the 3000E are controllable via hue, saturation and brightness. To control them these rules need to be met:

- To control each LED `set_led_states([led], 'on')` must be called first per LED.

Here is an example of the three different methods of changing the LEDs
```
import pypicosdk as psdk
import time

scope = psdk.psospa()
scope.open_unit()

# Set channel A to red (hue=0, sat=100)
scope.set_led_states('A', 'on')
scope.set_led_colours('A', 0, 100)
time.sleep(2)
# OR set A, B and C to red, green and blue (sat=100)
scope.set_led_states(['A', 'B', 'C'], ['on', 'on', 'on'])
scope.set_led_colours(['A', 'B', 'C'], ['red', 'green', 'blue'], [100, 100, 100])
time.sleep(2)
# or set all LEDs to pink.
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
