"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.
"""
import pypicosdk as psdk

# Pico examples use inline argument values for clarity

scope = psdk.ps6000a()

scope.open_unit()

# Setup signal generator (inline arguments)
scope.set_siggen(frequency=1000, pk2pk=2, wave_type=psdk.WAVEFORM.SINE)
input("Return to continue... ")

scope.close_unit()
