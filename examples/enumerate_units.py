# This example enumerates all PicoScope units (supported by pyPicoSDK), returns the number
# of units and a list of serial numbers.

import pypicosdk as psdk

# Enumerate units
n_units, unit_list = psdk.get_all_enumerated_units()

# Print output
print(f'Number of units: {n_units}')
for i in unit_list:
    print(f'Serial numbers: {i}')