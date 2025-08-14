"""
This is an example of using the LED channel identification
on the PSOSPA devices i.e. 3000E.

To exit the loop, use Ctrl+Z KeyboardInterrupt, or exit the
terminal.
"""

import pypicosdk as psdk
import time
from numpy.random import randint

scope = psdk.psospa()
scope.open_unit()

scope.set_all_led_states('on')

led_list = ['A', 'B', 'C', 'D', 'AUX', 'AWG']

while True:
    random_values = randint(0, 360, size=6)
    scope.set_led_colours(
        led_list, 
        randint(0, 360, size=6), 
        [100]*6,
    )
    time.sleep(1)
