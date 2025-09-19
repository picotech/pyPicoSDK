"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

This is an example of using the LED channel identification
on the PSOSPA devices i.e. 3000E.

To exit the loop, use Ctrl+Z KeyboardInterrupt, or exit the
terminal.
"""

import pypicosdk as psdk
import time

scope = psdk.psospa()
scope.open_unit()

scope.set_all_led_states('off')
scope.set_all_led_colours('red')

led_list = ['A', 'B', 'C', 'D', 'AUX', 'AWG']
sweep = ['off'] * 6
n_sweep = 1
sweep_inc = 1

while True:
    sweep[n_sweep] = 'on'
    scope.set_led_states(led_list, sweep)
    time.sleep(.1)
    sweep[n_sweep] = 'off'
    if n_sweep in [0, 5]:
        sweep_inc = -sweep_inc
    n_sweep += sweep_inc
