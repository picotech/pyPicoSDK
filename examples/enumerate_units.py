"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

This example enumerates all PicoScope units (supported by pyPicoSDK), returns the number
of units and a list of serial numbers.
"""

import pypicosdk as psdk

# Enumerate units
n_units, units = psdk.get_all_enumerated_units()

# Print output
print(f'Number of units: {n_units}')
for unit, serial in units.items():
    print(f'{unit}: {serial}')
