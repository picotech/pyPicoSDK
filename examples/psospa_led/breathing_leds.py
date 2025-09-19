"""
Copyright (C) 2018-2022 Pico Technology Ltd. See LICENSE file for terms.

This is an example of using the LED channel identification
on the PSOSPA devices i.e. 3000E.

To exit the loop, use Ctrl+Z KeyboardInterrupt, or exit the
terminal.
"""

import pypicosdk as psdk
import time

scope = psdk.psospa()
scope.open_unit()

scope.set_all_led_states('on')
scope.set_all_led_colours('blue')

brightness = 50
inc = 2

while True:
    scope.set_led_brightness(brightness)
    if brightness in [0, 100]:
        inc = -inc
    brightness += inc
    time.sleep(.1)
