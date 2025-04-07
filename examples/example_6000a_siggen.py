import pypicosdk as psdk

ps = psdk.ps6000a()

frequency_hz = 1000
voltage_pk2pk = 2
wave_type = psdk.WAVEFORM.SINE

ps.open_unit()

ps.set_siggen(frequency_hz, voltage_pk2pk, wave_type)
input("Return to continue... ")

ps.close_unit()