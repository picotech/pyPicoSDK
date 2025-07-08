import pypicosdk as psdk

scope = psdk.ps6000a()

frequency_hz = 1000
voltage_pk2pk = 2
wave_type = psdk.WAVEFORM.SINE

scope.open_unit()

# Set capture timebase
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=500,
                                         unit=psdk.SAMPLE_RATE.MSPS)
# TIMEBASE = 2  # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(20E-9)

scope.set_siggen(frequency_hz, voltage_pk2pk, wave_type)
input("Return to continue... ")

scope.close_unit()