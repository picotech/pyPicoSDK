import pypicosdk as psdk

scope = psdk.ps6000a()

frequency_hz = 1000
voltage_pk2pk = 2
wave_type = psdk.WAVEFORM.SINE

scope.open_unit()

scope.set_siggen(frequency_hz, voltage_pk2pk, wave_type)
input("Return to continue... ")

scope.close_unit()